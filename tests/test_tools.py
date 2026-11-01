"""Testes da T09: ferramentas e registry (ARCHITECTURE §5.5.1), exercitados via ``registry.execute``."""

from __future__ import annotations

import dataclasses
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from pydantic import BaseModel, ConfigDict

from emporio_agent.config import REPO_ROOT
from emporio_agent.data.repository import CatalogRepository, OrderRepository
from emporio_agent.domain.limitations import Limitation
from emporio_agent.domain.pricing import LIMITATION_P3, LIMITATION_P4, LIMITATION_P12, LIMITATION_P15
from emporio_agent.domain.shipping import LIMITATION_P5, LIMITATION_P8, LIMITATION_VALOR_POR_CEP
from emporio_agent.domain.store_hours import LIMITATION_DATAS_ESPECIAIS, LIMITATION_FERIADOS
from emporio_agent.policies.store import POLICY_TOPICS, PolicyStore
from emporio_agent.tools import build_tool_registry
from emporio_agent.tools import limitations as tl
from emporio_agent.tools.base import Tool, ToolRegistry, ToolResult

POLICIES_MD = REPO_ROOT / "knowledge" / "policies.md"
TZ = ZoneInfo("America/Campo_Grande")
SUNDAY = datetime(2026, 11, 1, 15, 47, tzinfo=TZ)
MONDAY = datetime(2026, 11, 2, 10, 0, tzinfo=TZ)

EXPECTED_TOOLS = [
    "buscar_produtos",
    "detalhar_produto",
    "listar_categorias",
    "consultar_pedido",
    "consultar_politica",
    "informacoes_loja",
    "estimar_frete",
]
MONEY_RE = re.compile(r"^R\$ \d{1,3}(\.\d{3})*,\d{2}$")


# ----------------------------------------------------------------------------- fixtures / helpers


@pytest.fixture(scope="module")
def policies() -> PolicyStore:
    return PolicyStore.from_markdown(POLICIES_MD)


@pytest.fixture(scope="module")
def registry(store_data, policies) -> ToolRegistry:
    return build_tool_registry(
        CatalogRepository(store_data), OrderRepository(store_data), policies, lambda: SUNDAY
    )


def make_registry(store_data, policies, now: datetime) -> ToolRegistry:
    return build_tool_registry(CatalogRepository(store_data), OrderRepository(store_data), policies, lambda: now)


def run(registry: ToolRegistry, name: str, **kwargs) -> dict:
    """Executa e devolve o JSON do ``to_llm()`` já decodificado (o que o LLM enxerga)."""
    result = registry.execute(name, kwargs)
    assert isinstance(result, ToolResult)
    return json.loads(result.to_llm())


def codes(payload: dict) -> list[str]:
    return [lim["codigo"] for lim in payload.get("limitacoes", [])]


def lim_messages(payload: dict) -> list[str]:
    return [lim["mensagem"] for lim in payload.get("limitacoes", [])]


def has_limitation(payload: dict, limitation: Limitation) -> bool:
    return any(
        lim["codigo"] == limitation.code and lim["mensagem"] == limitation.message
        for lim in payload.get("limitacoes", [])
    )


