# ARCHITECTURE.md — Arquitetura do agente Empório da Música

> Justificativas de cada escolha: `TECHNICAL_DECISIONS.md`. Fatos sobre os dados: `DATA_ANALYSIS.md`.

## 1. Visão geral

Agente de atendimento por texto, em Python, baseado em **function calling**: o LLM conversa com o cliente e decide quando chamar ferramentas determinísticas que consultam o **catálogo/pedidos (CSV)** ou as **políticas (PDF pré-processado)**. Toda regra de negócio numérica é calculada em Python.

```
┌────────────┐   texto    ┌──────────────────────────────────────────────┐
│  Cliente   │──────────▶│  Interface (CLI)                              │
│ (terminal) │◀──────────│  cli.py                                       │
└────────────┘            └───────────────┬──────────────────────────────┘
                                          │ Agent.respond(session, msg)
                          ┌───────────────▼──────────────────────────────┐
                          │  Agent (loop de tool use)                     │
                          │  agent/agent.py  +  agent/prompts.py          │
                          │  Session (histórico em memória)               │
                          └───────┬───────────────────────────┬──────────┘
                     LLMClient    │                           │ ToolRegistry.execute(name, args)
                ┌─────────────────▼───────┐       ┌───────────▼──────────────────────────┐
                │ llm/ (adaptador)        │       │ tools/ (schemas + handlers)           │
                │ Anthropic (padrão)      │       └──┬──────────────┬──────────────┬─────┘
                └─────────────────────────┘          │              │              │
                                        ┌────────────▼───┐ ┌────────▼───────┐ ┌────▼────────────┐
                                        │ data/          │ │ domain/        │ │ policies/       │
                                        │ loader +       │ │ pricing,       │ │ PolicyStore     │
                                        │ repository     │ │ store_hours,   │ │ (seções do .md) │
                                        │ (pandas)       │ │ shipping,dates │ │                 │
                                        └───────┬────────┘ └────────────────┘ └────────┬────────┘
                                                │ leitura (read-only)                    │ leitura
                                        data/*.csv                         knowledge/policies.md
                                                                              ▲ (gerado 1x por
                                                                              │  scripts/build_policies.py
                                                                              │  a partir do PDF)
```

### Princípios
1. **Originais intocados** — `data/` é somente leitura; tratamento acontece em memória.
2. **LLM redige, Python calcula** — preço final, parcelas, prazos, horário vêm prontos das tools.
3. **Camadas com dependência em um sentido só**: `cli → agent → tools → (data | domain | policies)`. `domain` não conhece `data` nem LLM; `data` não conhece LLM.
4. **Tudo testável sem LLM**, exceto o próprio loop (testado com LLM falso).
5. **Simplicidade** — sem framework de agentes, sem banco, sem vector store.

## 2. Estrutura de pastas

```
emporio-da-musica-agent/
├── data/                              # ORIGINAIS (read-only, versionados)
│   ├── desafio_tecnico_ai_eng - *.csv
│   ├── desafio_tecnico_ai_eng_artefact.pdf
│   └── políticas_da_loja.pdf
├── knowledge/
│   └── policies.md                    # PDF convertido + revisado, com marcadores de seção
├── src/
│   └── emporio_agent/
│       ├── __init__.py
│       ├── __main__.py                # python -m emporio_agent → cli.main()
│       ├── config.py                  # Settings (env, caminhos, REFERENCE_DATE, timezone)
│       ├── data/
│       │   ├── models.py              # Product, Category, Promotion, Order, OrderItem, Customer, ProductConflict
│       │   ├── loader.py              # lê CSVs → DataFrames tipados/normalizados
│       │   ├── quality.py             # detecção de conflitos de produto (DATA_ANALYSIS §3.1)
│       │   └── repository.py          # CatalogRepository, OrderRepository
│       ├── domain/
│       │   ├── limitations.py         # Limitation (compartilhado por domain e tools)
│       │   ├── pricing.py             # PriceQuote: promo, PIX, parcelas
│       │   ├── store_hours.py         # aberto agora? próximo horário
│       │   ├── shipping.py            # regra de frete metropolitano / outras cidades
│       │   └── text.py                # normalização (acentos, caixa) p/ busca
│       ├── policies/
│       │   └── store.py               # PolicyStore: carrega policies.md, get(topic)
│       ├── tools/
│       │   ├── base.py                # ToolResult, ToolError, Tool, ToolRegistry
│       │   ├── catalog_tools.py       # buscar_produtos, detalhar_produto, listar_categorias
│       │   ├── order_tools.py         # consultar_pedido
│       │   ├── policy_tools.py        # consultar_politica, informacoes_loja
│       │   └── handoff_tools.py       # encaminhar_atendente (opcional, T12)
│       ├── llm/
│       │   ├── base.py                # LLMClient (Protocol), Message, ToolCall, LLMResponse
│       │   └── anthropic_client.py    # adaptador padrão
│       ├── agent/
│       │   ├── prompts.py             # build_system_prompt(settings, now)
│       │   ├── session.py             # Session (histórico, truncamento, export .md)
│       │   └── agent.py               # Agent.respond(): loop de tool use
│       └── cli.py                     # REPL com rich, --debug, /sair, /salvar
├── scripts/
│   ├── build_policies.py              # PDF → knowledge/policies.md (rodado 1x)
│   └── run_scenarios.py               # cenários E2E com LLM real
├── tests/
│   ├── conftest.py                    # fixtures (repositório carregado, now fixo, FakeLLM)
│   ├── test_loader.py
│   ├── test_repository.py
│   ├── test_pricing.py
│   ├── test_store_hours.py
│   ├── test_shipping.py
│   ├── test_policy_store.py
│   ├── test_tools.py
│   └── test_agent_loop.py
├── examples/
│   └── conversations/                 # 3–5 transcripts .md (entregável E3)
├── runtime/                           # gerado em execução (gitignored): transcripts, handoffs
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml                     # metadados + config do pytest (pythonpath=src)
├── README.md
├── ARCHITECTURE.md / TASKS.md / TECHNICAL_DECISIONS.md / DATA_ANALYSIS.md
```

