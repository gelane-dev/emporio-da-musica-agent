"""Ferramentas consultar_politica, informacoes_loja e estimar_frete (§5.5.1).

Os dados da loja (endereço, contatos, horários) são extraídos do ``PolicyStore``; nada é digitado aqui.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from pydantic import Field

from emporio_agent.domain.limitations import Limitation
from emporio_agent.domain.pricing import LIMITATION_P3, LIMITATION_P4, LIMITATION_P12, format_brl
from emporio_agent.domain.shipping import LIMITATION_P5, LIMITATION_P8, shipping_estimate
from emporio_agent.domain.store_hours import (
    LIMITATION_DATAS_ESPECIAIS,
    LIMITATION_FERIADOS,
    STORE_TIMEZONE_DEFAULT,
    store_status,
)
from emporio_agent.policies.store import PolicySection, PolicyStore, PolicyTopic
from emporio_agent.tools.base import Tool, ToolArgs, ToolResult
from emporio_agent.tools.limitations import (
    LIMITATION_P1,
    LIMITATION_P2,
    LIMITATION_P6,
    LIMITATION_P7,
    LIMITATION_P13,
    LIMITATION_P14,
)

TOPIC_LIMITATIONS: dict[str, list[Limitation]] = {
    "pagamento": [LIMITATION_P3, LIMITATION_P4, LIMITATION_P12],
    "trocas_devolucoes": [LIMITATION_P6, LIMITATION_P7, LIMITATION_P14],
    "frete_entrega": [LIMITATION_P5, LIMITATION_P8, LIMITATION_P13],
    "sobre_loja": [LIMITATION_P1, LIMITATION_P2],
    "atendimento": [LIMITATION_P1],
    "horarios": [LIMITATION_FERIADOS, LIMITATION_DATAS_ESPECIAIS],
}

WEEKDAYS_PT = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo",
)


# --- consultar_politica -------------------------------------------------------


class ConsultarPoliticaArgs(ToolArgs):
    topico: PolicyTopic = Field(description="Tópico do manual de políticas da loja.")


class ConsultarPolitica(Tool):
    name = "consultar_politica"
    description = (
        "Consulta o texto oficial do manual de políticas da loja por tópico: sobre_loja, horarios, "
        "pagamento, trocas_devolucoes, frete_entrega, promocoes, atendimento, garantia, "
        "privacidade. Use para regras (parcelamento, trocas, devoluções, frete, garantia, "
        "promoções). Para preços e estoque de produtos use detalhar_produto; para endereço, "
        "contatos e horário de hoje use informacoes_loja. Repasse as limitações retornadas."
    )
    args_model = ConsultarPoliticaArgs

    def __init__(self, policies: PolicyStore):
        self._policies = policies

    def run(self, args: ConsultarPoliticaArgs) -> ToolResult:  # type: ignore[override]
        sections = self._policies.get(args.topico)
        data = {
            "topico": args.topico,
            "secoes": [{"titulo": s.title, "fonte": s.source, "texto": s.text} for s in sections],
        }
        return ToolResult.success(data, TOPIC_LIMITATIONS.get(args.topico, []))


# --- informacoes_loja ---------------------------------------------------------


class StoreInfoError(Exception):
    """O ``PolicyStore`` não tem a informação esperada no formato esperado."""


_ROW_RE = re.compile(r"^\|\s*(?P<key>[^|]+?)\s*\|\s*(?P<value>[^|]+?)\s*\|\s*$")
_SUBSECTION_RE = re.compile(r"^###\s+(\d+(?:\.\d+)*)\b")
_EMAIL_RE = re.compile(r"[^\s|<>()]+@[^\s|<>()]+")
_WHATSAPP_RE = re.compile(r"WhatsApp\s*(\(\d{2}\)\s*\d{4,5}-\d{4})")


def _table_rows(section: PolicySection) -> list[tuple[str, str, str]]:
    """Linhas de tabela como (chave, valor, fonte); a fonte cita a subseção ``###`` quando houver."""
    base = section.source.rsplit(", ", 1)[0]
    subsection: str | None = None
    rows = []
    for line in section.text.splitlines():
        heading = _SUBSECTION_RE.match(line)
        if heading:
            subsection = heading.group(1)
            continue
        row = _ROW_RE.match(line.strip())
        if row and not set(row["key"]) <= set("-: "):
            source = f"{base}, seção {subsection}" if subsection else section.source
            rows.append((row["key"], row["value"], source))
    return rows


def _find_section(store: PolicyStore, topic: str, title_start: str) -> PolicySection:
    for section in store.get(topic):
        if section.title.startswith(title_start):
            return section
    raise StoreInfoError(f"seção '{title_start}' não encontrada no tópico {topic}")


def _field(rows: list[tuple[str, str, str]], key: str) -> tuple[str, str]:
    for k, value, source in rows:
        if k.casefold() == key.casefold():
            return value, source
    raise StoreInfoError(f"campo '{key}' não encontrado")


