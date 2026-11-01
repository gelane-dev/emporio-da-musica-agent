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

- Produtos com **múltiplas promoções** (todas inativas): #93, #96, #99. O manual diz que promoções não são cumulativas (6.2), mas não diz qual vale se houver mais de uma ativa — tratamento em §4.2 (P15).
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

> **Revisado em 2026-11-01** conforme as diretrizes aprovadas (TECHNICAL_DECISIONS, "Diretrizes obrigatórias"):
> nenhum dado conflitante é tratado como fato; nenhuma regra é inventada para resolver contradições.

| # | Problema | Evidência | Impacto | Tratamento |
|---|---|---|---|---|
| Q1 | Nome × descrição divergentes (marca/modelo) | #135 "Music Man" → descrição "Fender Jazz Bass"; #136 "Ibanez" → "Precision" (modelo Fender); #137 "Yamaha" → "Ibanez"; #139 "Yamaha" → "Pearl Export"; #140 "Pearl" → "Tama"; #142 "Korg" → "Roland"; #144 "Roland" → "Yamaha" | Agente pode afirmar marca/modelo errados | **Não escolher fonte de verdade.** O loader (T02) detecta e expõe o conflito como dado estruturado (`ProductConflict`); a tool (T09) marca o produto como "informações conflitantes" e o agente não afirma marca/modelo/descrição além do nome cadastrado, informando a limitação |
| Q2 | Specs × descrição divergentes | #137 "5 cordas" / specs `strings: 4`; #142 "88 teclas" / specs `keys: 61`; #143 "piano de palco" / specs `type: Synthesizer` | Informação técnica contraditória | Idem Q1: os **dois** valores são expostos como conflitantes; o agente não apresenta nenhum deles como confirmado |
| Q3 | Total do pedido ≠ soma dos itens a preço atual | #3: R$ 3.450 vs 2×1.749 = 3.498; #20: R$ 1.400 vs 799+689 = 1.488 | Pergunta "quanto paguei?" | **Não é conflito confirmado**: `order_items` não guarda preço histórico, então o preço atual pode simplesmente ter mudado. Exibir `total_brl` como "valor total registrado no pedido"; nunca recalcular pelo preço atual |
| Q4 | Pedido com produto hoje `coming_soon` | #3 (delivered) e #14 (pending) contêm #130 | Inconsistência de cadastro | Não afeta o status do pedido; ao falar do produto, usar o `status` atual |
| Q5 | Produto descontinuado com estoque | #136 discontinued, estoque 13 | Agente poderia oferecer item fora de catálogo | Política 7.3: produto descontinuado "não faz mais parte do catálogo" ⇒ nunca ofertado, independente do estoque (regra do manual, não inventada) |
| Q6 | Produto `coming_soon` com estoque | #130 coming_soon, estoque 2 | Venda/disponibilidade incerta | O manual não define `coming_soon`. A tool informa o status "em breve" e devolve **limitação**: disponibilidade para compra não confirmada; não é listado como disponível |
| Q7 | PIX sem desconto aplicado no total | #1, #5, #10 pagos via PIX com total = preço de tabela | Divergência com política (5% PIX) | Pedidos históricos não são recalculados nem comentados; só o `total_brl` é exibido |
| Q8 | Parcelamento histórico fora da parcela mínima | #9 e #16 em 6x (R$ 58,32 e R$ 71,65); #18 em 12x (R$ 38,33) | Histórico contradiz política | Histórico nunca é usado como referência de regra |
| Q9 | Pedidos "parados" em relação à data atual | #8 `shipped` com previsão 2026-02-28; pendentes desde março/2026 | Agente pode afirmar atraso | Data real em produção; data controlada (`REFERENCE_DATE`) em testes/exemplos (D9). A tool informa a previsão como **estimativa** e não afirma atraso nem causa |
| Q10 | Typo no nome | #84 "Giannini GN-15 Nylon **Cedr** Natural" | Busca por "cedro" falha | Busca textual normalizada + fuzzy; nome exibido não é alterado |
| Q11 | Categorias vazias | Sopro (madeiras/metais), Cordas Orquestrais | Política diz que a loja trabalha com esses itens | Informar que não há produtos dessas categorias no sistema no momento e indicar o contato da loja |
| Q12 | Catálogo pequeno vs. política | Política: "mais de 300 instrumentos"; CSV: 65 | Agente não deve prometer o que não está nos dados | Responder apenas com base no sistema |

