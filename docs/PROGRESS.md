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
| T07 PolicyStore | concluída | (commit `feat(policies): PolicyStore`) | [[ARCHITECTURE#5.4.2 Contrato detalhado da T07 (`PolicyStore`)]] |
| T08 Adaptador LLM | em andamento | — | [[ARCHITECTURE#5.6.1 Contrato detalhado da T08]]; D16 |
| T09–T17 | pendentes | — | T14/T15 exigem credencial da API (ver pendências) |

Suíte atual: 534 testes passando (após a T07).

## Decisões recentes (resumo; detalhes nos documentos citados)

- 2026-11-01 — Tratamentos de ambiguidades P1–P16 aprovados ([[DATA_ANALYSIS#4.2 Contradições, lacunas e tratamento]], [[TECHNICAL_DECISIONS#D15 — Limitações explícitas em vez de interpretações (revisado em 2026-11-01)]]).
- 2026-11-01 — Persona Mel, sem emojis, somente CLI, Claude Sonnet com provedor configurável ([[TECHNICAL_DECISIONS#Decisões aprovadas (2026-11-01)]]).
- 2026-11-01 — Orquestração multiagente via Orca a partir da T05 ([[docs/AGENT_GUIDE]]).

## Execução multiagente (registro)

| Tarefa | Run Orca | Agentes | Worktrees/branches | Resultado |
|---|---|---|---|---|
| T05 | `run_a5ecc3d46e82` | Backend (impl.), QA (testes TDD a partir do contrato) — Sonnet | `gelane-dev/t05-backend`, `gelane-dev/t05-qa` | integração por squash sem conflitos; implementação e testes independentes concordaram na 1ª execução |

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
- Encoding de saída no Git Bash (RK11) — tratar na T13.

## Integridade dos dados originais

Hashes SHA-256 de `data/` conferidos após cada tarefa (T01–T06): inalterados.
