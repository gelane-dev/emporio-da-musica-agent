# Empório da Música — agente de atendimento

Protótipo em Python (desafio Artefact). Este arquivo é só um índice; o repositório é também o cofre do Obsidian.

## Onde está cada coisa

| Preciso de… | Documento |
|---|---|
| Estado das tarefas, commits, pendências | `docs/PROGRESS.md` |
| Regras para agentes (o que ler, ambiente, entrega) | `docs/AGENT_GUIDE.md` |
| Contratos entre módulos e estrutura | `ARCHITECTURE.md` (§5 = contratos) |
| Tarefas e critérios de aceite | `TASKS.md` |
| Decisões técnicas e diretrizes aprovadas | `TECHNICAL_DECISIONS.md` |
| API HTTP e frontend web (D18/D19) | `ARCHITECTURE.md` §5.10 e §8; `frontend/README.md` |
| Fatos sobre os dados e o manual, ambiguidades P1–P16 | `DATA_ANALYSIS.md` |
| Resultados reais da T14 e testes pendentes (cota Groq) | `docs/E2E_RESULTS.md` |

## Regras essenciais

- Nunca alterar `data/`. Não inventar regras: ambiguidade ⇒ `Limitation`.
- Testes: `venv/Scripts/python.exe -m pytest -q`; frontend: `cd frontend && npm test && npm run lint && npm run build` (tudo verde; o CI repete).
- Docker: `docker compose up --build` (site em http://localhost:8080). Padrões de código, testes, Git e segurança: `docs/AGENT_GUIDE.md`.
- Uma tarefa por vez; commit por tarefa, após validar os critérios em `TASKS.md`.
