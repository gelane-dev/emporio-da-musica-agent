"""Frete e prazos de entrega (Manual de Políticas v2.1, seções 5.1 e 5.2).

Implementa somente as regras confirmadas do manual (DATA_ANALYSIS.md §4.1).
Pontos omissos geram ``Limitation`` (§4.2: P5, P8, P13):

- Campo Grande (região metropolitana): grátis acima de R$ 500,00; R$ 35,00 abaixo;
  prazo de 1 a 3 dias úteis; entrega por motoboy próprio.
- Exatamente R$ 500,00: não coberto pelo manual ⇒ sem valor de frete (P5).
- Outras cidades: o manual não define os municípios da região metropolitana (P8) e o
  valor depende de CEP, peso e dimensões (5.2) ⇒ sem valor; prazos por transportadora.
- Frete especial (P13): a frase do manual é repassada sem classificar o produto.
- Cidade não informada ⇒ limitação pedindo a cidade.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from emporio_agent.domain.limitations import Limitation
from emporio_agent.domain.text import normalize

FREE_SHIPPING_THRESHOLD = Decimal("500.00")
METRO_FIXED_FEE = Decimal("35.00")
METRO_DEADLINE = "1 a 3 dias úteis"
OTHER_CITIES_DEADLINES = (
    "PAC (Correios): 5 a 12 dias úteis",
    "SEDEX (Correios): 2 a 5 dias úteis",
    "Jadlog (.package): 3 a 8 dias úteis",
)
NOTE_MOTOBOY = "Entrega realizada por motoboy próprio. O cliente será contactado por telefone antes da entrega."
NOTE_SEGURO = "Todos os envios incluem seguro contra extravios e danos durante o transporte."
NOTE_FRETE_ESPECIAL = (
    "Instrumentos de grande porte (baterias acústicas, pianos digitais, contrabaixos) "
    "podem exigir frete especial com cotação individual."
)

MANUAL = "Manual de Políticas v2.1"

_CAMPO_GRANDE_NAMES = {"campo grande", "campo grande ms"}

LIMITATION_P5 = Limitation(
    code="MANUAL_OMISSO",
    message=(
        "O manual diz que o frete na região metropolitana é grátis para compras acima de "
        "R$ 500,00 e custa R$ 35,00 para compras abaixo de R$ 500,00, mas não define o caso de "
        "exatamente R$ 500,00. É preciso confirmar o valor do frete com a equipe da loja."
    ),
    source=f"{MANUAL}, seção 5.1",
)

LIMITATION_P8 = Limitation(
    code="MANUAL_OMISSO",
    message=(
        "O manual não define quais municípios fazem parte da região metropolitana de Campo Grande. "
        "Na região metropolitana, o frete é grátis para compras acima de R$ 500,00 e custa "
        "R$ 35,00 abaixo desse valor, com entrega em 1 a 3 dias úteis. Para esta cidade, é preciso "
        "confirmar com a equipe da loja se essa regra vale."
    ),
    source=f"{MANUAL}, seção 5.1",
)

LIMITATION_VALOR_POR_CEP = Limitation(
    code="DADO_NAO_REGISTRADO",
    message=(
        "Para entregas fora da região metropolitana, o valor do frete é calculado por CEP, peso e "
        "dimensões do produto; o sistema não tem esses dados para informar o valor."
    ),
    source=f"{MANUAL}, seção 5.2",
)

LIMITATION_CIDADE_NAO_INFORMADA = Limitation(
    code="DADO_NAO_REGISTRADO",
    message="A cidade de entrega não foi informada. Pergunte ao cliente a cidade para estimar o frete.",
    source=f"{MANUAL}, seções 5.1 e 5.2",
)

ShippingRegion = Literal["metropolitana", "nao_confirmada"]
FeeStatus = Literal["gratis", "taxa_fixa", "nao_disponivel"]


class ShippingEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)

    region: ShippingRegion
    fee_status: FeeStatus
    fee: Decimal | None
    deadlines: list[str]
    notes: list[str]
    limitations: list[Limitation]


def is_campo_grande(city: str) -> bool:
    return normalize(city) in _CAMPO_GRANDE_NAMES


def shipping_estimate(city: str | None, order_value: Decimal) -> ShippingEstimate:
    """Estimativa de frete para a cidade e o valor do pedido (Decimal finito > 0)."""
    if not isinstance(order_value, Decimal) or not order_value.is_finite() or order_value <= 0:
        raise ValueError(f"order_value deve ser um Decimal positivo, recebido {order_value!r}")

    if city is None or not city.strip():
        return ShippingEstimate(
            region="nao_confirmada",
            fee_status="nao_disponivel",
            fee=None,
            deadlines=[],
            notes=[],
            limitations=[LIMITATION_CIDADE_NAO_INFORMADA],
        )

    if not is_campo_grande(city):
        return ShippingEstimate(
            region="nao_confirmada",
            fee_status="nao_disponivel",
            fee=None,
            deadlines=list(OTHER_CITIES_DEADLINES),
            notes=[NOTE_SEGURO, NOTE_FRETE_ESPECIAL],
            limitations=[LIMITATION_P8, LIMITATION_VALOR_POR_CEP],
        )

    fee_status: FeeStatus
    fee: Decimal | None
    limitations: list[Limitation] = []
    if order_value > FREE_SHIPPING_THRESHOLD:
        fee_status, fee = "gratis", Decimal("0.00")
    elif order_value < FREE_SHIPPING_THRESHOLD:
        fee_status, fee = "taxa_fixa", METRO_FIXED_FEE
    else:
        fee_status, fee = "nao_disponivel", None
        limitations.append(LIMITATION_P5)
    return ShippingEstimate(
        region="metropolitana",
        fee_status=fee_status,
        fee=fee,
        deadlines=[METRO_DEADLINE],
        notes=[NOTE_MOTOBOY],
        limitations=limitations,
    )
