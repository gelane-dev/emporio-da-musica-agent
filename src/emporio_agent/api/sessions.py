"""Armazenamento de sessões em memória (sem persistência), thread-safe."""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime

from emporio_agent.agent.session import Session

DEFAULT_MAX_SESSIONS = 200

# Criação de sessões por cliente: os mesmos números do nginx (10/min, rajada de 5).
SESSION_CREATE_PER_MINUTE = 10
SESSION_CREATE_BURST = 5
_MAX_TRACKED_CLIENTS = 10_000


class SessionNotFound(Exception):
    """Sessão desconhecida (ou já descartada)."""


class SessionBusy(Exception):
    """Já há uma mensagem sendo processada nesta sessão."""


class SessionCreationLimiter:
    """Balde de fichas por cliente para a criação de sessões (equivalente ao limit_req do nginx).

    Risco: ``POST /api/chat`` sem ``session_id`` também cria sessão e não passa pelo limite do
    nginx em ``POST /api/sessions``; criando sessões em massa, um cliente expulsa (LRU) as conversas
    de outros. Um único orçamento por cliente vale para os dois caminhos.
    """

    def __init__(
        self,
        per_minute: int = SESSION_CREATE_PER_MINUTE,
        burst: int = SESSION_CREATE_BURST,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rate = per_minute / 60.0
        self._capacity = float(burst + 1)  # nginx: 1 + burst passam de imediato (nodelay)
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def allow(self, client: str) -> bool:
        now = self._clock()
        with self._lock:
            tokens, last = self._buckets.get(client, (self._capacity, now))
            tokens = min(self._capacity, tokens + (now - last) * self._rate)
            allowed = tokens >= 1.0
            self._buckets[client] = (tokens - 1.0 if allowed else tokens, now)
            self._buckets.move_to_end(client)
            while len(self._buckets) > _MAX_TRACKED_CLIENTS:
                self._buckets.popitem(last=False)
            return allowed


class _Entry:
    __slots__ = ("session", "lock", "last_used")

    def __init__(self, session: Session, now: float) -> None:
        self.session = session
        self.lock = threading.Lock()
        self.last_used = now


class SessionStore:
    """Sessões por id, com um lock por sessão e limite de quantidade.

    A ordem interna reflete o último uso; ao passar de ``max_sessions``,
    descarta a sessão usada há mais tempo (pulando as que estão ocupadas).
    """

    def __init__(
        self,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        ttl_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_sessions <= 0:
            raise ValueError("max_sessions precisa ser positivo")
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds precisa ser positivo")
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            self._expire_locked()
            return len(self._entries)

    def __contains__(self, session_id: object) -> bool:
        with self._lock:
            self._expire_locked()
            return session_id in self._entries

    def create(self, started_at: datetime) -> Session:
        with self._lock:
            self._expire_locked()
            # Id exposto pela API é a única credencial da sessão: 128 bits aleatórios.
            session_id = secrets.token_urlsafe(16)
            while session_id in self._entries:  # colisão praticamente impossível
                session_id = secrets.token_urlsafe(16)
            session = Session(started_at=started_at, session_id=session_id)
            self._entries[session.id] = _Entry(session, self._clock())
            self._evict_locked(keep=session.id)
            return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._expire_locked()
            if self._entries.pop(session_id, None) is None:
                raise SessionNotFound(session_id)

    @contextmanager
    def use(self, session_id: str) -> Iterator[Session]:
        """Reserva a sessão com exclusividade enquanto o bloco executa.

        Lança ``SessionNotFound`` ou ``SessionBusy`` (sem esperar).
        """
        with self._lock:
            self._expire_locked()
            entry = self._entries.get(session_id)
            if entry is None:
                raise SessionNotFound(session_id)
            if not entry.lock.acquire(blocking=False):
                raise SessionBusy(session_id)
            self._entries.move_to_end(session_id)
            entry.last_used = self._clock()
        try:
            yield entry.session
        finally:
            with self._lock:
                entry.last_used = self._clock()  # a inatividade conta a partir do fim da resposta
            entry.lock.release()

    def _expire_locked(self) -> None:
        # Sessões paradas ocupam memória para sempre; as ocupadas nunca expiram no meio da requisição.
        if self.ttl_seconds is None:
            return
        limit = self._clock() - self.ttl_seconds
        for session_id in [
            sid for sid, e in self._entries.items() if e.last_used < limit and not e.lock.locked()
        ]:
            del self._entries[session_id]

    def _evict_locked(self, keep: str) -> None:
        if len(self._entries) <= self.max_sessions:
            return
        for session_id in list(self._entries):
            if len(self._entries) <= self.max_sessions:
                break
            if session_id != keep and not self._entries[session_id].lock.locked():
                del self._entries[session_id]
