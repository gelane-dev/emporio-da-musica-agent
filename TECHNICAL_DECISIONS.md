# TECHNICAL_DECISIONS.md — Decisões técnicas (para aprovação)

Formato de cada decisão: **contexto → decisão → alternativas descartadas → consequências**.
Todas as decisões que dependiam de aprovação foram aprovadas em 2026-11-01 (ver "Decisões aprovadas"); D17 substituiu o provedor de D5 por decisão do usuário. D18 (API HTTP) e D19 (frontend web) foram decididas pelo usuário em 2026-11-03 e revisam D6.

---

## Requisitos do desafio (base para as decisões)

### Obrigatórios
| ID | Requisito | Onde é atendido |
|---|---|---|
| R1 | Projeto em **Python** (única restrição técnica) | Todo o projeto |
| R2 | Agente de **mensagens de texto** para clientes da Empório da Música | `agent/` + `cli.py` |
| R3 | **Persona** alinhada ao tom da loja (informal, profissional, "amigo que entende de música") | `agent/prompts.py` |
| R4 | Responder com base no **contexto disponibilizado** (sem inventar) | Tools + prompt de grounding |
| R5 | Saber **quando consultar dados** (preço, estoque, pedido) e **quando consultar políticas** | Function calling com tools separadas |
| R6 | Lidar com perguntas **fora do escopo** | Prompt + regras de escopo (acessórios / temas alheios) |
| E1 | Repositório Git **público** com **histórico de commits real** (sem squash/force-push) | Commits por tarefa |
| E2 | **README.md**: como rodar, justificativas técnicas, limitações, uso de assistentes de IA | T16 |
| E3 | **3 a 5 conversas** de exemplo (.md/.txt/imagem), ≥1 não trivial | T15 |
| E4 | Ambiguidades: assumir interpretação razoável e **documentar no README** | Seção "Ambiguidades e limitações" (alimentada por DATA_ANALYSIS §3/§4.2). Por decisão aprovada (D15), ambiguidades do manual viram limitações explícitas, não regras |

### Implícitos (critérios de avaliação: lógica, clareza, iniciativa)
- Decisões justificadas e rastreáveis; código legível; comportamento previsível.
- Exatidão em preços/estoque (política 7.1: "nunca fornecer preços/estoque sem consultar o sistema").

---

## D1 — Abordagem do agente: **function calling (tool use) com loop próprio**

**Contexto.** O agente precisa decidir *quando* consultar dados vs. políticas (R5). Os dados são tabulares e pequenos; as políticas são um documento curto.

**Decisão.** Agente de tool use: o LLM recebe um conjunto de ferramentas tipadas e decide qual chamar. Loop implementado manualmente (~100 linhas): `LLM → tool_calls → executar → devolver resultados → LLM`, com limite de iterações.

**Alternativas descartadas.**
- *Agente de SQL (text-to-SQL)*: flexível, mas abre margem para queries erradas/perigosas, expõe tabela de clientes e dificulta aplicar regras de negócio (PIX, promo, parcelas). Overkill para 65 produtos.
- *RAG puro sobre tudo*: dados de preço/estoque precisam de exatidão e filtros numéricos (≤ R$ 1000) — vetores não fazem isso bem.
- *LangChain / LangGraph / LlamaIndex*: adicionam abstração e dependências sem ganho real neste tamanho; dificultam explicar o fluxo no README. Um loop explícito mostra o raciocínio de engenharia.

**Consequências.** Cada decisão de consulta fica **observável** (log de tool calls), o que facilita avaliação e testes de roteamento. Lógica de negócio fica em Python, testável sem LLM.

## D2 — Retrieval de políticas: **segmentação por seção + tool `consultar_politica(topico)`**

**Contexto.** PDF de 8 páginas (~3k tokens), estrutura em seções numeradas.

**Decisão.**
1. Extração **offline** (script) PDF → `knowledge/policies.md`, revisado manualmente e versionado.
2. Divisão por seção em tópicos fixos (`horarios`, `pagamento`, `trocas_devolucoes`, `frete_entrega`, `promocoes`, `garantia`, `privacidade`, `sobre_loja`, `atendimento`).
3. Tool `consultar_politica(topico)` com `enum` de tópicos; retorna o texto integral da(s) seção(ões).
4. Regras de **conduta** (tom de voz, escopo, fluxo, situações especiais — seção 7 e 10) vão direto no prompt de sistema, pois valem para toda mensagem.