def walk(obj):
    """Gera (chave, valor) de todos os nós de um JSON decodificado."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def products(payload: dict) -> list[dict]:
    return payload["dados"]["produtos"]


# ----------------------------------------------------------------------------- specs e registry


def test_specs_tem_as_sete_tools_com_schema_valido(registry):
    specs = registry.specs()
    assert [s.name for s in specs] == EXPECTED_TOOLS
    assert registry.names() == EXPECTED_TOOLS
    for spec in specs:
        assert spec.description.strip(), spec.name
        assert spec.input_schema["type"] == "object", spec.name
        json.dumps(spec.input_schema)  # serializável
        assert isinstance(spec.input_schema.get("properties", {}), dict), spec.name
        assert spec.input_schema.get("additionalProperties") is False, spec.name  # extra="forbid"
        for required in spec.input_schema.get("required", []):
            assert required in spec.input_schema["properties"], (spec.name, required)


def test_descricoes_em_portugues_e_dizem_quando_usar(registry):
    for spec in registry.specs():
        assert len(spec.description) > 40, spec.name
        assert re.search(r"\b(use|usar|quando|para)\b", spec.description, re.IGNORECASE), spec.name


def test_registry_rejeita_nomes_duplicados():
    class Dummy(Tool):
        name = "dup"
        description = "d"
        args_model = BaseModel

        def run(self, args):
            return ToolResult(ok=True, data={})

    with pytest.raises(ValueError):
        ToolRegistry([Dummy(), Dummy()])


def test_execute_nome_desconhecido_cita_tools_existentes(registry):
    payload = run(registry, "inexistente")
    assert payload["ok"] is False
    assert payload["erro"]["codigo"] == "INVALID_ARGUMENT"
    assert "buscar_produtos" in payload["erro"]["mensagem"]


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("buscar_produtos", {"limite": 0}),
        ("buscar_produtos", {"limite": 16}),
        ("buscar_produtos", {"preco_min": -1}),
        ("buscar_produtos", {"campo_inexistente": 1}),
        ("buscar_produtos", {"limite": "muitos"}),
        ("detalhar_produto", {"produto_id": "abc"}),
        ("listar_categorias", {"extra": 1}),
        ("consultar_pedido", {"pedido_id": 0, "email": "a@b.com"}),
        ("consultar_pedido", {}),
        ("consultar_politica", {"topico": "inexistente"}),
        ("consultar_politica", {}),
        ("estimar_frete", {"cidade": "Campo Grande", "valor_pedido": 0}),
        ("estimar_frete", {"cidade": "Campo Grande", "valor_pedido": -5}),
        ("estimar_frete", {"cidade": "Campo Grande"}),
        ("informacoes_loja", {"x": 1}),
    ],
)
def test_execute_argumentos_invalidos_nao_lanca(registry, name, args):
    result = registry.execute(name, args)
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "INVALID_ARGUMENT"
    assert result.error.message


def test_execute_args_nao_dict_nao_lanca(registry):
    result = registry.execute("buscar_produtos", None)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.error.code in {"INVALID_ARGUMENT", "INTERNAL_ERROR"}


def test_tool_que_lanca_vira_internal_error(caplog):
    class NoArgs(BaseModel):
        model_config = ConfigDict(extra="forbid")

    class Boom(Tool):
        name = "boom"
        description = "Tool de teste que sempre falha."
        args_model = NoArgs

        def run(self, args):
            raise RuntimeError("segredo-interno-123")

    reg = ToolRegistry([Boom()])
    with caplog.at_level("ERROR"):
        result = reg.execute("boom", {})
    assert result.ok is False
    assert result.error.code == "INTERNAL_ERROR"
    assert "segredo-interno-123" not in result.to_llm()  # mensagem genérica
    assert "segredo-interno-123" in caplog.text  # mas logada com traceback
    assert reg.execute("boom", {"x": 1}).error.code == "INVALID_ARGUMENT"


# ----------------------------------------------------------------------------- to_llm


def test_to_llm_formato_sucesso_e_erro(registry):
    ok = run(registry, "listar_categorias")
    assert ok["ok"] is True
    assert "dados" in ok and "erro" not in ok

    err = run(registry, "detalhar_produto", produto_id=999999)
    assert err["ok"] is False
    assert set(err["erro"]) >= {"codigo", "mensagem"}
    assert err["erro"]["codigo"] == "NOT_FOUND"
    assert "dados" not in err


def test_to_llm_nao_escapa_unicode_e_deduplica_limitacoes():
    lim = Limitation(code="MANUAL_OMISSO", message="Ação não definida", source="Manual")
    text = ToolResult(ok=True, data={"x": "ç"}, limitations=[lim, lim]).to_llm()
    assert "ç" in text and "\\u" not in text
    payload = json.loads(text)
    assert len(payload["limitacoes"]) == 1
    assert set(payload["limitacoes"][0]) == {"codigo", "mensagem", "fonte"}


def test_dinheiro_sempre_texto_formatado(registry):
    payload = run(registry, "detalhar_produto", nome="Takamine GD20")
    preco = payload["dados"]["preco"]
    for key in ("preco_tabela", "preco_final", "preco_pix"):
        assert isinstance(preco[key], str) and MONEY_RE.match(preco[key]), (key, preco[key])
    for item in preco["parcelamento"]:
        assert MONEY_RE.match(item["valor"])
    for p in products(run(registry, "buscar_produtos", categoria="Violões")):
        assert MONEY_RE.match(p["preco"])
        if "promocao" in p:
            assert MONEY_RE.match(p["promocao"]["preco"])
    frete = run(registry, "estimar_frete", cidade="Campo Grande", valor_pedido=100)
    assert MONEY_RE.match(frete["dados"]["taxa"])


# ----------------------------------------------------------------------------- catálogo


def test_buscar_violoes_ate_1000_sao_12(registry):
    payload = run(registry, "buscar_produtos", categoria="Violões", preco_max=1000, limite=15)
    assert payload["ok"] is True
    assert payload["dados"]["total_encontrado"] == 12
    assert len(products(payload)) == 12
    assert all(p["categoria"] == "Violões" for p in products(payload))


def test_buscar_ordena_por_preco(registry):
    def value(p):
        return float(p["preco"].removeprefix("R$ ").replace(".", "").replace(",", "."))

    asc = [value(p) for p in products(run(registry, "buscar_produtos", categoria="Violões", ordenar="preco_asc"))]
    desc = [value(p) for p in products(run(registry, "buscar_produtos", categoria="Violões", ordenar="preco_desc"))]
    assert asc == sorted(asc)
    assert desc == sorted(desc, reverse=True)


def test_buscar_limite_respeitado_e_total_antes_do_limite(registry):
    payload = run(registry, "buscar_produtos", categoria="Violões", limite=3)
    assert len(products(payload)) == 3
    assert payload["dados"]["total_encontrado"] > 3


def test_buscar_categoria_invalida_lista_validas(registry):
    payload = run(registry, "buscar_produtos", categoria="Categoria Fantasma")
    assert payload["erro"]["codigo"] == "INVALID_ARGUMENT"
    validas = payload["erro"]["detalhes"]["categorias_validas"]
    assert "Violões" in validas


def test_buscar_preco_min_maior_que_max_e_invalido(registry):
    payload = run(registry, "buscar_produtos", preco_min=2000, preco_max=1000)
    assert payload["erro"]["codigo"] == "INVALID_ARGUMENT"


def test_buscar_produto_142_marca_conflito(registry):
    payload = run(registry, "buscar_produtos", categoria="Teclados e Pianos", apenas_disponiveis=False, limite=15)
    found = [p for p in products(payload) if p["id"] == 142]
    assert found, "produto #142 deveria aparecer em Teclados e Pianos"
    assert found[0]["informacoes_conflitantes"] is True


def test_buscar_disponiveis_nao_traz_descontinuado_nem_em_breve(registry, store_data):
    ids = set()
    for cat in run(registry, "listar_categorias")["dados"]:
        ids.update(p["id"] for p in products(run(registry, "buscar_produtos", categoria=cat["nome"], limite=15)))
    assert 113 not in ids  # descontinuado
    assert 130 not in ids  # em breve


def test_detalhar_takamine_gd20(registry):
    payload = run(registry, "detalhar_produto", nome="Takamine GD20")
    assert payload["ok"] is True
    preco = payload["dados"]["preco"]
    assert preco["preco_tabela"] == "R$ 2.199,00"
    assert preco["preco_pix"] == "R$ 2.089,05"
    assert preco["max_parcelas_confirmadas"] == 12
    encerradas = payload["dados"]["promocoes_encerradas"]
    assert len(encerradas) == 1
    assert encerradas[0]["percentual"] in (12, "12%", 12.0)
    assert "Oferta Especial" in encerradas[0]["descricao"]
    assert "limitacoes" not in payload or payload["limitacoes"] == []


def test_detalhar_nome_ambiguo_traz_candidatos(registry):
    payload = run(registry, "detalhar_produto", nome="violao yamaha")
    assert payload["ok"] is False
    assert payload["erro"]["codigo"] == "AMBIGUOUS"
    candidatos = payload["erro"]["detalhes"]["candidatos"]
    assert 1 < len(candidatos) <= 5
    assert all({"id", "nome", "categoria"} <= set(c) for c in candidatos)


def test_detalhar_nome_sem_candidato_ou_id_inexistente_e_not_found(registry):
    assert run(registry, "detalhar_produto", produto_id=999999)["erro"]["codigo"] == "NOT_FOUND"
    assert run(registry, "detalhar_produto", nome="zzzzqqqq xxxxwwww")["erro"]["codigo"] == "NOT_FOUND"


@pytest.mark.parametrize("args", [{}, {"produto_id": 142, "nome": "Yamaha"}])
def test_detalhar_exige_exatamente_um_identificador(registry, args):
    assert run(registry, "detalhar_produto", **args)["erro"]["codigo"] == "INVALID_ARGUMENT"


def test_detalhar_142_expoe_conflitos_e_oculta_campos(registry):
    payload = run(registry, "detalhar_produto", produto_id=142)
    assert payload["ok"] is True
    dados = payload["dados"]
    tipos = {c["tipo"] for c in dados["conflitos"]}
    assert {"marca", "teclas"} <= tipos
    assert "descricao" not in dados["produto"]
    assert "keys" not in dados["produto"]["especificacoes"]
    assert "DADO_CONFLITANTE" in codes(payload)
    assert any("142" in lim["fonte"] for lim in payload["limitacoes"])
    for conflito in dados["conflitos"]:
        assert {"tipo", "campos", "valores", "observacao"} <= set(conflito)


def test_detalhar_121_promocao_20_pix_nulo_e_parcelas_a_confirmar(registry):
    payload = run(registry, "detalhar_produto", produto_id=121)
    preco = payload["dados"]["preco"]
    assert preco["promocao"] is not None
    assert preco["promocao"]["percentual"] in (20, "20%", 20.0)
    assert MONEY_RE.match(preco["preco_tabela"]) and MONEY_RE.match(preco["promocao"]["preco"])
    assert preco["preco_pix"] is None
    cinco = [p for p in preco["parcelamento"] if p["parcelas"] == 5]
    assert cinco and cinco[0]["status"] == "a_confirmar"
    assert has_limitation(payload, LIMITATION_P3)


def test_detalhar_96_indisponivel_com_alternativas(registry):
    dados = run(registry, "detalhar_produto", produto_id=96)["dados"]
    assert dados["produto"]["disponivel"] is False
    assert 1 <= len(dados["alternativas_sugeridas"]) <= 3


def test_detalhar_113_descontinuado_sem_preco(registry):
    dados = run(registry, "detalhar_produto", produto_id=113)["dados"]
    assert dados["produto"]["status"] in ("descontinuado", "discontinued")
    assert dados["produto"]["disponivel"] is False
    assert dados["preco"] is None
    assert dados["alternativas_sugeridas"]


def test_detalhar_130_em_breve_com_limitacao(registry):
    payload = run(registry, "detalhar_produto", produto_id=130)
    assert payload["dados"]["produto"]["status"] in ("em_breve", "coming_soon")
    assert has_limitation(payload, tl.LIMITATION_EM_BREVE)


def test_listar_categorias(registry):
    cats = run(registry, "listar_categorias")["dados"]
    assert isinstance(cats, list) and cats
    assert all({"nome", "descricao", "produtos_disponiveis"} <= set(c) for c in cats)
    assert "Violões" in {c["nome"] for c in cats}


# ----------------------------------------------------------------------------- pedidos


def test_pedido_19_cancelado_com_observacao(registry):
    payload = run(registry, "consultar_pedido", pedido_id=19, email="pedro.oliveira@jmail.com")
    assert payload["ok"] is True
    dados = payload["dados"]
    assert dados["status"] == "cancelled" or dados["status_descricao"] == "cancelado"
    assert dados["status_descricao"] == "cancelado"
    assert "Pagamento não confirmado" in dados["observacoes"]
    assert dados["primeiro_nome_cliente"] == "Pedro"


def test_pedido_email_normalizado(registry):
    payload = run(registry, "consultar_pedido", pedido_id=19, email="  Pedro.Oliveira@JMAIL.com ")
    assert payload["ok"] is True


def test_pedido_inexistente_e_email_errado_sao_indistinguiveis(registry):
    errado = run(registry, "consultar_pedido", pedido_id=19, email="outra.pessoa@jmail.com")
    inexistente = run(registry, "consultar_pedido", pedido_id=99999, email="pedro.oliveira@jmail.com")
    for payload in (errado, inexistente):
        assert payload["ok"] is False
        assert payload["erro"]["codigo"] == "VERIFICATION_FAILED"
        assert "dados" not in payload
    assert errado["erro"]["codigo"] == inexistente["erro"]["codigo"]
    assert errado["erro"]["mensagem"] == inexistente["erro"]["mensagem"]
    assert errado == inexistente
    assert "e-mail" in errado["erro"]["mensagem"].lower() or "email" in errado["erro"]["mensagem"].lower()


def test_pedido_telefone_errado_tambem_falha_igual(registry):
    a = run(registry, "consultar_pedido", pedido_id=8, telefone="67 90000-0000")
    b = run(registry, "consultar_pedido", pedido_id=99999, telefone="67 90000-0000")
    assert a["erro"]["codigo"] == "VERIFICATION_FAILED"
    assert a == b


def test_pedido_sem_email_nem_telefone_e_invalid_argument(registry):
    payload = run(registry, "consultar_pedido", pedido_id=19)
    assert payload["ok"] is False
    assert payload["erro"]["codigo"] == "INVALID_ARGUMENT"
    assert "dados" not in payload


@pytest.mark.parametrize("campo", ["nome", "nome_cliente", "cliente"])
def test_pedido_rejeita_argumento_de_nome(registry, campo):
    payload = run(registry, "consultar_pedido", pedido_id=19, **{campo: "Pedro Henrique Oliveira"})
    assert payload["ok"] is False
    assert payload["erro"]["codigo"] == "INVALID_ARGUMENT"
    assert "dados" not in payload
    # nome ao lado de credencial válida também é rejeitado (extra=forbid)
    payload = run(registry, "consultar_pedido", pedido_id=19, email="pedro.oliveira@jmail.com", **{campo: "Pedro"})
    assert payload["erro"]["codigo"] == "INVALID_ARGUMENT"


def test_pedido_8_enviado_com_rastreio_e_limitacoes(registry):
    payload = run(registry, "consultar_pedido", pedido_id=8, telefone="67 99654-7821")
    dados = payload["dados"]
    assert dados["status_descricao"] == "enviado"
    assert dados["codigo_rastreio"] == "BRJL5544332BR"
    assert dados["previsao_entrega_estimada"] == "28/02/2026"
    assert has_limitation(payload, tl.LIMITATION_P6)
    assert has_limitation(payload, tl.LIMITATION_P7)


def test_pedido_telefone_aceita_formatos_mas_exige_igualdade_exata(registry):
    assert run(registry, "consultar_pedido", pedido_id=8, telefone="(67) 99654-7821")["ok"] is True
    assert run(registry, "consultar_pedido", pedido_id=8, telefone="5567996547821")["ok"] is False  # não é igual
    assert run(registry, "consultar_pedido", pedido_id=8, telefone="99654-7821")["ok"] is False  # parcial


def test_pedido_3_com_credenciais_do_dono(registry, store_data):
    row = store_data.customers[store_data.customers["customer_id"] == 12].iloc[0]
    payload = run(registry, "consultar_pedido", pedido_id=3, email=row["email"])
    assert payload["ok"] is True
    dados = payload["dados"]
    assert dados["valor_total_registrado"] == "R$ 3.450,00"
    assert dados["status_descricao"] == "entregue"
    assert has_limitation(payload, tl.LIMITATION_P6) and has_limitation(payload, tl.LIMITATION_P7)
    assert dados["forma_pagamento"] == "Cartão de crédito em 12x"


def test_pedido_pendente_nao_tem_p6_p7(registry, store_data):
    pending = store_data.orders[store_data.orders["status"].isin(["pending", "confirmed"])]
    row = pending.iloc[0]
    cust = store_data.customers[store_data.customers["customer_id"] == row["customer_id"]].iloc[0]
    payload = run(registry, "consultar_pedido", pedido_id=int(row["order_id"]), email=cust["email"])
    assert payload["ok"] is True
    assert not has_limitation(payload, tl.LIMITATION_P7)


def test_email_compartilhado_so_libera_pedido_do_dono(registry, store_data):
    # clientes 11 e 43 compartilham o e-mail; só o cliente 11 tem pedido (#10)
    email = "bruno.martins@jmail.com"
    assert run(registry, "consultar_pedido", pedido_id=10, email=email)["ok"] is True
    for order_id in store_data.orders["order_id"]:
        if int(order_id) == 10:
            continue
        payload = run(registry, "consultar_pedido", pedido_id=int(order_id), email=email)
        assert payload["erro"]["codigo"] == "VERIFICATION_FAILED", order_id


def test_pedido_itens_e_campos_do_contrato(registry):
    dados = run(registry, "consultar_pedido", pedido_id=19, email="pedro.oliveira@jmail.com")["dados"]
    assert {"pedido_id", "primeiro_nome_cliente", "data_pedido", "status", "status_descricao",
            "valor_total_registrado", "forma_pagamento", "itens"} <= set(dados)
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", dados["data_pedido"])
    assert dados["itens"] and all({"nome", "quantidade"} <= set(i) for i in dados["itens"])
    assert dados["forma_pagamento"] == "Boleto bancário"


def test_varredura_pii_em_todos_os_pedidos(registry, store_data):
    customers = {int(r.customer_id): r for r in store_data.customers.itertuples(index=False)}
    checked = 0
    for order in store_data.orders.itertuples(index=False):
        owner = customers[int(order.customer_id)]
        for credential in ({"email": owner.email}, {"telefone": owner.phone_digits}):
            text = registry.execute("consultar_pedido", {"pedido_id": int(order.order_id), **credential}).to_llm()
            payload = json.loads(text)
            assert payload["ok"] is True, (order.order_id, credential)
            checked += 1
            lowered = text.lower()
            assert "@" not in text, order.order_id
            assert owner.email.lower() not in lowered
            digits = re.sub(r"\D", "", text)
            assert owner.phone_digits not in digits
            assert owner.phone_digits[-8:] not in digits
            for key, _ in walk(payload):
                assert key not in {"customer_id", "email", "telefone", "phone", "cliente_id", "nome_cliente"}
            assert owner.name.lower() not in lowered or owner.name.split()[0].lower() == owner.name.lower()
    assert checked >= 2 * 19


def test_pii_tambem_ausente_nos_erros(registry, store_data):
    owner = store_data.customers.iloc[0]
    text = registry.execute("consultar_pedido", {"pedido_id": 19, "email": owner["email"]}).to_llm()
    assert owner["email"] not in text
    assert owner["name"] not in text


# ----------------------------------------------------------------------------- políticas


@pytest.mark.parametrize("topico", POLICY_TOPICS)
def test_consultar_politica_devolve_todas_as_secoes_do_topico(registry, policies, topico):
    payload = run(registry, "consultar_politica", topico=topico)
    assert payload["ok"] is True
    assert payload["dados"]["topico"] == topico
    esperado = policies.get(topico)
    secoes = payload["dados"]["secoes"]
    assert [s["titulo"] for s in secoes] == [s.title for s in esperado]
    assert all(s["texto"].strip() and s["fonte"] for s in secoes)


def test_sobre_loja_inclui_capa(registry):
    titulos = [s["titulo"] for s in run(registry, "consultar_politica", topico="sobre_loja")["dados"]["secoes"]]
    assert "Capa" in titulos


def has_all(payload: dict, *limitations: Limitation) -> bool:
    return all(has_limitation(payload, lim) for lim in limitations)


def test_limitacoes_por_topico(registry):
    pol = lambda t: run(registry, "consultar_politica", topico=t)  # noqa: E731
    assert has_all(pol("pagamento"), LIMITATION_P3, LIMITATION_P4, LIMITATION_P12)
    assert has_all(pol("trocas_devolucoes"), tl.LIMITATION_P6, tl.LIMITATION_P7, tl.LIMITATION_P14)
    assert has_all(pol("frete_entrega"), LIMITATION_P5, LIMITATION_P8, tl.LIMITATION_P13)
    assert has_all(pol("sobre_loja"), tl.LIMITATION_P1, tl.LIMITATION_P2)
    assert has_all(pol("atendimento"), tl.LIMITATION_P1)
    assert has_all(pol("horarios"), LIMITATION_FERIADOS, LIMITATION_DATAS_ESPECIAIS)


@pytest.mark.parametrize("topico", ["promocoes", "garantia", "privacidade"])
def test_topicos_sem_limitacao(registry, topico):
    assert "limitacoes" not in run(registry, "consultar_politica", topico=topico)


# ----------------------------------------------------------------------------- informações da loja


def test_informacoes_loja_contatos_com_fonte(registry):
    payload = run(registry, "informacoes_loja")
    assert payload["ok"] is True
    dados = payload["dados"]
    assert "Rua 14 de Maio, 3200" in dados["endereco"]
    contatos = dados["contatos"]
    assert len(contatos) == 4
    for c in contatos:
        assert {"tipo", "valor", "rotulo_no_manual", "fonte"} <= set(c)
        assert c["fonte"]
    tipos = [c["tipo"] for c in contatos]
    assert sum("mail" in t.lower() for t in tipos) == 2
    assert len({c["valor"] for c in contatos}) == 4
    assert dados["horarios"]
    assert all({"dias", "horario"} <= set(h) for h in dados["horarios"])


def test_informacoes_loja_dados_vem_literalmente_do_manual(registry):
    manual = POLICIES_MD.read_text(encoding="utf-8")
    manual_digits = re.sub(r"\D", "", manual)
    dados = run(registry, "informacoes_loja")["dados"]
    assert dados["endereco"] in manual or "Rua 14 de Maio, 3200" in dados["endereco"]
    for c in dados["contatos"]:
        assert c["valor"] in manual, c
        if "@" not in c["valor"]:
            assert re.sub(r"\D", "", c["valor"]) in manual_digits
    # as duas grafias de e-mail do manual (com e sem acento) são ambas devolvidas
    emails = {c["valor"] for c in dados["contatos"] if "@" in c["valor"]}
    assert "contato@emporiodamusica.com.br" in emails
    assert "contato@empóriodamusica.com.br" in emails


def test_informacoes_loja_domingo_fechada_proxima_segunda(registry):
    payload = run(registry, "informacoes_loja")
    dados = payload["dados"]
    assert dados["aberto_agora_horario_regular"] is False
    assert dados["horario_hoje"] is None
    assert dados["proxima_abertura"]["hora"] == "09:00"
    assert "segunda" in dados["proxima_abertura"]["dia_semana"].lower()
    assert dados["proxima_abertura"]["data"] == "02/11/2026"
    ref = dados["referencia"]
    assert ref["data"] == "01/11/2026" and ref["hora"] == "15:47"
    assert "domingo" in ref["dia_semana"].lower()


def test_informacoes_loja_segunda_aberta(store_data, policies):
    dados = run(make_registry(store_data, policies, MONDAY), "informacoes_loja")["dados"]
    assert dados["aberto_agora_horario_regular"] is True
    assert dados["horario_hoje"] == "09:00 às 18:00"
    assert "proxima_abertura" not in dados or dados["proxima_abertura"] is None


def test_informacoes_loja_limitacoes(registry):
    payload = run(registry, "informacoes_loja")
    assert has_all(payload, tl.LIMITATION_P1, tl.LIMITATION_P2, LIMITATION_FERIADOS, LIMITATION_DATAS_ESPECIAIS)


def test_informacoes_loja_falha_de_extracao_vira_internal_error(store_data):
    vazio = PolicyStore.from_markdown(POLICIES_MD)
    # armazena sem seção de dados da empresa: construído a partir de um subconjunto
    parcial = PolicyStore([s for s in vazio.sections() if s.topic != "sobre_loja"])
    reg = build_tool_registry(CatalogRepository(store_data), OrderRepository(store_data), parcial, lambda: SUNDAY)
    result = reg.execute("informacoes_loja", {})
    assert result.ok is False
    assert result.error.code == "INTERNAL_ERROR"


# ----------------------------------------------------------------------------- frete


def test_frete_campo_grande_600_gratis(registry):
    dados = run(registry, "estimar_frete", cidade="Campo Grande", valor_pedido=600)["dados"]
    assert dados["regiao"] == "metropolitana"
    assert dados["situacao_taxa"] == "gratis"
    assert dados["taxa"] == "R$ 0,00"
    assert dados["prazos"]


def test_frete_campo_grande_abaixo_de_500_taxa_fixa(registry):
    dados = run(registry, "estimar_frete", cidade="campo grande", valor_pedido=300)["dados"]
    assert dados["situacao_taxa"] == "taxa_fixa"
    assert dados["taxa"] == "R$ 35,00"


def test_frete_exatamente_500_e_p5(registry):
    payload = run(registry, "estimar_frete", cidade="Campo Grande", valor_pedido=500)
    assert payload["dados"]["taxa"] is None
    assert has_limitation(payload, LIMITATION_P5)


def test_frete_dourados_regiao_nao_confirmada(registry):
    payload = run(registry, "estimar_frete", cidade="Dourados", valor_pedido=600)
    dados = payload["dados"]
    assert dados["regiao"] == "nao_confirmada"
    assert dados["taxa"] is None
    assert has_limitation(payload, LIMITATION_P8)
    assert has_limitation(payload, LIMITATION_VALOR_POR_CEP)


def test_frete_sem_cidade_nao_inventa(registry):
    payload = run(registry, "estimar_frete", valor_pedido=600)
    assert payload["ok"] is True
    assert payload["dados"]["taxa"] is None
    assert payload["limitacoes"]


# ----------------------------------------------------------------------------- conformidade geral


def test_nenhuma_tool_devolve_veredito_de_elegibilidade(registry):
    texto = run(registry, "consultar_pedido", pedido_id=19, email="pedro.oliveira@jmail.com")
    assert "elegível" not in json.dumps(texto, ensure_ascii=False).lower()
    assert "eligible" not in json.dumps(texto).lower()


@pytest.fixture(scope="module")
def registry_duas_promocoes(store_data, policies) -> ToolRegistry:
    """Dados sintéticos: o produto 121 (já com 1 promoção ativa) ganha uma segunda promoção ativa."""
    extra = pd.DataFrame(
        [{"promotion_id": 99, "product_id": 121, "discount_percent": 5,
          "description": "Sintética", "is_active": True}]
    )
    data = dataclasses.replace(store_data, promotions=pd.concat([store_data.promotions, extra], ignore_index=True))
    return make_registry(data, policies, SUNDAY)


def test_p15_quando_ha_mais_de_uma_promocao_ativa(registry_duas_promocoes):
    """Com múltiplas promoções ativas: promoção omitida, P15 presente e preço final = preço de tabela."""
    reg = registry_duas_promocoes
    found = []
    for cat in run(reg, "listar_categorias")["dados"]:
        payload = run(reg, "buscar_produtos", categoria=cat["nome"], limite=15, apenas_disponiveis=False)
        found.extend((payload, p) for p in products(payload) if p["id"] == 121)
    assert len(found) == 1, "produto #121 deveria aparecer em exatamente uma categoria"
    payload, resumo = found[0]
    assert "promocao" not in resumo
    assert has_limitation(payload, LIMITATION_P15)

    detalhe = run(reg, "detalhar_produto", produto_id=121)
    assert detalhe["ok"] is True
    preco = detalhe["dados"]["preco"]
    assert preco["promocao"] is None
    assert preco["preco_pix"] is None
    assert preco["preco_final"] == preco["preco_tabela"]
    assert has_limitation(detalhe, LIMITATION_P15)
