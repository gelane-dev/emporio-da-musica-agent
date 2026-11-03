"""API HTTP (FastAPI) da Mel, assistente da Empório da Música.

Camada fina sobre o agente: monta-o com ``cli.build_agent`` e delega cada
mensagem a ``Agent.respond``. Sessões ficam só em memória.

Executar: ``python -m emporio_agent.api`` ou
``uvicorn emporio_agent.api.app:app --port 8000``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from emporio_agent import __version__
from emporio_agent.agent.agent import Agent
from emporio_agent.api.schemas import (
    MAX_SESSION_ID_LENGTH,
    MSG_EMPTY,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    SessionCreated,
    ToolCallInfo,
)
from emporio_agent.api.sessions import DEFAULT_MAX_SESSIONS, SessionBusy, SessionNotFound, SessionStore
from emporio_agent.cli import build_agent, greeting
from emporio_agent.config import Settings, load_settings, now, read_env
from emporio_agent.data.loader import DataLoadError
from emporio_agent.domain.store_hours import store_status
from emporio_agent.llm.base import LLMClient, LLMError
from emporio_agent.policies.store import PolicyStoreError

logger = logging.getLogger("emporio_agent.api")

DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

MSG_NOT_FOUND = "Sessão não encontrada. Ela pode ter expirado ou o servidor foi reiniciado; inicie uma nova conversa."
MSG_BUSY = "Ainda estou respondendo à mensagem anterior desta conversa. Aguarde um instante e tente de novo."
MSG_UNAVAILABLE = "O atendimento está indisponível no momento. Tente novamente mais tarde."
MSG_INTERNAL = "Ocorreu um erro inesperado. Tente novamente em instantes."
MSG_INVALID = "Requisição inválida. Envie um JSON com o campo 'message' (texto)."
MSG_MISSING_MESSAGE = "O campo 'message' é obrigatório."
MSG_DATA_ERROR = "Não foi possível carregar os dados da loja."
MSG_TOO_LARGE = "A requisição é grande demais. Envie uma mensagem mais curta."

MAX_BODY_BYTES = 16 * 1024

_ERROR_RESPONSES: dict[int | str, dict] = {
    404: {"model": ErrorResponse, "description": "Sessão não encontrada (`session_not_found`)."},
    409: {"model": ErrorResponse, "description": "Sessão ocupada com outra mensagem (`session_busy`)."},
    413: {"model": ErrorResponse, "description": "Corpo acima de 16 KiB (`payload_too_large`)."},
    422: {"model": ErrorResponse, "description": "Requisição inválida (`invalid_request`)."},
    500: {"model": ErrorResponse, "description": "Erro inesperado (`internal_error`)."},
    503: {"model": ErrorResponse, "description": "Agente indisponível (`agent_unavailable`)."},
}

_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, message: str) -> None:
        super().__init__(error)
        self.status_code = status_code
        self.error = error
        self.message = message


@dataclass
class ApiState:
    settings: Settings
    agent: Agent | None
    detail: str | None
    sessions: SessionStore


def _error(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error, "message": message})


def _parse_origins(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return list(DEFAULT_CORS_ORIGINS)
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def _parse_max_sessions(raw: str | None) -> int:
    if raw is None or not raw.strip():
        return DEFAULT_MAX_SESSIONS
    try:
        value = int(raw.strip())
    except ValueError:
        value = 0
    if value <= 0:
        logger.warning("MAX_SESSIONS inválido (%r); usando %d.", raw, DEFAULT_MAX_SESSIONS)
        return DEFAULT_MAX_SESSIONS
    return value


def _build(settings: Settings, llm: LLMClient | None, env: Mapping[str, str] | None) -> tuple[Agent | None, str | None]:
    try:
        return build_agent(settings, llm=llm, env=env), None
    except LLMError as exc:
        logger.warning("Agente indisponível (LLM, %s).", exc.kind)
        return None, exc.message
    except (DataLoadError, PolicyStoreError):
        logger.exception("Agente indisponível: falha ao carregar dados/políticas.")
        return None, MSG_DATA_ERROR


def _validation_message(exc: RequestValidationError) -> str:
    for err in exc.errors():
        loc = tuple(err.get("loc", ()))
        if loc[-1:] == ("message",):
            if err.get("type") == "value_error":
                return str(err.get("ctx", {}).get("error", MSG_EMPTY))
            if err.get("type") == "missing":
                return MSG_MISSING_MESSAGE
            return "O campo 'message' precisa ser um texto."
        if loc[-1:] == ("session_id",):
            if err.get("type") == "string_too_long":
                return f"O campo 'session_id' pode ter no máximo {MAX_SESSION_ID_LENGTH} caracteres."
            return "O campo 'session_id' precisa ser um texto ou nulo."
    return MSG_INVALID


def create_app(
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    env: Mapping[str, str] | None = None,
) -> FastAPI:
    """Monta a aplicação. Se o agente não puder ser montado, sobe em modo degradado."""
    values = read_env() if env is None else env
    detail: str | None = None
    if settings is None:
        try:
            settings = load_settings() if env is None else load_settings(environ=env)
        except ValueError as exc:  # inclui ValidationError do Pydantic
            logger.warning("Configuração inválida: %s", exc)
            settings, detail = Settings(), "Configuração inválida. Verifique o arquivo .env."
    agent: Agent | None = None
    if detail is None:
        agent, detail = _build(settings, llm, env)

    state = ApiState(
        settings=settings,
        agent=agent,
        detail=detail,
        sessions=SessionStore(_parse_max_sessions(values.get("MAX_SESSIONS"))),
    )

    app = FastAPI(
        title="Empório da Música — API da Mel",
        description=(
            "API de atendimento da **Mel**, assistente virtual da Empório da Música.\n\n"
            "Fluxo: crie uma sessão (`POST /api/sessions`) para receber a saudação e envie "
            "mensagens em `POST /api/chat`. As sessões ficam apenas em memória: reiniciar o "
            "servidor apaga todas. Erros usam sempre o envelope `{error, message}`."
        ),
        version=__version__,
        openapi_tags=[
            {"name": "Saúde", "description": "Estado do serviço e do agente."},
            {"name": "Sessões", "description": "Criação e encerramento de conversas."},
            {"name": "Conversa", "description": "Troca de mensagens com a Mel."},
        ],
    )
    app.state.api = state

    # --- tratamento de erros -------------------------------------------------

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status_code, exc.error, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(422, "invalid_request", _validation_message(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = "Recurso não encontrado." if exc.status_code == 404 else "Requisição não suportada."
        return _error(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:  # fallback
        logger.error("Erro inesperado na API (%s).", type(exc).__name__, exc_info=exc)
        return _error(500, "internal_error", MSG_INTERNAL)

    # Middleware interno ao CORS: garante o envelope 500 *com* cabeçalhos CORS.
    @app.middleware("http")
    async def _catch_unexpected(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 — nunca vaza detalhes ao cliente
            logger.error("Erro inesperado na API (%s).", type(exc).__name__, exc_info=exc)
            return _error(500, "internal_error", MSG_INTERNAL)

    # Também interno ao CORS: rejeita corpos grandes antes de lê-los/decodificá-los.
    @app.middleware("http")
    async def _limit_body(request: Request, call_next):
        length = request.headers.get("content-length")
        if length is not None:
            if length.strip().isdigit() and int(length) > MAX_BODY_BYTES:
                return _error(413, "payload_too_large", MSG_TOO_LARGE)
        elif "chunked" in request.headers.get("transfer-encoding", "").lower():
            body = b""
            async for chunk in request.stream():
                body += chunk
                if len(body) > MAX_BODY_BYTES:
                    return _error(413, "payload_too_large", MSG_TOO_LARGE)
            request._body = body  # repassa o corpo já lido à rota (cache do BaseHTTPMiddleware)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_origins(values.get("CORS_ORIGINS")),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    def require_agent() -> Agent:
        if state.agent is None:
            raise ApiError(503, "agent_unavailable", MSG_UNAVAILABLE)
        return state.agent

    # --- rotas -----------------------------------------------------------------

    @app.get(
        "/api/health",
        response_model=HealthResponse,
        tags=["Saúde"],
        summary="Verificar o estado do serviço",
        description="Informa se o agente está pronto (`ok`) ou em modo degradado (`degraded`), com o motivo.",
    )
    def health() -> HealthResponse:
        ready = state.agent is not None
        return HealthResponse(
            status="ok" if ready else "degraded",
            agent_ready=ready,
            provider=state.settings.llm_provider,
            model=state.settings.llm_model,
            detail=None if ready else state.detail,
        )

    @app.post(
        "/api/sessions",
        response_model=SessionCreated,
        status_code=201,
        tags=["Sessões"],
        summary="Iniciar uma conversa",
        description="Cria uma sessão em memória e devolve a saudação inicial da Mel.",
        responses={k: _ERROR_RESPONSES[k] for k in (413, 500, 503)},
    )
    def create_session() -> SessionCreated:
        require_agent()
        current = now(state.settings)
        session = state.sessions.create(current)
        logger.info("Sessão %s criada.", session.id)
        return SessionCreated(
            session_id=session.id,
            greeting=greeting(current, store_status(current, state.settings.timezone)),
            created_at=current.isoformat(),
        )

    @app.post(
        "/api/chat",
        response_model=ChatResponse,
        tags=["Conversa"],
        summary="Enviar uma mensagem à Mel",
        description=(
            "Envia a mensagem do cliente e devolve a resposta da Mel. Sem `session_id`, cria uma "
            "sessão nova. Falhas do provedor de IA durante a conversa ainda retornam 200, com "
            "`stop=llm_error` e uma mensagem de contingência."
        ),
        responses={k: _ERROR_RESPONSES[k] for k in (404, 409, 413, 422, 500, 503)},
    )
    def chat(body: ChatRequest) -> ChatResponse:
        agent = require_agent()
        session_id = body.session_id
        if session_id is None:
            session_id = state.sessions.create(now(state.settings)).id
        try:
            with state.sessions.use(session_id) as session:
                reply = agent.respond(session, body.message)
        except SessionNotFound:
            raise ApiError(404, "session_not_found", MSG_NOT_FOUND) from None
        except SessionBusy:
            raise ApiError(409, "session_busy", MSG_BUSY) from None
        # Só metadados no log: nunca o texto do cliente nem argumentos de ferramentas.
        logger.info(
            "Sessão %s: stop=%s, ferramentas=%s.",
            session_id, reply.stop, [c.name for c in reply.tool_calls],
        )
        return ChatResponse(
            session_id=session_id,
            reply=reply.text,
            stop=reply.stop,
            tool_calls=[
                ToolCallInfo(name=c.name, ok=c.ok, duration_ms=c.duration_ms) for c in reply.tool_calls
            ],
        )

    @app.delete(
        "/api/sessions/{session_id}",
        status_code=204,
        response_class=Response,
        tags=["Sessões"],
        summary="Encerrar uma conversa",
        description="Remove a sessão da memória.",
        responses={k: _ERROR_RESPONSES[k] for k in (404, 500)},
    )
    def delete_session(session_id: str) -> Response:
        try:
            state.sessions.delete(session_id)
        except SessionNotFound:
            raise ApiError(404, "session_not_found", MSG_NOT_FOUND) from None
        return Response(status_code=204)

    return app


_default_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    """``app`` é criado sob demanda: importar o módulo não monta o agente."""
    global _default_app
    if name == "app":
        if _default_app is None:
            _default_app = create_app()
        return _default_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