**Alternativas descartadas.**
- *Embeddings + vector store (Chroma/FAISS)*: com ~10 seções, o recall de um enum bem descrito é superior e determinístico; vetores trariam dependência, custo e risco de recuperar o trecho errado. Fica como "com mais tempo / se o manual crescer".
- *Política inteira no system prompt*: funciona e é mais simples, mas torna invisível o "quando consultar políticas" exigido pelo desafio e polui todo turno com texto irrelevante.

**Consequências.** Retrieval 100% determinístico e auditável. Se o PDF mudar, é preciso rodar o script e revisar o `.md` (documentado).

## D3 — Camada de dados: **pandas em memória + repositório com funções de consulta**

**Decisão.** Carregar os CSVs uma vez na inicialização, normalizar tipos e expor funções de consulta (repositório). Nada de banco.

**Alternativas.** SQLite (útil se houvesse escrita/concorrência; não há). Dicionários puros com `csv` (viável; pandas simplifica filtros e é familiar a avaliadores). (Aprovado: pandas.)

**Consequências.** Os arquivos originais **nunca** são alterados; correções/normalizações acontecem em memória e são documentadas.

## D4 — Cálculos de negócio **em Python, não no LLM**

**Decisão.** Preço promocional, preço PIX, simulação de parcelas, frete metropolitano, "aberto agora?" — tudo calculado em `domain/` e retornado já pronto nas tools. O LLM só redige.

**Justificativa.** Política 7.1 ("informações incorretas podem configurar propaganda enganosa"); LLMs erram aritmética e datas. Torna o comportamento testável com pytest.

**Regras implementadas:** somente as **confirmadas** em DATA_ANALYSIS §4.1. Contradições e lacunas (§4.2) não viram regra: viram `Limitation` (D15). Valores com `Decimal`; arredondamento de exibição `ROUND_HALF_UP` em 2 casas.

## D15 — Limitações explícitas em vez de interpretações (revisado em 2026-11-01)

**Contexto.** O manual tem contradições (telefones, e-mails, parcelamento) e lacunas (valores-limite, região metropolitana, canal de compra, data de recebimento); os dados têm produtos com informações conflitantes.

**Decisão.**
1. Domínio e tools devolvem, ao lado dos valores, uma lista de `Limitation {code, message, source}` (ARCHITECTURE §5.3/§5.5).
2. Só regras sem contradição produzem valores afirmativos. O que depende de uma leitura não confirmada é marcado como **"a confirmar"** (ex.: parcelas) ou omitido com limitação (ex.: frete de R$ 500,00).
3. Conflitos de produto são detectados no carregamento e expostos à parte; os campos em conflito não são apresentados como fato.
4. Nenhuma tool emite veredito de elegibilidade de troca/devolução sem dados suficientes; o agente expõe regra + fatos + limitação e indica a confirmação com a equipe (manual, seção 10: "em caso de dúvidas... consultar a gerência").
5. O prompt (T10) obriga o agente a repassar as limitações recebidas, sem completá-las com suposições.

**Alternativa descartada.** Escolher uma interpretação "razoável" e documentá-la (abordagem da versão inicial deste plano) — rejeitada na aprovação: pode gerar informação incorreta ao cliente.

**Status.** Tratamentos de DATA_ANALYSIS §4.2 **aprovados em 2026-11-01**, com dois ajustes: limite máximo de 12x sempre respeitado; pagamento combinado somente acima de R$ 2.000,00 (exatamente R$ 2.000,00 ⇒ limitação explícita).

## D17 — Provedor Groq como padrão (decisão do usuário, 2026-11-01)

**Contexto.** O usuário decidiu usar a Groq como provedora de LLM (`GROQ_API_KEY`). A abstração `LLMClient` (D5, §5.6.1) foi feita para essa troca.

