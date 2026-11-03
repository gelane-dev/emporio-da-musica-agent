# Guia para agentes (Sonnet)

> Leia **só** as seções indicadas para o seu papel. Não releia documentos inteiros nem refaça análises já registradas.

## O que ler por papel

| Papel | Leitura obrigatória | Leitura sob demanda |
|---|---|---|
| Backend | Contrato da tarefa em [[ARCHITECTURE]] §5 (a subseção citada no seu pedido); critérios da tarefa em [[TASKS]] | [[DATA_ANALYSIS]] §4.1/§4.2 só para a regra que estiver implementando |
| IA/RAG | [[ARCHITECTURE]] §3, §4, §5.5–§5.7; critérios da tarefa em [[TASKS]] | [[TECHNICAL_DECISIONS]] D1, D2, D10, D15 |
| QA/Docs | Contrato e critérios da tarefa ([[ARCHITECTURE]] §5.x e [[TASKS]]) | `tests/conftest.py` (fixtures existentes) |

Estado e pendências: [[docs/PROGRESS]]. Não duplique conteúdo: cite a seção.

## Regras invariáveis

1. **Nunca** altere `data/` (arquivos originais do desafio).
2. Não invente regras de negócio. Contradição ou lacuna do manual ⇒ `Limitation` (ver [[TECHNICAL_DECISIONS]] D15).
3. Não altere código de tarefas concluídas nem decisões aprovadas. Se o contrato parecer errado, **pergunte ao coordenador** (comando `ask` do preâmbulo) em vez de improvisar.
4. Edite somente os arquivos listados como seus no pedido.
5. `domain/` não importa `emporio_agent.data` nem `emporio_agent.config`.
6. Código em inglês; textos para cliente e mensagens de limitação em português.

## Ambiente

- Worktrees não têm `venv/`. Use o Python do repositório principal, a partir da raiz do seu worktree:
  `C:/Users/Dell/Desktop/emporio-da-musica-agent/venv/Scripts/python.exe -m pytest -q`
  (o `pyproject.toml` coloca o `src/` do seu worktree à frente do pacote instalado).
- Rode a suíte completa antes de concluir (inclusive em correções pontuais); testes existentes não podem quebrar.
- Antes do `worker_done`, rode `orca orchestration check` para ler mensagens do coordenador (mudanças de contrato podem chegar durante a execução).

## Entrega

- Commit(s) pequenos no seu branch, mensagem no padrão `tipo(escopo): descrição` em português, terminando com:
  `Co-Authored-By: Claude Sonnet <noreply@anthropic.com>`
- Relatório final objetivo (no `worker_done`): arquivos alterados, testes executados com resultado, desvios do contrato (se houver) e pendências.

## Padrões do projeto (vale para agentes e pessoas)

**Arquitetura.** Backend em camadas: `domain/` (regras puras), `data/` e `policies/` (fontes), `tools/` (únicos pontos de consulta do modelo), `agent/` (loop e prompt), `llm/` (adaptadores atrás de `LLMClient`), `api/` (camada fina: usa `cli.build_agent` e `Agent.respond`, sem lógica própria de atendimento). No frontend, componentes não chamam `fetch` nem conhecem caminhos `/api` (só `services/`); o estado das conversas fica em `hooks/`; `data/` guarda só conteúdo estático (modo demonstrativo, sugestões, categorias).

**Testes.** Nenhum teste automático chama provedor de IA ou rede.
- Backend: `python -m pytest -q` com `FakeLLM` (`tests/fakes.py`); o marcador `llm` (provedor real) fica fora por padrão.
- Frontend: `cd frontend && npm test` (Vitest + Testing Library em `frontend/tests/`, espelhando `src/`); `fetch` sempre mockado com `tests/helpers.js`; consultas por papel, rótulo ou texto visível, não por detalhes de implementação.
- Antes de cada commit: a suíte do backend; se tocou o frontend, também `npm test`, `npm run lint` e `npm run build`; se tocou Docker, `docker compose config --quiet`. O CI (`.github/workflows/ci.yml`) repete tudo isso e constrói as imagens.
- Execuções reais (Groq ou Anthropic) só com autorização do usuário, no mínimo necessário, e registradas em [[docs/E2E_RESULTS]] ou `docs/e2e/`. Nunca apresentar teste não executado como aprovado.

**Git.** Um commit por mudança lógica, `tipo(escopo): descrição` em português (`feat`, `fix`, `test`, `docs`, `chore`, `ci`). `git add` com caminhos explícitos (nunca `git add -A`). Push só com autorização do usuário; sem force push nem reescrita de histórico.

**Segurança.** Nunca versionar `.env`, chaves, `venv/`, `node_modules/`, `dist/` ou `runtime/`; `.env.example` sem segredos. Variáveis `VITE_*` vão para o bundle do navegador: nunca coloque segredo nelas. A API não devolve argumentos de ferramentas nem dados pessoais; o `.dockerignore` da raiz é uma lista de inclusão.

**Documentação.** `README.md` (inglês) descreve o projeto para quem avalia; documentos internos em português. Toda mudança de comportamento, comando ou variável atualiza o README e, se for decisão, [[TECHNICAL_DECISIONS]]; progresso em [[docs/PROGRESS]].
