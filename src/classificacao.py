"""Classifica, via LLM (Gemini) com saída estruturada, se cada licitação pré-filtrada é
relevante para as categorias do projeto (Materiais de Limpeza, Serviços de
Portaria/Segurança, Serviços de Limpeza) e gera uma descrição resumida do objeto."""

import os
import time
from typing import Literal, Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODELO = "gemini-3.1-flash-lite"  # cota gratuita mais previsível (15 req/min) que o 3.5-flash

CATEGORIAS = (
    "Materiais de Limpeza",
    "Serviços de Portaria/Segurança",
    "Serviços de Limpeza",
)


class ClassificacaoLicitacao(BaseModel):
    relevante: bool = Field(description="Se o objeto da licitação pertence a uma das categorias-alvo.")
    categoria: Optional[Literal[
        "Materiais de Limpeza", "Serviços de Portaria/Segurança", "Serviços de Limpeza"
    ]] = Field(default=None, description="Categoria correspondente, ou null se não relevante.")
    descricao_resumida: str = Field(description="Resumo do objeto da licitação em até 20 palavras.")


_PROMPT_SISTEMA = f"""Você classifica objetos de licitações públicas brasileiras nas categorias:
{", ".join(CATEGORIAS)}.
Considere relevante apenas se o objeto for claramente compra de materiais de limpeza,
ou contratação de serviços de portaria/segurança patrimonial, ou serviços de limpeza/conservação.
Objetos ambíguos ou de outra natureza (ex.: vigilância em saúde/eletrônica, obras, TI,
locação de veículos) não são relevantes, mesmo que mencionem palavras parecidas de passagem."""


def _get_com_retentativa(payload: dict, api_key: str, tentativas: int = 5) -> dict:
    """POST com retentativa: rate limit (429) e falhas de rede/DNS transitórias são esperadas
    ao longo de uma rodada com centenas de chamadas."""
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.post(URL, json=payload, headers={"x-goog-api-key": api_key}, timeout=60)
        except requests.exceptions.RequestException as erro:
            if tentativa == tentativas:
                raise
            print(f"  [erro de rede] {erro}, tentativa {tentativa}/{tentativas}")
            time.sleep(5 * tentativa)
            continue
        if resp.status_code == 429:
            print(f"  [429] rate limit, tentativa {tentativa}/{tentativas}")
            time.sleep(int(resp.headers.get("Retry-After", 10 * tentativa)))
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("Excedeu as retentativas do Gemini")


def classificar_objeto(objeto_compra: str, api_key: str) -> ClassificacaoLicitacao:
    payload = {
        "model": MODELO,
        "input": f"{_PROMPT_SISTEMA}\n\nObjeto da licitação: {objeto_compra}",
        "generation_config": {"thinking_level": "minimal"},
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": ClassificacaoLicitacao.model_json_schema(),
        },
    }
    corpo = _get_com_retentativa(payload, api_key)
    saida = next(s for s in corpo["steps"] if s["type"] == "model_output")
    texto = saida["content"][0]["text"]
    return ClassificacaoLicitacao.model_validate_json(texto)


def classificar_dataframe(df: pd.DataFrame, pausa: float = 4.5) -> pd.DataFrame:
    """Classifica cada linha (coluna objetoCompra) e retorna só as relevantes.

    Sequencial e pausado (pausa >= 4.5s) para respeitar a cota gratuita de 15 req/min
    do gemini-3.1-flash-lite sem cair em retentativas por 429.
    """
    api_key = os.environ["GOOGLE_API_KEY"]
    resultados = []
    for i, objeto in enumerate(df["objetoCompra"]):
        resultados.append(classificar_objeto(objeto, api_key))
        if i % 10 == 0:
            print(f"  {i + 1}/{len(df)} classificadas")
        time.sleep(pausa)

    df = df.copy()
    df["categoria"] = [r.categoria for r in resultados]
    df["descricao_resumida"] = [r.descricao_resumida for r in resultados]
    df["relevante"] = [r.relevante for r in resultados]
    return df[df["relevante"]].drop(columns="relevante").reset_index(drop=True)


if __name__ == "__main__":
    bruto = pd.read_csv("licitacoes_filtradas.csv", encoding="utf-8-sig")
    classificado = classificar_dataframe(bruto)
    print(f"Após classificação por LLM: {len(classificado)} de {len(bruto)} confirmadas como relevantes")
    classificado.to_csv("licitacoes_classificadas.csv", index=False, encoding="utf-8-sig")