### 3.1 Detecção de conflitos de produto (Q1/Q2)

Duas camadas, ambas no loader (T02), sem alterar valores:

1. **Verificação automática** (pega casos novos se os dados mudarem):
   - *marca*: a descrição menciona uma marca de instrumento conhecida e nenhuma delas aparece no nome. Lista de marcas = fabricantes de instrumentos presentes nos dados (Yamaha, Tagima, Giannini, Rozini, Shelby, Crafter, Martin, Taylor, Takamine, Kala, Ohana, Kalani, Fender, Gibson, Ibanez, PRS, Music Man, Pearl, Tama, Korg, Nord, Roland). Marcas de componentes (LR Baggs, Aquila, Atmosfeel) **não** entram, pois não indicam o fabricante do instrumento.
   - *número de cordas*: "N cordas" na descrição ≠ `specs.strings`.
   - *número de teclas*: "N teclas" na descrição ≠ `specs.keys`.
   - Resultado verificado nos dados atuais: #135, #137 (marca e cordas), #139, #140, #142 (marca e teclas), #144.
2. **Lista revisada manualmente** (casos que a heurística não cobre sem gerar falsos positivos):
   - #136: descrição cita o modelo "Precision" (linha de outro fabricante) num produto Ibanez.
   - #143: descrição "piano de palco" × `specs.type = Synthesizer`.