**Decisão.**
- Novo adaptador `llm/groq_client.py` (SDK oficial `groq`), selecionado por `LLM_PROVIDER=groq` (novo padrão). O adaptador Anthropic permanece (troca por configuração).
- Modelo padrão **`openai/gpt-oss-120b`**: modelo de produção da Groq com suporte a tool use (documentação de *tool use* e *models* da Groq consultada em 2026-11-01); aceita `reasoning_effort` (`low|medium|high`), mapeado de `LLM_EFFORT`. Alternativa por configuração: `llama-3.3-70b-versatile` (produção, chamadas paralelas). Modelos em *preview* descartados para a entrega.
- `max_completion_tokens` padrão 4096: o limite de vazão por minuto da Groq (base do plano Developer: 8K tokens/min para o gpt-oss-120b) torna inviável reservar 16000.
- Raciocínio do gpt-oss não é devolvido nem reenviado (`include_reasoning=false`): a Groq não documenta o reenvio, e o histórico fica só com texto e chamadas de ferramenta.
- `tool_use_failed` (chamada malformada gerada pelo modelo) é repetido uma vez antes de virar erro; 429 com `retry-after` tratado pelo SDK (`max_retries=5`); `run_scenarios.py --pause` espaça os cenários.

**Consequência.** Nenhuma mudança em agente, ferramentas, domínio ou dados. Contrato em ARCHITECTURE §5.6.2. D16 passa a valer só para o adaptador Anthropic.

**Revisão (02/11/2026, decisão do usuário): `LLM_EFFORT` padrão = `medium`.** Evidência real (docs/E2E_RESULTS.md §4): com `low`, o `gpt-oss-120b` deu veredito de prazo de devolução e ofereceu procedimento fora do manual mesmo com o prompt reforçado; com `medium`, não deu veredito e usou `encaminhar_atendente` com o protocolo real. `low` continua configurável. Custo: mais tokens de raciocínio por chamada (pesa no limite diário da Groq). Os resultados da T14 em `low` ficam como histórico; uma regressão única em `medium` valida o novo padrão.

## D18 — API HTTP fina sobre o agente (decisão do usuário, 2026-11-03)

**Contexto.** O usuário decidiu oferecer o atendimento também por um chat web (D19). O agente só era acessível pela CLI (D6). Era preciso expor `Agent.respond` por HTTP sem tocar no núcleo já testado nem nos resultados reais (T14/T15).

**Decisão.**
- **Camada fina** em `src/emporio_agent/api/` (FastAPI + uvicorn): o app monta o agente uma vez com `cli.build_agent`, gera a saudação com `cli.greeting` e, a cada `POST /api/chat`, chama `Agent.respond` sobre uma `agent.session.Session`. Nenhuma regra, ferramenta, dado ou prompt foi alterado. Contrato em ARCHITECTURE §5.10.
- **Sessões só em memória, sem banco** (`api/sessions.py`, `SessionStore`): um lock por sessão (mensagem concorrente na mesma sessão ⇒ 409 `session_busy`, sem esperar e sem corromper o histórico) e limite `MAX_SESSIONS` (padrão 200) com descarte da sessão ociosa usada há mais tempo. `session_id` é um token aleatório de 128 bits gerado na API (`secrets.token_urlsafe(16)`), única credencial da conversa. Coerente com D7 (sem persistência de dados pessoais).
- **Modo degradado em vez de falha na subida:** sem chave, ou com falha ao carregar dados/políticas, o servidor sobe com `agent=None`; `GET /api/health` responde `degraded` com o motivo em português e as rotas de conversa respondem 503 `agent_unavailable`. A CLI mantém o código de saída 2.
- **Envelope único de erro** `{error, message}` para todos os status (422, 404, 409, 413, 503, 500 e rotas inexistentes), mensagens em pt-BR para o usuário final, sem stack trace no corpo. Corpo acima de 16 KiB ⇒ 413 `payload_too_large` antes de ler o JSON; `session_id` limitado a 64 caracteres.
- **Sem argumentos de ferramentas na resposta:** `tool_calls` traz só `name`, `ok`, `duration_ms` (argumentos de `consultar_pedido`/`encaminhar_atendente` contêm e-mail, telefone e texto livre). O log da rota de chat registra só id da sessão, `stop` e nomes das ferramentas.
- **Falha do provedor durante a conversa não é erro HTTP:** 200 com `stop="llm_error"` e o texto de contingência do agente, como na CLI.
- **CORS restrito** às origens do Vite local por padrão (`CORS_ORIGINS`), métodos GET/POST/DELETE/OPTIONS, header `Content-Type`, sem credenciais.

