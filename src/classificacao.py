"""Classifica, via LLM com saída estruturada, se cada licitação pré-filtrada é relevante
para as categorias do projeto (Materiais de Limpeza, Serviços de Portaria/Segurança,
Serviços de Limpeza) e gera uma descrição resumida do objeto."""

import os
import time
from typing import Literal, Optional

import anthropic
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

MODELO = "claude-haiku-4-5-20251001"

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


_FERRAMENTA = {
    "name": "registrar_classificacao",
    "description": "Registra a classificação da licitação.",
    "input_schema": ClassificacaoLicitacao.model_json_schema(),
}

_PROMPT_SISTEMA = f"""Você classifica objetos de licitações públicas brasileiras nas categorias:
{", ".join(CATEGORIAS)}.
Considere relevante apenas se o objeto for claramente compra de materiais de limpeza,
ou contratação de serviços de portaria/segurança patrimonial, ou serviços de limpeza/conservação.
Objetos ambíguos ou de outra natureza (ex.: limpeza de terreno/via pública, obras, TI) não são relevantes."""


def _cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def classificar_objeto(objeto_compra: str, cliente: anthropic.Anthropic) -> ClassificacaoLicitacao:
    resposta = cliente.messages.create(
        model=MODELO,
        max_tokens=300,
        temperature=0,
        system=_PROMPT_SISTEMA,
        tools=[_FERRAMENTA],
        tool_choice={"type": "tool", "name": "registrar_classificacao"},
        messages=[{"role": "user", "content": objeto_compra}],
    )
    bloco = next(b for b in resposta.content if b.type == "tool_use")
    return ClassificacaoLicitacao.model_validate(bloco.input)


def classificar_dataframe(df: pd.DataFrame, pausa: float = 0.3) -> pd.DataFrame:
    """Classifica cada linha (coluna objetoCompra) e retorna só as relevantes, com colunas novas."""
    cliente = _cliente()
    resultados = []
    for objeto in df["objetoCompra"]:
        resultados.append(classificar_objeto(objeto, cliente))
        time.sleep(pausa)

    df = df.copy()
    df["categoria"] = [r.categoria for r in resultados]
    df["descricao_resumida"] = [r.descricao_resumida for r in resultados]
    df["relevante"] = [r.relevante for r in resultados]
    return df[df["relevante"]].drop(columns="relevante").reset_index(drop=True)


if __name__ == "__main__":
    bruto = pd.read_csv("licitacoes_filtradas.csv")
    classificado = classificar_dataframe(bruto)
    print(f"Após classificação por LLM: {len(classificado)} de {len(bruto)} confirmadas como relevantes")
    classificado.to_csv("licitacoes_classificadas.csv", index=False)
