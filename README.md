# Empório da Música — agente de atendimento

> Rascunho do README (T16). As seções que dependem de execução com credencial da API estão marcadas como pendentes e serão preenchidas após as tarefas T14/T15.

## Visão geral

Protótipo em Python de um agente de atendimento por texto para a loja fictícia Empório da Música (desafio técnico Artefact). A assistente, chamada Mel, conversa em português com o cliente e responde sobre:

- catálogo de produtos (busca, detalhes, categorias, preço promocional, preço no PIX e parcelas);
- pedidos (consulta com verificação de identidade);
- políticas da loja (horários, pagamento, trocas e devoluções, frete, garantia, privacidade);
- informações gerais da loja e encaminhamento para atendente humano.

O agente usa **function calling (tool use)**: o modelo decide quando chamar ferramentas determinísticas que consultam os CSVs ou o manual de políticas. Toda regra numérica (preços, parcelas, frete, horário) é calculada em Python; o modelo apenas redige a resposta. Quando o manual ou os dados são contraditórios ou omissos, o agente informa a limitação em vez de inventar uma regra.

## Requisitos

- Python 3.13 (`requires-python = ">=3.13"`).
- Chave de API da Anthropic (`ANTHROPIC_API_KEY`) para conversar com o modelo real. Os testes automatizados não precisam de chave.

## Instalação

```bash
python -m venv venv
# Linux/macOS/Git Bash:        source venv/bin/activate   (Git Bash no Windows: source venv/Scripts/activate)
# PowerShell:                  venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env           # PowerShell: Copy-Item .env.example .env
```

Edite o `.env` e preencha `ANTHROPIC_API_KEY`. O arquivo `.env` não é versionado. As demais variáveis têm padrões adequados:

| Variável | Padrão | Função |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | provedor de IA (trocável por configuração) |
| `LLM_MODEL` | `claude-sonnet-5-5` | modelo |
| `LLM_MAX_TOKENS` | `16000` | limite de tokens da resposta |
| `LLM_EFFORT` | `low` | profundidade do raciocínio (`low` a `max`) |
| `LLM_REFUSAL_FALLBACK` | `true` | fallback de recusa no servidor |
| `REFERENCE_DATE` | vazio | data/hora controlada (ver abaixo) |
| `MAX_TOOL_ITERATIONS` | `6` | limite de iterações do loop de ferramentas |
| `MAX_HISTORY_TURNS` | `50` | janela do histórico |

## Como rodar

```bash
python -m emporio_agent            # conversa interativa
python -m emporio_agent --debug    # mostra as ferramentas chamadas em cada resposta
python -m emporio_agent --save     # grava a conversa ao encerrar
python -m emporio_agent --version
```

Comandos dentro da conversa:

| Comando | Efeito |
|---|---|
| `/salvar` | grava a conversa em `runtime/transcripts/conversa-<data>-<id>.md` |
| `/nova` | inicia uma nova conversa |
| `/ajuda` | lista os comandos |
| `/sair` | encerra |

Por padrão o agente usa a data e hora reais do sistema (fuso `America/Campo_Grande`). Para reproduzir uma situação com data fixa (testes e exemplos), defina `REFERENCE_DATE` no `.env` em ISO 8601, por exemplo `2026-03-25` ou `2026-03-25T10:30`. Os pedidos do dataset vão até 2026-03-22; com a data real, qualquer pedido já aparece como antigo.

Sem chave de API, a CLI encerra com mensagem clara em português e código de saída 2.

## Testes

```bash
python -m pytest -q          # suíte completa, sem chamar o modelo real
python -m pytest -q -m llm   # smoke test com o provedor real (exige ANTHROPIC_API_KEY)
```

Os testes de unidade e de integração usam um LLM falso (`FakeLLM`); os testes marcados com `llm` são ignorados por padrão (`addopts = "-m 'not llm'"`). Estado atual: 905 testes passando e 1 smoke real ignorado.

## Utilitários

```bash
python scripts/build_policies.py          # regenera knowledge/policies.md a partir do PDF
python scripts/build_policies.py --check  # verifica se o .md versionado está em dia com o PDF
python scripts/run_scenarios.py           # cenários end-to-end com o modelo real (T14)
```