Fora do escopo da detecção (documentado como limitação): nomes genéricos com modelo específico na descrição **da mesma marca** (#138 "Music Man Bass 4X" → "StingRay"; #141 "Yamaha Kit 3" → "Stage Custom") não são contradição explícita e não são marcados.

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

**Fuso horário.** Os arquivos não citam fuso; ele decorre do endereço da loja (Campo Grande/MS — enunciado do desafio e seção 1.2 do manual). O identificador IANA correspondente é `America/Campo_Grande` (UTC−4, sem horário de verão desde 2019 — conferido na base `tzdata` 2026f).

### 4.1 Regras confirmadas (viram lógica determinística)

Só entram aqui regras **sem contradição** no manual. Valores calculados em Python (TECHNICAL_DECISIONS D4).

| Regra | Fonte | Observação |
|---|---|---|
| PIX: 5% sobre preço de tabela | 3 (tabela) | — |
| PIX não se aplica sobre preço promocional; promoções não cumulativas | 6.2 | — |
| Preço promocional exibido com preço original e percentual | 6.2 | — |
| Promoção vigente = `is_active` no sistema | 7.3 ("verificar se ela encontra-se ativa no sistema") | O manual define o sistema como fonte; campanhas da seção 6.1 não indicam vigência |
| Crédito: até 12x sem juros — **limite máximo absoluto** | 3 e 3.1 (concordam) | Nenhuma opção acima de 12x é gerada, qualquer que seja o valor da parcela |
| Dentro do limite de 1x a 12x, parcela ≥ R$ 100,00 é aceita | 3 (mín. R$ 100) e 3.1 (mín. ≤ R$ 100 em todas as faixas) | Interseção das duas fontes: atende a todas as leituras. **Não** amplia o limite de 12x. Ver P3/P4 para o restante |
| Pagamento combinado permitido somente para compras **estritamente acima de** R$ 2.000,00 | 3.1 | Exatamente R$ 2.000,00 ⇒ limitação explícita (P12); abaixo ⇒ não permitido |
| Frete na região metropolitana: grátis **acima de** R$ 500,00; R$ 35,00 **abaixo de** R$ 500,00; 1 a 3 dias úteis | 5.1 | Exatamente R$ 500,00 ⇒ limitação (P5) |
| Campo Grande pertence à região metropolitana de Campo Grande | 5.1 (a região leva o nome do município-sede) | Demais municípios ⇒ limitação (P8) |
| Outras cidades: PAC 5–12, SEDEX 2–5, Jadlog 3–8 dias úteis; valor por CEP, peso e dimensões | 5.2 | Agente **não** cota valor (sem dados) ⇒ limitação |
| "Instrumentos de grande porte (baterias acústicas, pianos digitais, contrabaixos) podem exigir frete especial" | 5.2 | Repassado literalmente; o agente não classifica qual produto exige (ver P13) |
| Horário: seg–sex 09:00–18:00; sáb 09:00–13:00; domingo e feriados fechado | 2 | Feriados não são conhecidos pelo sistema ⇒ limitação ao responder "aberto agora?" |
| Datas especiais podem ter horário estendido, comunicado em redes sociais/WhatsApp | 2 | Repassado como ressalva |
| Arrependimento (compras online): 7 dias corridos após o **recebimento** | 4.1 | Ver P6/P7 |
| Troca por defeito: 30 dias corridos após a **compra** | 4.2 | — |
| Troca por preferência: até 7 dias | 4.3 | Referência de data não especificada — ver P14 |
| Garantia legal: 90 dias após o **recebimento** | 8.1 | — |
| Produto descontinuado: informar que saiu do catálogo e oferecer equivalentes | 7.3 | — |
| Produto fora de estoque: informar indisponibilidade e sugerir alternativas disponíveis | 7.3 | — |

### 4.2 Contradições, lacunas e tratamento

Princípio: **quando o manual é contraditório ou omisso, a ferramenta devolve uma limitação explícita** (`Limitation`, ver ARCHITECTURE §5.5) e o agente informa o cliente e indica a confirmação com a equipe. Nenhuma interpretação é aplicada como regra.

> Status: **aprovado em 2026-11-01**, com dois ajustes: (1) o limite máximo de 12x vale sempre, mesmo com parcela ≥ R$ 100; (2) pagamento combinado só para valores estritamente superiores a R$ 2.000,00, e exatamente R$ 2.000,00 devolve limitação explícita.

| # | Contradição / lacuna | O que é confirmado | Tratamento (limitação) |
|---|---|---|---|
| P1 | Telefone: seção 1.2 "Telefone / WhatsApp (67) 3341-4444" × seção 7 "WhatsApp (67) 3321-4500" | Os dois números constam no manual | `informacoes_loja` devolve **os dois**, cada um com a seção de origem e o rótulo exato do manual, mais a limitação "o manual cita dois números de WhatsApp". O agente não afirma qual é o correto |
| P2 | E-mail: capa `contato@emporiodamusica.com.br` × seção 1.2 `contato@empóriodamusica.com.br` | Ambas as grafias constam | Devolver as duas grafias com a origem e a limitação. O telefone (67) 3341-4444, idêntico na capa e na seção 1.2, é o contato sem divergência |
| P3 | Tabela de pagamento: crédito "parcela mínima de R$ 100,00" × seção 3.1: 4x–6x com mínimo de R$ 80,00 | Parcelas ≥ R$ 100, até 12x | Opções de até 12x com parcela ≥ R$ 100 são **confirmadas**. Opções 4x–6x com parcela entre R$ 80,00 e R$ 99,99 são devolvidas como **"a confirmar"**, com limitação citando as duas regras |
| P4 | Seção 3.1: até 3x "sem valor mínimo de parcela (exceto abaixo de R$ 50,00)" — autocontraditório; e conflita com o mínimo de R$ 100 da tabela | Parcelas ≥ R$ 100 | Opções 1x–3x com parcela < R$ 100 são **"a confirmar"**, com limitação citando o texto literal. Nenhum mínimo de R$ 50 é aplicado |
| P5 | Frete metropolitano: "acima de R$ 500" grátis / "abaixo de R$ 500" taxa — exatamente R$ 500,00 não está coberto | Demais valores | Valor = R$ 500,00 ⇒ `fee=None` + limitação |
| P6 | Arrependimento vale para compras **online**; pedidos não registram o canal | Regra de 7 dias | `consultar_pedido` devolve limitação "canal de compra não registrado"; o agente pergunta ao cliente e não conclui sozinho |
| P7 | Arrependimento conta do **recebimento**; só existe `estimated_delivery` | Previsão de entrega | A tool devolve a previsão rotulada como **estimativa** e limitação "data real de recebimento não registrada". **Nenhum veredito de elegibilidade** é calculado; o agente expõe a regra, os dados disponíveis e encaminha a confirmação para a equipe |
| P8 | "Região metropolitana de Campo Grande" não lista os municípios | Campo Grande pertence | Outra cidade ⇒ limitação "o manual não define os municípios da região metropolitana"; o agente apresenta as regras de 5.1 e 5.2 e indica confirmação |
| P9 | Garantia conta do recebimento; troca por defeito conta da compra | Ambas literais | Sem conflito real: cada prazo é informado com sua referência de data |
| P10 | "Registrar reclamação e encaminhar" | Fluxo do manual | T12 (opcional): registro local + protocolo |
| P11 | Campanhas sazonais (6.1) × promoções inativas no CSV | Seção 7.3 manda verificar no sistema | Preço sempre pelo CSV (`is_active`); a seção 6.1 não é usada para afirmar descontos vigentes |
| P12 | Pagamento combinado "acima de R$ 2.000,00" — exatamente R$ 2.000,00 não está coberto | > R$ 2.000,00 permitido; < R$ 2.000,00 não permitido | Valor = R$ 2.000,00 ⇒ `a_confirmar` + limitação explícita |
| P13 | "Contrabaixos" (frete especial) pode ser acústico (Cordas Orquestrais) ou elétrico (as descrições dos baixos usam "contrabaixo elétrico"); "pianos digitais" × teclados cadastrados como sintetizador | Texto literal | O agente repassa a frase do manual ("podem exigir frete especial com cotação individual") sem classificar o produto |
| P14 | Troca por preferência: "até 7 dias" sem dizer se após compra ou recebimento | Prazo de 7 dias | Informar "até 7 dias" com limitação sobre a referência de data |
| P15 | Mais de uma promoção ativa para o mesmo produto: não cumulativas, mas o manual não diz qual vale | Não cumulativas | Hoje nenhum produto tem duas ativas. Se ocorrer: exibir preço de tabela + limitação "há mais de uma promoção ativa; confirmar qual se aplica". Nenhuma é escolhida automaticamente |
| P16 | `status = coming_soon` não é definido no manual | Status do sistema | Ver Q6 |

## 5. Mapeamento dos cenários sugeridos no desafio

| Pergunta | Fonte | Resultado esperado com os dados atuais |
|---|---|---|
| "Quais opções de violões disponíveis custando até R$1000?" | products + promotions | **12 violões** ativos com estoque (#81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 107, 112). Excluir #96 (estoque 0) e #113 (descontinuado) |
| "Qual o endereço da loja?" | PDF 1.2 | Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, CEP 79202-333 |
| "Quanto custa o Takamine GD20?" | products #95 + promotions | R$ 2.199,00 (estoque 5); PIX R$ 2.089,05; até 12x de R$ 183,25 (confirmado: parcela ≥ R$ 100); promoção de 12% **inativa** |
| "Me arrependi da minha compra, posso devolver?" | orders + PDF 4.1/4.4 | Pedir nº do pedido + e-mail ou telefone; informar status, previsão de entrega (estimativa) e a regra de 7 dias após o recebimento; perguntar data de recebimento e canal de compra; **não** declarar elegibilidade — encaminhar a confirmação à equipe |

Cenários extras de alto valor para os exemplos:
- Pedido cancelado (#19) → explicar motivo (`notes`) com empatia.
- Produto esgotado (#96) → sugerir similares disponíveis (mesma categoria/faixa de preço).
- Produto em promoção ativa (#121: R$ 549 → R$ 439,20, 20% off) → mostrar original + promo + %; PIX não acumula; até 4x de R$ 109,80 confirmado; 5x de R$ 87,84 "a confirmar" (P3).
- Produto com informações conflitantes (#142) → informar nome e preço, avisar que há divergência no cadastro (marca e número de teclas) e sugerir confirmar com a loja.
- Pedido de acessório ("vocês vendem cordas?") → redirecionamento educado (política 7.1).
- Fora de escopo total ("qual a capital da França?") → recusa gentil e retorno ao tema.
- Categoria vazia ("vocês têm saxofone?") → transparência + contato da loja.
