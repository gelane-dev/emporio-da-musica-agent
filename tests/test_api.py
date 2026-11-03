"""Testes da API HTTP (FastAPI) com FakeLLM — nunca chamam um provedor real."""

from __future__ import annotations

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from emporio_agent.api.app import DEFAULT_CORS_ORIGINS, create_app
from emporio_agent.api.sessions import SessionBusy, SessionNotFound, SessionStore
from emporio_agent.config import Settings
from emporio_agent.llm.base import LLMError

from fakes import FakeLLM, fake_text, fake_tool_calls

TZ = ZoneInfo("America/Campo_Grande")
MONDAY = datetime(2026, 11, 2, 10, 0, tzinfo=TZ)  # loja aberta
EMAIL = "lucas.mendes@jmail.com"


def make_settings(tmp_path, **kwargs) -> Settings:
    return Settings(runtime_dir=tmp_path, reference_datetime=MONDAY, **kwargs)


def make_client(tmp_path, responses=(), env=None, **kwargs):
    llm = FakeLLM(list(responses))
    app = create_app(make_settings(tmp_path, **kwargs), llm=llm, env=env if env is not None else {})
    return TestClient(app), llm


def assert_envelope(response, status: int, error: str) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error", "message"}
    assert body["error"] == error
    assert body["message"]
    return body


# ----------------------------------------------------------------------------- health


def test_health_ok(tmp_path):
    client, _ = make_client(tmp_path)
    body = client.get("/api/health").json()
    assert body == {
        "status": "ok",
        "agent_ready": True,
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "detail": None,
    }


def test_health_degraded_sem_chave(tmp_path):
    app = create_app(make_settings(tmp_path), env={})  # sem llm e sem GROQ_API_KEY
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["agent_ready"] is False
    assert "GROQ_API_KEY" in body["detail"]


def test_health_degraded_dados_ausentes(tmp_path):
    app = create_app(make_settings(tmp_path, data_dir=tmp_path / "inexistente"), llm=FakeLLM([]), env={})
    body = TestClient(app).get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["detail"] == "Não foi possível carregar os dados da loja."
    assert str(tmp_path) not in body["detail"]


# ----------------------------------------------------------------------------- 503


def test_agente_indisponivel_retorna_503(tmp_path):
    client = TestClient(create_app(make_settings(tmp_path), env={}))
    assert_envelope(client.post("/api/sessions"), 503, "agent_unavailable")
    assert_envelope(client.post("/api/chat", json={"message": "oi"}), 503, "agent_unavailable")


# ----------------------------------------------------------------------------- sessões


def test_criar_sessao_com_saudacao(tmp_path):
    client, llm = make_client(tmp_path)
    response = client.post("/api/sessions")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"session_id", "greeting", "created_at"}
    assert body["session_id"]
    assert body["greeting"].startswith("Olá! Eu sou a Mel")
    assert "A loja está aberta agora" in body["greeting"]
    assert datetime.fromisoformat(body["created_at"]) == MONDAY
    assert llm.calls == []  # saudação não chama o modelo


def test_delete_sessao_204_e_depois_404(tmp_path):
    client, _ = make_client(tmp_path)
    session_id = client.post("/api/sessions").json()["session_id"]
    response = client.delete(f"/api/sessions/{session_id}")
    assert response.status_code == 204
    assert response.content == b""
    assert_envelope(client.delete(f"/api/sessions/{session_id}"), 404, "session_not_found")
    assert_envelope(client.post("/api/chat", json={"session_id": session_id, "message": "oi"}), 404, "session_not_found")


def test_delete_sessao_desconhecida_404(tmp_path):
    client, _ = make_client(tmp_path)
    assert_envelope(client.delete("/api/sessions/naoexiste"), 404, "session_not_found")


# ----------------------------------------------------------------------------- chat


def test_chat_sem_session_id_cria_sessao(tmp_path):
    client, llm = make_client(tmp_path, [fake_text("Olá! Como posso ajudar?")])
    response = client.post("/api/chat", json={"session_id": None, "message": "  oi  "})
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["reply"] == "Olá! Como posso ajudar?"
    assert body["stop"] == "end_turn"
    assert body["tool_calls"] == []
    assert llm.calls[0]["messages"][-1].content == "oi"  # mensagem chega sem espaços nas pontas


def test_chat_campo_session_id_ausente_cria_sessao(tmp_path):
    client, _ = make_client(tmp_path, [fake_text("ok")])
    assert client.post("/api/chat", json={"message": "oi"}).json()["session_id"]


