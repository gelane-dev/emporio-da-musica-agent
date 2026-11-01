#!/usr/bin/env python
"""Convert the store policy manual (PDF) into a topic-segmented Markdown file.

Usage:
    python scripts/build_policies.py [--pdf PATH] [--out PATH] [--check]

Contract: ARCHITECTURE.md section 5.4.1. All policy text comes from the PDF;
this script only holds *structure* literals (section -> topic map, header and
footer to strip, table headers, H1, cover title and the extraction note).

Structure that is not in the text itself is read from the PDF drawing
operations: paragraph boundaries come from the vertical spacing / font size
between lines, and bold comes from the font name (``*-Bold``) of the drawn text.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = REPO_ROOT / "data" / "políticas_da_loja.pdf"
DEFAULT_OUT = REPO_ROOT / "knowledge" / "policies.md"

# --- structure literals -----------------------------------------------------

H1 = "# Manual de Políticas e Procedimentos — Empório da Música"
COVER_TITLE = "## Capa"
COVER_TOPIC = "sobre_loja"
EXTRACTION_NOTE = (
    "> Nota de extração: gerado por scripts/build_policies.py a partir de "
    "data/políticas_da_loja.pdf (Versão 2.1 — Junho de 2025).\n"
    "> Texto fiel ao PDF. Divergências do próprio manual NÃO corrigidas: "
    "P1 (telefones), P2 (grafias do e-mail), P3/P4 (parcelamento). "
    "Ver DATA_ANALYSIS.md §4.2."
)

# H2 section number -> topic marker
SECTION_TOPICS = {
    1: "sobre_loja",
    2: "horarios",
    3: "pagamento",
    4: "trocas_devolucoes",
    5: "frete_entrega",
    6: "promocoes",
    7: "atendimento",
    8: "garantia",
    9: "privacidade",
    10: "atendimento",
}

PAGE_HEADER = "Empório da Música Manual de Políticas e Procedimentos"
PAGE_FOOTER_RE = re.compile(r"^Página \d+$")

TABLE_HEADERS = [
    ("Campo", "Informação"),
    ("Dia", "Horário"),
    ("Forma", "Condições", "Observações"),
    ("Modalidade", "Prazo Estimado", "Rastreamento", "Seguro"),
]

# A new paragraph starts when the distance to the previous line is larger than
# this multiple of the font size (wrapped lines are ~1.1-1.15x in the PDF,
# paragraph spacing ~1.45x), or when the font size changes.
PARA_GAP_RATIO = 1.3
LINE_Y_TOLERANCE = 1.0  # fragments within this vertical distance share a line

# --- parsing helpers --------------------------------------------------------

H2_RE = re.compile(r"^(\d{1,2})\. (\S.*)$")
H3_RE = re.compile(r"^(\d{1,2})\.(\d) \S")
BULLET_RE = re.compile(r"^\s*•\s+(.*)$")
NUMBERED_RE = re.compile(r"^\s*(\d)\.\s{2,}(\S.*)$")
CELL_SPLIT_RE = re.compile(r"\s{2,}")
FRAGMENT_RE = re.compile(r"\S+(?:[ ]\S+)*")


@dataclass
class Line:
    """One layout line plus the PDF facts (position, font) used for structure."""

    text: str  # layout text, right-stripped ("" = blank layout line)
    y: float = 0.0
    size: float = 0.0
    bold_prefix: str = ""  # leading words drawn in a bold font ("" = none)
    all_bold: bool = False


def pdf_line_facts(page) -> list[tuple[float, float, str, bool, str]]:
    """Visual lines of a page, top to bottom.

    Each item: (y, font size, bold prefix, all bold, whitespace-free text).
    """
    frags: list[tuple[float, float, float, bool, str]] = []

    def visitor(text, cm, tm, font_dict, font_size):
        if not text.strip():
            return
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        bold = "bold" in str((font_dict or {}).get("/BaseFont", "")).lower()
        frags.append((y, x, font_size, bold, text.strip()))

    page.extract_text(visitor_text=visitor)
    frags.sort(key=lambda f: (-f[0], f[1]))
    clusters: list[list[tuple[float, float, float, bool, str]]] = []
    for f in frags:
        if clusters and clusters[-1][0][0] - f[0] <= LINE_Y_TOLERANCE:
            clusters[-1].append(f)
        else:
            clusters.append([f])
    facts = []
    for c in clusters:
        c.sort(key=lambda f: f[1])
        prefix: list[str] = []
        for f in c:
            if not f[3]:
                break
            prefix.append(f[4])
        squashed = re.sub(r"\s+", "", "".join(f[4] for f in c))
        facts.append((c[0][0], max(f[2] for f in c), " ".join(prefix),
                      len(prefix) == len(c), squashed))
    return facts


def page_lines(page, first_page: bool) -> list[Line]:
    """Layout lines of a page (header/footer removed) annotated with PDF facts."""
    raw = [ln.rstrip() for ln in page.extract_text(extraction_mode="layout").splitlines()]
    facts = iter(pdf_line_facts(page))
    out: list[Line] = []
    for ln in raw:
        if not ln.strip():
            out.append(Line(""))
            continue
        y, size, prefix, all_bold, squashed = next(facts)
        if re.sub(r"\s+", "", ln) != squashed:
            raise RuntimeError(f"layout/visitor line mismatch: {ln.strip()!r}")
        out.append(Line(ln, y, size, prefix, all_bold))
    if next(facts, None) is not None:
        raise RuntimeError("PDF lines left unmatched")
    if first_page:
        return out
    return [
        ln
        for ln in out
        if ln.text.strip() != PAGE_HEADER and not PAGE_FOOTER_RE.match(ln.text.strip())
    ]


def bolded(line: Line) -> str:
    """Line text with ** around the words the PDF draws in a bold font."""
    s = line.text.strip()
    if not line.bold_prefix:
        return s
    if line.all_bold:
        return f"**{s}**"
    wanted = len(line.bold_prefix.replace(" ", ""))
    cut = count = 0
    while count < wanted:
        if not s[cut].isspace():
            count += 1
        cut += 1
    return f"**{s[:cut]}**{s[cut:]}"


def parse_table(lines: list[str], i: int, header: tuple[str, ...]) -> tuple[list[str], int]:
    """Parse a layout table whose header line is lines[i-1]; return md lines, next index."""
    ncols = len(header)
    rows: list[list[str]] = []
    n = len(lines)
    while i < n:
        if not lines[i].strip():
            i += 1
            continue
        j = i
        while j < n and lines[j].strip():
            j += 1
        group = lines[i:j]
        first = group[0].strip()
        if len(CELL_SPLIT_RE.split(first)) != ncols:
            break  # not a row: table is over
        starts = [m.start() for m in FRAGMENT_RE.finditer(group[0])]
        cells = [m.group(0) for m in FRAGMENT_RE.finditer(group[0])]
        for extra in group[1:]:
            for m in FRAGMENT_RE.finditer(extra):
                col = min(range(ncols), key=lambda c: abs(starts[c] - m.start()))
                cells[col] += " " + m.group(0)
        rows.append(cells)
        i = j
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * ncols]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out, i


def convert_body(lines: list[Line]) -> list[list[str]]:
    """Convert pages 2-8 into blocks (each block: marker, ## title, body lines)."""
    texts = [ln.text for ln in lines]
    blocks: list[list[str]] = []
    cur: list[str] | None = None
    section = 0
    open_kind = ""  # kind of the open paragraph / list item ("" = none)
    prev: Line | None = None  # previous line of the open paragraph
    last_kind = ""  # "", "para", "bullet", "num", "table", "head"

    def emit(kind: str, text: str) -> None:
        nonlocal last_kind
        assert cur is not None
        if kind in ("para", "table", "head") or (kind != last_kind and last_kind):
            if cur and cur[-1] != "":
                cur.append("")
        cur.append(text)
        last_kind = kind

    def continues(line: Line) -> bool:
        """True if `line` continues the open paragraph (no visual break before it)."""
        if not open_kind:
            return False
        if prev is None or prev.y < line.y:  # first line on a new page: no spacing info
            return True
        gap = prev.y - line.y
        return abs(line.size - prev.size) < 0.5 and gap <= PARA_GAP_RATIO * line.size

    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        raw = line.text
        s = raw.strip()
        if not s:
            i += 1
            continue
        m2 = H2_RE.match(s)
        if m2 and int(m2.group(1)) == section + 1 and int(m2.group(1)) in SECTION_TOPICS:
            section = int(m2.group(1))
            cur = [f"<!-- topic: {SECTION_TOPICS[section]} -->", f"## {s}"]
            blocks.append(cur)
            last_kind = "head"
            open_kind, prev = "", None
            i += 1
            continue
        m3 = H3_RE.match(s)
        if m3 and int(m3.group(1)) == section:
            emit("head", f"### {s}")
            last_kind = "head"
            open_kind, prev = "", None
            i += 1
            continue
        cells = tuple(CELL_SPLIT_RE.split(s))
        if cells in TABLE_HEADERS:
            tbl, i = parse_table(texts, i + 1, cells)
            for k, row in enumerate(tbl):
                if k == 0:
                    emit("table", row)
                else:
                    assert cur is not None
                    cur.append(row)
            last_kind = "table"
            open_kind, prev = "", None
            continue
        mb = BULLET_RE.match(raw)
        mn = NUMBERED_RE.match(raw)
        if mb or mn:
            if line.bold_prefix:
                raise RuntimeError(f"unexpected bold in list item: {s!r}")
            if mb:
                emit("bullet", "- " + mb.group(1).strip())
                open_kind = "bullet"
            else:
                emit("num", f"{mn.group(1)}. {mn.group(2).strip()}")
                open_kind = "num"
        elif continues(line):
            if line.bold_prefix:
                raise RuntimeError(f"unexpected bold in continuation line: {s!r}")
            assert cur is not None
            cur[-1] += " " + s
        else:
            emit("para", bolded(line))
            open_kind = "para"
        prev = line
        i += 1
    return blocks


def build(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = [page_lines(p, first_page=(k == 0)) for k, p in enumerate(reader.pages)]

    cover = [bolded(ln) for ln in pages[0] if ln.text.strip()]
    body: list[Line] = []
    for lines in pages[1:]:
        body += lines

    out = [H1, "", EXTRACTION_NOTE, ""]
    out += [f"<!-- topic: {COVER_TOPIC} -->", COVER_TITLE, *cover]
    for block in convert_body(body):
        out += ["", *block]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 0 if --out is identical to the generated output, else 1")
    args = ap.parse_args(argv)

    content = build(args.pdf).encode("utf-8")
    if args.check:
        same = args.out.exists() and args.out.read_bytes() == content
        return 0 if same else 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
