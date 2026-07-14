"""Coleta licitações publicadas no PNCP na última semana e filtra por palavra-chave.

Roda semanalmente: busca só o que foi publicado desde a última execução (janela de 7
dias), em vez de reprocessar todo o universo de licitações abertas a cada vez.
"""

import json
import re
import time
from datetime import date, timedelta

import pandas as pd
import requests

BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
MODALIDADES = [6, 8]  # Pregão Eletrônico, Dispensa
TAMANHO_PAGINA = 50

PALAVRAS_CHAVE = [
    "limpeza",
    "conservação",
    "conservacao",
    "asseio",
    "higienização",
    "higienizacao",
    "portaria",
    "vigilância",
    "vigilancia",
    "segurança patrimonial",
    "seguranca patrimonial",
    "monitoramento",
]


def _janela_semanal(dias: int = 7) -> tuple[str, str]:
    hoje = date.today()
    inicio = hoje - timedelta(days=dias)
    return inicio.strftime("%Y%m%d"), hoje.strftime("%Y%m%d")


def _get_com_retentativa(params: dict, tentativas: int = 5) -> dict:
    """GET com retentativa: a API pública do PNCP dá timeout e 429 (rate limit) sob paginação pesada."""
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            if resp.status_code == 429:
                espera = int(resp.headers.get("Retry-After", 10 * tentativa))
                time.sleep(espera)
                continue
            resp.raise_for_status()
            return json.loads(resp.content.decode("utf-8"))  # a API não declara charset; requests erra o encoding
        except requests.exceptions.RequestException:
            if tentativa == tentativas:
                raise
            time.sleep(3 * tentativa)
    raise RuntimeError("Excedeu as retentativas por rate limit (429) do PNCP")


def buscar_licitacoes_da_semana(data_inicial: str | None = None, data_final: str | None = None) -> pd.DataFrame:
    """Busca no PNCP as licitações publicadas na janela (padrão: últimos 7 dias), nas modalidades de interesse."""
    if data_inicial is None or data_final is None:
        data_inicial, data_final = _janela_semanal()
    registros = []
    for modalidade in MODALIDADES:
        pagina = 1
        while True:
            params = {
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "codigoModalidadeContratacao": modalidade,
                "pagina": pagina,
                "tamanhoPagina": TAMANHO_PAGINA,
            }
            corpo = _get_com_retentativa(params)
            registros.extend(corpo.get("data", []))
            if pagina >= corpo.get("totalPaginas", 0):
                break
            pagina += 1
            time.sleep(0.5)  # não sobrecarregar a API pública
    return pd.json_normalize(registros)


def filtrar_por_palavra_chave(df: pd.DataFrame, palavras: list[str] = PALAVRAS_CHAVE) -> pd.DataFrame:
    """Mantém só as linhas cujo objetoCompra contém alguma palavra-chave (case-insensitive)."""
    if df.empty:
        return df
    padrao = "|".join(rf"\b{re.escape(p)}\b" for p in palavras)
    mascara = df["objetoCompra"].str.contains(padrao, case=False, na=False, regex=True)
    return df[mascara].reset_index(drop=True)


def filtrar_ainda_abertas(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém só as licitações cuja proposta ainda não encerrou."""
    if df.empty:
        return df
    encerramento = pd.to_datetime(df["dataEncerramentoProposta"], errors="coerce")
    return df[encerramento >= pd.Timestamp.now()].reset_index(drop=True)


if __name__ == "__main__":
    bruto = buscar_licitacoes_da_semana()
    filtrado = filtrar_por_palavra_chave(bruto)
    filtrado = filtrar_ainda_abertas(filtrado)
    print(f"Publicadas na semana: {len(bruto)} | Após palavra-chave e ainda abertas: {len(filtrado)}")
    filtrado.to_csv("licitacoes_filtradas.csv", index=False, encoding="utf-8-sig")
