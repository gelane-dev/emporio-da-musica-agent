"""Ferramentas de catálogo: buscar_produtos, detalhar_produto, listar_categorias (§5.5.1)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from emporio_agent.data.models import Product
from emporio_agent.data.repository import CatalogRepository
from emporio_agent.domain.limitations import Limitation
from emporio_agent.domain.pricing import LIMITATION_P15, PriceQuote, format_brl, quote
from emporio_agent.domain.text import normalize
from emporio_agent.tools.base import Tool, ToolArgs, ToolResult
from emporio_agent.tools.limitations import LIMITATION_EM_BREVE, conflict_limitation

STATUS_PT = {"active": "ativo", "discontinued": "descontinuado", "coming_soon": "em_breve"}

NAME_RESOLVE_MIN_SCORE = 90.0
NAME_RESOLVE_MIN_GAP = 5.0
MAX_CANDIDATES = 5
MAX_ALTERNATIVES = 3


def _money(value: float) -> Decimal:
    return Decimal(str(value))


def product_summary(catalog: CatalogRepository, product: Product) -> tuple[dict, list[Limitation]]:
    """``ProdutoResumo`` + limitações (P15 quando há mais de uma promoção ativa)."""
    summary: dict = {
        "id": product.id,
        "nome": product.name,
        "categoria": product.category_name,
        "preco": format_brl(product.price),
    }
    limitations: list[Limitation] = []
    promotions = catalog.active_promotions(product.id)
    if len(promotions) == 1:
        promo = quote(product.price, promotions).promo
        assert promo is not None
        summary["promocao"] = {
            "percentual": promo.percent,
            "descricao": promo.description,
            "preco": format_brl(promo.price),
        }
    elif len(promotions) > 1:
        limitations.append(LIMITATION_P15)
    summary["disponivel"] = product.available
    summary["status"] = STATUS_PT[product.status]
    summary["informacoes_conflitantes"] = bool(catalog.conflicts(product.id))
    return summary, limitations


def _price_payload(q: PriceQuote) -> dict:
    return {
        "preco_tabela": format_brl(q.list_price),
        "promocao": (
            {
                "percentual": q.promo.percent,
                "descricao": q.promo.description,
                "preco": format_brl(q.promo.price),
            }
            if q.promo
            else None
        ),
        "preco_final": format_brl(q.final_price),
        "preco_pix": format_brl(q.pix_price) if q.pix_price is not None else None,
        "parcelamento": [
            {"parcelas": o.n, "valor": format_brl(o.value), "status": o.status} for o in q.installments
        ],
        "max_parcelas_confirmadas": q.max_confirmed_installments,
        "pagamento_combinado": q.combined_payment,
    }


# --- buscar_produtos ----------------------------------------------------------


class BuscarProdutosArgs(ToolArgs):
    texto: str | None = Field(
        default=None, description="Termos de busca livres (nome, marca, tipo, característica)."
    )
    categoria: str | None = Field(
        default=None, description="Nome exato de uma categoria (use listar_categorias para ver os nomes)."
    )
    preco_min: float | None = Field(default=None, ge=0, allow_inf_nan=False, description="Preço de tabela mínimo, em reais.")
    preco_max: float | None = Field(default=None, ge=0, allow_inf_nan=False, description="Preço de tabela máximo, em reais.")
    apenas_disponiveis: bool = Field(
        default=True, description="Se verdadeiro, só produtos ativos e com estoque."
    )
    ordenar: Literal["relevancia", "preco_asc", "preco_desc"] = "relevancia"
    limite: int = Field(default=8, ge=1, le=15, description="Máximo de produtos retornados (1 a 15).")


class BuscarProdutos(Tool):
    name = "buscar_produtos"
    description = (
        "Busca produtos no catálogo da loja por texto, categoria e faixa de preço. Use para "
        "recomendações, comparações e perguntas do tipo \"vocês têm...?\". Os filtros de preço usam "
        "o preço de tabela (sem promoção). Retorna uma lista resumida; para preço final, PIX, "
        "parcelas, estoque e especificações de um produto, use detalhar_produto. Para regras da "
        "loja (pagamento, trocas, frete), use consultar_politica."
    )
    args_model = BuscarProdutosArgs

    def __init__(self, catalog: CatalogRepository):
        self._catalog = catalog

    def run(self, args: BuscarProdutosArgs) -> ToolResult:  # type: ignore[override]
        category_id = None
        if args.categoria is not None:
            categories = [c for c, _ in self._catalog.categories()]
            wanted = normalize(args.categoria)
            match = next((c for c in categories if normalize(c.name) == wanted), None)
            if match is None:
                valid = [c.name for c in categories]
                return ToolResult.failure(
                    "INVALID_ARGUMENT",
                    f"Categoria desconhecida. Use exatamente um destes nomes: {', '.join(valid)}.",
                    details={"categorias_validas": valid},
                )
            category_id = match.id
        if args.preco_min is not None and args.preco_max is not None and args.preco_min > args.preco_max:
            return ToolResult.failure(
                "INVALID_ARGUMENT", "preco_min não pode ser maior que preco_max. Corrija a faixa de preço."
            )

        found = self._catalog.search(
            text=args.texto,
            category_id=category_id,
            min_price=_money(args.preco_min) if args.preco_min is not None else None,
            max_price=_money(args.preco_max) if args.preco_max is not None else None,
            only_available=args.apenas_disponiveis,
            limit=10**6,
            sort=args.ordenar,
        )
        limitations: list[Limitation] = []
        products = []
        for product in found[: args.limite]:
            summary, extra = product_summary(self._catalog, product)
            products.append(summary)
            limitations.extend(extra)
        return ToolResult.success({"total_encontrado": len(found), "produtos": products}, limitations)


# --- detalhar_produto ---------------------------------------------------------


class DetalharProdutoArgs(ToolArgs):
    produto_id: int | None = Field(default=None, ge=1, description="ID do produto (preferível, quando conhecido).")
    nome: str | None = Field(default=None, min_length=1, description="Nome (ou parte do nome) do produto.")

    @model_validator(mode="after")
    def _exactly_one(self) -> DetalharProdutoArgs:
        if (self.produto_id is None) == (self.nome is None):
            raise ValueError("informe exatamente um entre produto_id e nome")
        return self


class DetalharProduto(Tool):
    name = "detalhar_produto"
    description = (
        "Detalha um produto específico: preço final, promoção, PIX, parcelamento, estoque, "
        "especificações e divergências de cadastro. Informe produto_id (de uma busca anterior) ou o "
        "nome. Use sempre antes de informar preço, parcelas ou disponibilidade de um produto. Também "
        "retorna produtos descontinuados ou \"em breve\" (consulta direta), com o status explícito e "
        "alternativas quando indisponível."
    )
    args_model = DetalharProdutoArgs

    def __init__(self, catalog: CatalogRepository):
        self._catalog = catalog

    def _resolve(self, args: DetalharProdutoArgs) -> Product | ToolResult:
        if args.produto_id is not None:
            product = self._catalog.get(args.produto_id)
            if product is None:
                return ToolResult.failure(
                    "NOT_FOUND",
                    f"Não existe produto com id {args.produto_id}. Tente buscar por nome com buscar_produtos.",
                )
            return product

        assert args.nome is not None
        matches = self._catalog.find_by_name(args.nome, limit=MAX_CANDIDATES)
        if not matches:
            return ToolResult.failure(
                "NOT_FOUND",
                "Nenhum produto parecido com esse nome. Tente buscar_produtos com palavras-chave "
                "ou peça mais detalhes ao cliente.",
            )
        (first, first_score), rest = matches[0], matches[1:]
        if first_score >= NAME_RESOLVE_MIN_SCORE and (not rest or first_score - rest[0][1] >= NAME_RESOLVE_MIN_GAP):
            return first
        candidates = [{"id": p.id, "nome": p.name, "categoria": p.category_name} for p, _ in matches]
        return ToolResult.failure(
            "AMBIGUOUS",
            "Mais de um produto pode corresponder a esse nome. Mostre as opções ao cliente e peça que "
            "escolha; depois chame detalhar_produto com o produto_id.",
            details={"candidatos": candidates},
        )

    def run(self, args: DetalharProdutoArgs) -> ToolResult:  # type: ignore[override]
        resolved = self._resolve(args)
        if isinstance(resolved, ToolResult):
            return resolved
        product = resolved
        limitations: list[Limitation] = []

        description: str | None = product.description or None
        specs = dict(product.specs)
        conflicts = self._catalog.conflicts(product.id)
        for conflict in conflicts:
            for field in conflict.fields:
                if field == "description":
                    description = None
                elif field.startswith("specs."):
                    specs.pop(field.removeprefix("specs."), None)
        if conflicts:
            limitations.append(conflict_limitation(product.id, conflicts))

        produto: dict = {
            "id": product.id,
            "nome_cadastrado": product.name,
            "categoria": product.category_name,
            "status": STATUS_PT[product.status],
            "disponivel": product.available,
            "quantidade_estoque": product.stock,
        }
        if description:
            produto["descricao"] = description
        produto["especificacoes"] = specs

        preco = None
        if product.status != "discontinued":  # fora do catálogo (política 7.3)
            q = quote(product.price, self._catalog.active_promotions(product.id))
            preco = _price_payload(q)
            limitations.extend(q.limitations)
        if product.status == "coming_soon":
            limitations.append(LIMITATION_EM_BREVE)

        alternatives = []
        if not product.available:
            for similar in self._catalog.similar(product, limit=MAX_ALTERNATIVES):
                summary, extra = product_summary(self._catalog, similar)
                alternatives.append(summary)
                limitations.extend(extra)

        data = {
            "produto": produto,
            "conflitos": [
                {
                    "tipo": c.kind,
                    "campos": list(c.fields),
                    "valores": dict(c.values),
                    "observacao": c.note,
                }
                for c in conflicts
            ],
            "preco": preco,
            "promocoes_encerradas": [
                {"descricao": p.description, "percentual": p.discount_percent}
                for p in self._catalog.inactive_promotions(product.id)
            ],
            "alternativas_sugeridas": alternatives,
        }
        return ToolResult.success(data, limitations)


# --- listar_categorias --------------------------------------------------------


class ListarCategoriasArgs(ToolArgs):
    pass


class ListarCategorias(Tool):
    name = "listar_categorias"
    description = (
        "Lista as categorias de instrumentos da loja com a quantidade de produtos disponíveis em "
        "cada uma. Use quando o cliente quiser saber o que a loja vende ou para obter o nome exato "
        "de uma categoria antes de filtrar em buscar_produtos."
    )
    args_model = ListarCategoriasArgs

    def __init__(self, catalog: CatalogRepository):
        self._catalog = catalog

    def run(self, args: ListarCategoriasArgs) -> ToolResult:  # type: ignore[override]
        return ToolResult.success(
            [
                {"nome": c.name, "descricao": c.description, "produtos_disponiveis": count}
                for c, count in self._catalog.categories()
            ]
        )
