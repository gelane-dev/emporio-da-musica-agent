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

Outros scripts: `npm test` (Vitest), `npm run test:watch`, `npm run lint` (oxlint), `npm run build` (gera `dist/`), `npm run preview`.

Com Docker, o site e o backend sobem juntos pela raiz (`docker compose up --build`, site em
`http://localhost:8080`): ver a seção *Running with Docker Compose* do `README.md` da raiz. A imagem
deste diretório (`Dockerfile`) faz o build com Node e serve o `dist/` com nginx sem root; o nginx
encaminha `/api/` ao backend (`nginx/default.conf.template`), com limite de requisições por IP.

## Modos

| | Modo API | Modo demonstrativo |
|---|---|---|
| Ativado por | `VITE_API_BASE_URL` preenchida | variável vazia/ausente |
| Respostas | agente real (Mel) via FastAPI | fictícias, em `src/data/demoChat.js` |
| Conversa nova | saudação real de `POST /api/sessions` | saudação fixa de `src/data/demo.js` |
| Conversas iniciais | nenhuma (só as suas) | exemplos de `src/data/demo.js` |
| Cartões de produto | não (a resposta é texto) | sim (`ProductCard`) |
| Sinalização na UI | status de `GET /api/health`: "Online", "Atendimento degradado" ou "Indisponível" | "Modo demonstração" no cabeçalho e aviso no rodapé |
| `localStorage` | `emporio.conversations.api.v1` | `emporio.conversations.v1` |

A variável é lida no build/dev (`import.meta.env`): após alterá-la, reinicie o `npm run dev`.

## Integração com a API

Componentes não chamam `fetch` nem conhecem paths:

- `src/services/http.js` — cliente único. Timeout de 90 s (`AbortController`), erros como
  `ApiError` com `status` e `code` (campo `error` do envelope `{error, message}`).
- `src/services/chatService.js` — `createSession()` (`POST /api/sessions`),
  `sendChatMessage()` (`POST /api/chat` com `{session_id, message}`, normalizado para
  `{text, products: [], sessionId, stop, toolCalls}`) e `checkHealth()` (`GET /api/health`).
- `src/hooks/useConversations.js` — estado das conversas. Guarda o `sessionId` do backend em
  cada conversa (persistido no `localStorage`) e o envia na mensagem seguinte. Envio, erro e
  última mensagem são **por conversa**: uma conversa não bloqueia nem mostra o erro de outra.
- `src/hooks/useBackendHealth.js` — consulta `GET /api/health` uma vez ao montar a página e
  alimenta o status do cabeçalho (verificando, online, degradado, indisponível).

Tratamento de erros:

- `404 session_not_found` — as sessões vivem só na memória do servidor; após um reinício o id
  antigo some. O frontend descarta o id, mostra um aviso na conversa de que o contexto anterior
  se perdeu e reenvia a mensagem **uma vez** numa sessão nova.
- `409 session_busy` — o servidor ainda processa uma mensagem anterior da sessão (por exemplo,
  após um timeout do cliente): até 3 novas tentativas automáticas (após 2; 3,5; 5 s) antes de
  mostrar o erro.
- `503 agent_unavailable` — mensagem clara no banner de erro, com "Tentar de novo".
- `503 busy` (servidor no limite de conversas simultâneas) — pode ser repetido, com "Tentar de novo". `429 session_full` (sessão com 100 mensagens) — aviso sem "Tentar de novo"; é preciso iniciar outra conversa.
- `422` (mensagem inválida) — banner sem "Tentar de novo" (reenviar daria o mesmo erro). O
  composer já limita a mensagem a 2000 caracteres, o mesmo limite da API, com contador perto do fim.
- Timeout (90 s) — aviso de que a resposta ainda pode estar sendo processada e de que "Tentar de
  novo" pode enviar a mesma pergunta outra vez (o servidor não cancela o processamento).
- Rede / demais erros — banner com a mensagem do backend (pt-BR) ou uma genérica.

As respostas da Mel vêm em Markdown simples; o balão preserva quebras de linha
(`white-space: pre-wrap`) e mostra o texto sem interpretar HTML nem Markdown (`**negrito**`
aparece com os asteriscos).

## Verificação e limitações

- Testes automatizados em `tests/` (Vitest + React Testing Library, jsdom): 97 testes de
  serviços, hooks, componentes, da `ChatPage` integrada e da Mel (animações, avatar 3D, modelo GLB). Nenhum teste acessa a rede: o modo API é
  ligado por arquivo (`vi.hoisted(() => vi.stubEnv('VITE_API_BASE_URL', ...))`, porque os módulos
  leem a variável na importação) e o `fetch` é trocado por uma tabela de rotas (`tests/helpers.js`)
  que falha em qualquer chamada não mapeada. `npm run lint` e `npm run build` sem erros; os três
  rodam no CI (`.github/workflows/ci.yml`). A API é testada no backend (`tests/test_api.py`).
- Integração real validada uma vez: navegador → frontend → API → agente → Anthropic
  `claude-sonnet-5-5` (03/11/2026, `docs/e2e/web_e2e_anthropic.md`) e de novo em 04/11/2026 (capturas em
  `docs/screenshots/`). Com a Groq o caminho web **não** foi executado num navegador.
- As conversas (inclusive o que o cliente digitou) ficam no `localStorage` do navegador, sem
  expiração; o rodapé informa "As conversas ficam salvas neste navegador.".
- No modo API a resposta é só texto: sem cartões de produto. Sessões do backend vivem só em
  memória e se perdem ao reiniciá-lo (tratado com o aviso e o reenvio descritos acima).
- Arquitetura completa e diagramas: `README.md` da raiz (seção *Architecture*) e
  `ARCHITECTURE.md` §8.

## Mel (mascote)

- **Avatar do cabeçalho:** modelo 3D real `src/assets/mel/mel_base_v04.glb` (Three.js, estático), em
  `MelAvatar3D.jsx` + `melScene.js`. O Three.js é importado sob demanda quando o avatar fica visível (chunk
  separado); sem WebGL, fora da tela ou em erro, aparece a Mel 2D. Um contexto WebGL por vez.
- **Cartão de boas-vindas:** Mel 2D em SVG (`MelMascot.jsx`) com cinco animações em CSS (dançando,
  ukulele, cantando, fones, surpresa). Cada conversa nova sorteia uma diferente da anterior
  (`melAnimations.js`), sem chamada à API; `prefers-reduced-motion` desliga as animações.
- **Avatares pequenos** (mensagens, digitando, barra lateral): Mel 2D (`MelAvatar.jsx`), com ids de
  gradiente únicos por instância.
- Respostas da Mel: só o negrito em Markdown é renderizado (`utils/richText.jsx`, elementos React, sem HTML bruto).

## Estrutura

`src/`: `components/` (chat, layout, produtos), `pages/`, `hooks/` (estado das conversas e do backend),
`services/` (HTTP; único lugar com caminhos `/api`), `assets/mel/` (Mel 2D e 3D), `styles/`, `data/` (conteúdo do modo demonstrativo,
sugestões e categorias), `utils/`. `tests/` espelha o `src/`. `nginx/` e `Dockerfile`: imagem de produção.
