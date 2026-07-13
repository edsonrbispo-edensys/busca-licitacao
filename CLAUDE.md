# CLAUDE.md — Busca Licitação

## Objetivo

Buscar licitações públicas em aberto em nível nacional e apresentar as informações
relevantes de cada uma: Nome da Licitação (Objeto), Descrição Resumida, Data de
Abertura, Data de Fechamento, Data do Pregão, Valor, Órgão Licitante, Estado e
Município. Ajuda o usuário a identificar oportunidades de licitação sem precisar
vasculhar manualmente os portais públicos.

## Fontes de dados

- **PNCP — Portal Nacional de Contratações Públicas** — API pública de consulta de
  licitações abertas (https://pncp.gov.br). Fonte primária de dados.

## Filtros de busca

Limitar as buscas às seguintes categorias de objeto:

- Materiais de Limpeza
- Serviços de Portaria/Segurança
- Serviços de Limpeza

## Metodologia (CRISP-DM)

1. **Negócio** — encontrar licitações abertas relevantes (limpeza, portaria/segurança)
   em todo o território nacional, a tempo de participar do processo.
2. **Dados** — API do PNCP: volume nacional, atualização contínua, formato JSON.
3. **Preparação** — filtrar por categoria/objeto, normalizar campos (datas, valores,
   órgão, localização).
4. **Modelagem** — classificação/triagem das licitações relevantes com LLM via API
   (saída estruturada em Pydantic) a partir da descrição do objeto.
5. **Avaliação** — validar contra amostras conhecidas de licitações nas categorias-alvo.
6. **Implantação** — entrega reprodutível (paper Quarto e/ou automação de notificação).

## Regra de ouro

**Nunca inventar número.** Todo valor citado (datas, valores, contagens) vem de um
chunk/execução real contra a API do PNCP.

## Segredos

Chaves de API só no `.env` (no `.gitignore`), lidas por variável de ambiente.
Nunca versionar `.env`.

## Stack

- Python ≥ 3.10 em `.venv`
- Quarto + LaTeX (TinyTeX) para entrega em PDF
- Claude Code como agente de desenvolvimento