**Alternativas descartadas.** Reescrever o loop dentro da API (duplicaria lógica testada); persistir sessões em banco/Redis (dados pessoais, escopo de protótipo); expor os argumentos das ferramentas para depuração (vazamento de PII); streaming de tokens (o agente devolve a resposta final após o loop de ferramentas).

**Consequências.** Reiniciar o servidor apaga todas as sessões (o frontend trata o 404, D19). Funciona em um único processo (vários workers dividiriam as sessões). Sem autenticação nem limite de taxa: a API é para uso local (`python -m emporio_agent.api` escuta em 127.0.0.1). Testada só com `FakeLLM` (`tests/test_api.py`); nenhuma execução pela API com o provedor real.

## D19 — Frontend web reintroduzido e conectado à API (decisão do usuário, 2026-11-03)

**Contexto.** O chat React/Vite existia localmente, fora do escopo, e foi retirado do histórico antes da publicação (commit `1463ba2` e reescrita de 02/11). O usuário decidiu trazê-lo de volta neste branch (commit `773ed61`), revertendo essa exclusão, e ligá-lo ao agente pela API (D18). Revisa D6 ("somente CLI"): a CLI continua sendo a interface de referência das execuções reais.

**Decisão.**
- `frontend/` (React 19 + Vite 8, oxlint), sem biblioteca de UI, roteador ou gerenciador de estado: o estado fica em `hooks/useConversations.js`.
- **Isolamento do HTTP:** componentes não chamam `fetch`; `services/http.js` é o único cliente (timeout de 90 s, `ApiError` com `status` e `code` do envelope) e `services/chatService.js` é o único lugar que conhece as rotas `/api`.
- **Dois modos, decididos por `VITE_API_BASE_URL`:** com valor, modo API (saudação real de `POST /api/sessions`, `session_id` guardado por conversa); vazia, o modo demonstrativo original com respostas fictícias de `src/data/`, **sinalizado na UI** ("Modo demonstração" no cabeçalho e aviso no rodapé) para nunca ser confundido com o agente. Chaves de `localStorage` separadas por modo.
- **Sessão perdida (404 `session_not_found`):** descarta o id, avisa na conversa que o contexto anterior se perdeu e reenvia a mensagem **uma vez** em sessão nova.
- **Estado por conversa:** envio, erro e última mensagem ficam por conversa (uma conversa não bloqueia nem mostra o erro de outra); `409 session_busy` ⇒ até 3 novas tentativas automáticas com espera; status do cabeçalho por `GET /api/health` (`hooks/useBackendHealth.js`); composer limitado a 2000 caracteres.
- **Resposta só texto:** a API não devolve produtos estruturados, então no modo API não há cartões de produto; o texto é exibido sem interpretar HTML nem Markdown (só quebras de linha).

**Consequências.** Markdown aparece literal no chat; cartões e detalhe de produto existem só no modo demonstrativo (dados fictícios); o histórico das conversas fica no `localStorage` do navegador. Verificação: `npm run lint` e `npm run build`; não há testes automatizados do frontend e a integração frontend → API → Groq **não** foi testada com o provedor real.

## D16 — Parâmetros de chamada ao modelo (2026-11-01, antes da T08)

**Contexto.** Regras atuais da API para o Claude Sonnet 5.5 (`claude-sonnet-5-5`, modelo aprovado em D5), conferidas na documentação da API antes de escrever o adaptador.

