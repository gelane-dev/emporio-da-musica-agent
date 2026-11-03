# Validação real ponta a ponta pelo chat web (Anthropic)

> Executada em: 03/11/2026, por volta de 11:25 (data e hora reais; sem `REFERENCE_DATE`)
> Caminho: navegador (Edge headless, dirigido pelo Chrome DevTools Protocol) → frontend real (`npm`/Vite, modo API) → `POST /api/sessions` e `POST /api/chat` (FastAPI) → `Agent.respond` → Anthropic API
> Provedor/modelo: `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-sonnet-5-5`, `LLM_MAX_TOKENS=4096`, `LLM_EFFORT=medium` (variáveis de ambiente do processo; o `.env` continua com o padrão Groq)
> Commit do código: `510ac27` (main, após a integração da API e do frontend)
> Textos copiados sem edição do DOM da página (bolhas `.msg__bubble`) e do log do servidor.

## Configuração

- Backend: `python -m emporio_agent.api` (127.0.0.1:8000). `CORS_ORIGINS=http://localhost:5174,http://127.0.0.1:5174`, porque a porta 5173 estava ocupada por outro servidor Vite local; nenhuma mudança de código.
- Frontend: `VITE_API_BASE_URL=http://localhost:8000 npx vite --port 5174`.
- O `localStorage` do navegador foi limpo antes de cada execução; o script só digita no composer e clica em Enviar, como um usuário.

## 1. Conversa real (3 chamadas ao modelo no total)

Status no cabeçalho: **Online** (`GET /api/health` ⇒ `ok`, `agent_ready: true`, `provider: anthropic`).

**Mel (saudação, `POST /api/sessions` ⇒ 201, sem chamada ao modelo):**
Olá! Eu sou a Mel, assistente virtual da Empório da Música. Como posso ajudar?

A loja está aberta agora (hoje, das 09:00 às 18:00).

**Cliente:** Quanto custa o ukulele Ohana CK-20?

> Ferramenta: `detalhar_produto` {"nome":"Ohana CK-20"} (ok) — `POST /api/chat` ⇒ 200, `stop=end_turn`

**Mel:** O Ohana CK-20 Concert Natural está em promoção agora:

- Preço original: R$ 549,00
- Preço promocional: R$ 439,20 (20% de desconto)
- Estoque: disponível

Parcelamento no cartão:
- 1x de R$ 439,20
- 2x de R$ 219,60
- 3x de R$ 146,40
- 4x de R$ 109,80
- 5x de R$ 87,84, que está a confirmar

O manual traz regras diferentes para a parcela mínima, então a equipe precisa confirmar o parcelamento em 5x. Como o produto está em promoção, o desconto do PIX não se aplica, porque os dois não acumulam.

Ele é um ukulele concert com tampo sólido em Spruce e fundo e braço em Mogno, com cordas de nylon.

Posso ajudar com mais alguma coisa, como o frete para a sua cidade?

**Cliente:** E em 4x, quanto fica cada parcela?

> Sem ferramenta (respondeu com o resultado já presente no histórico da sessão) — `POST /api/chat` ⇒ 200, `stop=end_turn`

**Mel:** Em 4x, cada parcela fica em R$ 109,80. Essa opção está confirmada. O total é o mesmo preço promocional de R$ 439,20.

Quer que eu veja o frete para a sua cidade?

**Log do servidor (uso de tokens por chamada):**

| Chamada | `input_tokens` | `cache_creation_input_tokens` | `cache_read_input_tokens` | `output_tokens` | `stop_reason` |
|---|---|---|---|---|---|
| 1 | 229 | 5679 | 0 | 59 | `tool_use` |
| 2 | 1031 | 0 | 5679 | 316 | `end_turn` |
| 3 | 1368 | 0 | 5679 | 77 | `end_turn` |

O log da rota registrou só id da sessão, `stop` e nomes das ferramentas, sem o texto do cliente.

**Conferência:** valores iguais aos da ferramenta (preço original, promocional e percentual; 5x "a confirmar" com a limitação P3; PIX sem acúmulo); o segundo turno usou o contexto da sessão (`session_id` mantido pelo frontend). Sem emojis.

## 2. Indisponibilidade (sem chamada ao modelo)

**Sem chave** (`ANTHROPIC_API_KEY` vazia no processo): `GET /api/health` ⇒ `degraded`, "Chave da API não configurada. [...] ANTHROPIC_API_KEY."; `POST /api/sessions` e `POST /api/chat` ⇒ 503 `agent_unavailable`. No chat, o banner de erro: "O atendimento está indisponível no momento (o agente não pôde ser iniciado). Tente novamente mais tarde." com "Tentar de novo".

**Provedor inalcançável** (`ANTHROPIC_BASE_URL=http://127.0.0.1:9`, com chave): o SDK repetiu duas vezes, `LLMError(connection)`, `POST /api/chat` ⇒ 200 com `stop=llm_error`, e o chat mostrou o texto de contingência: "Desculpe, estou com um problema técnico no momento e não consegui responder. Tente novamente em instantes ou fale com nossa equipe."

## Não coberto aqui

- Caminho web com o provedor padrão (Groq): não executado.
- Sessão perdida após reinício do servidor (404 ⇒ reenvio): coberto só pelos testes automatizados da API e pela lógica do frontend, não nesta execução.