## 3. Fluxo de uma mensagem

```
1. CLI lê "Quanto custa o Takamine GD20?"
2. session.add_user(msg)
3. Agent monta: system_prompt(now) + session.messages + tool_specs
4. LLM → tool_call detalhar_produto({"nome": "Takamine GD20"})
5. ToolRegistry valida args (pydantic) → handler → CatalogRepository.find_by_name()
   → domain.pricing.quote(product, promotions) → ToolResult(ok=True, data={...})
6. Agent anexa tool_result ao histórico → chama LLM de novo
7. LLM → texto final ("O Takamine GD20 sai por R$ 2.199,00 ... no PIX R$ 2.089,05 ...")
8. session.add_assistant(...) ; CLI imprime (e, com --debug, as tool calls)
Limite: MAX_TOOL_ITERATIONS (padrão 6) → resposta de fallback educada.
```

## 4. Roteamento: quando consultar o quê

| Intenção do cliente | Tool | Fonte |
|---|---|---|
| Busca/recomendação ("violões até R$1000", "ukulele para iniciante") | `buscar_produtos` | products + categories + promotions |
| Preço/estoque/specs de um item | `detalhar_produto` | products + promotions → pricing |
| "Que tipos de instrumento vocês têm?" | `listar_categorias` | categories + contagem |
| Status/rastreio/itens de pedido | `consultar_pedido` | orders + order_items + customers (verificação) |
| Troca, devolução, garantia, pagamento, frete, promoções (regras), LGPD | `consultar_politica` | knowledge/policies.md |
| Endereço, telefone, horário, "estão abertos?" | `informacoes_loja` | policies (seção 1.2/2) + store_hours |
| Reclamação / caso que exige humano | `encaminhar_atendente` (opcional) | grava em runtime/handoffs.jsonl |
| Fora do escopo / acessórios | nenhuma | regra do prompt |

Casos compostos (ex.: "posso devolver meu pedido 7?") → `consultar_pedido` **e** `consultar_politica("trocas_devolucoes")`; o resultado do pedido traz os fatos (status, previsão de entrega rotulada como estimativa) e as limitações (canal de compra e data real de recebimento não registrados). O agente apresenta a regra e os fatos, mas **não** declara elegibilidade — a confirmação fica com a equipe (DATA_ANALYSIS P6/P7).

## 5. Contratos de integração

Convenções: modelos com **pydantic v2**; dinheiro como `Decimal` no domínio e serializado como `float` com 2 casas + string formatada `"R$ 2.199,00"` nos resultados de tools; datas ISO `YYYY-MM-DD`; nomes de tools e campos voltados ao LLM em **português** (melhora a escolha da tool), código interno em inglês.

### 5.1 `config.py`
```python
class Settings(BaseModel):
    data_dir: Path                 # padrão: <repo>/data
    policies_path: Path            # padrão: <repo>/knowledge/policies.md
    runtime_dir: Path              # padrão: <repo>/runtime
    llm_provider: Literal["anthropic"] = "anthropic"
    llm_model: str                 # LLM_MODEL
    llm_max_tokens: int = 1024
    timezone: str = "America/Campo_Grande"
    reference_datetime: datetime | None   # REFERENCE_DATE; None = agora
    max_tool_iterations: int = 6
    max_history_turns: int = 20

def load_settings() -> Settings: ...          # lê .env
def now(settings: Settings) -> datetime: ...  # tz-aware; usa reference_datetime se definido
```

