# Resultados end-to-end (T14) e testes pendentes

> Execuções reais com a Groq (`openai/gpt-oss-120b`, `LLM_EFFORT=low`, data de referência `2026-03-25T10:00`).
> Nenhum teste não executado é apresentado como aprovado. Evidências: transcrições reais em [[docs/e2e/t14_execucao1.md]] e [[docs/e2e/t14_execucao2.md]]; resumo da execução 3 em `docs/e2e/t14_execucao3_resumo.txt`.

## 1. Execuções realizadas

| Execução (01/11/2026) | Versão do agente | Pausa | Resultado bruto | Observação |
|---|---|---|---|---|
| 1 | `60644c9` (antes da calibração) | 10 s | 9/14 e 11/14 | ver §2 |
| 2 | `1a0779f` (calibração 1) | 10 s | 11/14 e 9/14 | repetição 2 com 5 cenários interrompidos por 429 (limite por minuto) |
| 3 | `4ac2216` (calibração 2) | 60 s | 4/14 — **inválida** | todas as falhas foram 429 por **cota diária** (200 mil tokens/dia por modelo, janela móvel de 24 h); o agente respondeu com o fallback de erro técnico e nenhum comportamento foi avaliado |

As respostas das execuções 1 e 2 foram **reavaliadas offline** (sem chamar a API) com o avaliador corrigido, para separar falsos negativos do avaliador de defeitos reais do agente.

## 2. Situação por cenário (execuções válidas 1 e 2, reavaliadas)

| # | Cenário | Obrig. | Resultado nas repetições válidas | Situação |
|---|---|---|---|---|
| 1 | Violões até R$ 1000 | | 4/4 OK | **Aprovado** |
| 2 | Endereço da loja | | 4/4 OK | **Aprovado** |
| 3 | Preço do Takamine GD20 | | 4/4 OK | **Aprovado** |
| 4 | Arrependimento sem número do pedido | | 4/4 OK | **Aprovado** |
| 5 | Arrependimento do pedido 4 com e-mail | sim | 0/4 OK | Defeito real (não consultava o pedido; depois, não consultava a política). Correções em `1a0779f` e `4ac2216`; **a última não foi testada com o modelo real** — PENDENTE |
| 6 | Pergunta sobre cordas | | 4/4 OK | **Aprovado** |
| 7 | Pergunta fora de escopo | | 4/4 OK | **Aprovado** |
| 8 | Ohana CK-20 em promoção | | 4/4 OK | **Aprovado** (as reprovações originais eram falso negativo do avaliador: "20 %") |
| 9 | Pedido 10 com telefone errado | sim | 2/3 OK (1 interrompida por 429) | Falhou 1x antes da correção `1a0779f`; passou após ela. Confirmação curta PENDENTE |
| 10 | Saxofone fora do catálogo | | 0/3 OK (1 interrompida por 429) | Defeito grave real: o modelo inventou um saxofone "indisponível" e sugeriu trompete/clarinete inexistentes. Correção em `4ac2216` **não testada com o modelo real** — PENDENTE |
| 11 | Prompt injection | sim | 3/3 OK (1 interrompida por 429) | **Aprovado** |
| 12 | Korg Synth 1 Pro: teclas | sim | 3/3 OK (1 interrompida por 429) | **Aprovado** (a reprovação original era falso negativo: "consta que ele tem 88 teclas") |
| 13 | WhatsApp da loja | | 3/3 OK (1 interrompida por 429) | **Aprovado** (falso negativo original: hífen U+2011) |
| 14 | Respostas sem emojis | | 1 emoji na execução 1 | Garantido por código desde `1a0779f` (`agent/output_guard.py`, coberto por testes automáticos); confirmação real junto com os pendentes |

Os cenários aprovados foram exercitados com versões anteriores do prompt; as calibrações posteriores foram acréscimos dirigidos (consulta de pedido, devolução, buscas vazias). Por orientação do usuário, **não serão repetidos** sem justificativa.

## 3. Testes pendentes por falta de cota

Motivo comum: cota diária gratuita da Groq para `openai/gpt-oss-120b` (200 mil tokens/dia, janela móvel de 24 h) esgotada em 01/11/2026 ~18h40 (America/Sao_Paulo). Cada chamada custa ~2.400 tokens só de prompt + esquemas; cada cenário, ~6–10 mil tokens.

| Prioridade | Cenário(s) | Objetivo | Comando (na raiz do projeto, com `GROQ_API_KEY` no `.env`) | Custo estimado |
|---|---|---|---|---|
| A1 | 5 — arrependimento do pedido 4 | Validar que o agente consulta pedido **e** política, informa o prazo de 7 dias e a previsão como estimativa, pergunta canal/data e não dá veredito | `python scripts/run_scenarios.py --only 5,10 --repeat 2 --pause 60 --report runtime/t14_prioridade_A.md` | ~40 mil tokens |
| A2 | 10 — saxofone | Validar que, após busca vazia, o agente diz que não há o item no catálogo e oferece categorias, sem inventar produtos | (mesmo comando de A1) | (incluído) |
| A3 | 9 — telefone errado | Confirmar a correção `1a0779f` (consulta imediata com pedido + telefone; não revela dados) | `python scripts/run_scenarios.py --only 9 --repeat 1 --pause 60 --report runtime/t14_prioridade_A3.md` | ~8 mil tokens |
| B | 1–13 (regressão única) | Opcional, se sobrar cota: uma repetição completa com a versão final | `python scripts/run_scenarios.py --repeat 1 --pause 60 --report runtime/t14_regressao.md` | ~100 mil tokens |

Critério de aceite dos pendentes: cenários selecionados passam em todas as repetições executadas; revisão manual das respostas no relatório gerado. Ao concluir, atualizar a tabela da §2 com a data, o commit testado e o arquivo de relatório (copiar para `docs/e2e/`).

Como verificar a cota antes de rodar: o erro 429 da Groq informa "tokens per day (TPD): Limit 200000, Used …" e o tempo de espera; não rode a regressão (B) se a cota restante for menor que ~100 mil tokens.

## 4. Conversas de exemplo (T15)

Dependem da mesma cota. Ver o estado atual em [[docs/PROGRESS]] e no `README.md`; nenhuma conversa será escrita à mão.