def test_chat_preserva_contexto_na_mesma_sessao(tmp_path):
    client, llm = make_client(tmp_path, [fake_text("Resposta 1"), fake_text("Resposta 2")])
    session_id = client.post("/api/sessions").json()["session_id"]
    first = client.post("/api/chat", json={"session_id": session_id, "message": "primeira"})
    second = client.post("/api/chat", json={"session_id": session_id, "message": "segunda"})
    assert first.json()["session_id"] == second.json()["session_id"] == session_id
    assert second.json()["reply"] == "Resposta 2"
    history = [(m.role, m.content) for m in llm.calls[1]["messages"]]
    assert history == [("user", "primeira"), ("assistant", "Resposta 1"), ("user", "segunda")]


def test_sessoes_diferentes_nao_compartilham_contexto(tmp_path):
    client, llm = make_client(tmp_path, [fake_text("a"), fake_text("b")])
    client.post("/api/chat", json={"message": "sessao A"})
    client.post("/api/chat", json={"message": "sessao B"})
    assert [m.content for m in llm.calls[1]["messages"]] == ["sessao B"]


def test_chat_com_ferramenta_real_sem_expor_argumentos(tmp_path):
    client, llm = make_client(
        tmp_path,
        [
            fake_tool_calls(("buscar_produtos", {"texto": "violão"}), ids=["t1"]),
            fake_text("Temos estes violões."),
        ],
    )
    response = client.post("/api/chat", json={"message": "tem violão?"})
    body = response.json()
    assert response.status_code == 200
    assert body["reply"] == "Temos estes violões."
    assert len(body["tool_calls"]) == 1
    call = body["tool_calls"][0]
    assert set(call) == {"name", "ok", "duration_ms"}
    assert call["name"] == "buscar_produtos"
    assert call["ok"] is True
    assert isinstance(call["duration_ms"], int)
    tool_result = llm.calls[1]["messages"][-1]
    assert tool_result.role == "tool" and not tool_result.is_error


def test_chat_nao_expoe_dados_pessoais_de_consultar_pedido(tmp_path):
    client, _ = make_client(
        tmp_path,
        [fake_tool_calls(("consultar_pedido", {"pedido_id": 4, "email": EMAIL}), ids=["t1"]), fake_text("Achei.")],
    )
    response = client.post("/api/chat", json={"message": "pedido 4"})
    assert response.json()["tool_calls"][0]["name"] == "consultar_pedido"
    assert EMAIL not in response.text


def test_chat_llm_error_retorna_200(tmp_path):
    client, _ = make_client(tmp_path, [LLMError("network", "Sem conexão com o provedor.")])
    response = client.post("/api/chat", json={"message": "oi"})
    assert response.status_code == 200
    body = response.json()
    assert body["stop"] == "llm_error"
    assert body["reply"]


# ----------------------------------------------------------------------------- 422


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"message": ""}, "A mensagem não pode ficar vazia."),
        ({"message": "   \n\t "}, "A mensagem não pode ficar vazia."),
        ({"message": "a" * 2001}, "A mensagem pode ter no máximo 2000 caracteres."),
        ({}, "O campo 'message' é obrigatório."),
        ({"message": 123}, "O campo 'message' precisa ser um texto."),
        ({"message": "oi", "session_id": 5}, "O campo 'session_id' precisa ser um texto ou nulo."),
    ],
)
def test_chat_mensagem_invalida_422(tmp_path, payload, expected):
    client, llm = make_client(tmp_path)
    body = assert_envelope(client.post("/api/chat", json=payload), 422, "invalid_request")
    assert body["message"] == expected
    assert llm.calls == []


def test_chat_mensagem_com_2000_caracteres_apos_strip_e_aceita(tmp_path):
    client, _ = make_client(tmp_path, [fake_text("ok")])
    assert client.post("/api/chat", json={"message": "  " + "a" * 2000 + "  "}).status_code == 200


@pytest.mark.parametrize("content", [b"isto nao e json", b"", b"[1, 2]"])
def test_chat_corpo_invalido_422(tmp_path, content):
    client, _ = make_client(tmp_path)
    response = client.post("/api/chat", content=content, headers={"Content-Type": "application/json"})
    assert_envelope(response, 422, "invalid_request")


# ----------------------------------------------------------------------------- 409 / 500


