"""Horário de funcionamento da loja (Manual de Políticas v2.1, seção 2).

Regras confirmadas (DATA_ANALYSIS.md §4.1):

- Segunda a sexta: 09:00 às 18:00; sábado: 09:00 às 13:00; domingo fechado.
- Aberto no intervalo ``[abertura, fechamento)``.
- O fuso decorre do endereço da loja (Campo Grande/MS): ``America/Campo_Grande``.

O sistema não conhece feriados (a loja fecha) nem datas especiais com horário
estendido (Black Friday, Aniversário, Natal); toda resposta carrega essas duas
``Limitation`` — por isso o resultado fala em "horário regular".
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from emporio_agent.domain.limitations import Limitation

STORE_TIMEZONE_DEFAULT = "America/Campo_Grande"

REGULAR_HOURS: dict[int, tuple[time, time]] = {  # chave = datetime.weekday(); domingo ausente
    0: (time(9), time(18)),
    1: (time(9), time(18)),
    2: (time(9), time(18)),
    3: (time(9), time(18)),
    4: (time(9), time(18)),
    5: (time(9), time(13)),
}

MANUAL = "Manual de Políticas v2.1"

LIMITATION_FERIADOS = Limitation(
    code="DADO_NAO_REGISTRADO",
    message=(
        "O sistema não conhece os feriados, e a loja fecha em feriados. O horário informado é o "
        "horário regular; para saber se a loja está aberta em um feriado, confirme com a equipe."
    ),
    source=f"{MANUAL}, seção 2",
)

LIMITATION_DATAS_ESPECIAIS = Limitation(
    code="DADO_NAO_REGISTRADO",
    message=(
        "Em datas especiais (Black Friday, Aniversário da loja, Natal) o horário pode ser "
        "estendido, com aviso nas redes sociais e no WhatsApp. O sistema não registra essas datas."
    ),
    source=f"{MANUAL}, seção 2",
)


class StoreStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_open_regular_hours: bool
    today_hours: str | None
    """``"09:00 às 18:00"``, ``"09:00 às 13:00"`` ou ``None`` (domingo), no dia local de ``now``."""
    next_opening: datetime | None
    """``None`` quando aberto; senão a próxima abertura, no fuso da loja."""
    limitations: list[Limitation]


def _format_hours(opening: time, closing: time) -> str:
    return f"{opening:%H:%M} às {closing:%H:%M}"


def store_status(now: datetime, timezone: str = STORE_TIMEZONE_DEFAULT) -> StoreStatus:
    """Situação da loja em ``now`` segundo o horário regular. Nunca chama ``datetime.now()``."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now deve ter fuso horário (datetime aware)")
    local = now.astimezone(ZoneInfo(timezone))
    limitations = [LIMITATION_FERIADOS, LIMITATION_DATAS_ESPECIAIS]

    today = REGULAR_HOURS.get(local.weekday())
    today_hours = _format_hours(*today) if today else None
    local_time = local.time()

    if today and today[0] <= local_time < today[1]:
        return StoreStatus(
            is_open_regular_hours=True,
            today_hours=today_hours,
            next_opening=None,
            limitations=limitations,
        )

    day = local.date()
    if not today or local_time >= today[1]:
        day += timedelta(days=1)  # já fechou (ou é domingo): procura a partir do dia seguinte
    while day.weekday() not in REGULAR_HOURS:
        day += timedelta(days=1)
    next_opening = datetime.combine(day, REGULAR_HOURS[day.weekday()][0], tzinfo=local.tzinfo)
    return StoreStatus(
        is_open_regular_hours=False,
        today_hours=today_hours,
        next_opening=next_opening,
        limitations=limitations,
    )
