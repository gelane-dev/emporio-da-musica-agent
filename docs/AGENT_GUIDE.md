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