`scripts/run_scenarios.py` é entregue pela T14 (contrato em [ARCHITECTURE.md](ARCHITECTURE.md), §5.9.1), exige credencial da API e aceita `--only`, `--repeat`, `--reference-date` e `--report`.

## Arquitetura resumida

```
Cliente → CLI (cli.py) → Agent (loop de tool use + Session)
                           ├─ llm/     adaptador do provedor (Anthropic por padrão)
                           └─ tools/   8 ferramentas tipadas
                                ├─ data/     CSVs carregados em memória (pandas), somente leitura
                                ├─ domain/   regras puras: preços, PIX, parcelas, horários, frete
                                └─ policies/ seções de knowledge/policies.md (gerado do PDF)
```

Princípios: `data/` original nunca é alterado; o LLM redige e o Python calcula; dependências em um só sentido (`cli → agent → tools → data | domain | policies`); tudo testável sem LLM, exceto o próprio loop (testado com LLM falso); sem framework de agentes, banco ou vector store. Detalhes, estrutura de pastas e contratos entre módulos: [ARCHITECTURE.md](ARCHITECTURE.md).

## Decisões técnicas

Justificativas completas em [TECHNICAL_DECISIONS.md](TECHNICAL_DECISIONS.md).

- **Abordagem do agente (D1).** Function calling com loop próprio de cerca de 100 linhas, com limite de iterações. Descartados: agente de SQL (abre margem para consultas erradas e expõe a tabela de clientes), RAG puro (preço e estoque exigem exatidão e filtros numéricos) e LangChain/LangGraph/LlamaIndex (abstração sem ganho neste tamanho). Cada decisão de consulta fica observável no log de ferramentas (`--debug`).
- **Cálculos em Python (D4).** Preço promocional, PIX, parcelas, frete e "aberto agora?" saem prontos das ferramentas, com `Decimal` e arredondamento `ROUND_HALF_UP`. O manual considera informação incorreta como propaganda enganosa, e modelos erram aritmética e datas.
- **Modelo e parâmetros (D5, D16).** `claude-sonnet-5-5` via API da Anthropic, atrás de uma interface `LLMClient` fina; provedor e modelo trocáveis por configuração. Sem `temperature`/`top_p`/`top_k` nem `tool_choice` forçado (o modelo rejeita), raciocínio adaptativo com esforço `low` por padrão, `max_tokens` 16000, blocos de raciocínio reenviados sem alteração no histórico, cache de prompt apenas no prefixo estável do sistema. Como não há `temperature`, os critérios de avaliação checam fatos e ferramentas chamadas, não texto exato.
- **Retrieval de políticas (D2).** O PDF é convertido offline para `knowledge/policies.md` (revisado e versionado), dividido por seção em tópicos fixos, e a ferramenta `consultar_politica(topico)` recebe um `enum` de tópicos e devolve o texto integral da seção. É determinístico e auditável. Embeddings foram descartados: com cerca de 10 seções, um enum bem descrito recupera melhor e sem risco de trazer o trecho errado.
- **Estratégia de prompt (D10).** O prompt de sistema define a persona (Mel, sem emojis), o escopo (só instrumentos da loja), a regra de grounding (preço, estoque e prazo só via ferramenta), a recusa gentil de temas alheios e a obrigação de repassar as limitações recebidas das ferramentas. Regras de conduta do manual vão no prompt; conteúdo de políticas vem por ferramenta. Não há classificador de intenção separado. A defesa contra prompt injection está na camada de ferramentas, não no prompt.
- **Tratamento de dados (D3, D8).** pandas em memória, sem banco; correções e normalizações só em memória. Consulta de pedido exige número do pedido e e-mail ou telefone que confiram com o cliente daquele pedido, e nunca devolve contatos ou endereço. Nunca se identifica cliente por nome ou e-mail isoladamente (há e-mail duplicado entre os clientes 11 e 43).
- **Histórico (D7).** Histórico em memória por sessão (necessário para follow-ups como "e em 10x?"), com janela de turnos configurável e exportação de transcript em Markdown. Sem persistência entre sessões, para evitar guardar dados pessoais (LGPD).
- **Interface (D6).** Somente CLI, com `rich` para formatação e `--debug` para observabilidade. O foco do desafio é o agente funcionando.
- **Data de referência (D9).** Data real do sistema em produção; `REFERENCE_DATE` apenas para testes e exemplos.

