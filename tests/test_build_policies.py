"""Testes da T06: conversão do manual (PDF) em ``knowledge/policies.md``.

Escritos de forma independente, a partir do contrato (ARCHITECTURE §5.4.1) e da
leitura direta do PDF. Os testes não importam nada de ``scripts/`` nem de
``emporio_agent``: o script é exercitado via subprocess e o ``.md`` é lido como texto.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = REPO_ROOT / "data" / "políticas_da_loja.pdf"
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_policies.py"
MD_PATH = REPO_ROOT / "knowledge" / "policies.md"

HEADER_WORDS = "Empório da Música Manual de Políticas e Procedimentos".split()  # 8 palavras

# ---------------------------------------------------------------------------
# Critério de fidelidade (§5.4.1, revisado: ''.join(W_md) == ''.join(W_pdf)) — implementação independente
# ---------------------------------------------------------------------------


def pdf_pages() -> list[str]:
    reader = PdfReader(str(PDF_PATH))
    return [page.extract_text() for page in reader.pages]


def pdf_page_words() -> list[list[str]]:
    return [text.split() for text in pdf_pages()]


def compute_w_pdf() -> list[str]:
    words_out: list[str] = []
    for number, words in enumerate(pdf_page_words(), start=1):
        if number >= 2:
            if words[: len(HEADER_WORDS)] == HEADER_WORDS:
                words = words[len(HEADER_WORDS):]
            if len(words) >= 2 and words[-2] == "Página" and words[-1] == str(number):
                words = words[:-2]
        words_out.extend(w for w in words if w != "•")
    return words_out


_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
_MARKER_RE = re.compile(r"^(?:#{1,3} |- )")


def compute_w_md(text: str) -> list[str]:
    text = _COMMENT_RE.sub("", text)
    kept: list[str] = []
    for line in text.split("\n"):
        if line.startswith("# ") or line.startswith(">") or line.strip() == "## Capa":
            continue
        if _TABLE_SEP_RE.match(line):
            continue
        line = _MARKER_RE.sub("", line)
        line = line.replace("**", "").replace("|", " ")
        kept.append(line)
    return "\n".join(kept).split()


def first_divergence(expected: list[str], actual: list[str], context: int = 40) -> str:
    """Compara ''.join(W_pdf) com ''.join(W_md); mostra ~40 caracteres de cada lado da 1ª diferença."""
    a, b = "".join(expected), "".join(actual)
    limit = min(len(a), len(b))
    idx = next((i for i in range(limit) if a[i] != b[i]), limit)
    lo, hi = max(0, idx - context), idx + context
    return (
        f"primeira divergência no caractere #{idx} (tamanhos sem espaços: PDF={len(a)}, MD={len(b)})\n"
        f"  PDF: ...{a[lo:idx]}[[{a[idx:idx + 1]}]]{a[idx + 1:hi]}...\n"
        f"  MD : ...{b[lo:idx]}[[{b[idx:idx + 1]}]]{b[idx + 1:hi]}..."
    )


def same_chars(w_pdf: list[str], w_md: list[str]) -> bool:
    return "".join(w_pdf) == "".join(w_md)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def w_pdf() -> list[str]:
    return compute_w_pdf()


@pytest.fixture(scope="module")
def pdf_text(w_pdf) -> str:
    return " ".join(w_pdf)


@pytest.fixture(scope="module")
def md_bytes() -> bytes:
    assert MD_PATH.is_file(), f"knowledge/policies.md não existe ({MD_PATH})"
    return MD_PATH.read_bytes()


@pytest.fixture(scope="module")
def md_text(md_bytes) -> str:
    return md_bytes.decode("utf-8")


_MARKER_LINE_RE = re.compile(r"^<!-- topic: (\w+) -->$", re.MULTILINE)


def split_blocks(md: str) -> list[tuple[str, str]]:
    """Devolve [(topic, corpo)] onde corpo começa na linha logo após o marcador."""
    matches = list(_MARKER_LINE_RE.finditer(md))
    blocks = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        blocks.append((m.group(1), md[m.end() + 1 : end]))
    return blocks


@pytest.fixture(scope="module")
def blocks(md_text) -> list[tuple[str, str]]:
    return split_blocks(md_text)


def norm(text: str) -> str:
    """Texto do bloco normalizado como em W_md (sem **, |, marcadores)."""
    return " ".join(compute_w_md(text))


@pytest.fixture(scope="module")
def script_run_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("build_policies")


def run_script(*args: str) -> subprocess.CompletedProcess:
    assert SCRIPT_PATH.is_file(), f"scripts/build_policies.py não existe ({SCRIPT_PATH})"
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=120,
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 1. Fidelidade
# ---------------------------------------------------------------------------


class TestFidelity:
    def test_w_pdf_length_sanity(self, w_pdf):
        assert len(w_pdf) == 1651

    def test_pdf_has_8_pages(self):
        assert len(pdf_pages()) == 8

    def test_header_and_footer_present_on_pages_2_to_8(self):
        for number, words in enumerate(pdf_page_words(), start=1):
            if number == 1:
                assert words[: len(HEADER_WORDS)] != HEADER_WORDS
                continue
            assert words[: len(HEADER_WORDS)] == HEADER_WORDS, f"cabeçalho ausente na página {number}"
            assert words[-2:] == ["Página", str(number)], f"rodapé ausente na página {number}"

    def test_w_md_equals_w_pdf(self, md_text, w_pdf):
        w_md = compute_w_md(md_text)
        assert same_chars(w_pdf, w_md), first_divergence(w_pdf, w_md)


# ---------------------------------------------------------------------------
# 2. Estrutura
# ---------------------------------------------------------------------------

EXPECTED_BLOCKS = [
    ("sobre_loja", "## Capa", []),
    ("sobre_loja", "## 1. Sobre a Empório da Música", ["### 1.1 Missão", "### 1.2 Dados da Empresa"]),
    ("horarios", "## 2. Horário de Funcionamento", []),
    ("pagamento", "## 3. Formas de Pagamento", ["### 3.1 Regras de Parcelamento"]),
    (
        "trocas_devolucoes",
        "## 4. Política de Trocas e Devoluções",
        [
            "### 4.1 Direito de Arrependimento (Compras Online)",
            "### 4.2 Trocas por Defeito",
            "### 4.3 Trocas por Preferência",
            "### 4.4 Itens Não Elegíveis para Troca",
        ],
    ),
    (
        "frete_entrega",
        "## 5. Política de Frete e Entregas",
        [
            "### 5.1 Entregas na Região Metropolitana de Campo Grande",
            "### 5.2 Entregas para Outras Cidades",
            "### 5.3 Código de Rastreamento",
        ],
    ),
    ("promocoes", "## 6. Promoções e Descontos", ["### 6.1 Tipos de Promoção", "### 6.2 Regras de Promoções"]),
    (
        "atendimento",
        "## 7. Atendimento via WhatsApp",
        ["### 7.1 Diretrizes de Atendimento", "### 7.2 Fluxo de Atendimento Padrão", "### 7.3 Situações Especiais"],
    ),
    (
        "garantia",
        "## 8. Garantia",
        ["### 8.1 Garantia Legal", "### 8.2 Garantia do Fabricante", "### 8.3 O que Não Cobre a Garantia"],
    ),
    ("privacidade", "## 9. Privacidade e Proteção de Dados", []),
    ("atendimento", "## 10. Disposições Finais", []),
]

NINE_TOPICS = {
    "sobre_loja",
    "horarios",
    "pagamento",
    "trocas_devolucoes",
    "frete_entrega",
    "promocoes",
    "atendimento",
    "garantia",
    "privacidade",
}


class TestStructure:
    def test_h1_and_extraction_note_at_top(self, md_text):
        lines = md_text.split("\n")
        assert lines[0] == "# Manual de Políticas e Procedimentos — Empório da Música"
        assert lines[1] == ""
        note = [ln for ln in lines[2:] if ln.startswith(">")]
        assert note, "nota de extração ausente"
        first_marker = md_text.index("<!-- topic:")
        assert md_text.index(note[0]) < first_marker
        assert md_text.rindex(note[-1], 0, first_marker) < first_marker
        note_text = "\n".join(note)
        assert "scripts/build_policies.py" in note_text
        assert "data/políticas_da_loja.pdf" in note_text
        assert "Versão 2.1" in note_text and "Junho de 2025" in note_text

    def test_extraction_note_cites_divergences(self, md_text):
        note = "\n".join(ln for ln in md_text.split("\n") if ln.startswith(">"))
        for item in ("P1", "P2", "P3/P4"):
            assert item in note
        assert "NÃO corrigidas" in note
        assert "DATA_ANALYSIS.md" in note

    def test_eleven_blocks(self, blocks):
        assert len(blocks) == 11

    def test_marker_lines_are_well_formed(self, md_text):
        # todo "<!-- topic" do arquivo é um marcador válido em linha própria
        assert md_text.count("<!-- topic:") == len(_MARKER_LINE_RE.findall(md_text)) == 11

    @pytest.mark.parametrize("idx", range(11))
    def test_block_topic_and_title_in_order(self, blocks, idx):
        topic, title, _ = EXPECTED_BLOCKS[idx]
        got_topic, body = blocks[idx]
        assert got_topic == topic
        assert body.split("\n", 1)[0] == title, "o ## deve estar na linha imediatamente após o marcador"

    @pytest.mark.parametrize("idx", range(11))
    def test_block_subtitles_literal_and_ordered(self, blocks, idx):
        expected = EXPECTED_BLOCKS[idx][2]
        body = blocks[idx][1]
        assert re.findall(r"^### .*$", body, re.MULTILINE) == expected

    def test_no_other_h2_inside_blocks(self, blocks):
        for _, body in blocks:
            assert len(re.findall(r"^## ", body, re.MULTILINE)) == 1

    def test_nine_topics_and_double_blocks(self, blocks):
        topics = [t for t, _ in blocks]
        assert set(topics) == NINE_TOPICS
        assert topics.count("sobre_loja") == 2
        assert topics.count("atendimento") == 2
        for t in NINE_TOPICS - {"sobre_loja", "atendimento"}:
            assert topics.count(t) == 1

    def test_titles_and_subtitles_exist_in_pdf(self, pdf_text):
        """Meta-teste: os títulos esperados são mesmo literais do PDF (exceto '## Capa')."""
        for _, title, subs in EXPECTED_BLOCKS[1:]:
            assert title[3:] in pdf_text, title
            for sub in subs:
                assert sub[4:] in pdf_text, sub


# ---------------------------------------------------------------------------
# 3. Tabelas
# ---------------------------------------------------------------------------


def parse_table(body: str, header: list[str]):
    """Acha a tabela com o cabeçalho literal e devolve (separador_ok, linhas_de_dados)."""
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("|") and [c.strip() for c in line.strip().strip("|").split("|")] == header:
            assert i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1]), "separador da tabela ausente"
            rows = []
            for row in lines[i + 2 :]:
                if not row.startswith("|"):
                    break
                rows.append([c.strip() for c in row.strip().strip("|").split("|")])
            return rows
    return None


TABLES = [
    # (índice do bloco, cabeçalho, nº de linhas de dados)
    (1, ["Campo", "Informação"], 7),
    (2, ["Dia", "Horário"], 3),
    (3, ["Forma", "Condições", "Observações"], 4),
    (5, ["Modalidade", "Prazo Estimado", "Rastreamento", "Seguro"], 3),
]


class TestTables:
    @pytest.mark.parametrize("block_idx,header,n_rows", TABLES, ids=["1.2", "2", "3", "5.2"])
    def test_table_header_and_row_count(self, blocks, block_idx, header, n_rows):
        rows = parse_table(blocks[block_idx][1], header)
        assert rows is not None, f"tabela {header} não encontrada"
        assert len(rows) == n_rows
        assert all(len(r) == len(header) for r in rows), "linha com número de células diferente do cabeçalho"
        assert all(all(c for c in r) for r in rows), "célula vazia"

    def test_exactly_four_tables(self, md_text):
        seps = [ln for ln in md_text.split("\n") if _TABLE_SEP_RE.match(ln)]
        assert len(seps) == 4

    def test_table_1_2_contents(self, blocks):
        rows = parse_table(blocks[1][1], ["Campo", "Informação"])
        by_label = {r[0]: r[1] for r in rows}
        assert list(by_label) == [
            "Razão Social",
            "Nome Fantasia",
            "CNPJ",
            "Endereço",
            "Telefone / WhatsApp",
            "E-mail",
            "Fundação",
        ]
        assert by_label["Razão Social"] == "Empório da Música Instrumentos Musicais Ltda."
        assert by_label["Nome Fantasia"] == "Empório da Música"
        assert by_label["CNPJ"] == "12.345.678/0001-90"
        assert by_label["Endereço"] == "Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333"
        assert by_label["Telefone / WhatsApp"] == "(67) 3341-4444"
        assert by_label["E-mail"] == "contato@empóriodamusica.com.br"
        assert by_label["Fundação"] == "2008"

    def test_table_2_contents(self, blocks):
        rows = parse_table(blocks[2][1], ["Dia", "Horário"])
        assert rows == [
            ["Segunda a Sexta-feira", "09:00 às 18:00"],
            ["Sábado", "09:00 às 13:00"],
            ["Domingo e Feriados", "Fechado"],
        ]

    def test_table_3_contents_and_merged_cell(self, blocks):
        rows = parse_table(blocks[3][1], ["Forma", "Condições", "Observações"])
        assert rows == [
            ["PIX", "Pagamento à vista", "5% de desconto sobre o preço de tabela"],
            ["Cartão de Débito", "Pagamento à vista", "Todas as bandeiras aceitas"],
            ["Cartão de Crédito", "Até 12x sem juros", "Parcela mínima de R$ 100,00"],
            ["Boleto Bancário", "Pagamento à vista", "Compensação em até 3 dias úteis"],
        ]

    def test_merged_cell_is_in_one_line_and_cell(self, md_text):
        lines = [ln for ln in md_text.split("\n") if "5% de desconto sobre o preço de tabela" in ln]
        assert len(lines) == 1 and lines[0].startswith("|")
        cells = [c.strip() for c in lines[0].strip().strip("|").split("|")]
        assert "5% de desconto sobre o preço de tabela" in cells

    def test_table_5_2_contents(self, blocks):
        rows = parse_table(blocks[5][1], ["Modalidade", "Prazo Estimado", "Rastreamento", "Seguro"])
        assert rows == [
            ["PAC (Correios)", "5 a 12 dias úteis", "Sim", "Incluído"],
            ["SEDEX (Correios)", "2 a 5 dias úteis", "Sim", "Incluído"],
            ["Jadlog (.package)", "3 a 8 dias úteis", "Sim", "Incluído"],
        ]

    def test_tables_in_right_subsections(self, blocks):
        """Tabela 1.2 após '### 1.2', 3 antes de '### 3.1', 5.2 após '### 5.2' e antes de '### 5.3'."""
        b = blocks[1][1]
        assert b.index("### 1.2") < b.index("| Campo | Informação |")
        b = blocks[3][1]
        assert b.index("| Forma | Condições | Observações |") < b.index("### 3.1")
        b = blocks[5][1]
        assert b.index("### 5.2") < b.index("| Modalidade |") < b.index("### 5.3")


# ---------------------------------------------------------------------------
# 4. Fatos críticos no bloco certo
# ---------------------------------------------------------------------------

# (tópico, frase literal do PDF). Cada frase deve estar no PDF, no bloco do tópico e
# em nenhum bloco de outro tópico.
FACTS = [
    # sobre_loja
    ("sobre_loja", "fundada em 2008 em Campo Grande, Mato Grosso do Sul"),
    ("sobre_loja", "mais de 300 instrumentos"),
    ("sobre_loja", "não comercializamos acessórios como cordas, palhetas, cabos, cases, pedais ou amplificadores"),
    ("sobre_loja", "CNPJ 12.345.678/0001-90"),
    ("sobre_loja", "Documento interno — Uso restrito da equipe de atendimento"),
    # horarios
    ("horarios", "Segunda a Sexta-feira 09:00 às 18:00"),
    ("horarios", "Sábado 09:00 às 13:00"),
    ("horarios", "Domingo e Feriados Fechado"),
    ("horarios", "O atendimento via WhatsApp segue o mesmo horário, com respostas automáticas fora do expediente."),
    ("horarios", "Em datas especiais (Black Friday, Aniversário da Loja, Natal), o horário pode ser estendido."),
    # pagamento
    ("pagamento", "PIX Pagamento à vista 5% de desconto sobre o preço de tabela"),
    ("pagamento", "Cartão de Crédito Até 12x sem juros Parcela mínima de R$ 100,00"),
    ("pagamento", "Boleto Bancário Pagamento à vista Compensação em até 3 dias úteis"),
    ("pagamento", "Parcelamento em até 3x: sem juros, sem valor mínimo de parcela (exceto abaixo de R$ 50,00)."),
    ("pagamento", "Parcelamento de 4x a 6x: sem juros, parcela mínima de R$ 80,00."),
    ("pagamento", "Parcelamento de 7x a 12x: sem juros, parcela mínima de R$ 100,00."),
    ("pagamento", "Combinação de formas de pagamento: permitida (ex.: PIX + cartão) para compras acima de R$ 2.000,00."),
    # trocas_devolucoes
    ("trocas_devolucoes", "em até 7 (sete) dias corridos após o recebimento do produto, sem necessidade de justificativa"),
    ("trocas_devolucoes", "O produto deve estar em sua embalagem original, sem sinais de uso, com todos os acessórios e manuais."),
    ("trocas_devolucoes", "mesma forma de pagamento original em até 10 dias úteis"),
    ("trocas_devolucoes", "O frete de devolução é por conta da loja em caso de arrependimento."),
    ("trocas_devolucoes", "podem ser trocados em até 30 (trinta) dias corridos após a compra"),
    ("trocas_devolucoes", "Após os 30 dias, o cliente deve acionar a garantia diretamente com o fabricante."),
    ("trocas_devolucoes", "Trocas por preferência (cor, modelo, tamanho) são permitidas em até 7 dias"),
    ("trocas_devolucoes", "Instrumentos com personalização ou ajustes sob encomenda (setup, regulagem especial)."),
    ("trocas_devolucoes", 'com aviso explícito de "venda final"'),
    ("trocas_devolucoes", "Boquilhas de instrumentos de sopro, por questões de higiene."),
    ("trocas_devolucoes", "Lei nº 8.078/90"),
    # frete_entrega
    ("frete_entrega", "Frete grátis para pedidos acima de R$ 500,00."),
    ("frete_entrega", "Para pedidos abaixo de R$ 500,00, taxa fixa de R$ 35,00."),
    ("frete_entrega", "Prazo de entrega: 1 a 3 dias úteis."),
    ("frete_entrega", "Entrega realizada por motoboy próprio."),
    ("frete_entrega", "PAC (Correios) 5 a 12 dias úteis Sim Incluído"),
    ("frete_entrega", "SEDEX (Correios) 2 a 5 dias úteis Sim Incluído"),
    ("frete_entrega", "Jadlog (.package) 3 a 8 dias úteis Sim Incluído"),
    ("frete_entrega", "podem exigir frete especial com cotação individual"),
    ("frete_entrega", "o cliente deve recusar o recebimento e entrar em contato imediatamente com a loja"),
    ("frete_entrega", "O formato padrão é BR seguido de 9 caracteres alfanuméricos e BR (exemplo: BR4K7M2X9P1BR)."),
    # promocoes
    ("promocoes", "Aniversário da Loja (Agosto): descontos de 10% a 25% em itens selecionados."),
    ("promocoes", "Black Friday (Novembro): descontos de 15% a 30% em todo o catálogo."),
    ("promocoes", "Semana do Músico: promoções na semana do Dia do Músico (22 de novembro)."),
    ("promocoes", "Cumulatividade: promoções não são cumulativas."),
    ("promocoes", "O desconto de PIX (5%) não se aplica sobre preços já promocionais."),
    ("promocoes", "não geram direito a rain check (reserva de preço)"),
    ("promocoes", "promoções estão sujeitas à disponibilidade de estoque"),
    ("promocoes", "junto ao preço original e o percentual de desconto"),
    # atendimento
    ("atendimento", "O canal de WhatsApp (67) 3321-4500 é o principal meio de atendimento remoto"),
    ("atendimento", "Tempo de resposta: máximo de 5 minutos durante o horário de funcionamento."),
    ("atendimento", "nunca fornecer informações sobre preços, estoque ou prazos sem consultar o sistema"),
    ("atendimento", "Nunca prometer um desconto que não está mais vigente."),
    ("atendimento", "Nunca confirmar disponibilidade sem verificar o estoque atual."),
    ("atendimento", "Reclamação: ouvir o cliente com empatia, registrar a reclamação e encaminhar para o responsável."),
    ("atendimento", "Prazo de retorno: 24 horas úteis."),
    ("atendimento", "o atendente deve consultar a gerência antes de fornecer informações ao cliente"),
    # garantia
    ("garantia", "garantia legal de 90 (noventa) dias contra defeitos de fabricação"),
    ("garantia", "contados a partir da data de recebimento pelo cliente"),
    ("garantia", "pode variar de 6 meses a 2 anos"),
    ("garantia", "Desgaste natural de peças (trastes, cordas, feltros, palhetas de sopro)."),
    ("garantia", "Danos por mau uso, queda, exposição a condições climáticas extremas."),
    ("garantia", "Modificações ou reparos realizados por terceiros não autorizados."),
    ("garantia", "Danos estéticos que não afetem a funcionalidade do instrumento."),
    # privacidade
    ("privacidade", "Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018)"),
    ("privacidade", "Envio de promoções e novidades (mediante consentimento explícito do cliente)."),
    ("privacidade", "Dados de clientes não são compartilhados com terceiros para fins de marketing."),
    ("privacidade", "O cliente pode solicitar a exclusão de seus dados a qualquer momento"),
]


class TestCriticalFacts:
    @pytest.mark.parametrize("topic,phrase", FACTS, ids=[f"{t}:{p[:40]}" for t, p in FACTS])
    def test_phrase_is_literal_in_pdf(self, topic, phrase, pdf_text):
        """Meta-teste: a frase escolhida é fiel ao PDF (não é invenção do teste)."""
        assert phrase in pdf_text

    @pytest.mark.parametrize("topic,phrase", FACTS, ids=[f"{t}:{p[:40]}" for t, p in FACTS])
    def test_phrase_only_in_its_topic(self, topic, phrase, blocks):
        holders = {t for t, body in blocks if phrase in norm(body)}
        assert holders == {topic}, f"frase em {sorted(holders)}, esperado só {topic}: {phrase!r}"

    def test_whatsapp_hours_note_and_table_are_in_horarios_block(self, blocks):
        body = blocks[2][1]
        assert "09:00 às 18:00" in body and "Fechado" in body

    def test_ordered_list_7_2_keeps_numbers(self, blocks):
        body = blocks[7][1].replace("**", "")
        for n, label in enumerate(["Saudação:", "Entendimento:", "Consulta:", "Resposta:", "Fechamento:"], 1):
            assert re.search(rf"^{n}\. {re.escape(label)}", body, re.MULTILINE), f"item {n}. {label} ausente"

    def test_bullets_use_dash_and_no_bullet_glyph(self, md_text, blocks):
        assert "•" not in md_text
        trocas = blocks[4][1]
        assert len(re.findall(r"^- ", trocas, re.MULTILINE)) == 4 + 3 + 3 + 3  # 4.1–4.4
        garantia = blocks[8][1]
        assert len(re.findall(r"^- ", garantia, re.MULTILINE)) == 4  # 8.3


# ---------------------------------------------------------------------------
# 5. Divergências preservadas (NÃO corrigidas)
# ---------------------------------------------------------------------------


class TestPreservedDivergences:
    def test_both_phone_numbers_present(self, blocks):
        assert "(67) 3341-4444" in blocks[0][1]  # capa
        assert "(67) 3321-4500" in blocks[7][1]  # seção 7
        assert "3321-4500" not in blocks[0][1] + blocks[1][1]

    def test_phone_1_2_not_normalised_to_other_number(self, blocks):
        body = blocks[1][1]
        assert "(67) 3341-4444" in body
        assert "3321" not in body

    def test_both_email_spellings_each_in_own_place(self, blocks):
        cover, sec12 = blocks[0][1], blocks[1][1]
        assert "contato@emporiodamusica.com.br" in cover
        assert "contato@empóriodamusica.com.br" not in cover
        assert "contato@empóriodamusica.com.br" in sec12
        assert "contato@emporiodamusica.com.br" not in sec12

    def test_emails_appear_exactly_once_each_in_document(self, md_text):
        # (a nota de extração não deve repetir os e-mails literalmente)
        assert md_text.count("contato@emporiodamusica.com.br") == 1
        assert md_text.count("contato@empóriodamusica.com.br") == 1

    def test_installment_minimums_both_kept(self, blocks):
        body = blocks[3][1]
        assert "Parcela mínima de R$ 100,00" in body  # tabela
        assert "parcela mínima de R$ 80,00" in body  # 3.1, faixa 4x–6x
        assert "parcela mínima de R$ 100,00" in body  # 3.1, faixa 7x–12x
        assert "(exceto abaixo de R$ 50,00)" in norm(body)  # P4 literal

    def test_installment_minimum_not_harmonised(self, md_text):
        # a divergência seria "corrigida" se R$ 80 desaparecesse ou virasse R$ 100
        assert md_text.count("R$ 80,00") == 1
        assert md_text.count("R$ 50,00") == 1


# ---------------------------------------------------------------------------
# 6. Limpeza
# ---------------------------------------------------------------------------


class TestCleaning:
    def test_no_page_footer_lines(self, md_text):
        assert not re.search(r"^\s*P[áa]gina\s+\d+\s*$", md_text, re.MULTILINE)
        assert not re.search(r"P[áa]gina\s+\d+", md_text)

    def test_repeated_header_absent(self, md_text):
        flat = " ".join(md_text.split())
        assert "Empório da Música Manual de Políticas e Procedimentos" not in flat

    def test_header_phrase_only_in_h1(self, md_text):
        # única ocorrência permitida da expressão: o título H1 (a capa a escreve em maiúsculas)
        assert " ".join(md_text.split()).count("Manual de Políticas e Procedimentos") == 1
        assert md_text.split("\n")[0].startswith("# Manual de Políticas e Procedimentos")

    def test_cover_present_in_first_block(self, blocks):
        body = " ".join(blocks[0][1].replace("**", "").split())
        for needle in (
            "EMPÓRIO DA MÚSICA",
            "Sua música começa aqui.",
            "MANUAL DE POLÍTICAS E PROCEDIMENTOS",
            "Atendimento ao Cliente",
            "Rua 14 de Maio, 3200 — Centro",
            "Campo Grande – MS – CEP 79202-333",
            "(67) 3341-4444 — contato@emporiodamusica.com.br",
            "Versão 2.1 — Junho de 2025",
            "Documento interno — Uso restrito da equipe de atendimento",
        ):
            assert needle in body, needle

    def test_final_footer_in_last_block(self, blocks):
        assert blocks[-1][0] == "atendimento"
        body = " ".join(blocks[-1][1].replace("**", "").split())
        assert body.endswith("Empório da Música — Sua música começa aqui. Última atualização: Junho de 2025 — Versão 2.1")

    def test_cover_heading_only_acrescimo(self, md_text):
        assert md_text.count("## Capa") == 1


# ---------------------------------------------------------------------------
# 6b. Estrutura de parágrafos e negrito
# ---------------------------------------------------------------------------


def paragraphs(md: str) -> list[str]:
    """Parágrafos = blocos de texto separados por linha em branco (quebras internas viram espaço)."""
    body = _COMMENT_RE.sub("", md)
    return [" ".join(chunk.split()) for chunk in re.split(r"\n[ \t]*\n", body) if chunk.strip()]


def para_ending_with(paras: list[str], suffix: str) -> int:
    hits = [i for i, p in enumerate(paras) if p.replace("**", "").endswith(suffix)]
    assert len(hits) == 1, f"esperado 1 parágrafo terminando em {suffix!r}, achei {len(hits)}"
    return hits[0]


def pdf_bold_chars() -> str:
    """Todo o texto em fonte bold do PDF (BaseFont contém 'Bold'), concatenado sem espaços."""
    reader = PdfReader(str(PDF_PATH))
    out: list[str] = []

    def visitor(text, cm, tm, font_dict, font_size):
        base_font = str((font_dict or {}).get("/BaseFont", ""))
        if "Bold" in base_font:
            out.append("".join(text.split()))

    for page in reader.pages:
        page.extract_text(visitor_text=visitor)
    return "".join(out)


class TestParagraphStructure:
    def test_section_1_two_paragraphs(self, md_text):
        paras = paragraphs(md_text)
        i = para_ending_with(paras, "músicos iniciantes, intermediários e profissionais.")
        assert paras[i + 1].replace("**", "").startswith("Nosso catálogo abrange")

    def test_section_5_2_paragraphs_after_table(self, md_text):
        paras = paragraphs(md_text)
        i = para_ending_with(paras, "podem exigir frete especial com cotação individual.")
        assert paras[i + 1].replace("**", "").startswith("Todos os envios incluem seguro")

    def test_section_10_paragraphs(self, md_text):
        paras = paragraphs(md_text)
        i = para_ending_with(paras, "estão sujeitas a atualizações periódicas.")
        assert paras[i + 1].replace("**", "").startswith("Em caso de dúvidas sobre a aplicação")

    def test_7_3_prazo_de_retorno_same_paragraph_as_reclamacao_and_not_bold(self, md_text):
        paras = paragraphs(md_text)
        hits = [p for p in paras if p.replace("**", "").startswith("Reclamação:")]
        assert len(hits) == 1
        plain = hits[0].replace("**", "")
        assert "Prazo de retorno: 24 horas úteis." in plain, "Prazo de retorno deve estar no mesmo parágrafo"
        assert plain.endswith("Prazo de retorno: 24 horas úteis.")
        assert "**Prazo de retorno" not in hits[0]
        assert "Prazo de retorno:**" not in hits[0]

    def test_ultima_atualizacao_not_bold(self, md_text):
        assert "**Última atualização" not in md_text
        assert "Última atualização:**" not in md_text

    def test_final_footer_lines(self, md_text):
        lines = [ln.replace("**", "").strip() for ln in md_text.split("\n")]
        assert "Empório da Música — Sua música começa aqui." in lines
        assert "Última atualização: Junho de 2025 — Versão 2.1" in lines
        assert lines.index("Empório da Música — Sua música começa aqui.") < lines.index(
            "Última atualização: Junho de 2025 — Versão 2.1"
        )

    def test_pdf_confirms_paragraph_expectations(self):
        """Meta-teste: o PDF tem bold em 'Reclamação:' e não em 'Prazo de retorno'/'Última atualização'."""
        bold = pdf_bold_chars()
        assert "Reclamação:" in bold
        assert "Prazoderetorno" not in bold
        assert "Últimaatualização" not in bold

    def test_bold_only_on_labels_bold_in_pdf(self, md_text):
        bold = pdf_bold_chars()
        spans = re.findall(r"\*\*(.+?)\*\*", _COMMENT_RE.sub("", md_text))
        for span in spans:
            squeezed = "".join(span.split())
            assert squeezed in bold, f"negrito no .md sem negrito correspondente no PDF: **{span}**"


# ---------------------------------------------------------------------------
# 7. Script (CLI, determinismo, --check, formato de arquivo)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def generated(script_run_dir) -> Path:
    out = script_run_dir / "policies_1.md"
    proc = run_script("--out", str(out))
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert out.is_file()
    return out


class TestScript:
    def test_runs_with_out_in_tmp(self, generated):
        assert generated.stat().st_size > 0

    def test_two_runs_are_byte_identical(self, generated, script_run_dir):
        out2 = script_run_dir / "policies_2.md"
        proc = run_script("--out", str(out2))
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        assert out2.read_bytes() == generated.read_bytes()

    def test_rewriting_same_out_is_idempotent(self, script_run_dir):
        out = script_run_dir / "policies_idem.md"
        assert run_script("--out", str(out)).returncode == 0
        first = out.read_bytes()
        assert run_script("--out", str(out)).returncode == 0
        assert out.read_bytes() == first

    def test_output_equals_versioned_file(self, generated, md_bytes):
        assert generated.read_bytes() == md_bytes

    def test_explicit_pdf_argument_matches_default(self, script_run_dir, generated):
        out = script_run_dir / "policies_pdfarg.md"
        proc = run_script("--pdf", str(PDF_PATH), "--out", str(out))
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        assert out.read_bytes() == generated.read_bytes()

    def test_generated_output_is_faithful(self, generated, w_pdf):
        w_md = compute_w_md(generated.read_text(encoding="utf-8"))
        assert same_chars(w_pdf, w_md), first_divergence(w_pdf, w_md)

    def test_check_ok_with_versioned_file(self, md_bytes):
        proc = run_script("--check", "--out", str(MD_PATH))
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")

    def test_check_default_out_is_versioned_file(self, md_bytes):
        proc = run_script("--check")
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")

    def test_check_fails_with_altered_file(self, script_run_dir, generated):
        altered = script_run_dir / "altered.md"
        altered.write_bytes(generated.read_bytes() + b"linha extra\n")
        before = altered.read_bytes()
        proc = run_script("--check", "--out", str(altered))
        assert proc.returncode == 1
        assert altered.read_bytes() == before, "--check não pode escrever"

    def test_check_fails_with_one_word_changed(self, script_run_dir, generated):
        altered = script_run_dir / "altered_word.md"
        altered.write_bytes(generated.read_bytes().replace(b"7 (sete)", b"8 (oito)", 1))
        assert run_script("--check", "--out", str(altered)).returncode == 1

    def test_check_fails_when_out_missing(self, script_run_dir):
        missing = script_run_dir / "nao_existe.md"
        proc = run_script("--check", "--out", str(missing))
        assert proc.returncode == 1
        assert not missing.exists(), "--check não pode criar o arquivo"

    def test_check_passes_on_fresh_output(self, script_run_dir, generated):
        assert run_script("--check", "--out", str(generated)).returncode == 0

    def test_utf8_lf_single_trailing_newline(self, md_bytes, generated):
        for data in (md_bytes, generated.read_bytes()):
            assert not data.startswith(b"\xef\xbb\xbf"), "BOM não permitido"
            text = data.decode("utf-8")  # levanta se não for UTF-8 válido
            assert "\r" not in text
            assert text.endswith("\n") and not text.endswith("\n\n")
            assert "ó" in text and "Empório" in text  # acentos preservados (não mojibake)
            # mojibake real = UTF-8 lido como latin-1/cp1252: "Ã"/"Â" + U+0080–U+00BF
            # ("Ã" sozinho é letra válida em português, ex.: "NÃO")
            assert not re.search(r"[ÃÂ][\u0080-¿]", text)


# ---------------------------------------------------------------------------
# 8. Sem texto de política no script
# ---------------------------------------------------------------------------

POLICY_PHRASES = [
    "sem necessidade de justificativa",
    "Frete grátis para pedidos acima",
    "rain check",
    "7 (sete) dias",
    "30 (trinta) dias",
    "90 (noventa) dias",
    "motoboy próprio",
    "Boquilhas",
    "taxa fixa",
    "venda final",
    "consentimento explícito",
    "propaganda enganosa",
    "Democratizar o acesso",
    "24 horas úteis",
    "não são cumulativas",
    "Compensação em até",
    "Todas as bandeiras",
    "Mato Grosso do Sul",
    "12.345.678/0001-90",
    "3321-4500",
]


class TestNoPolicyTextInScript:
    @pytest.fixture(scope="class")
    @classmethod
    def script_text(cls) -> str:
        assert SCRIPT_PATH.is_file(), f"scripts/build_policies.py não existe ({SCRIPT_PATH})"
        return SCRIPT_PATH.read_text(encoding="utf-8")

    @pytest.mark.parametrize("phrase", POLICY_PHRASES)
    def test_distinctive_policy_phrase_absent(self, script_text, phrase):
        assert phrase.lower() not in " ".join(script_text.split()).lower()

    def test_phrases_are_really_policy_text(self, pdf_text):
        """Meta-teste: as frases acima vêm mesmo do PDF."""
        flat = pdf_text.lower()
        for phrase in POLICY_PHRASES:
            assert phrase.lower() in flat, phrase

    def test_script_does_not_import_package(self, script_text):
        assert not re.search(r"^\s*(?:from|import)\s+emporio_agent", script_text, re.MULTILINE)

    def test_script_uses_pypdf(self, script_text):
        assert "pypdf" in script_text


# ---------------------------------------------------------------------------
# 9. PDF intacto
# ---------------------------------------------------------------------------


class TestPdfUntouched:
    def test_pdf_hash_unchanged_by_script(self, script_run_dir):
        before = sha256(PDF_PATH)
        mtime_before = PDF_PATH.stat().st_mtime_ns
        for args in (["--out", str(script_run_dir / "hash_run.md")], ["--check", "--out", str(MD_PATH)]):
            run_script(*args)
        assert sha256(PDF_PATH) == before
        assert PDF_PATH.stat().st_mtime_ns == mtime_before
