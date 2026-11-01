"""Testes da T05 (horários): contrato em ARCHITECTURE §5.3.1, manual seção 2."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.domain import store_hours
from emporio_agent.domain.store_hours import (
    LIMITATION_DATAS_ESPECIAIS,
    LIMITATION_FERIADOS,
    STORE_TIMEZONE_DEFAULT,
    store_status,
)

CG = ZoneInfo("America/Campo_Grande")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Datas de 2026-11: 02=seg, 03=ter, 06=sex, 07=sáb, 08=dom, 09=seg."""
    return datetime(2026, 11, day, hour, minute, tzinfo=CG)


# --- aberto / fechado -----------------------------------------------------------

def test_default_timezone_constant():
    assert STORE_TIMEZONE_DEFAULT == "America/Campo_Grande"


def test_monday_10_is_open():
    s = store_status(at(2, 10))
    assert s.is_open_regular_hours is True
    assert s.today_hours == "09:00 às 18:00"
    assert s.next_opening is None


@pytest.mark.parametrize("day", [2, 3, 4, 5, 6])
def test_weekdays_open_at_09_00_inclusive(day):
    s = store_status(at(day, 9, 0))
    assert s.is_open_regular_hours is True
    assert s.next_opening is None


@pytest.mark.parametrize("day", [2, 3, 4, 5, 6])
def test_weekdays_open_at_17_59(day):
    assert store_status(at(day, 17, 59)).is_open_regular_hours is True


def test_monday_18_00_is_closed_closing_exclusive():
    s = store_status(at(2, 18, 0))
    assert s.is_open_regular_hours is False
    assert s.today_hours == "09:00 às 18:00"
    assert s.next_opening == at(3, 9, 0)


def test_monday_08_59_closed_next_opening_same_day():
    s = store_status(at(2, 8, 59))
    assert s.is_open_regular_hours is False
    assert s.today_hours == "09:00 às 18:00"
    assert s.next_opening == at(2, 9, 0)


def test_saturday_12_59_is_open():
    s = store_status(at(7, 12, 59))
    assert s.is_open_regular_hours is True
    assert s.today_hours == "09:00 às 13:00"
    assert s.next_opening is None


def test_saturday_09_00_is_open():
    assert store_status(at(7, 9, 0)).is_open_regular_hours is True


def test_saturday_13_00_is_closed():
    s = store_status(at(7, 13, 0))
    assert s.is_open_regular_hours is False
    assert s.today_hours == "09:00 às 13:00"
    assert s.next_opening == at(9, 9, 0)  # segunda 09:00


def test_saturday_before_opening_next_opening_same_day():
    s = store_status(at(7, 8, 0))
    assert s.is_open_regular_hours is False
    assert s.next_opening == at(7, 9, 0)


def test_sunday_closed_no_hours_next_opening_monday():
    s = store_status(at(8, 11, 0))
    assert s.is_open_regular_hours is False
    assert s.today_hours is None
    assert s.next_opening == at(9, 9, 0)
    assert s.next_opening.weekday() == 0


@pytest.mark.parametrize("hour,minute", [(0, 0), (23, 59)])
def test_sunday_any_time_next_monday(hour, minute):
    s = store_status(at(8, hour, minute))
    assert s.is_open_regular_hours is False
    assert s.today_hours is None
    assert s.next_opening == at(9, 9, 0)


def test_friday_19_00_next_opening_saturday_09_00():
    s = store_status(at(6, 19, 0))
    assert s.is_open_regular_hours is False
    assert s.next_opening == at(7, 9, 0)
    assert s.next_opening.weekday() == 5


def test_saturday_14_00_next_opening_monday_09_00():
    s = store_status(at(7, 14, 0))
    assert s.is_open_regular_hours is False
    assert s.next_opening == at(9, 9, 0)


def test_tuesday_after_closing_next_opening_wednesday():
    assert store_status(at(3, 20, 0)).next_opening == at(4, 9, 0)


# --- fuso horário -----------------------------------------------------------------

def test_utc_input_converted_to_store_timezone_open():
    # 13:30Z = 09:30 em Campo Grande (UTC-4) numa segunda ⇒ aberto
    s = store_status(datetime(2026, 11, 2, 13, 30, tzinfo=timezone.utc))
    assert s.is_open_regular_hours is True
    assert s.today_hours == "09:00 às 18:00"
    assert s.next_opening is None


def test_utc_input_converted_to_store_timezone_closed():
    # 12:30Z = 08:30 local ⇒ fechado, abre 09:00 local no mesmo dia
    s = store_status(datetime(2026, 11, 2, 12, 30, tzinfo=timezone.utc))
    assert s.is_open_regular_hours is False
    assert s.next_opening == at(2, 9, 0)


