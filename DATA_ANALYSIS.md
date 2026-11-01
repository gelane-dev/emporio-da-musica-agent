# DATA_ANALYSIS.md — Análise dos dados e políticas

> Análise feita sobre os arquivos originais em `data/` (somente leitura, nenhum arquivo foi alterado).
> Números obtidos com um script de inspeção pontual (stdlib `csv`/`json`), não versionado.

## 1. Visão geral

| Arquivo | Linhas | Papel para o agente | Uso previsto |
|---|---|---|---|
| `products.csv` | 65 | Catálogo: preço, estoque, status, specs | **Essencial** |
| `categories.csv` | 9 | Nome/descrição das categorias | **Essencial** (filtro e linguagem natural) |
| `promotions.csv` | 25 | Descontos por produto com flag `is_active` | **Essencial** (preço final) |
| `orders.csv` | 20 | Status, rastreio, previsão de entrega | **Essencial** (status de pedido) |
| `order_items.csv` | 22 | Itens de cada pedido | **Essencial** (detalhar pedido) |
| `customers.csv` | 50 | Nome, telefone, e-mail, cidade | **Restrito** — só para verificar identidade e personalizar saudação (LGPD) |
| `políticas_da_loja.pdf` | 8 páginas | Manual de atendimento | **Essencial** (políticas + persona + regras de conduta) |

Todos os CSVs estão em UTF-8 (sem BOM), separador `,`, com aspas duplas onde há vírgulas. Nenhuma célula obrigatória vazia nos produtos. Todos os `specs` são JSON válidos.

## 2. Esquema e relacionamentos

```
categories (category_id PK) 1──N products (product_id PK, category_id FK)
products   (product_id)     1──N promotions (product_id FK)          [0..N promoções por produto]
products   (product_id)     1──N order_items (product_id FK)
orders     (order_id PK)    1──N order_items (order_id FK)           [order_items não tem PK própria]
customers  (customer_id PK) 1──N orders (customer_id FK)
```

Integridade referencial verificada: **todas** as FKs resolvem (nenhum produto/cliente órfão).

### 2.1 `products.csv`
Colunas: `product_id, price_brl, name, category_id, description, stock_quantity, status, specs, created_at`

