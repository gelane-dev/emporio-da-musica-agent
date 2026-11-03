# Empório da Música — frontend de atendimento

Interface do chatbot da Mel. Não é uma loja virtual: produtos aparecem só dentro da conversa.

## Como rodar

Pré-requisito: Node.js 20+.

```bash
cd frontend
cp .env.example .env      # define VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev               # http://localhost:5173
```

Com o modo API, suba antes o backend na raiz do repositório:

```bash
venv/Scripts/python.exe -m uvicorn emporio_agent.api.app:app --reload --port 8000
```

O backend precisa de `GROQ_API_KEY` no `.env` da raiz. Sem a chave, `GET /api/health` responde
`degraded` e o chat mostra que o atendimento está indisponível. O CORS do backend libera
`http://localhost:5173` e `http://127.0.0.1:5173` por padrão (`CORS_ORIGINS`).

Outros scripts: `npm run lint` (oxlint), `npm run build` (gera `dist/`), `npm run preview`.

## Modos

| | Modo API | Modo demonstrativo |
|---|---|---|
| Ativado por | `VITE_API_BASE_URL` preenchida | variável vazia/ausente |
| Respostas | agente real (Mel) via FastAPI | fictícias, em `src/data/demoChat.js` |
| Conversa nova | saudação real de `POST /api/sessions` | saudação fixa de `src/data/demo.js` |
| Conversas iniciais | nenhuma (só as suas) | exemplos de `src/data/demo.js` |
| Cartões de produto | não (a resposta é texto) | sim (`ProductCard`) |
| Sinalização na UI | "Online" | "Modo demonstração" no cabeçalho e aviso no rodapé |
| `localStorage` | `emporio.conversations.api.v1` | `emporio.conversations.v1` |

A variável é lida no build/dev (`import.meta.env`): após alterá-la, reinicie o `npm run dev`.

## Integração com a API

Componentes não chamam `fetch` nem conhecem paths:

- `src/services/http.js` — cliente único. Timeout de 60 s (`AbortController`), erros como
  `ApiError` com `status` e `code` (campo `error` do envelope `{error, message}`).
- `src/services/chatService.js` — `createSession()` (`POST /api/sessions`),
  `sendChatMessage()` (`POST /api/chat` com `{session_id, message}`, normalizado para
  `{text, products: [], sessionId, stop, toolCalls}`) e `checkHealth()` (`GET /api/health`).
- `src/hooks/useConversations.js` — estado das conversas. Guarda o `sessionId` do backend em
  cada conversa (persistido no `localStorage`) e o envia na mensagem seguinte.

Tratamento de erros:

- `404 session_not_found` — as sessões vivem só na memória do servidor; após um reinício o id
  antigo some. O frontend descarta o id, mostra um aviso na conversa de que o contexto anterior
  se perdeu e reenvia a mensagem **uma vez** numa sessão nova.
- `409 session_busy` e `503 agent_unavailable` — mensagem clara no banner de erro, com
  "Tentar de novo".
- Timeout / rede / demais erros — banner com a mensagem do backend (pt-BR) ou uma genérica.

As respostas da Mel vêm em Markdown simples; o balão preserva quebras de linha
(`white-space: pre-wrap`) e mostra o texto sem interpretar HTML.

## Estrutura

`components/` (chat, layout, produtos), `pages/`, `hooks/` (estado), `services/` (HTTP),
`styles/`, `data/` (somente modo demonstrativo), `utils/`.