### 5.2 `data/` — modelos e repositório
```python
ProductStatus = Literal["active", "discontinued", "coming_soon"]
OrderStatus   = Literal["pending", "confirmed", "shipped", "delivered", "cancelled"]

class Product(BaseModel):
    id: int; name: str; category_id: int; category_name: str
    description: str; price: Decimal; stock: int; status: ProductStatus
    specs: dict[str, str]; created_at: date
    @property
    def available(self) -> bool: return self.status == "active" and self.stock > 0

class Category(BaseModel):
    id: int; name: str; description: str

class Promotion(BaseModel):
    id: int; product_id: int; discount_percent: int; description: str; is_active: bool

class OrderItem(BaseModel):
    product_id: int; product_name: str; quantity: int

class Order(BaseModel):
    id: int; customer_id: int; order_date: date; status: OrderStatus
    total: Decimal; payment_method: str; tracking_code: str | None
    estimated_delivery: date | None; notes: str | None; items: list[OrderItem]

class Customer(BaseModel):
    id: int; name: str; phone_digits: str; email: str; city: str

class ProductConflict(BaseModel):              # DATA_ANALYSIS §3.1
    product_id: int
    kind: Literal["marca", "cordas", "teclas", "revisao_manual"]
    fields: tuple[str, ...]                    # campos envolvidos, ex.: ("name", "description")
    values: dict[str, str]                     # valor de cada lado, ex.: {"name": "Music Man", "description": "Fender"}
    detection: Literal["automatica", "revisao_manual"]
    note: str                                  # explicação em PT

@dataclass(frozen=True)
class StoreData:                              # retorno de loader.load_all(data_dir)
    products: pd.DataFrame; categories: pd.DataFrame; promotions: pd.DataFrame
    orders: pd.DataFrame; order_items: pd.DataFrame; customers: pd.DataFrame
    product_conflicts: dict[int, list[ProductConflict]]   # vazio para produtos sem conflito

class CatalogRepository:
    def __init__(self, data: StoreData): ...
    def get(self, product_id: int) -> Product | None
    def search(self, *, text: str | None = None, category_id: int | None = None,
               min_price: Decimal | None = None, max_price: Decimal | None = None,
               only_available: bool = True, limit: int = 10,
               sort: Literal["preco_asc", "preco_desc", "relevancia"] = "relevancia") -> list[Product]
    def find_by_name(self, query: str, limit: int = 3) -> list[tuple[Product, float]]  # fuzzy score 0–100
    def categories(self) -> list[tuple[Category, int]]                                # (categoria, nº disponíveis)
    def active_promotions(self, product_id: int) -> list[Promotion]                   # TODAS as ativas; não escolhe (P15)
    def inactive_promotions(self, product_id: int) -> list[Promotion]                 # encerradas; sem datas ⇒ não há "mais recente"
    def conflicts(self, product_id: int) -> list[ProductConflict]
    def similar(self, product: Product, limit: int = 3) -> list[Product]              # sugestão: mesma categoria, disponível, preço próximo

class OrderRepository:
    def get(self, order_id: int) -> Order | None
    def customer_of(self, order: Order) -> Customer
```
Regras do `loader` (normalização em memória, sem alterar valores): tipos numéricos (`price`/`total` como `Decimal`) e datas (`date`); `specs` → `dict`; strings `strip()`; telefone → só dígitos; e-mail → minúsculas; `is_active` → `bool`; `notes`/`tracking_code`/`estimated_delivery` vazios → `None`; join de `category_name`; detecção de conflitos de produto (DATA_ANALYSIS §3.1) com log WARNING por conflito.

`similar()` é uma heurística de **sugestão** (política 7.3: "sugerir alternativas semelhantes"), não uma regra de negócio; os resultados são apresentados como sugestões.

### 5.3 `domain/` — regras de negócio puras

Toda função de domínio devolve, junto com o resultado, as **limitações** aplicáveis. Só regras confirmadas (DATA_ANALYSIS §4.1) produzem valores afirmativos; contradições e lacunas (§4.2) produzem `Limitation`.