def test_local_day_is_used_not_utc_day():
    # 01:00Z de segunda 09/11 = 21:00 de domingo 08/11 em Campo Grande
    s = store_status(datetime(2026, 11, 9, 1, 0, tzinfo=timezone.utc))
    assert s.today_hours is None
    assert s.is_open_regular_hours is False
    assert s.next_opening == at(9, 9, 0)


def test_next_opening_is_in_store_timezone():
    s = store_status(datetime(2026, 11, 2, 23, 0, tzinfo=timezone.utc))  # 19:00 local
    assert s.is_open_regular_hours is False
    assert s.next_opening == at(3, 9, 0)
    assert s.next_opening.utcoffset() == timedelta(hours=-4)
    assert (s.next_opening.hour, s.next_opening.minute) == (9, 0)


def test_next_opening_uses_campo_grande_offset_for_foreign_offset_input():
    # sexta 22:00 em UTC-3 = 21:00 local
    s = store_status(datetime(2026, 11, 6, 22, 0, tzinfo=timezone(timedelta(hours=-3))))
    assert s.next_opening.utcoffset() == timedelta(hours=-4)
    assert s.next_opening == at(7, 9, 0)


def test_explicit_timezone_argument_is_used():
    now = datetime(2026, 11, 2, 13, 30, tzinfo=timezone.utc)
    # São Paulo (UTC-3): 10:30 de segunda ⇒ aberto; Tóquio (UTC+9): 22:30 ⇒ fechado
    assert store_status(now, "America/Sao_Paulo").is_open_regular_hours is True
    tokyo = store_status(now, "Asia/Tokyo")
    assert tokyo.is_open_regular_hours is False
    assert tokyo.next_opening == datetime(2026, 11, 3, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


def test_naive_datetime_raises_value_error():
    with pytest.raises(ValueError):
        store_status(datetime(2026, 11, 2, 10, 0))


# --- determinismo (sem relógio da máquina) -------------------------------------------

@pytest.mark.parametrize("year,monday", [(2020, 2), (2030, 4)])  # 2020-03-02 e 2030-03-04 são segundas
def test_deterministic_for_past_and_future_mondays(year, monday):
    s = store_status(datetime(year, 3, monday, 10, 0, tzinfo=CG))
    assert s.is_open_regular_hours is True
    assert s.next_opening is None
    s = store_status(datetime(year, 3, monday, 18, 0, tzinfo=CG))
    assert s.is_open_regular_hours is False
    assert s.next_opening == datetime(year, 3, monday + 1, 9, 0, tzinfo=CG)


@pytest.mark.parametrize("year,sunday", [(2020, 1), (2030, 3)])  # 2020-03-01 e 2030-03-03 são domingos
def test_deterministic_for_past_and_future_sundays(year, sunday):
    s = store_status(datetime(year, 3, sunday, 12, 0, tzinfo=CG))
    assert s.is_open_regular_hours is False
    assert s.today_hours is None
    assert s.next_opening == datetime(year, 3, sunday + 1, 9, 0, tzinfo=CG)


def test_same_input_same_output():
    now = at(2, 10)
    assert store_status(now) == store_status(now)


# --- limitações ---------------------------------------------------------------------

@pytest.mark.parametrize("now", [at(2, 10), at(2, 18), at(7, 13), at(8, 12), at(6, 19)])
def test_limitations_always_present_and_identical(now):
    s = store_status(now)
    assert s.limitations == [LIMITATION_FERIADOS, LIMITATION_DATAS_ESPECIAIS]
    assert s.limitations[0] is LIMITATION_FERIADOS
    assert s.limitations[1] is LIMITATION_DATAS_ESPECIAIS


def test_limitation_codes_sources_and_keywords():
    for lim in (LIMITATION_FERIADOS, LIMITATION_DATAS_ESPECIAIS):
        assert lim.code == "DADO_NAO_REGISTRADO"
        assert lim.source == "Manual de Políticas v2.1, seção 2"
    assert "feriado" in LIMITATION_FERIADOS.message.lower()
    assert "black friday" in LIMITATION_DATAS_ESPECIAIS.message.lower()


def test_status_model_is_frozen():
    s = store_status(at(2, 10))
    with pytest.raises(Exception):
        s.is_open_regular_hours = False


# --- arquitetura ----------------------------------------------------------------------

def test_domain_does_not_import_data_or_config_layers():
    source = Path(store_hours.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not any(m.startswith(("emporio_agent.data", "emporio_agent.config")) for m in imported)
