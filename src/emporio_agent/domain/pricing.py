"""Preço final, PIX, parcelamento e pagamento combinado.

Implementa somente as regras confirmadas do manual (DATA_ANALYSIS.md §4.1).
Pontos contraditórios ou omissos geram ``Limitation`` (§4.2: P3, P4, P12, P15):

- Crédito: até 12x sem juros — limite absoluto, independentemente do valor.
- Parcela ≥ R$ 100,00 (dentro de 1x–12x): confirmada pelas duas fontes do manual.
- 1x–3x com parcela < R$ 100,00: "a confirmar" (P4 — seção 3.1 autocontraditória
  e tabela da seção 3 com mínimo de R$ 100,00).
- 4x–6x com parcela entre R$ 80,00 e R$ 99,99: "a confirmar" (P3).
- Demais combinações: vedadas por todas as leituras ⇒ omitidas.
- PIX: 5% sobre o preço de tabela; não se aplica sobre preço promocional (6.2).
- Pagamento combinado: só para valores estritamente acima de R$ 2.000,00;
  exatamente R$ 2.000,00 ⇒ limitação (P12).
- Mais de uma promoção ativa: nenhuma é escolhida (P15).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from emporio_agent.domain.limitations import Limitation

MAX_INSTALLMENTS = 12
CONFIRMED_MIN_INSTALLMENT = Decimal("100.00")
MID_TIER_MIN_INSTALLMENT = Decimal("80.00")  # seção 3.1, de 4x a 6x (contradiz a tabela)
COMBINED_PAYMENT_THRESHOLD = Decimal("2000.00")
PIX_DISCOUNT_PERCENT = Decimal("5")
_CENT = Decimal("0.01")

MANUAL = "Manual de Políticas v2.1"

LIMITATION_P3 = Limitation(
    code="MANUAL_CONTRADITORIO",
    message=(
        "O manual traz regras diferentes para a parcela mínima de 4x a 6x: a tabela de formas de "
        "pagamento indica parcela mínima de R$ 100,00 no cartão de crédito, e as regras de "
        "parcelamento indicam R$ 80,00. As opções marcadas como \"a confirmar\" precisam ser "
        "confirmadas com a equipe da loja."
    ),
    source=f"{MANUAL}, seções 3 e 3.1",
)

LIMITATION_P4 = Limitation(
    code="MANUAL_CONTRADITORIO",
    message=(
        "Para parcelamento em até 3x, o manual diz \"sem valor mínimo de parcela (exceto abaixo de "
        "R$ 50,00)\", enquanto a tabela de formas de pagamento indica parcela mínima de R$ 100,00 no "
        "cartão de crédito. As opções marcadas como \"a confirmar\" precisam ser confirmadas com a "
        "equipe da loja."
    ),
    source=f"{MANUAL}, seções 3 e 3.1",
)

LIMITATION_P12 = Limitation(
    code="MANUAL_OMISSO",
    message=(
        "O manual permite combinar formas de pagamento em compras acima de R$ 2.000,00, mas não "
        "define o caso de exatamente R$ 2.000,00. É preciso confirmar com a equipe da loja."
    ),
    source=f"{MANUAL}, seção 3.1",
)

LIMITATION_P15 = Limitation(
    code="MANUAL_OMISSO",
    message=(
        "Este produto tem mais de uma promoção ativa no sistema. O manual diz que promoções não "
        "são cumulativas, mas não define qual delas vale. O preço final precisa ser confirmado com "
        "a equipe da loja; os valores e parcelas mostrados usam o preço de tabela."
    ),
    source=f"{MANUAL}, seção 6.2; promotions.csv",
)

class ActivePromotion(Protocol):
    """Formato mínimo de promoção usado aqui (compatível com ``data.models.Promotion``).

    Protocolo estrutural para manter ``domain`` independente de ``data`` (ARCHITECTURE §1).
    """

    @property
    def id(self) -> int: ...
    @property
    def discount_percent(self) -> int: ...
    @property
    def description(self) -> str: ...
    @property
    def is_active(self) -> bool: ...


InstallmentStatus = Literal["confirmada", "a_confirmar"]
CombinedPayment = Literal["permitido", "nao_permitido", "a_confirmar"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class InstallmentOption(_Frozen):
    n: int
    value: Decimal
    status: InstallmentStatus


class PromoInfo(_Frozen):
    percent: int
    description: str
    price: Decimal


class PriceQuote(_Frozen):
    list_price: Decimal
    promo: PromoInfo | None
    final_price: Decimal
    pix_price: Decimal | None
    installments: list[InstallmentOption]
    max_confirmed_installments: int | None
    combined_payment: CombinedPayment
    limitations: list[Limitation]


def money(value: Decimal) -> Decimal:
    """Arredonda para centavos (ROUND_HALF_UP) — apenas para exibição."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def format_brl(value: Decimal) -> str:
    """``Decimal("2089.05")`` → ``"R$ 2.089,05"``."""
    text = f"{money(value):,.2f}"
    return "R$ " + text.replace(",", "_").replace(".", ",").replace("_", ".")