```python
class Limitation(BaseModel):                   # domain/limitations.py — compartilhado por domain e tools
    code: Literal["MANUAL_CONTRADITORIO", "MANUAL_OMISSO",
                  "DADO_NAO_REGISTRADO", "DADO_CONFLITANTE"]
    message: str                               # PT, pronta para o agente repassar
    source: str                                # ex.: "Manual v2.1, seções 3 e 3.1" | "products.csv #142"

class InstallmentOption(BaseModel):
    n: int; value: Decimal
    status: Literal["confirmada", "a_confirmar"]   # P3/P4

class PromoInfo(BaseModel):
    percent: int; description: str; price: Decimal

class PriceQuote(BaseModel):
    list_price: Decimal
    promo: PromoInfo | None                    # só se houver exatamente 1 promoção ativa
    final_price: Decimal                       # promo.price ou list_price
    pix_price: Decimal | None                  # None com promo (6.2) ou com promoções ambíguas (P15)
    installments: list[InstallmentOption]      # só n em 1..12 (limite do manual); omite opções vedadas por TODAS as leituras
    max_confirmed_installments: int | None     # maior n ≤ 12 com parcela ≥ R$ 100; None se nenhum
    combined_payment: Literal["permitido", "nao_permitido", "a_confirmar"]   # > 2000 (estrito) | < 2000 | == 2000 + limitação (P12)
    limitations: list[Limitation]

def quote(price: Decimal, active_promotions: list[ActivePromotion]) -> PriceQuote   # ActivePromotion: Protocol estrutural (domain não importa data)
def installment_options(amount: Decimal) -> list[InstallmentOption]
```
Classificação de parcelas (`v = amount / n`, arredondado a 2 casas):

| Faixa | `v ≥ 100` | `80 ≤ v < 100` | `v < 80` |
|---|---|---|---|
| 1x–3x | confirmada | a_confirmar (P4) | a_confirmar (P4) |
| 4x–6x | confirmada | a_confirmar (P3) | omitida (vedada pela tabela e pela 3.1) |
| 7x–12x | confirmada | omitida (vedada pelas duas) | omitida |
| 13x ou mais | **nunca gerada** (limite de 12x do manual, independentemente do valor) | — | — |

```python
class StoreStatus(BaseModel):
    is_open_regular_hours: bool                # pelo horário regular da seção 2
    today_hours: str | None; next_opening: datetime | None
    limitations: list[Limitation]              # feriados não conhecidos; datas especiais com horário estendido
def store_status(now: datetime, timezone: str = "America/Campo_Grande") -> StoreStatus   # detalhes: §5.3.1

class ShippingEstimate(BaseModel):
    region: Literal["metropolitana", "nao_confirmada"]   # só "Campo Grande" é confirmada (P8)
    fee_status: Literal["gratis", "taxa_fixa", "nao_disponivel"]
    fee: Decimal | None                        # None quando nao_disponivel
    deadlines: list[str]                       # "1 a 3 dias úteis" | PAC/SEDEX/Jadlog
    notes: list[str]                           # frase literal do manual sobre frete especial (P13)
    limitations: list[Limitation]              # P5 (R$ 500,00), P8 (outros municípios), valor por CEP
def shipping_estimate(city: str | None, order_value: Decimal) -> ShippingEstimate
```
#### 5.3.1 Contrato detalhado da T05 (horários e frete)

Fonte única para quem implementa e para quem testa. Strings marcadas como *literais* reproduzem o manual e podem ser comparadas por igualdade; as `message` das limitações são livres (testar `code`, `source` e presença de termos-chave, não o texto inteiro).

**`domain/store_hours.py`** — manual, seção 2.
```python
STORE_TIMEZONE_DEFAULT = "America/Campo_Grande"
REGULAR_HOURS: dict[int, tuple[time, time]] = {          # chave = datetime.weekday(); domingo ausente
    0: (time(9), time(18)), 1: ..., 2: ..., 3: ..., 4: (time(9), time(18)),
    5: (time(9), time(13)),
}
LIMITATION_FERIADOS: Limitation          # DADO_NAO_REGISTRADO — o sistema não conhece feriados (loja fecha em feriados)
LIMITATION_DATAS_ESPECIAIS: Limitation   # DADO_NAO_REGISTRADO — Black Friday, Aniversário, Natal podem ter horário estendido
                                         # source de ambas: "Manual de Políticas v2.1, seção 2"

class StoreStatus(BaseModel, frozen=True):
    is_open_regular_hours: bool
    today_hours: str | None              # literal "09:00 às 18:00" | "09:00 às 13:00" | None (domingo)
    next_opening: datetime | None        # None quando aberto; senão a próxima abertura, no fuso da loja
    limitations: list[Limitation]        # sempre [LIMITATION_FERIADOS, LIMITATION_DATAS_ESPECIAIS]

def store_status(now: datetime, timezone: str = STORE_TIMEZONE_DEFAULT) -> StoreStatus
```
- `now` sem fuso ⇒ `ValueError`. `now` é convertido para `timezone` antes de qualquer cálculo; nunca chama `datetime.now()`.
- Aberto no intervalo `[abertura, fechamento)`. `today_hours` refere-se ao dia local de `now`.
- Antes das 09:00 de um dia útil ou sábado ⇒ `next_opening` = mesmo dia 09:00.