def test_sessao_ocupada_409(tmp_path):
    client, _ = make_client(tmp_path)
    session_id = client.post("/api/sessions").json()["session_id"]
    with client.app.state.api.sessions.use(session_id):  # simula mensagem em andamento
        response = client.post("/api/chat", json={"session_id": session_id, "message": "oi"})
    assert_envelope(response, 409, "session_busy")


def test_sessao_ocupada_409_concorrente(tmp_path):
    started, release = threading.Event(), threading.Event()

    class SlowLLM(FakeLLM):
        def complete(self, **kwargs):
            started.set()
            release.wait(5)
            return super().complete(**kwargs)

    llm = SlowLLM([fake_text("lenta")])
    client = TestClient(create_app(make_settings(tmp_path), llm=llm, env={}))
    session_id = client.post("/api/sessions").json()["session_id"]
    results = {}
    worker = threading.Thread(
        target=lambda: results.update(
            first=client.post("/api/chat", json={"session_id": session_id, "message": "1"})
        )
    )
    worker.start()
    assert started.wait(5)
    second = client.post("/api/chat", json={"session_id": session_id, "message": "2"})
    release.set()
    worker.join(5)
    assert_envelope(second, 409, "session_busy")
    assert results["first"].status_code == 200


def test_erro_inesperado_500_sem_detalhes(tmp_path):
    client, _ = make_client(tmp_path)
    agent = client.app.state.api.agent

    def boom(session, text):
        raise RuntimeError("detalhe-interno-secreto")

    agent.respond = boom
    client = TestClient(client.app, raise_server_exceptions=False)
    response = client.post(
        "/api/chat", json={"message": "oi"}, headers={"Origin": DEFAULT_CORS_ORIGINS[0]}
    )
    body = assert_envelope(response, 500, "internal_error")
    assert "detalhe-interno-secreto" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in body["message"]
    assert response.headers["access-control-allow-origin"] == DEFAULT_CORS_ORIGINS[0]


def test_sessao_liberada_apos_erro(tmp_path):
    client, _ = make_client(tmp_path)
    session_id = client.post("/api/sessions").json()["session_id"]
    agent = client.app.state.api.agent
    original = agent.respond
    agent.respond = lambda s, t: (_ for _ in ()).throw(RuntimeError("x"))
    client = TestClient(client.app, raise_server_exceptions=False)
    assert client.post("/api/chat", json={"session_id": session_id, "message": "oi"}).status_code == 500
    agent.respond = original
    client.app.state.api.agent._llm._responses.append(fake_text("voltou"))
    response = client.post("/api/chat", json={"session_id": session_id, "message": "oi"})
    assert response.status_code == 200


def test_rota_inexistente_usa_envelope(tmp_path):
    client, _ = make_client(tmp_path)
    assert_envelope(client.get("/api/nada"), 404, "not_found")


# ----------------------------------------------------------------------------- CORS


