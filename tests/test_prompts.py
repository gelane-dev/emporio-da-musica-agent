"""Testes da T10: prompt de sistema e contexto dinâmico (ARCHITECTURE §5.7.1), por termos-chave."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.agent.prompts import KNOWN_TOOLS, build_dynamic_context, build_system_prompt
from emporio_agent.config import REPO_ROOT
from emporio_agent.domain.store_hours import store_status

TZ = ZoneInfo("America/Campo_Grande")
SUNDAY = datetime(2026, 11, 1, 15, 47, tzinfo=TZ)
MONDAY = datetime(2026, 11, 2, 10, 0, tzinfo=TZ)


@pytest.fixture(scope="module")
def prompt() -> str:
    return build_system_prompt(KNOWN_TOOLS).lower()


def ctx(now: datetime) -> str:
    return build_dynamic_context(now, store_status(now))


def has_all(text: str, *terms: str) -> bool:
    return all(t.lower() in text for t in terms)


def has_any(text: str, *terms: str) -> bool:
    return any(t.lower() in text for t in terms)


def sentences(text: str) -> list[str]:
    """Divide o texto em frases (ponto final, quebra de linha ou ponto e vírgula)."""
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+|;", text) if x.strip()]


def has_sentence(text: str, *groups: tuple[str, ...]) -> bool:
    """Existe UMA frase que contém, para cada grupo, ao menos um dos termos (conceitos na mesma frase)."""
    return any(all(any(t.lower() in sent for t in group) for group in groups) for sent in sentences(text))


def drop_sentences(text: str, *stems: str) -> str:
    """Remove do texto as frases que contêm algum dos radicais (usado nos casos negativos)."""
    return "\n".join(x for x in sentences(text) if not any(t.lower() in x for t in stems))


NEG = ("nunca", "não", "sem ")


# ----------------------------------------------------------------------------- conteúdo obrigatório


def test_persona_mel_e_empresa(prompt):
    assert has_all(prompt, "mel", "assistente virtual", "empório da música")


def test_tom_informal_mas_profissional(prompt):
    assert "informal" in prompt and "profissional" in prompt


def test_proibe_emojis(prompt):
    assert "emoji" in prompt
    assert has_any(prompt, "sem emoji", "não use emoji", "nunca use emoji", "não utilize emoji", "nunca emoji")


def test_prompt_nao_contem_emojis():
    text = build_system_prompt(KNOWN_TOOLS) + ctx(SUNDAY)
    assert not re.search("[\U0001f300-\U0001faff☀-➿⭐️]", text)


def test_escopo_instrumentos_e_acessorios_redirecionados(prompt):
    assert has_all(prompt, "instrumento")
    assert "acessório" in prompt
    for item in ("cordas", "cabos", "palhetas", "pedais", "amplificadores", "cases"):
        assert item in prompt, item
    assert has_any(prompt, "redirecion", "não comercializ", "não vend")


def test_temas_fora_da_loja_recusados_com_gentileza(prompt):
    assert has_any(prompt, "fora do escopo", "fora da loja", "fora do assunto", "outros assuntos", "outros temas")
    assert has_any(prompt, "gentil", "educad", "cordial")


def grounding_ok(text: str) -> bool:
    fonte = has_sentence(text, ("preço",), ("estoque",), ("prazo",), ("somente", "apenas", "exclusivamente", "só "), ("ferramenta",))
    sem_recalculo = has_sentence(text, ("recalcul", "estime", "estimar"), NEG)
    return fonte and sem_recalculo


def test_preco_estoque_prazo_somente_via_ferramenta(prompt):
    assert grounding_ok(prompt)
    # negativos: sem a frase de fonte única ou sem a proibição de recalcular, a verificação falha
    assert not grounding_ok(drop_sentences(prompt, "recalcul", "estime"))
    assert not grounding_ok(drop_sentences(prompt, "somente das ferramentas"))


def test_promocao_preco_original_promocional_e_percentual(prompt):
    assert "promoç" in prompt
    assert has_all(prompt, "original", "promocional", "percentual")


def test_pix_nao_acumula_com_promocao(prompt):
    assert "pix" in prompt
    assert has_any(prompt, "não acumula", "não se acumula", "não é acumul", "não cumulativ", "não pode ser combinad")


def identificacao_ok(text: str) -> bool:
    credenciais = has_sentence(text, ("pedido",), ("e-mail",), ("telefone",))
    isolado = has_sentence(text, ("isolad", "somente o nome", "apenas o nome", "por nome", "pelo nome"), NEG)
    terceiros = has_sentence(text, ("outros clientes", "outro cliente", "de terceiros"), ("nunca", "não"))
    return credenciais and isolado and terceiros


def test_identificacao_de_cliente_pedido_mais_email_ou_telefone(prompt):
    assert has_any(prompt, "número do pedido")
    assert identificacao_ok(prompt)
    assert not identificacao_ok(drop_sentences(prompt, "isolad"))
    assert not identificacao_ok(drop_sentences(prompt, "outros clientes"))
    assert not identificacao_ok(drop_sentences(prompt, "número do pedido"))


def test_repassa_limitacoes_sem_suposicoes(prompt):
    assert "limitaç" in prompt
    assert has_any(prompt, "equipe", "gerência", "atendente")
    assert has_any(prompt, "suposiç", "suposi", "inventar", "não complete", "não presuma", "sem supor")
    assert has_any(prompt, "confirm")


def conflitos_ok(text: str) -> bool:
    return has_sentence(
        text,
        ("conflit",),
        ("não são fatos", "não é fato", "como verdade", "como fato", "não apresente", "nunca apresente", "não trate", "não afirme", "nunca afirme"),
        NEG,
    )


def test_conflitos_nao_sao_fatos(prompt):
    assert conflitos_ok(prompt)
    assert not conflitos_ok(drop_sentences(prompt, "conflit"))


def test_opcoes_a_confirmar_ditas_como_tal(prompt):
    assert "a confirmar" in prompt


def elegibilidade_ok(text: str) -> bool:
    return has_sentence(
        text,
        ("troca", "devoluç"),
        ("aceita ou negada", "elegib", "direito", "aprovad", "garant"),
        ("nunca", "não"),
    )


def test_nunca_declara_elegibilidade_de_troca_devolucao(prompt):
    assert elegibilidade_ok(prompt)
    assert not elegibilidade_ok(drop_sentences(prompt, "aceita ou negada"))
    # afirmar a elegibilidade (sem negação) não satisfaz o contrato
    assert not elegibilidade_ok("Declare que a troca é aceita ou negada.")


def test_situacoes_especiais_7_3(prompt):
    assert has_any(prompt, "fora de estoque", "indisponível", "sem estoque")
    assert "alternativ" in prompt
    assert has_any(prompt, "descontinuad")
    assert has_any(prompt, "promoção expirad", "promoção encerrad", "promoção expir", "promoção já encerrad", "expirou", "encerrou")


def test_fora_do_expediente_informa_horario_de_retorno(prompt):
    assert has_any(prompt, "fora do expediente", "fora do horário", "loja fechada", "fechad")
    assert has_any(prompt, "retorno", "reabr", "próxima abertura", "volta a abrir", "voltamos")


def test_duvida_sobre_politica_consulta_equipe_gerencia(prompt):
    assert has_any(prompt, "gerência", "gerente")
    assert has_any(prompt, "dúvida")


def test_ignora_mudanca_de_papel_e_vazamento_de_instrucoes(prompt):
    assert has_any(prompt, "mudar de papel", "mudar seu papel", "troque de papel", "assumir outro papel", "outro papel", "personagem")
    assert has_any(prompt, "instruções", "prompt")
    assert has_any(prompt, "internos", "internas", "confidencia", "não revele", "nunca revele", "não divulgue")


# ----------------------------------------------------------------------------- determinismo, ferramentas, limites


def test_determinismo():
    assert build_system_prompt(KNOWN_TOOLS) == build_system_prompt(KNOWN_TOOLS)
    assert build_system_prompt(["buscar_produtos", "informacoes_loja"]) == build_system_prompt(
        ["buscar_produtos", "informacoes_loja"]
    )


def test_ordem_da_entrada_nao_altera_o_prompt():
    a = build_system_prompt(["buscar_produtos", "informacoes_loja", "consultar_pedido"])
    b = build_system_prompt(("consultar_pedido", "buscar_produtos", "informacoes_loja"))
    assert a == b


def test_prompt_completo_cita_todas_as_ferramentas_conhecidas():
    text = build_system_prompt(KNOWN_TOOLS)
    for name in KNOWN_TOOLS:
        assert name in text, name


def test_so_cita_ferramentas_presentes():
    subset = ["buscar_produtos", "consultar_pedido"]
    text = build_system_prompt(subset)
    for name in subset:
        assert name in text
    for name in set(KNOWN_TOOLS) - set(subset):
        assert name not in text, name


def test_sem_ferramentas_nao_cita_nenhuma():
    text = build_system_prompt([])
    assert not any(name in text for name in KNOWN_TOOLS)


def test_known_tools_contem_as_oito():
    assert set(KNOWN_TOOLS) == {
        "buscar_produtos", "detalhar_produto", "listar_categorias", "consultar_pedido",
        "consultar_politica", "informacoes_loja", "estimar_frete", "encaminhar_atendente",
    }


@pytest.mark.parametrize("bad", [["nao_existe"], ["buscar_produtos", "ferramenta_fantasma"]])
def test_nome_desconhecido_levanta_value_error(bad):
    with pytest.raises(ValueError):
        build_system_prompt(bad)


def test_sem_data_hora_no_prompt_estavel():
    text = build_system_prompt(KNOWN_TOOLS)
    assert not re.search(r"\d{2}/\d{2}/\d{4}", text)
    assert not re.search(r"\b\d{1,2}:\d{2}\b", text)
    assert not re.search(r"\b20\d{2}\b", text)


def test_sem_precos_telefones_nem_dados_do_manual():
    text = build_system_prompt(KNOWN_TOOLS)
    assert "R$" not in text
    assert not re.search(r"\d+[.,]\d{2}\b", text)  # valores monetários
    manual = (REPO_ROOT / "knowledge" / "policies.md").read_text(encoding="utf-8")
    # telefones/CEP/CNPJ/e-mails do manual não podem aparecer no prompt
    forbidden = set(re.findall(r"\(\d{2}\)\s?\d{4,5}-\d{4}", manual))
    forbidden |= set(re.findall(r"\d{5}-\d{3}", manual))
    forbidden |= set(re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", manual))
    forbidden |= set(re.findall(r"[\w.]+@[\w.]+", manual))
    assert forbidden
    for item in forbidden:
        assert item not in text, item
    assert not re.search(r"\d{4,5}-\d{4}", text)
    assert "Rua 14 de Maio" not in text


def test_nao_copia_trechos_longos_do_manual():
    text = build_system_prompt(KNOWN_TOOLS)
    manual = (REPO_ROOT / "knowledge" / "policies.md").read_text(encoding="utf-8")
    for line in manual.splitlines():
        line = line.strip()
        if len(line) >= 80:
            assert line not in text, line


def test_tamanho_maximo():
    assert len(build_system_prompt(KNOWN_TOOLS)) <= 7000


# ----------------------------------------------------------------------------- contexto dinâmico


def test_contexto_domingo_fechada_e_proxima_abertura():
    text = ctx(SUNDAY).lower()
    assert has_all(text, "domingo", "01/11/2026", "15:47")
    assert has_any(text, "fechada", "fechado")
    assert not has_any(text, "está aberta", "loja aberta")
    assert has_all(text, "próxima abertura", "segunda", "09:00")
    assert "02/11/2026" in text


def test_contexto_segunda_aberta():
    text = ctx(MONDAY).lower()
    assert has_all(text, "segunda", "02/11/2026", "10:00")
    assert has_any(text, "aberta", "aberto")
    assert not has_any(text, "fechada", "fechado")
    assert "próxima abertura" not in text


def test_contexto_menciona_fuso_da_loja():
    assert "America/Campo_Grande" in ctx(SUNDAY)


def test_contexto_termina_lembrando_feriados():
    text = ctx(SUNDAY)
    assert "feriado" in text.lower()
    assert "feriado" in text.lower().splitlines()[-1] or "feriado" in text.lower()[-300:]


def test_contexto_converte_para_o_fuso_da_loja():
    utc = datetime(2026, 11, 1, 19, 47, tzinfo=ZoneInfo("UTC"))  # 15:47 em Campo Grande
    text = ctx(utc).lower()
    assert has_all(text, "domingo", "01/11/2026", "15:47")


def test_contexto_sabado_com_horario_reduzido():
    saturday = datetime(2026, 10, 31, 14, 0, tzinfo=TZ)
    text = ctx(saturday).lower()
    assert has_all(text, "sábado", "31/10/2026", "14:00")
    assert has_any(text, "fechada", "fechado")  # sábado fecha às 13:00


def test_contexto_deterministico():
    assert ctx(SUNDAY) == ctx(SUNDAY)
    assert ctx(SUNDAY) != ctx(MONDAY)