**`domain/shipping.py`** — manual, seções 5.1 e 5.2.
```python
FREE_SHIPPING_THRESHOLD = Decimal("500.00")
METRO_FIXED_FEE = Decimal("35.00")
METRO_DEADLINE = "1 a 3 dias úteis"                                      # literal
OTHER_CITIES_DEADLINES = (                                               # literais
    "PAC (Correios): 5 a 12 dias úteis",
    "SEDEX (Correios): 2 a 5 dias úteis",
    "Jadlog (.package): 3 a 8 dias úteis",
)
NOTE_MOTOBOY = "Entrega realizada por motoboy próprio. O cliente será contactado por telefone antes da entrega."
NOTE_SEGURO = "Todos os envios incluem seguro contra extravios e danos durante o transporte."
NOTE_FRETE_ESPECIAL = ("Instrumentos de grande porte (baterias acústicas, pianos digitais, contrabaixos) "
                       "podem exigir frete especial com cotação individual.")
LIMITATION_P5: Limitation                 # MANUAL_OMISSO — exatamente R$ 500,00 não coberto (seção 5.1)
LIMITATION_P8: Limitation                 # MANUAL_OMISSO — municípios da região metropolitana não definidos (5.1);
                                          # a message resume a regra 5.1 (grátis acima de R$ 500,00; R$ 35,00 abaixo; 1 a 3 dias úteis)
LIMITATION_VALOR_POR_CEP: Limitation      # DADO_NAO_REGISTRADO — valor calculado por CEP, peso e dimensões (5.2)
LIMITATION_CIDADE_NAO_INFORMADA: Limitation  # DADO_NAO_REGISTRADO — pedir a cidade de entrega

class ShippingEstimate(BaseModel, frozen=True): ...   # campos acima

def is_campo_grande(city: str) -> bool    # domain.text.normalize(city) in {"campo grande", "campo grande ms"}
def shipping_estimate(city: str | None, order_value: Decimal) -> ShippingEstimate
```
| Entrada | region | fee_status | fee | deadlines | notes | limitations |
|---|---|---|---|---|---|---|
| `order_value` não é `Decimal` finito > 0 | `ValueError` | | | | | |
| cidade `None`/vazia | `nao_confirmada` | `nao_disponivel` | `None` | `[]` | `[]` | `[CIDADE_NAO_INFORMADA]` |
| Campo Grande, valor > 500,00 | `metropolitana` | `gratis` | `Decimal("0.00")` | `[METRO_DEADLINE]` | `[NOTE_MOTOBOY]` | `[]` |
| Campo Grande, valor < 500,00 | `metropolitana` | `taxa_fixa` | `Decimal("35.00")` | `[METRO_DEADLINE]` | `[NOTE_MOTOBOY]` | `[]` |
| Campo Grande, valor = 500,00 | `metropolitana` | `nao_disponivel` | `None` | `[METRO_DEADLINE]` | `[NOTE_MOTOBOY]` | `[P5]` |
| Outra cidade (qualquer valor) | `nao_confirmada` | `nao_disponivel` | `None` | `list(OTHER_CITIES_DEADLINES)` | `[NOTE_SEGURO, NOTE_FRETE_ESPECIAL]` | `[P8, VALOR_POR_CEP]` |

`domain/` não importa `emporio_agent.data` nem `emporio_agent.config` (pode importar `domain.text` e `domain.limitations`).

Dinheiro em `Decimal`; arredondamento de exibição em 2 casas com `ROUND_HALF_UP` (técnico, não regra de negócio).

### 5.4 `policies/store.py`
```python
PolicyTopic = Literal["sobre_loja", "horarios", "pagamento", "trocas_devolucoes",
                      "frete_entrega", "promocoes", "atendimento", "garantia", "privacidade"]

class PolicySection(BaseModel):
    topic: PolicyTopic; title: str; source: str   # ex.: "Manual v2.1, seção 4"
    text: str

class PolicyStore:
    @classmethod
    def from_markdown(cls, path: Path) -> "PolicyStore"
    def get(self, topic: PolicyTopic) -> list[PolicySection]
    def topics(self) -> list[PolicyTopic]
```
Formato de `knowledge/policies.md`: cada bloco começa com `<!-- topic: trocas_devolucoes -->` seguido de `## 4. Política de Trocas e Devoluções`. O `PolicyStore` falha na inicialização se algum tópico do `Literal` não existir no arquivo. O texto é **fiel ao PDF**: divergências (telefones, e-mails, parcelamento) não são corrigidas no `.md`, apenas anotadas no topo do arquivo.

