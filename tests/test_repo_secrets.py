"""Higiene de segredos: nada com cara de chave real versionado; .env fora do Git; frontend sem chaves."""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

PATTERNS = {
    "chave Anthropic": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "chave Groq": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "atribuição de segredo": re.compile(r"(API_KEY|SECRET|TOKEN)\s*=\s*['\"]?[A-Za-z0-9_\-]{24,}"),
    "chave privada": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
}
# Valores falsos conhecidos (exatos) usados nos testes.
ALLOWED = {"sk-ant-segredo-123456", "gsk_segredo_123456", "sk-ant-x"}
# Este arquivo contém os padrões; fica fora da varredura.
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()
BINARY_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".xlsx", ".zip"}


def _git(*args):
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git indisponível ou fora de um repositório")
    return out.stdout


def _tracked():
    return [f for f in _git("ls-files").splitlines() if f != SELF and Path(f).suffix.lower() not in BINARY_EXT]


def test_nenhum_segredo_com_cara_de_real_versionado():
    achados = set()
    for rel in _tracked():
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for nome, rx in PATTERNS.items():
            for m in rx.finditer(text):
                if m.group(0) not in ALLOWED:
                    achados.add(f"{rel}: {nome}")  # nunca imprime o valor
    assert not achados, "possíveis segredos versionados: " + "; ".join(sorted(achados))


def test_env_nao_versionado_e_ignorado():
    assert ".env" not in _git("ls-files").splitlines()
    linhas = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in [ln.strip() for ln in linhas]


def test_env_example_sem_valores_de_chave():
    for ln in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        ln = ln.strip().lstrip("#").strip()
        if "_API_KEY=" in ln:
            nome, valor = ln.split("=", 1)
            assert valor.strip() == "", f"{nome} deve ficar vazio no .env.example"


def test_frontend_nao_referencia_chaves():
    rx = re.compile(r"ANTHROPIC|GROQ|API_KEY", re.IGNORECASE)
    ofensores = []
    for f in (ROOT / "frontend" / "src").rglob("*"):
        if f.is_file():
            try:
                if rx.search(f.read_text(encoding="utf-8")):
                    ofensores.append(f.relative_to(ROOT).as_posix())
            except UnicodeDecodeError:
                continue
    assert not ofensores, f"frontend referencia chaves de API: {ofensores}"
