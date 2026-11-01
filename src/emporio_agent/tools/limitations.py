"""Limitações usadas pelas tools e não definidas no domínio (DATA_ANALYSIS.md §4.2).

O domínio já define P3, P4, P12, P15 (pricing), P5, P8, valor por CEP, cidade não informada
(shipping), feriados e datas especiais (store_hours).
"""

from __future__ import annotations

from emporio_agent.data.models import ProductConflict
from emporio_agent.domain.limitations import Limitation

MANUAL = "Manual de Políticas v2.1"

LIMITATION_P1 = Limitation(
    code="MANUAL_CONTRADITORIO",
    message=(
        "O manual cita dois números de WhatsApp diferentes: um nos dados da empresa (seção 1.2) e "
        "outro no atendimento via WhatsApp (seção 7). Não afirme qual deles é o correto; informe "
        "os dois, cada um com a sua origem, e sugira confirmar com a equipe da loja."
    ),
    source=f"{MANUAL}, seções 1.2 e 7",
)

LIMITATION_P2 = Limitation(
    code="MANUAL_CONTRADITORIO",
    message=(
        "O manual traz duas grafias do e-mail da loja: uma na capa (sem acento) e outra nos dados "
        "da empresa (seção 1.2, com acento). Não afirme qual é a correta; informe as duas, cada "
        "uma com a sua origem, e sugira confirmar com a equipe da loja."
    ),
    source=f"{MANUAL}, capa e seção 1.2",
)

LIMITATION_P6 = Limitation(
    code="DADO_NAO_REGISTRADO",
    message=(
        "O pedido não registra se a compra foi online ou presencial, e o direito de arrependimento "
        "do manual vale para compras online. Pergunte ao cliente onde comprou; não conclua sozinho."
    ),
    source=f"{MANUAL}, seção 4.1; orders.csv",
)

LIMITATION_P7 = Limitation(
    code="DADO_NAO_REGISTRADO",
    message=(
        "O sistema não registra a data real de recebimento do pedido, apenas a previsão de entrega, "
        "que é uma estimativa. Os prazos de arrependimento contam a partir do recebimento, então "
        "não é possível confirmar se um prazo está dentro ou fora; encaminhe a confirmação à equipe."
    ),
    source=f"{MANUAL}, seção 4.1; orders.csv",
)

LIMITATION_P13 = Limitation(
    code="MANUAL_OMISSO",
    message=(
        "O manual diz que instrumentos de grande porte (baterias acústicas, pianos digitais, "
        "contrabaixos) podem exigir frete especial, mas não define quais produtos do catálogo se "
        "enquadram. Não classifique um produto; confirme a cotação com a equipe da loja."
    ),
    source=f"{MANUAL}, seção 5.2",
)

LIMITATION_P14 = Limitation(
    code="MANUAL_OMISSO",
    message=(
        "Para trocas por preferência o manual diz \"até 7 dias\", sem dizer se a contagem começa na "
        "compra ou no recebimento. Informe o prazo como está no manual e confirme com a equipe a "
        "data de referência."
    ),
    source=f"{MANUAL}, seção 4.3",
)

LIMITATION_EM_BREVE = Limitation(
    code="MANUAL_OMISSO",
    message=(
        "Este produto está com status \"em breve\", que o manual não define. Não é possível "
        "confirmar que ele já pode ser comprado nem informar data de lançamento; confirme "
        "a disponibilidade com a equipe da loja."
    ),
    source="products.csv (status coming_soon)",
)


def conflict_limitation(product_id: int, conflicts: list[ProductConflict]) -> Limitation:
    """Limitação ``DADO_CONFLITANTE`` descrevendo as divergências do cadastro do produto."""
    lines = []
    for conflict in conflicts:
        values = "; ".join(f"{field}: {value}" for field, value in conflict.values.items())
        lines.append(f"{conflict.note} ({values})")
    return Limitation(
        code="DADO_CONFLITANTE",
        message=(
            f"O cadastro do produto #{product_id} tem informações que se contradizem: "
            + " ".join(lines)
            + " Não afirme nenhum dos lados como correto; informe a divergência ao cliente e "
            "sugira confirmar com a equipe da loja."
        ),
        source=f"products.csv #{product_id}",
    )