#### 5.4.1 Contrato detalhado da T06 (extração do PDF → `knowledge/policies.md`)

Fonte única para quem implementa (IA/RAG) e para quem valida (QA). A T07 (`PolicyStore`) **não** faz parte da T06.

**Script `scripts/build_policies.py`** (CLI; sem import pelo pacote `emporio_agent`)
```text
python scripts/build_policies.py [--pdf PATH] [--out PATH] [--check]
  --pdf    padrão: <repo>/data/políticas_da_loja.pdf   (somente leitura; nunca escrever nele)
  --out    padrão: <repo>/knowledge/policies.md
  --check  não escreve; sai com código 0 se --out já é idêntico ao que seria gerado, 1 caso contrário
```
- Usa `pypdf` (o modo `extraction_mode="layout"` é recomendado para as tabelas). Determinístico e idempotente: duas execuções geram bytes idênticos.
- Saída UTF-8, quebras de linha `\n`, terminando com uma única `\n`.
- **Todo texto de política vem do PDF.** O script só pode conter literais de *estrutura*: mapa seção → tópico, cabeçalho/rodapé a remover, cabeçalhos de tabela, título H1, linha `## Capa` e a nota de extração. É proibido digitar conteúdo do manual no script.
- Remove cabeçalho repetido (`Empório da Música Manual de Políticas e Procedimentos`, páginas 2–8) e rodapé (`Página N`). Nada mais é descartado (inclui a capa e o rodapé final "Empório da Música — Sua música começa aqui. / Última atualização: Junho de 2025 — Versão 2.1", que ficam no último bloco).
- Não corrige divergências (P1 telefones, P2 grafias do e-mail, P3/P4 parcelamento): reproduz o PDF e as lista na nota de extração.

**Formato de `knowledge/policies.md`**
```markdown
# Manual de Políticas e Procedimentos — Empório da Música

> Nota de extração: gerado por scripts/build_policies.py a partir de data/políticas_da_loja.pdf (Versão 2.1 — Junho de 2025).
> Texto fiel ao PDF. Divergências do próprio manual NÃO corrigidas: P1 (telefones), P2 (grafias do e-mail), P3/P4 (parcelamento). Ver DATA_ANALYSIS.md §4.2.

<!-- topic: sobre_loja -->
## Capa
<texto da página 1, linha a linha>

<!-- topic: sobre_loja -->
## 1. Sobre a Empório da Música
...
### 1.1 Missão
...
```
Blocos, em ordem do documento (cada bloco = do marcador `<!-- topic: X -->` até o próximo marcador; a primeira linha após o marcador é o `## ` do bloco; um tópico pode ter mais de um bloco):

| # | topic | `## ` (texto literal do PDF) | Subtítulos `### ` |
|---|---|---|---|
| 1 | `sobre_loja` | `## Capa` (único título acrescentado) | — |
| 2 | `sobre_loja` | `## 1. Sobre a Empório da Música` | 1.1, 1.2 |
| 3 | `horarios` | `## 2. Horário de Funcionamento` | — |
| 4 | `pagamento` | `## 3. Formas de Pagamento` | 3.1 |
| 5 | `trocas_devolucoes` | `## 4. Política de Trocas e Devoluções` | 4.1–4.4 |
| 6 | `frete_entrega` | `## 5. Política de Frete e Entregas` | 5.1–5.3 |
| 7 | `promocoes` | `## 6. Promoções e Descontos` | 6.1, 6.2 |
| 8 | `atendimento` | `## 7. Atendimento via WhatsApp` | 7.1–7.3 |
| 9 | `garantia` | `## 8. Garantia` | 8.1–8.3 |
| 10 | `privacidade` | `## 9. Privacidade e Proteção de Dados` | — |
| 11 | `atendimento` | `## 10. Disposições Finais` | — |

Subtítulos `### ` usam o texto literal (ex.: `### 4.1 Direito de Arrependimento (Compras Online)`). Listas com `•` viram `- `; a lista numerada da 7.2 mantém `1.` … `5.`; rótulos em negrito do PDF (ex.: `Cumulatividade:`) podem usar `**…**`.

Tabelas Markdown (cabeçalho literal, células literais; células quebradas em várias linhas no PDF são unidas com um espaço):

