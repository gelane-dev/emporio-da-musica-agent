# Progresso e pendências

> Fonte de verdade do **estado** do projeto. Critérios de aceite ficam em [[TASKS]]; decisões em [[TECHNICAL_DECISIONS]].
> Atualizado pelo coordenador (Opus) a cada tarefa integrada.

## Estado das tarefas

| Tarefa | Status | Commit | Observações |
|---|---|---|---|
| T01 Setup | concluída | `b629367` | 11 testes |
| T02 Loader e modelos | concluída | `5f1d536` | conflitos de produto detectados: #135–137, #139, #140, #142–144 |
| T03 Repositórios | concluída | `6a0a2df` | `inactive_promotions` substitui `latest_inactive_promotion` (sem datas) |
| T04 Preços/PIX/parcelas | concluída | `dc6bdbb` | limite 12x absoluto; combinado só > R$ 2.000,00 |
| T05 Horários e frete | concluída | `72b24c6` | contrato [[ARCHITECTURE#5.3.1 Contrato detalhado da T05 (horários e frete)]]; Backend + QA (Sonnet) em paralelo via Orca |
| T06 Extração do PDF | concluída | `084ce88` | contrato [[ARCHITECTURE#5.4.1 Contrato detalhado da T06 (extração do PDF → `knowledge/policies.md`)]]; IA/RAG + QA (Sonnet) via Orca |
| T07 PolicyStore | concluída | `b2de4d1` | [[ARCHITECTURE#5.4.2 Contrato detalhado da T07 (`PolicyStore`)]] |
| T08 Adaptador LLM | concluída (smoke real pendente de credencial) | `a22cdab` | [[ARCHITECTURE#5.6.1 Contrato detalhado da T08]]; D16 |
| T08b Adaptador Groq | concluída (smoke real pendente da chave) | `60644c9` | D17; [[ARCHITECTURE#5.6.2 Contrato do adaptador Groq (T08b — provedor padrão desde 2026-11-01, D17)]] |
| T09 Ferramentas | concluída | `d7828ec` | [[ARCHITECTURE#5.5.1 Contrato detalhado da T09 (ferramentas)]] |
| T10 Prompt | concluída | `9ab4b5c` | [[ARCHITECTURE#5.7.1 Contrato detalhado da T10 (prompt de sistema)]] |
| T11 Loop do agente | concluída | `1166fb1` | [[ARCHITECTURE#5.7.2 Contrato detalhado da T11 (loop do agente e sessão)]] |
| T12 Encaminhamento | concluída | `fa858b9` |
| T13 CLI | concluída | `80f487f` |
| T14 Cenários E2E | 10 de 13 cenários aprovados em execuções reais; 5, 9, 10 pendentes de cota (relatório [[docs/E2E_RESULTS]]) | `b80958e`, `1a0779f`, `4ac2216` | [[ARCHITECTURE#5.9.1 Contrato detalhado da T14 (cenários end-to-end)]] |
| T16 README | em inglês e atualizado para Groq (resultados e exemplos pendentes de T14/T15) | (commit `docs: README em inglês`) | `20c9785` rascunho PT | [[ARCHITECTURE#5.8.1 Contrato detalhado da T13 (CLI)]] | [[ARCHITECTURE#5.5.2 Contrato detalhado da T12 (`encaminhar_atendente`)]] |
| T15, T17 | pendentes | — T14/T15 exigem credencial da API (ver pendências) |

Suíte atual: 968 testes passando + 2 smokes reais pulados (Anthropic e Groq) após a T08b.

## Decisões recentes (resumo; detalhes nos documentos citados)

- 2026-11-01 — Tratamentos de ambiguidades P1–P16 aprovados ([[DATA_ANALYSIS#4.2 Contradições, lacunas e tratamento]], [[TECHNICAL_DECISIONS#D15 — Limitações explícitas em vez de interpretações (revisado em 2026-11-01)]]).
- 2026-11-01 — Persona Mel, sem emojis, somente CLI, Claude Sonnet com provedor configurável ([[TECHNICAL_DECISIONS#Decisões aprovadas (2026-11-01)]]).
- 2026-11-01 — Orquestração multiagente via Orca a partir da T05 ([[docs/AGENT_GUIDE]]).

## Execução multiagente (registro)

| Tarefa | Run Orca | Agentes | Worktrees/branches | Resultado |
|---|---|---|---|---|
| T05 | `run_a5ecc3d46e82` | Backend (impl.), QA (testes TDD a partir do contrato) — Sonnet | `gelane-dev/t05-backend`, `gelane-dev/t05-qa` | integração por squash sem conflitos; implementação e testes independentes concordaram na 1ª execução |

| T08b (Groq) | `run_bb5ce514aa0a` | IA/RAG (adaptador), QA (testes) — Sonnet; +2 correções | `t08b-ia-rag`, `w6-qa` | 1ª tentativa parou no limite de uso de 5h da conta (sem produzir nada; provado pela transcrição) ⇒ `worker-stop`/`worker-abandon` + `--retry-of`; integração achou captura antecipada de `time.sleep` (script) e objetos de teste com validação estrita (testes) |
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

## Limpeza

2026-11-01: os 18 worktrees/branches temporários das T05–T16 foram removidos após verificação (sem alterações pendentes; conteúdo integrado por squash nos commits de cada tarefa).

## Execuções reais da T14 (Groq, openai/gpt-oss-120b)

| Execução | Resultado | Causa das falhas | Ação |
|---|---|---|---|
| 1 (pausa 10 s) | 9/14 e 11/14 | agente não consultava pedido; emoji; falsos negativos do avaliador (hífen U+2011, "20 %") | `1a0779f` (prompt, guard de saída, avaliador, isolamento de credenciais nos testes) |
| 2 (pausa 10 s) | 11/14 e 9/14 | produto inventado após busca vazia; devolução sem política; 429 por 8K tokens/min | `4ac2216` (grounding nas tools e prompt, paciência com 429, pausa 60 s) |
| 3 (pausa 60 s) | 4/14 (inválida) | **cota diária esgotada**: 200K tokens/dia por modelo, janela móvel de 24 h (mensagem 429 da Groq); nenhum cenário avaliou o agente | decisão do usuário: sem novas baterias completas; só os testes essenciais pendentes (cenários 5, 10, 9) quando a cota renovar — ver [[docs/E2E_RESULTS]] |

Medição: cada chamada custa ~2.400 tokens só de prompt + esquemas; uma bateria completa (13 × 2) consome perto de 100–200 mil tokens, ou seja, a cota diária inteira.

## Preparação da T17 (revisão de entrega, 01/11/2026 — sem publicação)

- Segredos: nenhuma chave real no histórico completo (`gsk_…`, `sk-ant-…`); única atribuição é valor fictício de teste.
- Não versionados (confirmado): `.env`, `venv/`, `runtime/`, `frontend/` (fora do escopo, decisão do usuário; mantida intacta no disco), `node_modules`.
- Tamanho do `.git`: 3 MB; maiores arquivos: PDFs de `data/`.
- Histórico: commits incrementais (sem squash/force-push), autor `gelane-dev`.
- `gh` não instalado; publicação depende de instalação/autenticação ou de um repositório vazio criado pelo usuário.
- `data/desafio_tecnico_ai_eng_artefact.pdf` (enunciado) removido do versionamento por decisão do usuário (preservado localmente, no `.gitignore`).
- **Histórico reescrito em 01/11/2026 (autorizado pelo usuário, antes de qualquer publicação):** o PDF foi removido de todos os commits (`git filter-branch --index-filter`), referências de backup e reflog expurgadas, `git gc --prune=now`; verificado que nenhum commit ou objeto contém o PDF e `git fsck` limpo. Todos os hashes mudaram; as referências desta documentação foram atualizadas (38 commits mapeados um a um pela mensagem).
- Remoto configurado (sem push): `origin` = https://github.com/gelane-dev/emporio-da-musica-agent.git
- Publicação só após aprovação explícita do usuário.

## Retomada quando a cota da Groq renovar (prevista para 02/11 a partir de ~17h30)

1. Testes pendentes da T14 (prioridade A de [[docs/E2E_RESULTS]]): cenários 5 e 10 (2 repetições) e 9 (1 repetição).
2. T15: 3 conversas reais gravadas com `--save` (catálogo; preço/parcelamento/promoção; devolução não trivial), sem edição de conteúdo.
3. T16: README final com resultados e exemplos reais.
4. T17: revisão final e aprovação do usuário para publicar.

## Pendências abertas

- Nenhuma decisão de negócio pendente.
- **Provedor alterado para Groq (decisão do usuário, D17).** T14/T15 executam quando `GROQ_API_KEY` estiver no `.env` (ainda ausente em 2026-11-01).
- `tests/test_build_policies.py`: fixture de classe definida como método de instância gera `PytestRemovedIn10Warning` (sem efeito hoje) — ajustar quando houver nova rodada de QA.
- RK11 (acentuação no Git Bash) resolvido na T13 (validação manual).

## Integridade dos dados originais

Hashes SHA-256 de `data/` conferidos após cada tarefa (T01–T06): inalterados.
