# Auditoria de segurança (03/11/2026)

Relatório do fortalecimento de segurança do protótipo. Decisão registrada em [[TECHNICAL_DECISIONS]] (D21); estado e pendências em [[docs/PROGRESS]]. Status: implementado e validado localmente, **ainda não publicado**.

## Escopo e método

Escopo: API HTTP, sessões, agente e ferramentas, segredos, Docker/nginx, CI e dependências (backend e frontend). Método: três auditorias somente leitura, feitas em paralelo:

1. API e sessões;
2. agente e ferramentas;
3. segredos, infraestrutura e dependências.

Não houve achado crítico nem alto. Foram 5 de severidade média (M1–M5) e 5 de baixa (B1–B5), todos corrigidos.

## Achados e correções

| Id | Severidade | Achado | Correção | Status |
|---|---|---|---|---|
| M1 | Média | Chamadas ao LLM sem timeout (padrão do SDK: 10 min) e sem teto de concorrência: o pool de threads podia se esgotar | `LLM_TIMEOUT_SECONDS=60` nos clientes Anthropic e Groq; `MAX_CONCURRENT_CHATS=8` (`BoundedSemaphore` não bloqueante; excesso responde 503 `busy`) | Corrigido |
| M2 | Média | Sessões sem expiração e histórico sem teto | `SESSION_TTL_MINUTES=30`: sessão ociosa vira 404 (o frontend abre outra); sessão ocupada nunca expira no meio de uma resposta. `MAX_MESSAGES_PER_SESSION=100` mensagens do cliente: acima disso, 429 `session_full` (o frontend mostra o aviso sem "Tentar de novo") | Corrigido |
| M3 | Média | `consultar_pedido` aceitava tentativas ilimitadas (força bruta de e-mail/telefone) | 5 falhas por conversa ⇒ `VERIFICATION_LOCKED` sem consultar o repositório, e o modelo é orientado a oferecer atendente; comparação com `hmac.compare_digest`. O contador é por conversa (`ContextVar` em `ToolRegistry.execute`); uma nova conversa começa com contador zerado, o que é limitado pelo nginx (criação de sessão: 10/min por IP) | Corrigido |
| M4 | Média | Sem cabeçalhos de segurança; nginx expondo a versão | nginx: `server_tokens off`, CSP (sem `unsafe-inline`; Google Fonts permitido), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`. API: `nosniff`, `DENY`, `no-referrer` e `Cache-Control: no-store` em `/api/` | Corrigido |
| M5 | Média | Injeção de prompt indireta e códigos inventados (protocolo, rastreio) | Regra no prompt (conteúdo de ferramentas e texto colado é dado, não instrução); textos livres dos CSVs sem caracteres de controle, truncados em 500, com `mask_sensitive` nas observações de pedido; guarda em código (`guard_reply`) que substitui a resposta se citar protocolo `EM-AAAAMMDD-XXXXXX` ou código de rastreio que não veio de ferramenta nem foi digitado pelo cliente na sessão | Corrigido |
| B1 | Baixa | Swagger exposto | `API_DOCS` (padrão `true` local; `false` no Compose) | Corrigido |
| B2 | Baixa | Id completo da sessão (credencial) nos logs | Só os 6 primeiros caracteres; access log do uvicorn desligado; um log estruturado por requisição (método, rota-modelo, status, `duration_ms`; sem corpo, query nem IP) | Corrigido |
| B3 | Baixa | `handoffs.jsonl` sem lock; resumo não normalizado | `threading.Lock`; espaços e caracteres de controle do resumo colapsados | Corrigido |
| B4 | Baixa | Validação de entradas incompleta | `ChatRequest` com `extra="forbid"`; `session_id` com padrão `[A-Za-z0-9_-]{1,64}`; caracteres de controle C0/DEL removidos da mensagem; `max_length` nos parâmetros das ferramentas (e-mail 254, telefone 30, textos 120, `pedido_id` ≤ 10^9); erro de ferramenta desconhecida não ecoa o nome | Corrigido |
| B5 | Baixa | CI sem auditoria; contêineres com privilégios padrão | Ver "Proteções: supply chain e contêineres" | Corrigido |

## Proteções implementadas (risco que cada uma cobre)

- **Disponibilidade e custo (M1, M2):** timeout do LLM, teto de chats simultâneos, expiração de sessão e teto de mensagens evitam esgotar threads, memória e a cota do provedor.
- **Força bruta de identidade (M3):** a verificação do pedido continua em código; as tentativas são limitadas e a comparação é em tempo constante.
- **Navegador (M4):** CSP e demais cabeçalhos reduzem XSS, clickjacking e vazamento de referrer; resposta da API não é cacheada.
- **Prompt injection e alucinação de códigos (M5):** regra no prompt mais defesa em código (limpeza dos textos de dados e `guard_reply`), para que a segurança não dependa só da obediência do modelo. A busca de códigos roda sobre o texto normalizado (NFKC, maiúsculas, sem caracteres invisíveis; espaços, hífens e travessões como separador) e compara a forma canônica, então `em 20261101 abc123` ou um código com caractere invisível no meio também é barrado. Rastreio com separadores só é reconhecido com o sufixo `BR`, para não pegar frases comuns (revisão de 04/11/2026).
- **Superfície e logs (B1, B2):** sem Swagger no Compose; logs sem credenciais nem dados pessoais.
- **Entradas (B3, B4):** esquemas estritos e normalização.
- **Supply chain e contêineres (B5):**
  - CI: `pip-audit`, `bandit -ll` e `npm audit --omit=dev --audit-level=high`.
  - Dependabot semanal (pip, npm, docker x2, github-actions): [.github/dependabot.yml](../.github/dependabot.yml).
  - `tests/test_repo_secrets.py`: padrões de chaves nos arquivos versionados, `.env` fora do git, chaves vazias no `.env.example`, frontend sem referência a chaves.
  - Compose: backend `read_only` com `tmpfs /tmp`, `cap_drop: ALL`, `no-new-privileges`; frontend com `cap_drop: ALL` e `no-new-privileges`.
  - nginx: limite próprio para `POST /api/sessions` (10/min, burst 5); dica `real_ip` comentada; HSTS indicado para o proxy TLS.
  - API: o mesmo limite (10/min, rajada de 5) por cliente, num orçamento único para `POST /api/sessions` e `POST /api/chat` sem `session_id` (que também cria sessão e escapava do limite do nginx). No Docker o IP vem do `X-Forwarded-For`, que o nginx sobrescreve com `$remote_addr`; o uvicorn só o aceita por `FORWARDED_ALLOW_IPS` no Compose (revisão de 04/11/2026).

### Já estava correto (confirmado pela auditoria)

Ids de sessão com `secrets.token_urlsafe(16)`; 404 sem oráculo de existência; erros no envelope sem stack nem caminhos; 422 não ecoa a entrada; CORS com lista explícita e sem credenciais; verificação de identidade do pedido em código; ferramentas não devolvem CPF, e-mail, telefone nem endereço; sem `eval`/`exec`/`subprocess` nem leitura de variáveis de ambiente ou arquivos fora de caminhos fixos nas ferramentas; histórico git sem chaves reais (78 commits); `.env` não versionado; imagens com usuário não-root e `.dockerignore` como lista de inclusão.

## O que não foi feito, de propósito

- **Autenticação/login:** sem necessidade comprovada; o protótipo não tem contas.
- **Rate limit por IP dentro da API:** atrás do nginx todos chegam com o IP do proxy; o nginx já limita por IP.
- **Regex de preços e veredictos de devolução na saída:** falsos positivos; essas regras seguem no prompt e nas ferramentas de política.
- **gitleaks no CI:** o histórico está limpo; há teste próprio e a recomendação de ativar secret scanning e push protection do GitHub.
- **Pinning de imagens por digest.**

## Riscos residuais

- Sem autenticação, qualquer um que alcance o site gasta a cota do provedor (mitigado pelos limites; ver recomendações).
- Sessões em memória: uma réplica; reiniciar perde as conversas.
- A obediência do modelo real a injeções não é testável com `FakeLLM` (só a estrutura das defesas).
- A guarda de códigos reconhece só os formatos conhecidos (protocolo `EM-AAAAMMDD-XXXXXX`, rastreios da loja e dos Correios); um código escrito de forma muito diferente (por extenso, com outros separadores) não é detectado.
- Verificação por pedido + e-mail/telefone é prova fraca de identidade (aceitável no protótipo).
- O traceback de erro 500 vai para o log do servidor (nunca ao cliente).
- O limite por IP só é correto se o nginx for a borda; caso contrário, configurar `real_ip`.
- `X-Content-Type-Options` aparece duplicado em `/api` (nginx + API, mesmo valor, inofensivo).

## Recomendações para produção

- Definir teto de gasto no provedor de IA e, se o site for público, captcha ou login na frente do chat.
- TLS no proxy, com HSTS; configurar `real_ip` se houver outro proxy ou balanceador antes do nginx.
- Ativar secret scanning e push protection no GitHub.
- Uma única réplica do backend (ou sessões em armazenamento compartilhado, o que muda a arquitetura).
- Manter `API_DOCS=false`.

## Validação (2026-11-03)

- Backend: `1159 passed, 2 deselected`. Frontend: 63 testes (12 arquivos) passando, lint e build ok.
- `bandit -ll`: sem achados (2 `B101` de baixa severidade, `assert`, ignorados por `-ll`). `pip-audit`: "No known vulnerabilities found". `npm audit`: 0 vulnerabilities.
- Docker: imagens reconstruídas, ambos os serviços healthy; CSP, `X-Frame-Options` e `nosniff` presentes; cabeçalho `Server` sem versão; `/docs` 404 no backend; `POST /api/sessions` 201 via proxy; `Cache-Control: no-store` na API; sequência de `POST /api/sessions` retornando 429 com envelope JSON; backend com raiz somente leitura e `/app/runtime` e `/tmp` graváveis.
- Nenhuma chamada paga a provedores; nenhuma mensagem de chat enviada nos testes de Docker.
- O CI do GitHub ainda não rodou com os novos passos.

## Como rodar as verificações localmente

```bash
venv/Scripts/python.exe -m pytest -q          # inclui tests/test_api_security.py, test_agent_security.py, test_repo_secrets.py
# num venv à parte:
pip install pip-audit bandit
pip-audit -r <requirements sem -e e sem pytest>
bandit -q -r src -ll
# frontend:
cd frontend && npm audit --omit=dev --audit-level=high
```