| Seção | Cabeçalho | Linhas de dados |
|---|---|---|
| 1.2 | `\| Campo \| Informação \|` | 7 |
| 2 | `\| Dia \| Horário \|` | 3 |
| 3 | `\| Forma \| Condições \| Observações \|` | 4 |
| 5.2 | `\| Modalidade \| Prazo Estimado \| Rastreamento \| Seguro \|` | 3 |

**Critério de fidelidade (verificável por teste)** — sequência de palavras:
- `W_pdf`: para cada página (ordem 1→8), `page.extract_text()` no modo **padrão** do pypdf, `split()` em espaços; nas páginas 2–8 remover as 8 primeiras palavras se forem o cabeçalho e as 2 últimas se forem `Página <n>`; remover tokens `•`.
- `W_md`: do `.md`, (1) remover comentários `<!-- … -->`; (2) remover as linhas: H1 (`# `), linhas iniciadas por `>`, separadores de tabela (`|---|…`), a linha `## Capa`; (3) remover marcadores no início da linha: `#`/`##`/`###` + espaço e `- `; (4) remover `**`; (5) trocar `|` por espaço; (6) `split()`.
- **Exigência: `W_md == W_pdf`** (mesmas palavras, mesma ordem). Garante que nada foi omitido, alterado ou acrescentado fora das áreas permitidas.

Referência medida pelo coordenador em 2026-11-01: `len(W_pdf) == 1651`; cabeçalho e rodapé presentes em todas as páginas 2–8.

### 5.5 `tools/` — contrato com o LLM
```python
class ToolError(BaseModel):
    code: Literal["NOT_FOUND", "AMBIGUOUS", "VERIFICATION_FAILED",
                  "INVALID_ARGUMENT", "INTERNAL_ERROR"]
    message: str                          # texto em PT, orientando o LLM ("peça o e-mail ...")

class ToolResult(BaseModel):
    ok: bool
    data: dict | list | None = None
    error: ToolError | None = None
    limitations: list[Limitation] = []    # serializado como "limitacoes"; o agente DEVE repassá-las
    def to_llm(self) -> str               # JSON compacto, ensure_ascii=False

class Tool(Protocol):
    name: str; description: str
    args_model: type[BaseModel]           # gera o JSON Schema enviado ao LLM
    def run(self, args: BaseModel) -> ToolResult

class ToolRegistry:
    def specs(self) -> list[ToolSpec]     # {name, description, input_schema}
    def execute(self, name: str, raw_args: dict) -> ToolResult   # nunca lança: erros viram ToolResult(ok=False)
```

| Tool | Argumentos | `data` em caso de sucesso | Limitações típicas |
|---|---|---|---|
| `buscar_produtos` | `texto?: str`, `categoria?: enum(nomes)`, `preco_min?: float`, `preco_max?: float`, `apenas_disponiveis: bool = true`, `ordenar?: enum`, `limite: int = 8 (≤15)` | `{total_encontrado, produtos: [ {id, nome, categoria, preco_formatado, promocao?: {percentual, preco_formatado}, disponivel: bool, status, informacoes_conflitantes: bool} ]}` | Promoções múltiplas (P15) |
| `detalhar_produto` | `produto_id?: int`, `nome?: str` (um dos dois) | `{produto: {id, nome_cadastrado, categoria, status, disponivel, quantidade_estoque, descricao?, especificacoes}, conflitos: [{tipo, campos, valores, observacao}], preco: PriceQuote formatado, promocoes_encerradas?: [{descricao, percentual}], alternativas_sugeridas?: [...]}`. Campos envolvidos em conflito **saem** de `produto` e aparecem só em `conflitos`. `AMBIGUOUS` com candidatos se fuzzy < limiar | `DADO_CONFLITANTE` (Q1/Q2), parcelas a confirmar (P3/P4), `coming_soon` (Q6), P12, P15 |
| `listar_categorias` | — | `[ {nome, descricao, produtos_disponiveis} ]` | — |
| `consultar_pedido` | `pedido_id: int` **e** (`email` **ou** `telefone`) | `{pedido_id, primeiro_nome_cliente, data_pedido, status, status_descricao, valor_total_registrado, forma_pagamento_descricao, itens: [{nome, quantidade}], codigo_rastreio?, previsao_entrega_estimada?, observacoes?}` | Canal de compra não registrado (P6); data real de recebimento não registrada (P7) |
| `consultar_politica` | `topico: PolicyTopic` | `{topico, secoes: [{titulo, fonte, texto}]}` | Divergências conhecidas do tópico (ex.: P3/P4 em `pagamento`) |
| `informacoes_loja` | — | `{nome, endereco, contatos: [{tipo, valor, rotulo_no_manual, fonte}], horarios: [...], aberto_agora_horario_regular, proxima_abertura?, data_hora_referencia}` | P1, P2, feriados/datas especiais |
| `encaminhar_atendente` *(opcional)* | `motivo: enum(reclamacao, caso_complexo, pedido_cliente)`, `resumo: str`, `pedido_id?: int` | `{protocolo, prazo_retorno: "24 horas úteis"}` | — |

