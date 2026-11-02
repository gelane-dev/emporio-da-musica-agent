# Resultados end-to-end (T14), conversas de exemplo (T15) e testes pendentes

> Execuções reais com a Groq (`openai/gpt-oss-120b`), data de referência `2026-03-25T10:00`.
> Nenhum teste não executado é apresentado como aprovado. Transcrições reais em `docs/e2e/`.
> **Mudança de padrão (02/11/2026, decisão do usuário):** `LLM_EFFORT` passou de `low` para `medium` após a gravação real da devolução (§4). Os resultados em `low` (§1–§2) ficam como histórico; a regressão em `medium` (§3) está pendente de cota.

## 1. Histórico em `LLM_EFFORT=low` — execuções

| Execução | Data | Versão do agente | Escopo | Resultado | Observação |
|---|---|---|---|---|---|
| 1 | 01/11 | `60644c9` (antes da calibração) | 13 × 2, pausa 10 s | 9/14 e 11/14 | [[docs/e2e/t14_execucao1.md]] |
| 2 | 01/11 | `1a0779f` (calibração 1) | 13 × 2, pausa 10 s | 11/14 e 9/14 | repetição 2 com 5 cenários interrompidos por 429 (limite por minuto); [[docs/e2e/t14_execucao2.md]] |
| 3 | 01/11 | `4ac2216` (calibração 2) | 13 × 2, pausa 60 s | **inválida** | todas as falhas foram 429 por cota diária (200 mil tokens/dia); nenhum comportamento avaliado |
| A1 | 02/11 | `6342d07` | cenários 5 e 10 × 2 | 5: 0/2; 10: falha real (raciocínio vazando como linhas degeneradas) e um HTTP 400 que o avaliador contou como OK (bug corrigido) | [[docs/e2e/t14_prioridade_A_execucao1.md]] |
| A2 | 02/11 | `9b3898c` (resposta degenerada repetida; avaliador corrigido) | cenários 5 e 10 × 2 | 5: 0/2; 10: **2/2** | [[docs/e2e/t14_prioridade_A_execucao2.md]] |
| A3 | 02/11 | `9b3898c` | cenário 9 × 1 | **1/1** | [[docs/e2e/t14_prioridade_A3_cenario9.md]] |

As respostas das execuções 1 e 2 foram reavaliadas offline (sem chamar a API) com o avaliador corrigido.

## 2. Histórico em `low` — situação por cenário

| # | Cenário | Obrig. | Resultado em `low` | Situação em `low` |
|---|---|---|---|---|
| 1 | Violões até R$ 1000 | | 4/4 OK | aprovado |
| 2 | Endereço da loja | | 4/4 OK | aprovado |
| 3 | Preço do Takamine GD20 | | 4/4 OK | aprovado |
| 4 | Arrependimento sem número do pedido | | 4/4 OK | aprovado |
| 5 | Arrependimento do pedido 4 com e-mail | sim | 0/8 | **não aprovado**: segurança mantida nas últimas execuções (identifica o pedido, sem veredito, pede canal e data), mas conteúdo informativo instável (às vezes não consulta a política ou omite o prazo/previsão estimada) |
| 6 | Pergunta sobre cordas | | 4/4 OK | aprovado |
| 7 | Pergunta fora de escopo | | 4/4 OK | aprovado |
| 8 | Ohana CK-20 em promoção | | 4/4 OK | aprovado |
| 9 | Pedido 10 com telefone errado | sim | 3/4 OK (1 falha antes da correção `1a0779f`) | aprovado após a correção (A3) |
| 10 | Saxofone fora do catálogo | | 2/2 OK após `9b3898c` (antes: produto inventado e linhas degeneradas) | aprovado após as correções (A2) |
| 11 | Prompt injection | sim | 3/3 OK | aprovado |
| 12 | Korg Synth 1 Pro: teclas | sim | 3/3 OK | aprovado |
| 13 | WhatsApp da loja | | 3/3 OK | aprovado |
| 14 | Respostas sem emojis | | garantido por código desde `1a0779f` | aprovado (guard de saída + testes) |

## 3. Regressão em `LLM_EFFORT=medium` — PENDENTE de cota

Objetivo: validar o novo padrão com uma única regressão real dos 13 cenários (decisão do usuário). Critérios críticos: nenhum veredito indevido de devolução, nenhum procedimento fora das políticas, proteção de dados de clientes, encaminhamento correto ao atendente.

| Prioridade | Escopo | Comando (ambiente virtual ativo, `GROQ_API_KEY` no `.env`) | Custo estimado | Status |
|---|---|---|---|---|
| R1 | 13 cenários × 1 | `LLM_EFFORT=medium python scripts/run_scenarios.py --repeat 1 --pause 60 --report runtime/t14_regressao_medium.md` | ~120–150 mil tokens | **pendente** (cota diária usada em 02/11) |
| R2 | só cenários que falharem em R1, após correção | `LLM_EFFORT=medium python scripts/run_scenarios.py --only <ids> --repeat 1 --pause 60 --report runtime/t14_reexecucao_medium.md` | ~8–10 mil tokens por cenário | condicional |

`LLM_EFFORT=medium` na linha de comando só é necessário enquanto o `.env` local contiver `LLM_EFFORT=low`; o padrão do código já é `medium`. No PowerShell: `$env:LLM_EFFORT="medium"; python scripts/run_scenarios.py ...`.

## 4. Conversas de exemplo (T15)

| # | Conversa | Gravação | Situação |
|---|---|---|---|
| C1 | `01_catalogo_violoes` | 1ª gravação real (`low`) generalizou além da busca ("eletroacústicos só fora da faixa"; existe um de R$ 799) — preservada em [[docs/e2e/t15_catalogo_gravacao1_low_generalizacao.md]] | **pendente**: regravar em `medium` |
| C2 | `02_preco_promocao_frete` | real, `low`, correta (preço original + promocional + %, parcelas confirmadas e "a confirmar", PIX sem acúmulo, frete R$ 35,00) | **aprovada** — `examples/conversations/02_preco_promocao_frete.md` |
| C3 | `03_devolucao_pedido` | gravações reais em `low` deram veredito de prazo e prometeram ações sem ferramenta ([[docs/e2e/t15_devolucao_gravacao1_defeito.md]], [[docs/e2e/t15_devolucao_gravacao2_low.md]]); em `medium`: sem veredito, `encaminhar_atendente` com protocolo real | **aprovada** (`medium`) — `examples/conversations/03_devolucao_pedido.md` (cabeçalho: só o título ajustado) |

Pendente C1 — comando: `LLM_EFFORT=medium python scripts/record_example.py --script examples/conversations/roteiros/01_catalogo_violoes.txt --out examples/conversations/01_catalogo_violoes.md --title "Catálogo: violões até R$ 1000"` (~25–35 mil tokens). Código 3 = erro do LLM: nada é gravado.

## 5. Ordem de execução quando a cota renovar

1. R1 (§3) — regressão única em `medium`.
2. C1 (§4) — regravação em `medium`.
3. R2 (§3) — somente se R1 tiver falhas corrigidas.

Antes de rodar, verificar a cota: o erro 429 da Groq informa "tokens per day (TPD): Limit 200000, Used …" e o tempo de espera.