## Tratamento de dados e ambiguidades

Análise completa em [DATA_ANALYSIS.md](DATA_ANALYSIS.md).

**Princípio (D15): limitação explícita em vez de interpretação.** Ferramentas e domínio devolvem, junto dos valores, uma lista de `Limitation {code, message, source}`. Só regras sem contradição produzem valores afirmativos; o que depende de leitura não confirmada aparece como "a confirmar" ou é omitido com limitação. O prompt obriga o agente a repassar as limitações sem completá-las com suposições.

**Qualidade dos dados (Q1–Q12), resumo:**

- Q1–Q2: produtos cujo nome diverge da descrição (marca/modelo) ou cujas especificações divergem da descrição (cordas, teclas, tipo). O loader detecta e expõe o conflito sem escolher fonte de verdade; o agente não afirma os campos em conflito. Detecção automática por heurística mais uma lista revisada manualmente (produtos 135–137, 139, 140, 142–144).
- Q3 e Q7–Q8: totais e formas de pagamento históricos de pedidos divergem de regras atuais; o agente mostra apenas o valor total registrado e nunca recalcula pedidos antigos.
- Q4–Q6: produtos `coming_soon` ou descontinuados aparecem com estoque; descontinuado nunca é ofertado (manual, 7.3) e `coming_soon` devolve limitação de disponibilidade.
- Q9: pedidos "parados" em relação à data atual; a previsão é apresentada como estimativa, sem afirmar atraso.
- Q10: typo no nome do produto 84 ("Cedr"); a busca é normalizada com fuzzy e o nome exibido não é alterado.
- Q11–Q12: categorias vazias (sopro, cordas orquestrais) e catálogo de 65 itens contra "mais de 300" no manual; o agente responde só com base no sistema.

**Contradições e lacunas do manual (P1–P16), resumo:**

- Contatos (P1–P2): dois números de WhatsApp e duas grafias de e-mail; ambos são informados, com a seção de origem, sem afirmar qual é o correto.
- Pagamento (P3, P4, P12): mínimos de parcela contraditórios (R$ 100, R$ 80, R$ 50); parcelas dentro da faixa contraditória saem como "a confirmar". O limite de 12x vale sempre, e pagamento combinado só acima de R$ 2.000,00 (exatamente R$ 2.000,00 devolve limitação).
- Frete (P5, P8, P13): exatamente R$ 500,00 e municípios da região metropolitana não são definidos no manual; frete especial de "contrabaixos" e "pianos digitais" é repassado literalmente, sem classificar o produto.
- Arrependimento e trocas (P6, P7, P9, P14): o canal de compra e a data real de recebimento não estão registrados, então não há veredito de elegibilidade; o agente expõe regra, dados disponíveis e limitação.
- Promoções e status (P11, P15, P16): preço sempre pelo CSV (`is_active`); mais de uma promoção ativa gera limitação e nenhuma é escolhida; `coming_soon` não é definido no manual.
- P10: registro de reclamação e encaminhamento, implementado como protocolo local (T12).

## Limitações conhecidas