def extract_store_info(store: PolicyStore) -> dict:
    """Nome, endereço, contatos e horários, lidos do texto do manual."""
    company = _find_section(store, "sobre_loja", "1.")
    cover = _find_section(store, "sobre_loja", "Capa")
    support = _find_section(store, "atendimento", "7.")
    schedule = _find_section(store, "horarios", "2.")

    rows = _table_rows(company)
    name, _ = _field(rows, "Nome Fantasia")
    address, _ = _field(rows, "Endereço")
    phone, phone_source = _field(rows, "Telefone / WhatsApp")
    email, email_source = _field(rows, "E-mail")

    cover_email = _EMAIL_RE.search(cover.text)
    whatsapp = _WHATSAPP_RE.search(support.text)
    if not cover_email or not whatsapp:
        raise StoreInfoError("e-mail da capa ou WhatsApp da seção 7 não encontrados")

    hours = [
        {"dias": key, "horario": value}
        for key, value, _ in _table_rows(schedule)
        if key.casefold() != "dia"
    ]
    if not hours:
        raise StoreInfoError("tabela de horários não encontrada")

    return {
        "nome": name,
        "endereco": address,
        "contatos": [
            {"tipo": "telefone_whatsapp", "valor": phone, "rotulo_no_manual": "Telefone / WhatsApp", "fonte": phone_source},
            {"tipo": "whatsapp", "valor": whatsapp.group(1), "rotulo_no_manual": "canal de WhatsApp", "fonte": support.source},
            {"tipo": "email", "valor": email, "rotulo_no_manual": "E-mail", "fonte": email_source},
            {"tipo": "email", "valor": cover_email.group(0).rstrip(".,;"), "rotulo_no_manual": "e-mail da capa", "fonte": cover.source},
        ],
        "horarios": hours,
    }


def _moment(value: datetime) -> dict:
    return {
        "data": value.strftime("%d/%m/%Y"),
        "hora": value.strftime("%H:%M"),
        "dia_semana": WEEKDAYS_PT[value.weekday()],
    }


class InformacoesLojaArgs(ToolArgs):
    pass


class InformacoesLoja(Tool):
    name = "informacoes_loja"
    description = (
        "Informa endereço, telefones/WhatsApp, e-mails e horários da loja, e se ela está aberta "
        "agora (horário regular) com a próxima abertura. Use para perguntas como \"onde fica\", "
        "\"qual o telefone\", \"estão abertos?\". Os contatos têm divergências no manual: repasse "
        "todos, com a origem, e as limitações."
    )
    args_model = InformacoesLojaArgs

    def __init__(self, policies: PolicyStore, clock: Callable[[], datetime]):
        self._policies = policies
        self._clock = clock

    def run(self, args: InformacoesLojaArgs) -> ToolResult:  # type: ignore[override]
        try:
            data = extract_store_info(self._policies)
        except StoreInfoError as exc:
            return ToolResult.failure(
                "INTERNAL_ERROR",
                f"Não foi possível ler as informações da loja no manual ({exc}). Avise o cliente do "
                "problema técnico e não invente endereço, contatos ou horários.",
            )
        now = self._clock()
        status = store_status(now)
        local = now.astimezone(ZoneInfo(STORE_TIMEZONE_DEFAULT))
        data["aberto_agora_horario_regular"] = status.is_open_regular_hours
        data["horario_hoje"] = status.today_hours
        if status.next_opening is not None:
            data["proxima_abertura"] = _moment(status.next_opening)
        data["referencia"] = _moment(local)
        limitations = [LIMITATION_P1, LIMITATION_P2, *status.limitations]
        return ToolResult.success(data, limitations)


# --- estimar_frete ------------------------------------------------------------


class EstimarFreteArgs(ToolArgs):
    cidade: str | None = Field(default=None, max_length=120, description="Cidade de entrega, se o cliente informou.")
    valor_pedido: float = Field(gt=0, allow_inf_nan=False, description="Valor do pedido em reais.")


class EstimarFrete(Tool):
    name = "estimar_frete"
    description = (
        "Estima frete e prazo de entrega a partir da cidade e do valor do pedido, conforme o manual "
        "(Campo Grande: taxa e prazo; outras cidades: prazos por modalidade, valor depende do CEP). "
        "Use quando o cliente perguntar sobre frete ou prazo de entrega. Se a cidade não foi "
        "informada, pergunte antes. Repasse as limitações."
    )
    args_model = EstimarFreteArgs

    def run(self, args: EstimarFreteArgs) -> ToolResult:  # type: ignore[override]
        estimate = shipping_estimate(args.cidade, Decimal(str(args.valor_pedido)))
        data = {
            "regiao": estimate.region,
            "situacao_taxa": estimate.fee_status,
            "taxa": format_brl(estimate.fee) if estimate.fee is not None else None,
            "prazos": list(estimate.deadlines),
            "observacoes": list(estimate.notes),
        }
        return ToolResult.success(data, estimate.limitations)