def _check_amount(amount: Decimal) -> None:
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
        raise ValueError(f"valor deve ser um Decimal positivo, recebido {amount!r}")


def _classify(n: int, exact_value: Decimal) -> InstallmentStatus | None:
    """Classifica a parcela pelo valor exato (sem arredondar antes de comparar)."""
    if exact_value >= CONFIRMED_MIN_INSTALLMENT:
        return "confirmada"
    if n <= 3:
        return "a_confirmar"  # P4
    if n <= 6 and exact_value >= MID_TIER_MIN_INSTALLMENT:
        return "a_confirmar"  # P3
    return None  # vedada por todas as leituras do manual


def installment_options(amount: Decimal) -> list[InstallmentOption]:
    """Opções de 1x a 12x no cartão de crédito, sem juros. Nunca acima de 12x."""
    _check_amount(amount)
    options = []
    for n in range(1, MAX_INSTALLMENTS + 1):
        exact = amount / n
        status = _classify(n, exact)
        if status is not None:
            options.append(InstallmentOption(n=n, value=money(exact), status=status))
    return options


def _installment_limitations(options: list[InstallmentOption]) -> list[Limitation]:
    pending = [o.n for o in options if o.status == "a_confirmar"]
    limitations = []
    if any(n <= 3 for n in pending):
        limitations.append(LIMITATION_P4)
    if any(4 <= n <= 6 for n in pending):
        limitations.append(LIMITATION_P3)
    return limitations


def combined_payment_status(amount: Decimal) -> CombinedPayment:
    """Pagamento combinado só é permitido estritamente acima de R$ 2.000,00."""
    if amount > COMBINED_PAYMENT_THRESHOLD:
        return "permitido"
    if amount == COMBINED_PAYMENT_THRESHOLD:
        return "a_confirmar"
    return "nao_permitido"


def quote(price: Decimal, active_promotions: list[ActivePromotion]) -> PriceQuote:
    """Cotação de um produto a partir do preço de tabela e das promoções **ativas**."""
    _check_amount(price)
    for promotion in active_promotions:
        if not promotion.is_active:
            raise ValueError(f"promoção #{promotion.id} não está ativa")
        if not 0 < promotion.discount_percent < 100:
            raise ValueError(f"desconto inválido na promoção #{promotion.id}: {promotion.discount_percent}%")

    limitations: list[Limitation] = []
    promo: PromoInfo | None = None
    pix_price: Decimal | None = None

    if len(active_promotions) == 1:
        (promotion,) = active_promotions
        promo = PromoInfo(
            percent=promotion.discount_percent,
            description=promotion.description,
            price=money(price * (100 - promotion.discount_percent) / 100),
        )
        final_price = promo.price  # PIX não incide sobre preço promocional (6.2)
    elif len(active_promotions) > 1:
        final_price = price
        limitations.append(LIMITATION_P15)  # sem preço final confirmado, PIX também não é calculado
    else:
        final_price = price
        pix_price = money(price * (100 - PIX_DISCOUNT_PERCENT) / 100)

    options = installment_options(final_price)
    limitations.extend(_installment_limitations(options))

    combined = combined_payment_status(final_price)
    if combined == "a_confirmar":
        limitations.append(LIMITATION_P12)

    confirmed = [o.n for o in options if o.status == "confirmada"]
    return PriceQuote(
        list_price=price,
        promo=promo,
        final_price=final_price,
        pix_price=pix_price,
        installments=options,
        max_confirmed_installments=max(confirmed) if confirmed else None,
        combined_payment=combined,
        limitations=limitations,
    )