**Decisão.**
- Sem `temperature`/`top_p`/`top_k` (o modelo rejeita valores não padrão com 400). A variabilidade é tratada nos critérios de aceite (fatos, não texto exato — RK13).
- Sem `tool_choice` forçado (400); `auto` + instruções no prompt.
- Raciocínio adaptativo padrão (sem parâmetro `thinking`); profundidade por `output_config.effort`, padrão **`low`** (recomendação para chat), configurável em `LLM_EFFORT`.
- `max_tokens` padrão 16000 (com raciocínio adaptativo, 1024 truncaria respostas), configurável.
- Blocos brutos do provedor (raciocínio, fallback) reenviados sem alteração no histórico (`Message.provider_content`).
- Fallback de recusa no servidor ligado por padrão (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`), desligável em `LLM_REFUSAL_FALLBACK=false`. A validação real acontece na T14 (exige credencial).
- Cache de prompt só no prefixo estável do sistema; data/hora vão num bloco separado após o ponto de cache.

**Consequência.** Contrato em ARCHITECTURE §5.6.1.

## D5 — Modelo e provedor (aprovado; provedor substituído por D17)

**Recomendação.** **Anthropic Claude via API**, modelo `claude-sonnet-5-5` como padrão (bom equilíbrio custo/qualidade em tool use e português), `claude-haiku-5-5` como opção econômica para testes. SDK oficial `anthropic`.

**Mitigação de lock-in.** Interface `LLMClient` fina (ver ARCHITECTURE §5.6) — trocar para OpenAI, Gemini ou Ollama (local, gratuito) exige só um novo adaptador. Configuração via `.env` (`LLM_PROVIDER`, `LLM_MODEL`, `ANTHROPIC_API_KEY`).

**Aprovado (2026-11-01):** Claude Sonnet via API com camada independente de provedor. **Substituído por D17:** o usuário passou a usar a Groq como provedor padrão; o adaptador Anthropic permanece como alternativa por configuração.

## D6 — Interface: **CLI** (aprovado; sem UI — revisado por D18/D19 em 2026-11-03)

**Decisão.** CLI interativa (`python -m emporio_agent`) com `rich` para formatação, flag `--debug` que exibe as tool calls. Foco do desafio é o agente funcionando.

**Aprovado:** somente CLI. Streamlit não será implementado.

**Revisão (2026-11-03, decisão do usuário):** além da CLI, API HTTP fina (D18) e chat web React/Vite (D19). A CLI segue como interface de referência das execuções com o modelo real.

## D7 — Histórico de conversa: **em memória por sessão + exportação de transcript**

**Decisão.** `Session` mantém a lista de mensagens (inclusive tool calls) durante a conversa — necessário para follow-ups ("e em 10x?", "e o outro modelo?"). Ao sair, opcionalmente salva o transcript em Markdown em `runtime/transcripts/` — **mesmo mecanismo gera os exemplos do entregável E3** (conversas reais, não escritas à mão).

**Não fazer:** persistência entre sessões (banco). Justificativa: protótipo de atendimento; sessão = conversa; evita guardar dados pessoais (LGPD).

**Controle de tamanho:** truncar histórico após N turnos (configurável) para limitar tokens.

## D8 — Verificação de identidade em consulta de pedidos (LGPD)

**Decisão.** `consultar_pedido` exige `order_id` **e** um dado de verificação (e-mail **ou** telefone) que bata com o cliente do pedido. Sem verificação, a tool retorna erro `VERIFICATION_FAILED` e o agente pede o dado. Retorno nunca inclui e-mail/telefone/endereço completos — só primeiro nome, status, itens, rastreio, datas.

**Justificativa.** Política 9 (LGPD); e-mail duplicado e nomes parecidos nos dados (DATA_ANALYSIS §2.4) tornam identificação por nome inviável. Sem essa barreira, qualquer pessoa consultaria o pedido de outra.

**Normalização:** telefone comparado só por dígitos; e-mail em minúsculas e sem espaços.

**Diretriz aprovada:** nunca identificar cliente por nome ou e-mail isoladamente. A identificação é sempre `order_id` + dado de contato, conferido contra o cliente daquele pedido; o e-mail compartilhado entre os clientes #11 e #43 não permite acessar pedidos do outro.

## D9 — Data de referência ("hoje") (aprovado)

**Contexto.** Pedidos vão até 2026-03-22; hoje é 2026-10-31. Com a data real, todo pedido "shipped" está 8 meses atrasado e nenhum está no prazo de arrependimento.

**Decisão proposta.** `REFERENCE_DATE` configurável no `.env` (padrão: data/hora atual em `Amer**Aprovado:** data real do sistema em produção; `REFERENCE_DATE` apenas em testes e exemplos (documentado no cabeçalho de cada exemplo). Com a revisão D15, a data controlada não serve para "provar" elegibilidade de devolução — o agente não emite esse veredito sem a data real de recebimento.adrão** e usar `REFERENCE_DATE=2026-03-25` apenas para gravar um dos exemplos, documentando isso no README.

## D10 — Escopo e guardrails

- **Prompt de sistema** define: persona, escopo (só instrumentos musicais da loja), regra de grounding ("preço/estoque/prazo só via ferramenta; se a ferramenta não retornar, diga que não sabe"), recusa gentil para temas alheios, redirecionamento de acessórios (política 7.1), formato de preço (original + promo + %).
- **Sem classificador de intenção separado**: o próprio LLM decide; evita uma chamada extra e uma camada a mais. Testes de cenário (T14) medem se está funcionando.
- **Resistência a prompt injection básica**: instrução no prompt para ignorar pedidos de mudar de papel / revelar dados de outros clientes; a defesa real está na tool (D8), não no prompt.
- **Limite de iterações** no loop de tools (ex.: 6) para evitar ciclos.

## D11 — Tom e idioma

Português do Brasil, informal mas profissional, frases curtas (canal tipo WhatsApp), sem emojis (aprovado), saudação pelo nome quando conhecido (após verificação do pedido), fechamento perguntando se precisa de algo mais (fluxo 7.2).

## D12 — Qualidade: testes em duas camadas

1. **Unitários (pytest, sem LLM, rápidos, determinísticos):** loader, repositório, pricing, horários, policy store, handlers das tools.
2. **Cenários end-to-end (script, com LLM real):** ~10 perguntas com asserções de *roteamento* (qual tool foi chamada) e de conteúdo-chave (ex.: preço "2.199"). Não roda em CI por custo; roda manualmente.

## D13 — Stack e dependências

| Pacote | Uso |
|---|---|
| `anthropic` | Cliente LLM (D5) |
| `pandas` | Dados (D3) |
| `pypdf` | Extração do PDF (só no script offline) |
| `pydantic` | Contratos/modelos de dados e validação de argumentos das tools |
| `python-dotenv` | Configuração |
| `rich` | CLI |
| `rapidfuzz` | Busca aproximada por nome de produto ("takamine gd 20") |
| `pytest` | Testes (dev) |
| `fastapi`, `uvicorn` | API HTTP (D18, 2026-11-03) |
| `httpx` | só para o `TestClient` do FastAPI nos testes da API (dev) |

Python 3.13 (já há `venv/` com 3.13.15). `requirements.txt` com versões fixadas.

## D14 — Fluxo de Git

- Branch `main`, commits pequenos por tarefa (`TASKS.md` lista a mensagem sugerida), sem squash nem force-push (exigência do desafio).
- `.gitignore`: `venv/`, `.env`, `runtime/`, `__pycache__/`, `.pytest_cache/`.
- `data/` versionado (o avaliador precisa dos arquivos para rodar).
- Este planejamento (`*.md`) entra no primeiro commit — demonstra o workflow com assistente de IA (pedido pelo README).

---

## Decisões aprovadas (2026-11-01)

| # | Decisão | Aprovado |
|---|---|---|
| D5 | Provedor/modelo | Claude Sonnet via API; camada independente de provedor; provedor e modelo configuráveis |
| D3 | Dados | pandas |
| D9 | Data de referência | Data real do sistema em produção; data controlada injetável em testes e exemplos |
| D10 | Persona | Mel |
| D11 | Emojis | **Sem emojis** por padrão |
| D6 | Interface | **Somente CLI**; Streamlit não será implementado (revisado em 2026-11-03: D18/D19) |
| D18/D19 | API HTTP e frontend web (2026-11-03) | API FastAPI fina com sessões em memória; chat React/Vite reintroduzido e ligado à API, modo demonstrativo sinalizado |

## Diretrizes obrigatórias (definidas na aprovação)

1. **Não resolver contradições do manual inventando regras.** Sem informação confiável, o agente informa a limitação. As "interpretações propostas" de `DATA_ANALYSIS.md` §4.2 precisam ser revistas sob esta regra antes das tarefas que as usam (T04, T05, T09).
2. **Nunca identificar cliente por e-mail ou nome isoladamente** (há duplicidades nos dados).
3. **Não apresentar informações conflitantes de produtos como fatos confirmados.**
4. **Não alterar os CSVs nem o PDF originais.**
5. **Manter provedor e modelo de IA trocáveis por configuração.**
