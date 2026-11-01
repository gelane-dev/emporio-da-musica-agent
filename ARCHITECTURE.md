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
│       │   ├── models.py              # Product, Category, Promotion, Order, OrderItem, Customer
│       │   ├── loader.py              # lê CSVs → DataFrames tipados/normalizados
│       │   └── repository.py          # CatalogRepository, OrderRepository
│       ├── domain/
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

Casos compostos (ex.: "posso devolver meu pedido 7?") → `consultar_pedido` **e** `consultar_politica("trocas_devolucoes")`; o resultado do pedido já traz `dias_desde_entrega_estimada` para o LLM não calcular datas.

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

class StoreData:                              # retorno de loader.load_all(data_dir)
    products: pd.DataFrame; categories: pd.DataFrame; promotions: pd.DataFrame
    orders: pd.DataFrame; order_items: pd.DataFrame; customers: pd.DataFrame

class CatalogRepository:
    def __init__(self, data: StoreData): ...
    def get(self, product_id: int) -> Product | None
    def search(self, *, text: str | None = None, category_id: int | None = None,
               min_price: Decimal | None = None, max_price: Decimal | None = None,
               only_available: bool = True, limit: int = 10,
               sort: Literal["preco_asc", "preco_desc", "relevancia"] = "relevancia") -> list[Product]
    def find_by_name(self, query: str, limit: int = 3) -> list[tuple[Product, float]]  # fuzzy score 0–100
    def categories(self) -> list[tuple[Category, int]]                                # (categoria, nº disponíveis)
    def active_promotion(self, product_id: int) -> Promotion | None                   # maior desconto ativo
    def latest_inactive_promotion(self, product_id: int) -> Promotion | None          # p/ "promo expirada"
    def similar(self, product: Product, limit: int = 3) -> list[Product]              # mesma categoria, disponível, preço ±40%

class OrderRepository:
    def get(self, order_id: int) -> Order | None
    def customer_of(self, order: Order) -> Customer
```
Regras do `loader` (normalização em memória): tipos numéricos/datas; `specs` → dict; strings `strip()`; telefone → só dígitos; e-mail → minúsculas; `is_active` → bool; `notes`/`tracking_code` vazios → `None`; join de `category_name`; flag de inconsistência (DATA_ANALYSIS Q1–Q2) registrada em log, sem alterar valores.

### 5.3 `domain/` — regras de negócio puras
```python
class InstallmentOption(BaseModel):
    n: int; value: Decimal

class PromoInfo(BaseModel):
    percent: int; description: str; price: Decimal

class PriceQuote(BaseModel):
    list_price: Decimal
    promo: PromoInfo | None              # {percent, description, price}
    final_price: Decimal                 # promo.price ou list_price
    pix_price: Decimal | None            # None quando há promo (não cumulativo)
    max_installments: int                # maior n válido (1..12)
    installment_examples: list[InstallmentOption]   # ex.: 3x, 6x, max
    combined_payment_allowed: bool       # final_price > 2000

def quote(price: Decimal, promotion: Promotion | None) -> PriceQuote
def installment_options(amount: Decimal) -> list[InstallmentOption]   # todas as válidas

class StoreStatus(BaseModel):
    is_open: bool; today_hours: str | None; next_opening: datetime | None
def store_status(now: datetime) -> StoreStatus      # seg–sex 9–18, sáb 9–13, dom fechado
                                                     # feriados: fora do escopo (documentado)

class ShippingEstimate(BaseModel):
    region: Literal["metropolitana", "outras_cidades"]
    fee: Decimal | None                  # None = calculado por CEP (não disponível)
    deadline: str                        # "1 a 3 dias úteis" | tabela PAC/SEDEX/Jadlog
    notes: list[str]                     # ex.: frete especial p/ baterias/teclados
def shipping_estimate(city: str, order_value: Decimal, category_id: int | None) -> ShippingEstimate
```

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
Formato de `knowledge/policies.md`: cada bloco começa com `<!-- topic: trocas_devolucoes -->` seguido de `## 4. Política de Trocas e Devoluções`. O `PolicyStore` falha na inicialização se algum tópico do `Literal` não existir no arquivo.

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
    def to_llm(self) -> str               # JSON compacto, ensure_ascii=False

class Tool(Protocol):
    name: str; description: str
    args_model: type[BaseModel]           # gera o JSON Schema enviado ao LLM
    def run(self, args: BaseModel) -> ToolResult

class ToolRegistry:
    def specs(self) -> list[ToolSpec]     # {name, description, input_schema}
    def execute(self, name: str, raw_args: dict) -> ToolResult   # nunca lança: erros viram ToolResult(ok=False)
```

| Tool | Argumentos | `data` em caso de sucesso |
|---|---|---|
| `buscar_produtos` | `texto?: str`, `categoria?: enum(nomes)`, `preco_min?: float`, `preco_max?: float`, `apenas_disponiveis: bool = true`, `ordenar?: enum`, `limite: int = 8 (≤15)` | `{total_encontrado, produtos: [ {id, nome, categoria, preco, preco_formatado, promocao?: {percentual, preco}, estoque_status: "disponível"/"últimas unidades"/"esgotado", status} ]}` |
| `detalhar_produto` | `produto_id?: int`, `nome?: str` (um dos dois) | `{produto: {id, nome, categoria, descricao, specs, status, estoque_status, quantidade_estoque}, preco: PriceQuote formatado, promocao_expirada?: {descricao, percentual}, alternativas?: [...] (se indisponível)}`. `AMBIGUOUS` com candidatos se fuzzy < limiar |
| `listar_categorias` | — | `[ {nome, descricao, produtos_disponiveis} ]` |
| `consultar_pedido` | `pedido_id: int`, `email?: str`, `telefone?: str` (≥1 obrigatório) | `{pedido_id, primeiro_nome_cliente, data_pedido, status, status_descricao, total_formatado, forma_pagamento_descricao, itens: [{nome, quantidade}], codigo_rastreio?, previsao_entrega?, dias_desde_entrega_estimada?, observacoes?, cidade_entrega}` |
| `consultar_politica` | `topico: PolicyTopic` | `{topico, secoes: [{titulo, fonte, texto}]}` |
| `informacoes_loja` | — | `{nome, endereco, telefone, whatsapp, email, horarios: [...], aberto_agora, proxima_abertura?, data_hora_referencia}` |
| `encaminhar_atendente` *(opcional)* | `motivo: enum(reclamacao, caso_complexo, pedido_cliente)`, `resumo: str`, `pedido_id?: int` | `{protocolo, prazo_retorno: "24 horas úteis"}` |

Regras transversais das tools:
- Nunca retornam e-mail/telefone de cliente nem `customer_id`.
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
