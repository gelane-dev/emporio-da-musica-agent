"""Testes de endurecimento da API (limites, expiração, logs, cabeçalhos) — sem provedor real."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from emporio_agent.agent.agent import AgentReply
from emporio_agent.api.app import MAX_BODY_BYTES, create_app
from emporio_agent.api.sessions import SessionStore
from emporio_agent.config import Settings, load_settings

from fakes import FakeLLM, fake_text

TZ = ZoneInfo("America/Campo_Grande")
MONDAY = datetime(2026, 11, 2, 10, 0, tzinfo=TZ)
SECRET = "sk-ant-TESTSECRET123"


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class BlockingAgent:
    """Agente falso que bloqueia em ``respond`` até o teste liberar."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def respond(self, session, text):
        session.add_user(text)
        self.started.set()
        assert self.release.wait(10)
        return AgentReply(text="ok", tool_calls=[], stop="end_turn")


class ExplodingAgent:
    def respond(self, session, text):
        raise RuntimeError("falha interna")


def make_app(tmp_path, responses=(), env=None, clock=None, **kwargs):
    settings = Settings(runtime_dir=tmp_path, reference_datetime=MONDAY, **kwargs)
    extra = {"clock": clock} if clock else {}
    return create_app(settings, llm=FakeLLM(list(responses)), env=env if env is not None else {}, **extra)


def make_client(tmp_path, responses=(), **kwargs):
    return TestClient(make_app(tmp_path, responses, **kwargs))


def new_session(client) -> str:
    return client.post("/api/sessions").json()["session_id"]


# ------------------------------------------------------------------ configuração


def test_novas_configuracoes_padrao_e_invalidas():
    s = Settings()
    assert (s.llm_timeout_seconds, s.max_concurrent_chats, s.session_ttl_minutes) == (60, 8, 30)
    assert (s.max_messages_per_session, s.api_docs) == (100, True)
    loaded = load_settings(environ={"API_DOCS": "false", "MAX_CONCURRENT_CHATS": "2", "LLM_TIMEOUT_SECONDS": "5"})
    assert loaded.api_docs is False and loaded.max_concurrent_chats == 2 and loaded.llm_timeout_seconds == 5
    for name in ("LLM_TIMEOUT_SECONDS", "MAX_CONCURRENT_CHATS", "SESSION_TTL_MINUTES", "MAX_MESSAGES_PER_SESSION"):
        with pytest.raises(ValueError):
            load_settings(environ={name: "0"})
    with pytest.raises(ValueError):
        load_settings(environ={"API_DOCS": "talvez"})


# ------------------------------------------------------------------ concorrência


def test_limite_de_conversas_simultaneas_retorna_503_busy(tmp_path):
    app = make_app(tmp_path, max_concurrent_chats=1)
    agent = BlockingAgent()
    app.state.api.agent = agent
    client = TestClient(app)
    first_session = new_session(client)
    other_session = new_session(client)
    result = {}

    def first():
        result["r"] = client.post("/api/chat", json={"session_id": first_session, "message": "oi"})

    thread = threading.Thread(target=first)
    thread.start()
    assert agent.started.wait(10)
    response = client.post("/api/chat", json={"session_id": other_session, "message": "oi"})
    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "busy" and body["message"]
    # sem session_id também é recusado, e nenhuma sessão nova é criada
    total = len(app.state.api.sessions)
    assert client.post("/api/chat", json={"message": "oi"}).status_code == 503
    assert len(app.state.api.sessions) == total
    agent.release.set()
    thread.join(10)
    assert result["r"].status_code == 200
    # a vaga foi devolvida e a outra sessão não ficou presa
    assert client.post("/api/chat", json={"session_id": other_session, "message": "oi"}).status_code == 200


def test_vaga_devolvida_apos_erro_500(tmp_path):
    app = make_app(tmp_path, max_concurrent_chats=1)
    app.state.api.agent = ExplodingAgent()
    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(2):
        assert client.post("/api/chat", json={"message": "oi"}).status_code == 500