- IDs de 81 a 145, sem buracos nem duplicatas. **O ID 145 aparece fora de ordem** (antes do 131) — irrelevante se indexarmos por ID.
- `price_brl`: R$ 159,90 a R$ 19.567,00 (float com ponto decimal).
- `status`: `active` (62), `discontinued` (2: #113, #136), `coming_soon` (1: #130).
- `stock_quantity = 0`: #96 (ativo, esgotado) e #113 (descontinuado).
- `created_at`: 2020-02-28 a 2025-05-15 — pouco útil para o atendimento.
- `specs`: chaves variam por categoria:
  - violões/ukuleles: `top, back_sides, neck, strings, scale, electronics, color`
  - guitarras/baixos: `body, neck, strings, color`
  - baterias: `shells, pieces, hardware, color`
  - teclados: `keys, type, polyphony, color`
  - Formatação JSON inconsistente (com/sem espaço após `:`) — irrelevante após `json.loads`.

Distribuição por categoria:

| ID | Categoria | Produtos |
|---|---|---|
| 5 | Violões | 35 |
| 9 | Ukuleles | 15 |
| 1 | Guitarras | 5 |
| 2 | Baixos | 4 |
| 3 | Baterias e Percussão | 3 |
| 4 | Teclados e Pianos | 3 |
| 6 | Sopro (Madeiras) | **0** |
| 7 | Sopro (Metais) | **0** |
| 8 | Cordas Orquestrais | **0** |

### 2.2 `promotions.csv`
Colunas: `promotion_id, product_id, discount_percent, description, is_active`

- **Não há datas** de início/fim: a única fonte de vigência é `is_active` (0/1).
- Apenas **4 promoções ativas**:

| promo | produto | desconto | descrição |
|---|---|---|---|
| 12 | #127 Kalani KAL-700T Tenor | 10% | Oferta Especial |
| 14 | #121 Ohana CK-20 Concert | 20% | Desconto Exclusivo |
| 19 | #90 Crafter HT-100 Folk | 18% | Desconto Exclusivo |
| 24 | #94 Taylor 110e Dreadnought | 8% | Desconto Exclusivo |

- Produtos com **múltiplas promoções** (todas inativas): #93, #96, #99. Regra necessária: se houver >1 ativa, usar uma só (não cumulativas — política 6.2). Proposta: maior desconto.
- Promoções inativas com nomes de campanhas (Black Friday, Semana do Músico…) são úteis para o cenário **"promoção expirada"** (política 7.3). Ex.: Takamine GD20 (#95) teve "Oferta Especial" 12%, hoje inativa.

### 2.3 `orders.csv` + `order_items.csv`
Colunas orders: `order_id, customer_id, order_date, status, total_brl, payment_method, tracking_code, estimated_delivery, notes`

- Datas de 2025-10-15 a 2026-03-22.
- `status`: `delivered` (7), `shipped` (1), `confirmed` (4), `pending` (4), `cancelled` (4).
- `tracking_code` e `estimated_delivery` só existem para `delivered`/`shipped`. Todos os códigos seguem o padrão da política (`BR` + 9 alfanuméricos + `BR`).
- `notes` só preenchido nos cancelados (motivo do cancelamento) — bom para resposta transparente.
- `payment_method`: `pix, debit, boleto, credit_3x, credit_6x, credit_12x`.
- **Não há canal de compra** (online vs. presencial) nem **data real de entrega** — relevante para o direito de arrependimento (7 dias após *recebimento*, compras *online*).
- Pedidos com múltiplos itens: #15 (2 itens) e #20 (2 itens). Pedido #3 tem quantidade 2.

### 2.4 `customers.csv`
Colunas: `customer_id, name, phone, email, city`

- 50 clientes; só os IDs 1–18 têm pedidos.
- Cidades: Campo Grande (24), Dourados (7), Três Lagoas (7), Corumbá (6), Ponta Porã (6). Útil para política de frete (região metropolitana vs. outras cidades).
- **E-mail duplicado**: `bruno.martins@jmail.com` em #11 (Bruno Carvalho Martins) e #43 (Bruno Martins). Verificação de identidade só por e-mail é ambígua → sempre combinar com `order_id`.
- Nomes parecidos (ex.: "Diego Fernandes Castro" #13 / "Diego Castro" #47) → **nunca** identificar cliente só pelo nome.

### 2.5 `categories.csv`
9 categorias com descrição. Três sem nenhum produto (ver 2.1).

## 3. Problemas de qualidade encontrados

| # | Problema | Evidência | Impacto | Tratamento proposto |
|---|---|---|---|---|
| Q1 | Nome × descrição divergentes em baixos/baterias/teclados | #135 "Music Man Bass 1X" descrito como "Fender Jazz Bass"; #136 "Ibanez" → "Precision"; #137 "Yamaha" → "Ibanez"; #139 "Yamaha" → "Pearl Export"; #140 "Pearl" → "Tama"; #142 "Korg" → "Roland" | Agente pode afirmar a marca errada | Tratar `name` como fonte de verdade da marca/modelo; na listagem, não repetir trechos de marca da descrição. Registrar flag `description_mismatch` e citar a limitação no README |
| Q2 | Specs × descrição divergentes | #137 descrição "5 cordas" / specs `strings: 4`; #142 "88 teclas" / specs `keys: 61`; #143 "piano de palco" / specs `type: Synthesizer` | Informação técnica contraditória | Specs estruturados como fonte de verdade; agente orientado a não inventar specs |
| Q3 | Total do pedido ≠ soma dos itens | #3: R$ 3.450 vs 2×1.749 = 3.498; #20: R$ 1.400 vs 799+689 = 1.488 | Pergunta "quanto paguei?" | Sempre exibir `total_brl` do pedido (valor faturado); não recalcular |
| Q4 | Pedido entregue com produto `coming_soon` | #3 (delivered) contém #130 (coming_soon); #14 (pending) também | Inconsistência de cadastro | Não afeta resposta de status; ao falar do produto, respeitar `status` atual |
| Q5 | Produto descontinuado com estoque | #136 discontinued, estoque 13 | Agente poderia oferecer item fora de catálogo | Regra: `discontinued` nunca é ofertado, independente do estoque |
| Q6 | Produto `coming_soon` com estoque | #130 coming_soon, estoque 2 | Idem | Regra: `coming_soon` é informado como "em breve", sem venda |
| Q7 | PIX sem desconto aplicado no total | #1, #5, #10 pagos via PIX com total = preço de tabela | Divergência com política (5% PIX) | Não recalcular pedidos históricos; documentar suposição |
| Q8 | Parcelamento fora da regra de parcela mínima | #9 e #16 em 6x (parcelas R$ 58,32 e R$ 71,65 < R$ 80); #18 em 12x (R$ 38,33 < R$ 100) | Histórico contradiz política | Não usar histórico como referência; simulador de parcelas segue a política |
| Q9 | Pedidos "parados" em relação à data atual | #8 `shipped` com previsão 2026-02-28; pendentes desde março/2026; hoje = 2026-10-31 | Agente pode dizer "atrasado 8 meses" | Data de referência configurável (`REFERENCE_DATE`) — ver TECHNICAL_DECISIONS D9 |
| Q10 | Typo no nome | #84 "Giannini GN-15 Nylon **Cedr** Natural" | Busca por "cedro" falha | Busca textual normalizada + fuzzy; não alterar o nome exibido |
| Q11 | Categorias vazias | Sopro (madeiras/metais), Cordas Orquestrais | Política diz que a loja vende esses itens | Responder "no momento não temos em estoque/catálogo" e oferecer contato com a loja |
| Q12 | Catálogo pequeno vs. política | Política: "mais de 300 instrumentos"; CSV: 65 | Agente não deve prometer o que não está nos dados | Persona responde apenas com base no sistema |

## 4. Análise do PDF de políticas

8 páginas, texto extraível (não é scan). Estrutura em seções numeradas — ideal para **segmentar por seção**:

| Seção | Conteúdo | Tópico (chave proposta) |
|---|---|---|
| 1 / 1.1 / 1.2 | Sobre, missão, dados da empresa, **escopo: só instrumentos, sem acessórios** | `sobre_loja` |
| 2 | Horários (seg–sex 9–18h, sáb 9–13h, dom/feriados fechado) | `horarios` |
| 3 / 3.1 | Formas de pagamento, PIX 5%, parcelamento | `pagamento` |
| 4.1–4.4 | Arrependimento, defeito, preferência, itens não elegíveis | `trocas_devolucoes` |
| 5.1–5.3 | Frete metropolitano, outras cidades, rastreamento | `frete_entrega` |
| 6.1–6.2 | Campanhas, regras de promoção (não cumulativas, PIX não incide sobre promo, transparência) | `promocoes` |
| 7.1–7.3 | Tom de voz, escopo, fluxo padrão, situações especiais | **Prompt de sistema** (conduta) + `atendimento` |
| 8.1–8.3 | Garantia legal 90 dias, fabricante, exclusões | `garantia` |
| 9 | LGPD | `privacidade` |
| 10 | Disposições finais (em dúvida → gerência) | Prompt de sistema (escalonamento) |

Tamanho estimado: ~2,5–3,5 mil tokens no total — **cabe inteiro no contexto** de qualquer LLM moderno.

### 4.1 Regras que viram lógica determinística (não deixar para o LLM calcular)

- **PIX**: 5% de desconto sobre preço de tabela; **não** se aplica sobre preço promocional.
- **Promoções**: não cumulativas; exibir preço original + preço promocional + percentual.
- **Parcelamento** (até 12x sem juros):
  - 1–3x: parcela mínima R$ 50,00 (interpretação de "sem valor mínimo, exceto abaixo de R$ 50");
  - 4–6x: parcela mínima R$ 80,00;
  - 7–12x: parcela mínima R$ 100,00.
- **Pagamento combinado**: permitido acima de R$ 2.000,00.
- **Frete metropolitano**: grátis acima de R$ 500,00; senão R$ 35,00; 1–3 dias úteis.
- **Outras cidades**: PAC 5–12, SEDEX 2–5, Jadlog 3–8 dias úteis; valor calculado por CEP (agente **não** tem como cotar).
- **Horário de funcionamento** → "estamos abertos agora?" e mensagem fora do expediente (7.1).
- **Prazos**: arrependimento 7 dias corridos após recebimento; troca por defeito 30 dias após compra; troca por preferência 7 dias; garantia legal 90 dias após recebimento.

### 4.2 Inconsistências e ambiguidades no PDF

| # | Inconsistência | Decisão proposta |
|---|---|---|
| P1 | Telefone: capa/tabela "(67) 3341-4444" vs. seção 7 "WhatsApp (67) 3321-4500" | Informar ambos com rótulo: telefone da loja 3341-4444; WhatsApp de atendimento 3321-4500 (seção 7 é a específica do canal). Documentar |
| P2 | E-mail: capa `contato@emporiodamusica.com.br` vs. tabela 1.2 `contato@empóriodamusica.com.br` (com acento) | Usar a versão sem acento (domínios com acento são improváveis) |
| P3 | Tabela de pagamento: "crédito até 12x, parcela mínima R$ 100" vs. 3.1 com faixas (50/80/100) | Seção 3.1 (mais detalhada) prevalece; R$ 100 vale para 7–12x |
| P4 | "Sem valor mínimo de parcela (exceto abaixo de R$ 50,00)" é autocontraditório | Interpretar como mínimo de R$ 50 por parcela de 1–3x |
| P5 | "Frete grátis acima de R$ 500" / "taxa para abaixo de R$ 500" — exatamente R$ 500 não definido | Considerar ≥ R$ 500,00 como grátis (favorável ao cliente); documentar |
| P6 | Arrependimento só para compras **online**, mas pedidos não têm canal | Assumir que pedidos do sistema são online; agente pergunta em caso de dúvida |
| P7 | Arrependimento conta do **recebimento**, mas só existe `estimated_delivery` | Usar `estimated_delivery` como proxy e deixar claro que é estimativa; casos-limite → atendente humano |
| P8 | "Região metropolitana de Campo Grande" não é definida (quais cidades) | Considerar apenas o município de Campo Grande como metropolitano nos dados; demais → "outras cidades" |
| P9 | Garantia: "a partir do recebimento"; troca por defeito: "após a compra" — referências de data diferentes | Respeitar literalmente cada regra, explicitando a referência ao cliente |
| P10 | Política fala em "registrar reclamação e encaminhar" | Tool de handoff que registra em arquivo local (ver TASKS T12) |
| P11 | Campanhas sazonais no PDF (ex.: Black Friday em novembro) vs. promoções inativas no CSV | **Fonte de verdade para preço é o CSV** (`is_active`). O PDF descreve campanhas genéricas, não vigência |

## 5. Mapeamento dos cenários sugeridos no desafio

| Pergunta | Fonte | Resultado esperado com os dados atuais |
|---|---|---|
| "Quais opções de violões disponíveis custando até R$1000?" | products + promotions | **12 violões** ativos com estoque (#81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 107, 112). Excluir #96 (estoque 0) e #113 (descontinuado) |
| "Qual o endereço da loja?" | PDF 1.2 | Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, CEP 79202-333 |
| "Quanto custa o Takamine GD20?" | products #95 + promotions | R$ 2.199,00 (estoque 5); PIX R$ 2.089,05; até 12x de R$ 183,25; promoção de 12% **inativa** |
| "Me arrependi da minha compra, posso devolver?" | orders + PDF 4.1/4.4 | Pedir nº do pedido + verificação; avaliar status e prazo de 7 dias; com a data de referência atual, todos os entregues estão fora do prazo → explicar alternativas (defeito/garantia) |

Cenários extras de alto valor para os exemplos:
- Pedido cancelado (#19) → explicar motivo (`notes`) com empatia.
- Produto esgotado (#96) → sugerir similares disponíveis (mesma categoria/faixa de preço).
- Produto em promoção ativa (#121: R$ 549 → R$ 439,20, 20% off) → mostrar original + promo + %; PIX não acumula.
- Pedido de acessório ("vocês vendem cordas?") → redirecionamento educado (política 7.1).
- Fora de escopo total ("qual a capital da França?") → recusa gentil e retorno ao tema.
- Categoria vazia ("vocês têm saxofone?") → transparência + contato da loja.
