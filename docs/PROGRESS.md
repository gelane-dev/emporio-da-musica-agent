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
| T05 Horários e frete | concluída | `e24798c` | contrato [[ARCHITECTURE#5.3.1 Contrato detalhado da T05 (horários e frete)]]; Backend + QA (Sonnet) em paralelo via Orca |
| T06 Extração do PDF | concluída | `053352e` | contrato [[ARCHITECTURE#5.4.1 Contrato detalhado da T06 (extração do PDF → `knowledge/policies.md`)]]; IA/RAG + QA (Sonnet) via Orca |
| T07 PolicyStore | concluída | `00c85b3` | [[ARCHITECTURE#5.4.2 Contrato detalhado da T07 (`PolicyStore`)]] |
| T08 Adaptador LLM | concluída (smoke real pendente de credencial) | `35485ec` | [[ARCHITECTURE#5.6.1 Contrato detalhado da T08]]; D16 |
| T09 Ferramentas | concluída | `8594164` | [[ARCHITECTURE#5.5.1 Contrato detalhado da T09 (ferramentas)]] |
| T10 Prompt | concluída | `db61a89` | [[ARCHITECTURE#5.7.1 Contrato detalhado da T10 (prompt de sistema)]] |
| T11 Loop do agente | concluída | `f7e1088` | [[ARCHITECTURE#5.7.2 Contrato detalhado da T11 (loop do agente e sessão)]] |
| T12 Encaminhamento | concluída | `585ac91` |
| T13 CLI | concluída | `453a1cb` |
| T14 Cenários E2E | preparação concluída; **execução real bloqueada pela credencial** | `9df578b` | [[ARCHITECTURE#5.9.1 Contrato detalhado da T14 (cenários end-to-end)]] |
| T16 README | rascunho concluído | (commit `docs: rascunho do README`) | seções de resultados E2E e exemplos pendentes de T14/T15 | [[ARCHITECTURE#5.8.1 Contrato detalhado da T13 (CLI)]] | [[ARCHITECTURE#5.5.2 Contrato detalhado da T12 (`encaminhar_atendente`)]] |
| T15, T17 | pendentes | — T14/T15 exigem credencial da API (ver pendências) |

Suíte atual: 905 testes passando + 1 smoke real pulado (após a preparação da T14).

## Decisões recentes (resumo; detalhes nos documentos citados)

- 2026-11-01 — Tratamentos de ambiguidades P1–P16 aprovados ([[DATA_ANALYSIS#4.2 Contradições, lacunas e tratamento]], [[TECHNICAL_DECISIONS#D15 — Limitações explícitas em vez de interpretações (revisado em 2026-11-01)]]).
- 2026-11-01 — Persona Mel, sem emojis, somente CLI, Claude Sonnet com provedor configurável ([[TECHNICAL_DECISIONS#Decisões aprovadas (2026-11-01)]]).
- 2026-11-01 — Orquestração multiagente via Orca a partir da T05 ([[docs/AGENT_GUIDE]]).

## Execução multiagente (registro)

| Tarefa | Run Orca | Agentes | Worktrees/branches | Resultado |
|---|---|---|---|---|
| T05 | `run_a5ecc3d46e82` | Backend (impl.), QA (testes TDD a partir do contrato) — Sonnet | `gelane-dev/t05-backend`, `gelane-dev/t05-qa` | integração por squash sem conflitos; implementação e testes independentes concordaram na 1ª execução |

| T14 (preparação) + README | `run_c7d7988248ee` | IA/RAG (script de cenários + ajustes de texto), QA (testes; +1 correção), Docs (rascunho do README) — Sonnet | `t14-ia-rag`, `w5-qa`, `t16-docs` | ambiguidade do contrato (emoji dentro ou fora do `evaluate`) resolvida a favor da checagem global |
| T13 | `run_140a77ff0235` | Backend (CLI), QA (testes) — Sonnet | `t13-backend`, `w4-qa` | Backend perguntou (ask) antes de alterar teste da T01; aprovado `--version`; 33 testes do QA passaram na 1ª integração |
| T11+T12 | `run_2d70073736b9` | IA/RAG (T11), Backend (T12), QA (testes) — Sonnet | `t11-ia-rag`, `t12-backend`, `w3-qa` | integração sem correções: 96 testes do QA passaram na 1ª execução |
| T09+T10 | `run_5532f4d9b606` | Backend (T09), IA/RAG (T10), QA (testes; +2 correções) — Sonnet | `t09-backend`, `t10-ia-rag`, `w2-qa` | testes do QA corrigidos: categoria com nome exato, P15 com dados sintéticos (sem skip) e verificação de conceitos no prompt em vez de frases exatas |
| T07+T08 | `run_df55428d95e4` | Backend (T07), IA/RAG (T08 + 1 correção), QA (testes de ambas) — Sonnet, 3 em paralelo | `t07-backend`, `t08-ia-rag`, `w1-qa` | QA detectou vazamento potencial de texto da API (com a chave) na mensagem de `bad_request` → corrigido pelo IA/RAG |
| T06 | `run_31a1ddbd85a8` | IA/RAG (script + .md; 2 dispatches), QA (testes de fidelidade; 3 dispatches) — Sonnet | `gelane-dev/t06-ia-rag`, `gelane-dev/t06-qa` | revisão do coordenador achou 4 desvios de estrutura (parágrafos, negrito por regex) → corrigidos pelo IA/RAG; QA corrigiu critério e falso positivo; integração 499 testes |

Lições:
- Contrato detalhado (assinaturas + tabela de casos + literais) permite implementação e testes em paralelo (T05, T06).
- Verificar a viabilidade do critério de aceite no dado real antes de despachar (T06: artefato de kerning do pypdf exigiu trocar comparação por palavras por comparação de caracteres).
- `orchestration send` só garante enfileiramento: mudança de contrato durante a execução precisa ser confirmada no `worker_done` (o QA da T06 não leu a mensagem).
- Reuso do mesmo terminal após `worker_done` falhou ("not running a recognized agent"); funciona iniciar novo Sonnet no **mesmo worktree**.
- `autocrlf=true`: arquivos gerados com `--check` precisam de `.gitattributes` (`eol=lf`).

## Pendências abertas

- Nenhuma decisão de negócio pendente.
- **Credencial da API ausente** (sem `ANTHROPIC_API_KEY`, sem `.env`, sem CLI `ant`): T07–T13 seguem com `FakeLLM`; T14 (cenários reais) e T15 (conversas de exemplo) dependem do usuário fornecer a chave em `.env`.
- `tests/test_build_policies.py`: fixture de classe definida como método de instância gera `PytestRemovedIn10Warning` (sem efeito hoje) — ajustar quando houver nova rodada de QA.
- RK11 (acentuação no Git Bash) resolvido na T13 (validação manual).

## Integridade dos dados originais

Hashes SHA-256 de `data/` conferidos após cada tarefa (T01–T06): inalterados.
