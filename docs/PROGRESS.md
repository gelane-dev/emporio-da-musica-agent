# Progresso e pendências

> Fonte de verdade do **estado** do projeto. Critérios de aceite ficam em [[TASKS]]; decisões em [[TECHNICAL_DECISIONS]].
> Atualizado pelo coordenador (Opus) a cada tarefa integrada.

## Estado das tarefas

| Tarefa | Status | Commit | Observações |
|---|---|---|---|
| T01 Setup | concluída | `047c0fc` | 11 testes |
| T02 Loader e modelos | concluída | `6d84b83` | conflitos de produto detectados: #135–137, #139, #140, #142–144 |
| T03 Repositórios | concluída | `3e0cf27` | `inactive_promotions` substitui `latest_inactive_promotion` (sem datas) |
| T04 Preços/PIX/parcelas | concluída | `295e130` | limite 12x absoluto; combinado só > R$ 2.000,00 |
| T05 Horários e frete | em andamento | — | contrato em [[ARCHITECTURE#5.3.1 Contrato detalhado da T05 (horários e frete)]] |
| T06–T17 | pendentes | — | — |

Suíte atual: 106 testes passando (antes da T05).

## Decisões recentes (resumo; detalhes nos documentos citados)

- 2026-11-01 — Tratamentos de ambiguidades P1–P16 aprovados ([[DATA_ANALYSIS#4.2 Contradições, lacunas e tratamento]], [[TECHNICAL_DECISIONS#D15 — Limitações explícitas em vez de interpretações (revisado em 2026-11-01)]]).
- 2026-11-01 — Persona Mel, sem emojis, somente CLI, Claude Sonnet com provedor configurável ([[TECHNICAL_DECISIONS#Decisões aprovadas (2026-11-01)]]).
- 2026-11-01 — Orquestração multiagente via Orca a partir da T05 ([[docs/AGENT_GUIDE]]).

## Pendências abertas

- Nenhuma decisão de negócio pendente.
- Encoding de saída no Git Bash (RK11) — tratar na T13.

## Integridade dos dados originais

Hashes SHA-256 de `data/` conferidos após cada tarefa (T01–T04): inalterados.
