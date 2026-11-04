"""Testes da T12: ``encaminhar_atendente`` (ARCHITECTURE §5.5.2)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.config import REPO_ROOT
from emporio_agent.data.repository import CatalogRepository, OrderRepository
from emporio_agent.policies.store import PolicyStore
from emporio_agent.tools import build_tool_registry
from emporio_agent.tools.base import ToolResult
from emporio_agent.tools.handoff_tools import EncaminharAtendente

TZ = ZoneInfo("America/Campo_Grande")
NOW = datetime(2026, 11, 1, 15, 47, tzinfo=TZ)
PROTOCOLO_RE = re.compile(r"^EM-20261101-[0-9A-F]{6}$")

SEVEN = [
    "buscar_produtos",
    "detalhar_produto",
    "listar_categorias",
    "consultar_pedido",
    "consultar_politica",
    "informacoes_loja",
    "estimar_frete",
]


@pytest.fixture(scope="module")
def policies() -> PolicyStore:
    return PolicyStore.from_markdown(REPO_ROOT / "knowledge" / "policies.md")


@pytest.fixture
def runtime(tmp_path) -> Path:
    return tmp_path / "runtime"  # não existe ainda: a tool precisa criar


@pytest.fixture
def tool(runtime) -> EncaminharAtendente:
    return EncaminharAtendente(runtime, lambda: NOW)


def call(tool: EncaminharAtendente, **kwargs) -> ToolResult:
    return tool.run(tool.args_model(**kwargs))


def records(runtime: Path) -> list[dict]:
    path = runtime / "handoffs.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def lim_codes(result: ToolResult) -> list[str]:
    return [lim.code for lim in result.limitations]


# ----------------------------------------------------------------------------- metadados


def test_nome_e_args_model(tool):
    assert tool.name == "encaminhar_atendente"
    assert tool.description
    schema = tool.args_model.model_json_schema()
    assert set(schema["properties"]) == {"motivo", "resumo", "pedido_id"}
    assert set(schema["required"]) == {"motivo", "resumo"}


# ----------------------------------------------------------------------------- protocolo e arquivo


def test_protocolo_no_formato_e_dados(tool):
    result = call(tool, motivo="reclamacao", resumo="Produto chegou com defeito.", pedido_id=19)
    assert result.ok
    assert PROTOCOLO_RE.match(result.data["protocolo"])
    assert result.data["motivo"] == "reclamacao"
    assert "prazo_retorno" in result.data


def test_protocolo_usa_data_do_clock(runtime):
    other = datetime(2027, 3, 9, 8, 0, tzinfo=TZ)
    result = call(EncaminharAtendente(runtime, lambda: other), motivo="reclamacao", resumo="x")
    assert re.match(r"^EM-20270309-[0-9A-F]{6}$", result.data["protocolo"])


def test_protocolos_unicos(tool):
    protos = {call(tool, motivo="reclamacao", resumo=f"caso {i}").data["protocolo"] for i in range(50)}
    assert len(protos) == 50


def test_cria_pasta_e_arquivo(tool, runtime):
    assert not runtime.exists()
    call(tool, motivo="caso_complexo", resumo="Situação especial.")
    assert (runtime / "handoffs.jsonl").is_file()


def test_uma_linha_json_por_chamada_com_campos_do_contrato(tool, runtime):
    r1 = call(tool, motivo="reclamacao", resumo="Primeiro caso.", pedido_id=19)
    r2 = call(tool, motivo="pedido_cliente", resumo="Quero falar com alguém.")
    raw = (runtime / "handoffs.jsonl").read_text(encoding="utf-8")
    assert raw.endswith("\n")
    recs = records(runtime)
    assert len(recs) == 2
    assert all(set(r) == {"protocolo", "criado_em", "motivo", "resumo", "pedido_id"} for r in recs)
    assert [r["protocolo"] for r in recs] == [r1.data["protocolo"], r2.data["protocolo"]]
    assert recs[0]["pedido_id"] == 19 and recs[1]["pedido_id"] is None
    assert recs[0]["motivo"] == "reclamacao" and recs[1]["motivo"] == "pedido_cliente"
    assert recs[0]["resumo"] == "Primeiro caso."


def test_criado_em_iso_com_fuso(tool, runtime):
    call(tool, motivo="reclamacao", resumo="x")
    criado = datetime.fromisoformat(records(runtime)[0]["criado_em"])
    assert criado.tzinfo is not None
    assert criado == NOW


def test_acrescenta_sem_sobrescrever_arquivo_existente(runtime):
    runtime.mkdir()
    (runtime / "handoffs.jsonl").write_text('{"antigo": true}\n', encoding="utf-8")
    call(EncaminharAtendente(runtime, lambda: NOW), motivo="reclamacao", resumo="novo")
    recs = records(runtime)
    assert recs[0] == {"antigo": True}
    assert len(recs) == 2


def test_utf8_preservado(tool, runtime):
    call(tool, motivo="reclamacao", resumo="Cliente muito insatisfeito: violão com defeito na ação.")
    assert "violão" in (runtime / "handoffs.jsonl").read_text(encoding="utf-8")
    assert "violão" in records(runtime)[0]["resumo"]


def test_resumo_multilinha_continua_uma_linha_no_arquivo(tool, runtime):
    call(tool, motivo="reclamacao", resumo="linha 1\nlinha 2")
    assert len((runtime / "handoffs.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert records(runtime)[0]["resumo"] == "linha 1 linha 2"


# ----------------------------------------------------------------------------- mascaramento


def test_mascara_email(tool, runtime):
    call(tool, motivo="reclamacao", resumo="Cliente joao.silva+x@jmail.com reclamou do atraso.")
    resumo = records(runtime)[0]["resumo"]
    assert "jmail" not in resumo and "@" not in resumo
    assert resumo == "Cliente [e-mail removido] reclamou do atraso."


def test_mascara_varios_emails(tool, runtime):
    call(tool, motivo="reclamacao", resumo="a@b.com e Outro.Mail@Dominio.com.br")
    assert records(runtime)[0]["resumo"] == "[e-mail removido] e [e-mail removido]"


@pytest.mark.parametrize(
    "texto",
    [
        "67984321098",
        "(67) 98432-1098",
        "67 98432 1098",
        "67.98432.1098",
        "+55 (67) 98432-1098",
        "12345678",
    ],
)
def test_mascara_numeros_longos(tool, runtime, texto):
    call(tool, motivo="reclamacao", resumo=f"Ligar para {texto} amanhã")
    resumo = records(runtime)[0]["resumo"]
    assert "[número removido]" in resumo
    assert not re.search(r"\d{4}", resumo)
    assert resumo.startswith("Ligar para ") and resumo.endswith("amanhã")


def test_nao_mascara_numeros_curtos(tool, runtime):
    call(tool, motivo="reclamacao", resumo="Pedido 19, 3 itens, R$ 1.299,00, 12x")
    assert records(runtime)[0]["resumo"] == "Pedido 19, 3 itens, R$ 1.299,00, 12x"


def test_mascara_antes_de_gravar_e_nao_aparece_em_lugar_nenhum_do_arquivo(tool, runtime):
    call(tool, motivo="reclamacao", resumo="x@y.com tel 67984321098", pedido_id=3)
    raw = (runtime / "handoffs.jsonl").read_text(encoding="utf-8")
    assert "x@y.com" not in raw and "67984321098" not in raw


def test_resultado_ao_llm_nao_vaza_dados(tool):
    result = call(tool, motivo="reclamacao", resumo="x@y.com 67984321098")
    payload = result.to_llm()
    assert "x@y.com" not in payload and "67984321098" not in payload


# ----------------------------------------------------------------------------- prazo / limitação


def test_reclamacao_tem_prazo_24_horas_uteis(tool):
    result = call(tool, motivo="reclamacao", resumo="Produto com defeito.")
    assert result.data["prazo_retorno"] == "24 horas úteis"
    assert "MANUAL_OMISSO" not in lim_codes(result)


@pytest.mark.parametrize("motivo", ["caso_complexo", "pedido_cliente"])
def test_outros_motivos_sem_prazo_e_com_limitacao(tool, motivo):
    result = call(tool, motivo=motivo, resumo="Preciso de ajuda.")
    assert result.ok
    assert result.data["prazo_retorno"] is None
    assert result.data["motivo"] == motivo
    assert "MANUAL_OMISSO" in lim_codes(result)
    lim = next(l for l in result.limitations if l.code == "MANUAL_OMISSO")
    assert "prazo" in lim.message.lower() and "reclama" in lim.message.lower()


def test_to_llm_serializa_prazo_nulo_e_limitacao(tool):
    payload = json.loads(call(tool, motivo="pedido_cliente", resumo="ajuda").to_llm())
    assert payload["ok"] is True
    assert payload["dados"]["prazo_retorno"] is None
    assert [l["codigo"] for l in payload["limitacoes"]] == ["MANUAL_OMISSO"]


# ----------------------------------------------------------------------------- validação (via registry)


@pytest.fixture
def registry(store_data, policies, runtime):
    return build_tool_registry(
        CatalogRepository(store_data), OrderRepository(store_data), policies, lambda: NOW, runtime_dir=runtime
    )


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"motivo": "reclamacao"},
        {"resumo": "sem motivo"},
        {"motivo": "outro", "resumo": "motivo inválido"},
        {"motivo": "reclamacao", "resumo": ""},
        {"motivo": "reclamacao", "resumo": "   "},
        {"motivo": "reclamacao", "resumo": "x" * 1001},
        {"motivo": "reclamacao", "resumo": "ok", "pedido_id": 0},
        {"motivo": "reclamacao", "resumo": "ok", "pedido_id": -3},
        {"motivo": "reclamacao", "resumo": "ok", "extra": 1},
    ],
)
def test_argumentos_invalidos_viram_invalid_argument_e_nao_gravam(registry, runtime, args):
    result = registry.execute("encaminhar_atendente", args)
    assert not result.ok
    assert result.error.code == "INVALID_ARGUMENT"
    assert not (runtime / "handoffs.jsonl").exists()


def test_resumo_no_limite_1000_e_aceito_e_espacos_nas_pontas_sao_removidos(registry, runtime):
    assert registry.execute("encaminhar_atendente", {"motivo": "reclamacao", "resumo": "x" * 1000}).ok
    result = registry.execute("encaminhar_atendente", {"motivo": "reclamacao", "resumo": "  texto  "})
    assert result.ok
    assert records(runtime)[-1]["resumo"] == "texto"


def test_falha_de_escrita_vira_internal_error(store_data, policies, tmp_path):
    blocker = tmp_path / "arquivo"
    blocker.write_text("não sou pasta", encoding="utf-8")
    registry = build_tool_registry(
        CatalogRepository(store_data),
        OrderRepository(store_data),
        policies,
        lambda: NOW,
        runtime_dir=blocker / "sub",
    )
    result = registry.execute("encaminhar_atendente", {"motivo": "reclamacao", "resumo": "x"})
    assert not result.ok
    assert result.error.code == "INTERNAL_ERROR"


# ----------------------------------------------------------------------------- registry 8 x 7


def test_com_runtime_dir_sao_8_ferramentas_com_handoff_por_ultimo(registry):
    assert registry.names() == [*SEVEN, "encaminhar_atendente"]
    assert len(registry.specs()) == 8
    spec = next(s for s in registry.specs() if s.name == "encaminhar_atendente")
    assert spec.input_schema["properties"]["motivo"]


def test_sem_runtime_dir_continuam_7(store_data, policies):
    reg = build_tool_registry(CatalogRepository(store_data), OrderRepository(store_data), policies, lambda: NOW)
    assert reg.names() == SEVEN
    assert reg.execute("encaminhar_atendente", {"motivo": "reclamacao", "resumo": "x"}).error.code == "INVALID_ARGUMENT"


def test_execucao_via_registry_grava(registry, runtime):
    result = registry.execute("encaminhar_atendente", {"motivo": "reclamacao", "resumo": "Defeito", "pedido_id": 5})
    assert result.ok and PROTOCOLO_RE.match(result.data["protocolo"])
    assert records(runtime)[0]["pedido_id"] == 5