Regras transversais das tools:
- **Identificação de cliente**: nunca por nome ou e-mail isolados. `consultar_pedido` exige o número do pedido **e** e-mail ou telefone, conferidos contra o cliente **daquele** pedido.
- Nunca retornam e-mail/telefone de cliente nem `customer_id`.
- `status_descricao` é a tradução literal do status do sistema (pendente, confirmado, enviado, entregue, cancelado) — sem inferir significado não documentado.
- Valores de pedido são apresentados como "valor total registrado no pedido"; nunca recalculados pelo preço atual (Q3).
- Nenhuma tool emite **veredito** de elegibilidade de troca/devolução: devolvem fatos + regra + limitações (P6/P7).
- Produtos `discontinued`/`coming_soon` só aparecem em `detalhar_produto` (consulta direta), com status explícito; nunca em `buscar_produtos` com `apenas_disponiveis=true`.
- Mensagens de erro dizem ao LLM **o que fazer** (ex.: `VERIFICATION_FAILED: "Os dados não conferem. Peça ao cliente o e-mail ou telefone usado na compra; não revele dados do pedido."`).

### 5.6 `llm/` — adaptador
```python
class ToolCall(BaseModel):    id: str; name: str; arguments: dict
class Message(BaseModel):     role: Literal["user", "assistant", "tool"]
                              content: str | None; tool_calls: list[ToolCall] = []
                              tool_call_id: str | None = None   # quando role="tool"
class LLMResponse(BaseModel): text: str | None; tool_calls: list[ToolCall]
                              stop_reason: str; usage: dict[str, int]

class LLMClient(Protocol):
    def complete(self, *, system: str, messages: list[Message],
                 tools: list[ToolSpec], max_tokens: int) -> LLMResponse
```
O formato `Message` é **neutro**; cada adaptador converte para o formato do provedor. Erros de rede/limite viram `LLMError` (retry com backoff simples no adaptador, 2 tentativas).

### 5.7 `agent/`
```python
class Session:
    id: str; messages: list[Message]; started_at: datetime
    def add_user(self, text: str) -> None
    def add(self, msg: Message) -> None
    def window(self, max_turns: int) -> list[Message]   # corta só em fronteira de turno do usuário
    def to_markdown(self) -> str                          # transcript p/ examples/

class ToolCallRecord(BaseModel): name: str; arguments: dict; ok: bool; duration_ms: int
class AgentReply(BaseModel):     text: str; tool_calls: list[ToolCallRecord]

class Agent:
    def __init__(self, llm: LLMClient, tools: ToolRegistry, settings: Settings,
                 clock: Callable[[], datetime] = ...): ...
    def respond(self, session: Session, user_text: str) -> AgentReply

def build_system_prompt(now: datetime, store_status: StoreStatus) -> str
```
Prompt de sistema (seções): identidade/persona → escopo → regras de grounding → quando usar cada tool → formato de preço e promoção → privacidade/verificação → situações especiais (7.3) → fora do expediente → data/hora de referência.

### 5.8 `cli.py`
`python -m emporio_agent [--debug] [--save]` — comandos: `/sair`, `/salvar`, `/nova` (nova sessão). Ao iniciar, mostra saudação (gerada localmente, sem chamada de LLM). Se o horário estiver fora do expediente, a saudação informa o próximo horário (política 7.1).

### 5.9 Composição (injeção de dependências)
Feita em um único lugar (`cli.py` → `build_agent(settings)`): `load_all → repositórios → PolicyStore → ToolRegistry([...]) → AnthropicClient → Agent`. Testes montam o mesmo grafo com `FakeLLM` e `clock` fixo.

## 6. Observabilidade
- `logging` padrão: nível INFO registra cada tool call (nome, args, ok, duração) e uso de tokens por turno; nunca loga e-mail/telefone do cliente (mascarar).
- `--debug` na CLI mostra as tool calls inline — útil para os exemplos e para o avaliador entender o "quando consultar".

## 7. Segurança e privacidade
- Chave de API só via `.env` (gitignored); `.env.example` versionado.
- Verificação de identidade obrigatória para pedidos (TECHNICAL_DECISIONS D8).
- Sem persistência de dados pessoais entre sessões; transcripts salvos apenas sob comando e em `runtime/` (gitignored). Exemplos publicados usam pedidos fictícios do próprio dataset.