def test_cors_preflight_origem_padrao_permitida(tmp_path):
    client, _ = make_client(tmp_path)
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_preflight_origem_estranha_negada(tmp_path):
    client, _ = make_client(tmp_path)
    response = client.options(
        "/api/chat",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_configuravel(tmp_path):
    client, _ = make_client(tmp_path, env={"CORS_ORIGINS": "https://loja.example, http://outro.example/"})
    headers = {"Access-Control-Request-Method": "POST"}
    ok = client.options("/api/chat", headers={**headers, "Origin": "http://outro.example"})
    assert ok.headers["access-control-allow-origin"] == "http://outro.example"
    denied = client.options("/api/chat", headers={**headers, "Origin": "http://localhost:5173"})
    assert denied.status_code == 400


# ----------------------------------------------------------------------------- OpenAPI


def test_openapi_contem_rotas(tmp_path):
    client, _ = make_client(tmp_path)
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "Empório da Música — API da Mel"
    paths = spec["paths"]
    assert set(paths) >= {"/api/health", "/api/sessions", "/api/chat", "/api/sessions/{session_id}"}
    assert "post" in paths["/api/chat"] and "delete" in paths["/api/sessions/{session_id}"]
    assert paths["/api/chat"]["post"]["summary"] == "Enviar uma mensagem à Mel"


# ----------------------------------------------------------------------------- configuração


def test_max_sessions_descarta_a_menos_usada(tmp_path):
    client, _ = make_client(tmp_path, [fake_text("ok")], env={"MAX_SESSIONS": "2"})
    a = client.post("/api/sessions").json()["session_id"]
    b = client.post("/api/sessions").json()["session_id"]
    client.post("/api/chat", json={"session_id": a, "message": "oi"})  # a passa a ser a mais recente
    c = client.post("/api/sessions").json()["session_id"]
    store = client.app.state.api.sessions
    assert a in store and c in store and b not in store


def test_max_sessions_invalido_usa_padrao(tmp_path):
    client, _ = make_client(tmp_path, env={"MAX_SESSIONS": "abc"})
    assert client.app.state.api.sessions.max_sessions == 200


def test_importar_modulo_nao_monta_app():
    import emporio_agent.api.app as module

    assert module._default_app is None  # ``app`` só é montado quando acessado
    assert callable(module.create_app)


# ----------------------------------------------------------------------------- SessionStore


def test_session_store_lock_e_erros():
    store = SessionStore(max_sessions=1)
    session = store.create(MONDAY)
    with store.use(session.id) as same:
        assert same is session
        with pytest.raises(SessionBusy):
            with store.use(session.id):
                pass
        other = store.create(MONDAY)  # a ocupada não é descartada
        assert session.id in store and other.id in store
    with pytest.raises(SessionNotFound):
        store.delete("x")
    with pytest.raises(ValueError):
        SessionStore(max_sessions=0)


# ----------------------------------------------------------------------------- B1/B6


def test_session_id_e_token_urlsafe_longo_e_distinto(tmp_path):
    import re

    client, _ = make_client(tmp_path, [fake_text("Olá!")])
    ids = {client.post("/api/sessions").json()["session_id"] for _ in range(20)}
    ids.add(client.post("/api/chat", json={"message": "oi"}).json()["session_id"])
    assert len(ids) == 21
    for session_id in ids:
        assert len(session_id) >= 22  # token_urlsafe(16): 128 bits
        assert re.fullmatch(r"[A-Za-z0-9_-]+", session_id)


def test_session_id_longo_demais_422(tmp_path):
    client, _ = make_client(tmp_path)
    body = assert_envelope(
        client.post("/api/chat", json={"session_id": "x" * 65, "message": "oi"}), 422, "invalid_request"
    )
    assert "64" in body["message"]


@pytest.mark.parametrize("origin", [DEFAULT_CORS_ORIGINS[0], None])
def test_corpo_grande_413_com_envelope_e_cors(tmp_path, origin):
    client, llm = make_client(tmp_path)
    headers = {"Origin": origin} if origin else {}
    response = client.post("/api/chat", json={"message": "a" * 17_000}, headers=headers)
    assert_envelope(response, 413, "payload_too_large")
    if origin:
        assert response.headers["access-control-allow-origin"] == origin
    else:
        assert "access-control-allow-origin" not in response.headers
    assert len(client.app.state.api.sessions) == 0


def test_corpo_grande_413_origem_nao_permitida_sem_cors(tmp_path):
    client, _ = make_client(tmp_path)
    response = client.post(
        "/api/chat", json={"message": "a" * 17_000}, headers={"Origin": "http://evil.example"}
    )
    assert_envelope(response, 413, "payload_too_large")
    assert "access-control-allow-origin" not in response.headers


def test_corpo_chunked_grande_413_e_pequeno_passa(tmp_path):
    import json

    client, _ = make_client(tmp_path, [fake_text("Olá!")])
    headers = {"Content-Type": "application/json"}

    def chunks(payload: bytes):
        for i in range(0, len(payload), 1024):
            yield payload[i : i + 1024]

    big = json.dumps({"message": "a" * 17_000}).encode()
    assert_envelope(client.post("/api/chat", content=chunks(big), headers=headers), 413, "payload_too_large")
    small = json.dumps({"message": "oi"}).encode()
    response = client.post("/api/chat", content=chunks(small), headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "Olá!"


def test_corpo_no_limite_nao_e_413(tmp_path):
    client, _ = make_client(tmp_path)
    # ~16 KiB mas mensagem acima de 2000 caracteres: passa do middleware e vira 422.
    response = client.post("/api/chat", json={"message": "a" * 16_000})
    assert_envelope(response, 422, "invalid_request")


def test_openapi_documenta_413(tmp_path):
    client, _ = make_client(tmp_path)
    paths = client.get("/openapi.json").json()["paths"]
    assert "413" in paths["/api/chat"]["post"]["responses"]
    assert "413" in paths["/api/sessions"]["post"]["responses"]