- **Dados inconsistentes de cadastro (Q1–Q12).** Os produtos com informações conflitantes são apresentados apenas pelo nome cadastrado, com aviso de divergência.
- **Conflitos de produto não detectados automaticamente além da lista revisada.** A heurística cobre marca, número de cordas e de teclas; os casos 136 e 143 estão em lista manual. Divergências sutis (por exemplo, nome genérico com modelo específico da mesma marca, como #138 e #141) não são marcadas.
- **Contradições do manual tratadas como limitação (P1–P16).** O agente não escolhe qual telefone, e-mail ou regra de parcela vale; informa a divergência e indica confirmação com a equipe.
- **Feriados não conhecidos.** O horário de funcionamento considera só a grade regular; o manual não lista feriados, então o agente não afirma abertura em feriado.
- **Frete por CEP indisponível.** O manual não traz tabela por CEP nem a lista de municípios da região metropolitana; fora de Campo Grande o agente apresenta as regras e a limitação.
- **Sem veredito de devolução.** Não há canal de compra nem data real de recebimento nos pedidos, então o agente não diz se a devolução ou troca é elegível.
- **Sem persistência entre sessões.** Cada conversa vive em memória; só o transcript opcional é gravado em disco.
- **Sem canal WhatsApp real.** Somente CLI; Streamlit e integrações de mensageria não foram implementados.
- **Cenários end-to-end heurísticos e pequenos.** São 13 cenários mais uma checagem de emojis, avaliados por presença de termos e ferramentas chamadas; o relatório precisa de revisão manual e há variabilidade do modelo entre execuções.
- **Credencial.** O smoke test real e os cenários dependem de chave de API, que não estava disponível durante o desenvolvimento das tarefas T07–T13 (feitas com LLM falso).

## O que faria com mais tempo

- Executar e calibrar os cenários end-to-end com o modelo real e ampliar a avaliação (mais cenários, mais repetições, avaliação por juiz).
- Resolver com a equipe as contradições P1–P16 e então transformar as limitações em regras.
- Adicionar embeddings e vector store caso o manual cresça.
- Persistência opcional de conversas com consentimento, canal WhatsApp real e feriados por calendário.
- Detecção de conflitos de produto mais abrangente, com revisão assistida.

## Uso de assistentes de IA

Ferramenta: **Claude Code**. O **Claude Opus 5.5** atuou como coordenador e arquiteto; agentes **Claude Sonnet** executaram as tarefas via **Orca**, em worktrees e branches separados, nos papéis de implementação (Backend), IA/RAG e QA.

Workflow:

- **Planejamento aprovado antes do código.** Análise dos dados e do manual (`DATA_ANALYSIS.md`), decisões técnicas (`TECHNICAL_DECISIONS.md`) e arquitetura (`ARCHITECTURE.md`) foram revisadas e aprovadas antes da T01. A aprovação gerou ajustes reais: troca de "interpretações razoáveis" por limitações explícitas (D15), proibição de identificar cliente por nome ou e-mail e persona sem emojis.
- **Memória técnica.** O repositório é também um cofre do Obsidian; `CLAUDE.md` indexa os documentos, e `docs/AGENT_GUIDE.md` diz a cada agente o que ler e quais regras são invariáveis (nunca alterar `data/`, não inventar regras, editar só os arquivos do seu pedido).
- **Contrato por tarefa.** Cada tarefa tem critérios de aceite em `TASKS.md` e, desde a T05, um contrato detalhado (assinaturas, tabela de casos e literais) em `ARCHITECTURE.md` §5. Isso permitiu que implementação e testes fossem escritos em paralelo e de forma independente: na T05, as duas versões concordaram na primeira execução.
- **Revisão e integração pelo coordenador.** Um commit por tarefa, após validar os critérios; suíte verde antes de integrar; hashes SHA-256 de `data/` conferidos após cada tarefa e inalterados. O registro está em `docs/PROGRESS.md`.

Exemplos de problemas pegos pelo processo (de `docs/PROGRESS.md`):

- T07+T08: o QA independente detectou que a mensagem de `bad_request` poderia vazar texto da API, incluindo a chave; foi corrigido pelo agente de IA/RAG.
- T06: a revisão do coordenador achou quatro desvios de estrutura na extração do PDF (parágrafos e negrito por regex), corrigidos pelo agente; o QA corrigiu um critério e um falso positivo. Antes de despachar, verificar a viabilidade do critério no dado real mostrou que o kerning do pypdf exigia comparar caracteres, e não palavras.
- T09+T10: o QA corrigiu seus próprios testes (nome exato de categoria, P15 com dados sintéticos, verificação de conceitos no prompt em vez de frases exatas).
- T13: o agente Backend perguntou ao coordenador (`ask`) antes de alterar um teste da T01, e a flag `--version` foi aprovada.
- Na T11+T12, 96 testes do QA passaram na primeira integração; na T13, 33.
- Lições registradas: `send` só garante enfileiramento, então mudanças de contrato precisam ser confirmadas no `worker_done`; arquivos gerados com `--check` exigem `.gitattributes` com `eol=lf`.

## Resultados dos cenários end-to-end

_Pendente: depende da execução com credencial da API (T14/T15)._

## Exemplos de conversa

_Pendente: depende da execução com credencial da API (T14/T15)._
