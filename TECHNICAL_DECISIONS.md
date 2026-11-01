# TECHNICAL_DECISIONS.md — Decisões técnicas (para aprovação)

Formato de cada decisão: **contexto → decisão → alternativas descartadas → consequências**.
Itens marcados com ⚠️ **APROVAR** dependem de escolha sua antes do desenvolvimento.

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
| E4 | Ambiguidades: assumir interpretação razoável e **documentar no README** | Seção "Suposições" (alimentada por DATA_ANALYSIS §3/§4.2) |

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

**Alternativas.** SQLite (útil se houvesse escrita/concorrência; não há). Dicionários puros com `csv` (viável; pandas simplifica filtros e é familiar a avaliadores). ⚠️ Se preferir zero dependências pesadas, trocar pandas por `csv` + dataclasses é trivial — os contratos não mudam.

**Consequências.** Os arquivos originais **nunca** são alterados; correções/normalizações acontecem em memória e são documentadas.

## D4 — Cálculos de negócio **em Python, não no LLM**

**Decisão.** Preço promocional, preço PIX, simulação de parcelas, frete metropolitano, "aberto agora?", dias desde a entrega — tudo calculado em `domain/` e retornado já pronto nas tools. O LLM só redige.

**Justificativa.** Política 7.1 ("informações incorretas podem configurar propaganda enganosa"); LLMs erram aritmética e datas. Torna o comportamento testável com pytest.

**Regras adotadas** (ver DATA_ANALYSIS §4.1/§4.2): PIX 5% só sem promo; promo ativa de maior desconto se houver mais de uma; parcela mínima 50/80/100; combinação de pagamentos > R$ 2.000; frete grátis ≥ R$ 500 em Campo Grande. Valores com `Decimal`, arredondamento `ROUND_HALF_UP` em 2 casas.

## D5 — Modelo e provedor ⚠️ APROVAR

**Recomendação.** **Anthropic Claude via API**, modelo `claude-sonnet-5-5` como padrão (bom equilíbrio custo/qualidade em tool use e português), `claude-haiku-5-5` como opção econômica para testes. SDK oficial `anthropic`.

**Mitigação de lock-in.** Interface `LLMClient` fina (ver ARCHITECTURE §5.6) — trocar para OpenAI, Gemini ou Ollama (local, gratuito) exige só um novo adaptador. Configuração via `.env` (`LLM_PROVIDER`, `LLM_MODEL`, `ANTHROPIC_API_KEY`).

**Pergunta para você:** confirma Claude (API paga) ou prefere um provedor gratuito/local (ex.: Ollama com Qwen/Llama — tool use menos confiável em PT-BR) ou outro provedor que você já tenha chave?

## D6 — Interface: **CLI** (+ UI opcional) ⚠️ APROVAR

**Decisão.** CLI interativa (`python -m emporio_agent`) com `rich` para formatação, flag `--debug` que exibe as tool calls. Foco do desafio é o agente funcionando.

**Aprovado:** somente CLI. Streamlit não será implementado.

## D7 — Histórico de conversa: **em memória por sessão + exportação de transcript**

**Decisão.** `Session` mantém a lista de mensagens (inclusive tool calls) durante a conversa — necessário para follow-ups ("e em 10x?", "e o outro modelo?"). Ao sair, opcionalmente salva o transcript em Markdown em `runtime/transcripts/` — **mesmo mecanismo gera os exemplos do entregável E3** (conversas reais, não escritas à mão).

**Não fazer:** persistência entre sessões (banco). Justificativa: protótipo de atendimento; sessão = conversa; evita guardar dados pessoais (LGPD).

**Controle de tamanho:** truncar histórico após N turnos (configurável) para limitar tokens.

## D8 — Verificação de identidade em consulta de pedidos (LGPD)

**Decisão.** `consultar_pedido` exige `order_id` **e** um dado de verificação (e-mail **ou** telefone) que bata com o cliente do pedido. Sem verificação, a tool retorna erro `VERIFICATION_FAILED` e o agente pede o dado. Retorno nunca inclui e-mail/telefone/endereço completos — só primeiro nome, status, itens, rastreio, datas.

**Justificativa.** Política 9 (LGPD); e-mail duplicado e nomes parecidos nos dados (DATA_ANALYSIS §2.4) tornam identificação por nome inviável. Sem essa barreira, qualquer pessoa consultaria o pedido de outra.

**Normalização:** telefone comparado só por dígitos; e-mail em minúsculas e sem espaços.

## D9 — Data de referência ("hoje") ⚠️ APROVAR

**Contexto.** Pedidos vão até 2026-03-22; hoje é 2026-10-31. Com a data real, todo pedido "shipped" está 8 meses atrasado e nenhum está no prazo de arrependimento.

**Decisão proposta.** `REFERENCE_DATE` configurável no `.env` (padrão: data/hora atual em `America/Campo_Grande`). A data é injetada no prompt de sistema e usada pelas tools (prazos, "aberto agora?").

**Pergunta para você:** padrão = data real (mais honesto; exemplos mostram "fora do prazo") ou fixar uma data coerente com os dados (ex.: `2026-03-25`, permitindo demonstrar um caso **dentro** do prazo de 7 dias)? Recomendo **data real como padrão** e usar `REFERENCE_DATE=2026-03-25` apenas para gravar um dos exemplos, documentando isso no README.

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
| D6 | Interface | **Somente CLI**; Streamlit não será implementado |

## Diretrizes obrigatórias (definidas na aprovação)

1. **Não resolver contradições do manual inventando regras.** Sem informação confiável, o agente informa a limitação. As "interpretações propostas" de `DATA_ANALYSIS.md` §4.2 precisam ser revistas sob esta regra antes das tarefas que as usam (T04, T05, T09).
2. **Nunca identificar cliente por e-mail ou nome isoladamente** (há duplicidades nos dados).
3. **Não apresentar informações conflitantes de produtos como fatos confirmados.**
4. **Não alterar os CSVs nem o PDF originais.**
5. **Manter provedor e modelo de IA trocáveis por configuração.**
