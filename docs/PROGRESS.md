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
| T12 Encaminhamento | concluída | `fa858b9` | [[ARCHITECTURE#5.5.2 Contrato detalhado da T12 (`encaminhar_atendente`)]] |
| T13 CLI | concluída | `80f487f` | [[ARCHITECTURE#5.8.1 Contrato detalhado da T13 (CLI)]] |
| T14 Cenários E2E | histórico em `low` (Groq): 12/13 aprovados, cenário 5 não aprovado; regressão `medium` em 03/11 com Anthropic `claude-sonnet-5-5`: 14/14 checagens e revisão manual ok; regressão `medium` na Groq não executada (cota) — [[docs/E2E_RESULTS]] | `b80958e`, `1a0779f`, `4ac2216` | [[ARCHITECTURE#5.9.1 Contrato detalhado da T14 (cenários end-to-end)]] |
| T15 Conversas de exemplo | 3 conversas reais: C1 regravada em 03/11 com Anthropic `claude-sonnet-5-5` `medium` (correta; gravação `low` com erro preservada em docs/e2e); C2 `low` correta; C3 `medium` correta | `01f50ba` | [[ARCHITECTURE#5.9.2 Contrato da T15 (gravação das conversas de exemplo)]] |
| T16 README | final em inglês; atualizado em 03/11 com a regressão e a C1 feitas com a Anthropic | `f541806` | — |
| T18 API HTTP + frontend web | concluída e integrada na `main`; pytest com `FakeLLM`, lint e build; 1 conversa real frontend → API → Anthropic em 03/11 (Groq não) | `67f6b1f`, `71bd693`, `9cc2441`, `6404109` | D18/D19; [[ARCHITECTURE#5.10 `api/` — camada HTTP (2026-11-03, D18)]] e §8 |
| T17 Entrega | publicada em 02/11 (push autorizado pelo usuário); atualização de 03/11 commitada localmente, **push aguardando autorização** | — | ver "Preparação da T17" |

Suíte atual (03/11/2026, `main` após a integração): **1099 passed, 2 deselected** (marcador `llm`) (1091 em `71bd693`, antes das correções da revisão), inclusive `tests/test_api.py`; `npm run lint` e `npm run build` do frontend sem erros.

Suíte em 01/11 (antes da API): 1029 testes passando + 2 smokes reais pulados (Anthropic e Groq), sem avisos; verificada também em clone limpo e em ambiente virtual novo instalado só pelo `requirements.txt`.

## Decisões recentes (resumo; detalhes nos documentos citados)

- 2026-11-03 — API HTTP fina (FastAPI) sobre o agente, sessões só em memória ([[TECHNICAL_DECISIONS#D18 — API HTTP fina sobre o agente (decisão do usuário, 2026-11-03)]]) e frontend React/Vite reintroduzido e ligado à API ([[TECHNICAL_DECISIONS#D19 — Frontend web reintroduzido e conectado à API (decisão do usuário, 2026-11-03)]]); revisam D6.

- 2026-11-01 — Tratamentos de ambiguidades P1–P16 aprovados ([[DATA_ANALYSIS#4.2 Contradições, lacunas e tratamento]], [[TECHNICAL_DECISIONS#D15 — Limitações explícitas em vez de interpretações (revisado em 2026-11-01)]]).
- 2026-11-01 — Persona Mel, sem emojis, somente CLI, Claude Sonnet com provedor configurável ([[TECHNICAL_DECISIONS#Decisões aprovadas (2026-11-01)]]).
- 2026-11-01 — Orquestração multiagente via Orca a partir da T05 ([[docs/AGENT_GUIDE]]).

## Execução multiagente (registro)

| Tarefa | Run Orca | Agentes | Worktrees/branches | Resultado |
|---|---|---|---|---|
| T05 | `run_a5ecc3d46e82` | Backend (impl.), QA (testes TDD a partir do contrato) — Sonnet | `gelane-dev/t05-backend`, `gelane-dev/t05-qa` | integração por squash sem conflitos; implementação e testes independentes concordaram na 1ª execução |

| T08b (Groq) | `run_bb5ce514aa0a` | IA/RAG (adaptador), QA (testes) — Sonnet; +2 correções | `t08b-ia-rag`, `w6-qa` | 1ª tentativa parou no limite de uso de 5h da conta (sem produzir nada; provado pela transcrição) ⇒ `worker-stop`/`worker-abandon` + `--retry-of`; integração achou captura antecipada de `time.sleep` (script) e objetos de teste com validação estrita (testes) |
| T14 Cenários E2E | histórico em `low` (Groq): 12/13 aprovados, cenário 5 não aprovado; regressão `medium` em 03/11 com Anthropic `claude-sonnet-5-5`: 14/14 checagens e revisão manual ok; regressão `medium` na Groq não executada (cota) — [[docs/E2E_RESULTS]] | `b80958e`, `1a0779f`, `4ac2216` | [[ARCHITECTURE#5.9.1 Contrato detalhado da T14 (cenários end-to-end)]] |
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
- Não versionados (confirmado): `.env`, `venv/`, `runtime/`, `frontend/` (fora do escopo, decisão do usuário; mantida intacta no disco — **revertido em 03/11 por nova decisão do usuário: `frontend/` voltou em `71bd693` (`773ed61` na branch), T18**), `node_modules`.
- Tamanho do `.git`: 3 MB; maiores arquivos: PDFs de `data/`.
- Histórico: commits incrementais (sem squash/force-push), autor `gelane-dev`.
- `gh` não instalado; publicação depende de instalação/autenticação ou de um repositório vazio criado pelo usuário.
- `data/desafio_tecnico_ai_eng_artefact.pdf` (enunciado) removido do versionamento por decisão do usuário (preservado localmente, no `.gitignore`).
- **Histórico reescrito em 01/11/2026 (autorizado pelo usuário, antes de qualquer publicação):** o PDF foi removido de todos os commits (`git filter-branch --index-filter`), referências de backup e reflog expurgadas, `git gc --prune=now`; verificado que nenhum commit ou objeto contém o PDF e `git fsck` limpo. Todos os hashes mudaram; as referências desta documentação foram atualizadas (38 commits mapeados um a um pela mensagem).
- Remoto configurado (sem push): `origin` = https://github.com/gelane-dev/emporio-da-musica-agent.git
- Publicação só após aprovação explícita do usuário.
- Revisão sem cota (01/11, noite): clone limpo (1029 testes, `build_policies --check`, CLI sem `.env` ⇒ código 2); instalação do zero em venv novo (`pip check` limpo); `compileall` ok; dependências declaradas = importadas; sem TODO/print de depuração; achado **F1** (argumentos de `encaminhar_atendente` em log INFO) corrigido em `e7ee89a`; aviso `PytestRemovedIn10Warning` eliminado; marcações de aprovação pendente já resolvidas removidas de TECHNICAL_DECISIONS. Observação de ambiente: no Windows, instalar o projeto em caminho muito longo pode exceder 260 caracteres por causa do SDK `anthropic` (ocorreu só no diretório temporário da ferramenta).

## Retomada quando a cota da Groq renovar (prevista para 02/11 a partir de ~17h30)

1. Testes pendentes da T14 (prioridade A de [[docs/E2E_RESULTS]]): cenários 5 e 10 (2 repetições) e 9 (1 repetição).
2. T15: 3 conversas reais gravadas com `--save` (catálogo; preço/parcelamento/promoção; devolução não trivial), sem edição de conteúdo.
3. T16: README final com resultados e exemplos reais.
4. T17: revisão final e aprovação do usuário para publicar.

## Reescrita do histórico para publicação (02/11/2026, autorizada pelo usuário)

- Backup antes de alterar: bundle completo do repositório e cópia do `frontend/` (sem `node_modules`/`dist`) em `C:/Users/Dell/Desktop/emporio-da-musica-agent-backups/20261102-1849`.
- `frontend/` e `.obsidian/` removidos do versionamento (mantidos no disco, no `.gitignore`); `frontend/` expurgado de todo o histórico (`git filter-branch --index-filter`, `--prune-empty`): 2 commits que só continham o frontend foram removidos; a mensagem do commit que ficou só com a alteração do `.gitignore` foi corrigida.
- Verificado: nenhum commit/objeto com `frontend/` ou com o enunciado do desafio; `git fsck` limpo; referências de commit da documentação atualizadas.

## Execução final com a Anthropic (03/11/2026, decisão do usuário)

- Agendamento autônomo na Groq (18h41) cancelado após o usuário pedir para terminar com a API da Anthropic.
- Regressão única `medium`: `claude-sonnet-5-5`, `LLM_MAX_TOKENS=4096`, 13 cenários × 1 ⇒ 14/14; revisão manual sem veredito, sem procedimento fora do manual, sem exposição de dados; uma imprecisão de redação no cenário 2 (feriados). Relatório: [[docs/e2e/t14_regressao_claude_medium.md]].
- C1 regravada com o mesmo provedor: correta. Nenhuma alteração de código.
- Não executado: regressão `medium` na Groq (padrão do projeto).

## API HTTP e frontend (T18, 03/11/2026, branch `gelane-dev/backend-e-frontend`)

- `67f6b1f` (na branch: `40cafe0`) — `src/emporio_agent/api/` (`app.py`, `schemas.py`, `sessions.py`, `__main__.py`) + `tests/test_api.py`; `fastapi`, `uvicorn`, `httpx` no `requirements.txt`; `CORS_ORIGINS` e `MAX_SESSIONS` no `.env.example`. Nada fora de `api/` mudou em `src/`, `data/` ou `knowledge/`.
- `71bd693` (na branch: `773ed61`) — `frontend/` volta ao versionamento por decisão do usuário, revertendo a exclusão de `1463ba2` e da reescrita de 02/11 (que continuam válidas para o histórico anterior); `node_modules/`, `dist/` e `frontend/.env` ignorados.
- Verificado (local, sem provedor real): `pytest` 1091 passed, 2 deselected em `71bd693` e 1099 com as correções da revisão; `npm run lint` e `npm run build` sem erros; respostas reais da API conferidas em processo com `TestClient` + `FakeLLM` (exemplos do README).
- Revisão somente leitura (outro agente, Orca): 0 achados altos, 3 médios, 7 baixos. Correções despachadas em paralelo pelo coordenador: estado de envio por conversa, tratamento de 409/timeout, `maxLength` 2000 no composer, status do cabeçalho por `GET /api/health`, texto da nota de privacidade (frontend); `session_id` com `secrets.token_urlsafe` e limite de tamanho do corpo com 413 `payload_too_large` (API). Essas correções já estavam aplicadas no worktree (ainda não commitadas) quando a documentação foi atualizada, e ela as descreve como estão no código: corpo até 16 KiB (`MAX_BODY_BYTES`), `session_id` até 64 caracteres, token de 128 bits, timeout do cliente de 90 s, `hooks/useBackendHealth.js`, até 3 novas tentativas em 409. **Conferir de novo no commit final.** Achados aceitos como limitação documentada: sem limite de taxa em `POST /api/sessions` (descarte LRU em massa; API só local), `Session.messages` sem limite em memória, traceback no log de erro 500, histórico do chat no `localStorage`, sem autenticação.
- Documentação atualizada (README com diagramas Mermaid validados com `@mermaid-js/mermaid-cli`, ARCHITECTURE §5.10/§8, TECHNICAL_DECISIONS D18/D19, TASKS T18, `frontend/README.md`).
- **Pendente:** conversa real pelo caminho web com a Groq; testes automatizados do frontend. (A conversa real pelo caminho web com a Anthropic foi feita na integração; ver a seção seguinte.)

## Integração na `main` (03/11/2026)

- Os 4 commits da branch `gelane-dev/backend-e-frontend` foram aplicados na `main` por cherry-pick (histórico linear, mensagens originais): `40cafe0`→`67f6b1f`, `773ed61`→`71bd693`, `81a17b0`→`9cc2441`, `1324625`→`6404109`. Conflitos só em `README.md` e `docs/PROGRESS.md` (resultados da Anthropic de `7901bdc`/`cf4f182` × camada web), resolvidos mantendo os dois lados.
- Antes da integração, a cópia local antiga de `frontend/` (ignorada, versão de 01/11 só com modo demonstrativo) foi guardada em `C:/Users/Dell/Desktop/emporio-da-musica-agent-backups/20261103-integracao/frontend-local-main`; a versão versionada (03/11, ligada à API) a substitui.
- Consolidação (`510ac27`): removido `frontend/src/assets/hero.png` (sem uso) e `frontend/.gitignore` (regras repetidas; as úteis foram para o `.gitignore` da raiz).
- Verificado na `main`: `pytest` 1099 passed, 2 deselected; `npm run lint` e `npm run build` sem erros.
- Validação real pelo navegador com Anthropic `claude-sonnet-5-5` (3 chamadas), modo degradado e provedor inalcançável: [[docs/e2e/web_e2e_anthropic.md]]. Provedor padrão do `.env` inalterado (Groq).

## Pendências abertas

- Nenhuma decisão de negócio pendente.
- **Provedor alterado para Groq (decisão do usuário, D17).** T14/T15 executam quando `GROQ_API_KEY` estiver no `.env` (ainda ausente em 2026-11-01).
- RK11 (acentuação no Git Bash) resolvido na T13 (validação manual).

## Integridade dos dados originais

Hashes SHA-256 de `data/` conferidos após cada tarefa (T01–T06): inalterados.
