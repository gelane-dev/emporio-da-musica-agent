# Backend: API FastAPI do agente Mel (python -m emporio_agent.api).
# Contexto de build: raiz do repositório (o .dockerignore deixa entrar só o necessário).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Layout src/: o pacote é importado direto do código copiado. config.REPO_ROOT resolve para /app,
    # onde ficam data/, knowledge/ e runtime/ — a mesma estrutura do repositório.
    PYTHONPATH=/app/src \
    API_HOST=0.0.0.0 \
    API_PORT=8000

WORKDIR /app

# Dependências primeiro (camada reaproveitada enquanto requirements.txt não mudar).
# Fora da imagem: a instalação editável do pacote (-e .) e o pytest, que só servem ao desenvolvimento.
COPY requirements.txt .
RUN grep -vE '^(-e |pytest==)' requirements.txt > /tmp/requirements-runtime.txt \
    && pip install -r /tmp/requirements-runtime.txt \
    && rm /tmp/requirements-runtime.txt

RUN useradd --create-home --uid 10001 mel

COPY src/ src/
COPY knowledge/ knowledge/
COPY data/ data/
# runtime/ recebe os encaminhamentos ao atendente (handoffs.jsonl); no Compose é um volume.
RUN mkdir -p runtime && chown mel:mel runtime

USER mel
EXPOSE 8000

# 200 também quando o agente está "degraded" (ex.: sem chave): o processo está no ar;
# o estado do agente aparece no corpo de /api/health e no cabeçalho do frontend.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

CMD ["python", "-m", "emporio_agent.api"]