# ------------------------------------------------------------------ expiração


def test_sessao_ociosa_expira_com_relogio_injetado(tmp_path):
    clock = Clock()
    client = TestClient(make_app(tmp_path, [fake_text("a"), fake_text("b")], clock=clock, session_ttl_minutes=30))
    sid = new_session(client)
    clock.t += 29 * 60
    assert client.post("/api/chat", json={"session_id": sid, "message": "oi"}).status_code == 200
    clock.t += 29 * 60  # o uso renovou o prazo
    assert client.post("/api/chat", json={"session_id": sid, "message": "oi"}).status_code == 200
    clock.t += 31 * 60
    response = client.post("/api/chat", json={"session_id": sid, "message": "oi"})
    assert response.status_code == 404 and response.json()["error"] == "session_not_found"
    assert client.delete(f"/api/sessions/{sid}").status_code == 404


def test_criacao_varre_sessoes_expiradas():
    clock = Clock()
    store = SessionStore(10, ttl_seconds=60, clock=clock)
    store.create(MONDAY)
    clock.t += 61
    store.create(MONDAY)
    assert len(store) == 1


def test_sessao_ocupada_nao_expira():
    clock = Clock()
    store = SessionStore(10, ttl_seconds=60, clock=clock)
    session = store.create(MONDAY)
    with store.use(session.id):
        clock.t += 600
        store.create(MONDAY)
        assert session.id in store
    clock.t += 30  # o fim do uso renovou o prazo
    assert session.id in store
    clock.t += 61
    assert session.id not in store


# ------------------------------------------------------------------ tamanho da sessão


def test_sessao_cheia_retorna_429(tmp_path):
    client = make_client(tmp_path, [fake_text("a"), fake_text("b")], max_messages_per_session=2)
    sid = new_session(client)
    for _ in range(2):
        assert client.post("/api/chat", json={"session_id": sid, "message": "oi"}).status_code == 200
    response = client.post("/api/chat", json={"session_id": sid, "message": "oi"})
    assert response.status_code == 429
    body = response.json()
    assert body["error"] == "session_full" and "nova conversa" in body["message"]
    # a sessão não ficou presa e continua existindo
    assert client.post("/api/chat", json={"session_id": sid, "message": "oi"}).status_code == 429


# ------------------------------------------------------------------ entrada


def test_campo_extra_retorna_422(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/chat", json={"message": "oi", "admin": True})
    assert response.status_code == 422 and response.json()["error"] == "invalid_request"


def test_caracteres_de_controle_sao_removidos(tmp_path):
    llm = FakeLLM([fake_text("ok")])
    client = TestClient(create_app(Settings(runtime_dir=tmp_path, reference_datetime=MONDAY), llm=llm, env={}))
    response = client.post("/api/chat", json={"message": "ol\x00\x1b[31má\x07\x7f\nlinha\ttab"})
    assert response.status_code == 200
    assert llm.calls[0]["messages"][-1].content == "ol[31má\nlinha\ttab"


def test_somente_caracteres_de_controle_e_mensagem_vazia(tmp_path):
    client = make_client(tmp_path)
    assert client.post("/api/chat", json={"message": "\x00\x01 \x1f"}).status_code == 422


def test_limite_de_2000_caracteres(tmp_path):
    client = make_client(tmp_path, [fake_text("ok")])
    assert client.post("/api/chat", json={"message": "a" * 2001}).status_code == 422
    assert client.post("/api/chat", json={"message": "a" * 2000}).status_code == 200


@pytest.mark.parametrize("bad", ["../etc/passwd", "a b", "x" * 65, "id\n", "%00"])
def test_session_id_com_formato_invalido_retorna_422(tmp_path, bad):
    client = make_client(tmp_path)
    assert client.post("/api/chat", json={"session_id": bad, "message": "oi"}).status_code == 422


def test_corpo_grande_por_content_length_retorna_413(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/chat", content=b"x" * (MAX_BODY_BYTES + 1), headers={"content-type": "application/json"})
    assert response.status_code == 413 and response.json()["error"] == "payload_too_large"


def test_corpo_grande_chunked_retorna_413(tmp_path):
    client = make_client(tmp_path)

    def chunks():
        for _ in range(MAX_BODY_BYTES // 1024 + 2):
            yield b"x" * 1024

    response = client.post("/api/chat", content=chunks(), headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_json_malformado_retorna_422_sem_ecoar_entrada(tmp_path):
    client = make_client(tmp_path)
    response = client.post(
        "/api/chat", content=b'{"message": "SEGREDO-ECOADO", ', headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    assert "SEGREDO-ECOADO" not in response.text


def test_sessao_desconhecida_ou_adivinhada_retorna_404(tmp_path):
    client = make_client(tmp_path)
    sid = new_session(client)
    for guess in ("inexistente", sid[:-1] + ("A" if sid[-1] != "A" else "B"), sid[:6]):
        response = client.post("/api/chat", json={"session_id": guess, "message": "oi"})
        assert response.status_code == 404 and response.json()["error"] == "session_not_found"
    assert client.delete("/api/sessions/inexistente").status_code == 404


# ------------------------------------------------------------------ erros, docs, cabeçalhos


def test_erro_500_e_generico_sem_texto_da_excecao(tmp_path):
    app = make_app(tmp_path, env={"ANTHROPIC_API_KEY": SECRET})
    app.state.api.agent = ExplodingAgent()
    response = TestClient(app, raise_server_exceptions=False).post("/api/chat", json={"message": "oi"})
    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert "falha interna" not in response.text and SECRET not in response.text


def test_docs_desligadas_retornam_404(tmp_path):
    client = make_client(tmp_path, api_docs=False)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
    assert client.get("/api/health").status_code == 200


def test_docs_ligadas_por_padrao(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_cabecalhos_de_seguranca(tmp_path):
    client = make_client(tmp_path)
    for response in (client.get("/api/health"), client.post("/api/chat", json={}), client.get("/nada")):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/health").headers["cache-control"] == "no-store"
    assert "content-security-policy" not in client.get("/docs").headers


def test_logs_nunca_trazem_o_id_completo_nem_corpo(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    client = make_client(tmp_path, [fake_text("resposta")])
    sid = new_session(client)
    client.post("/api/chat?token=abc", json={"session_id": sid, "message": "TEXTO-SECRETO-CLIENTE"})
    client.delete(f"/api/sessions/{sid}")
    client.get(f"/api/desconhecido/{sid}")
    # só os logs da aplicação (o cliente de teste, httpx, registra as próprias URLs)
    text = " | ".join(r.getMessage() for r in caplog.records if r.name.startswith("emporio_agent"))
    assert sid not in text
    assert "TEXTO-SECRETO-CLIENTE" not in text and "token=abc" not in text
    assert sid[:6] in text
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("request ")]
    assert len(lines) == 4
    assert "path=/api/sessions/{session_id} status=204" in lines[2]
    assert "duration_ms=" in lines[0] and "method=POST" in lines[0]
    assert "path=(sem rota)" in lines[3]


def test_segredo_nao_aparece_em_respostas_nem_logs(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    env = {"ANTHROPIC_API_KEY": SECRET, "GROQ_API_KEY": SECRET}
    app = make_app(tmp_path, env=env)
    client = TestClient(app, raise_server_exceptions=False)
    outputs = [client.get("/api/health").text, client.get("/api/health", headers={"x-api-key": SECRET}).text]
    outputs.append(client.post("/api/chat", json={"message": ""}).text)
    outputs.append(client.post("/api/chat", json={"session_id": "nao-existe", "message": "oi"}).text)
    app.state.api.agent = ExplodingAgent()
    outputs.append(client.post("/api/chat", json={"message": "oi"}).text)
    degraded = TestClient(create_app(Settings(runtime_dir=tmp_path), env=env))
    outputs.append(degraded.get("/api/health").text)
    assert all(SECRET not in text for text in outputs)
    assert SECRET not in caplog.text
