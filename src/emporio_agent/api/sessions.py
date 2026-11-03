"""Armazenamento de sessões em memória (sem persistência), thread-safe."""

from __future__ import annotations

import secrets
import threading
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from emporio_agent.agent.session import Session

DEFAULT_MAX_SESSIONS = 200


class SessionNotFound(Exception):
    """Sessão desconhecida (ou já descartada)."""


class SessionBusy(Exception):
    """Já há uma mensagem sendo processada nesta sessão."""


class _Entry:
    __slots__ = ("session", "lock")

    def __init__(self, session: Session) -> None:
        self.session = session
        self.lock = threading.Lock()


class SessionStore:
    """Sessões por id, com um lock por sessão e limite de quantidade.

    A ordem interna reflete o último uso; ao passar de ``max_sessions``,
    descarta a sessão usada há mais tempo (pulando as que estão ocupadas).
    """

    def __init__(self, max_sessions: int = DEFAULT_MAX_SESSIONS) -> None:
        if max_sessions <= 0:
            raise ValueError("max_sessions precisa ser positivo")
        self.max_sessions = max_sessions
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __contains__(self, session_id: object) -> bool:
        with self._lock:
            return session_id in self._entries

    def create(self, started_at: datetime) -> Session:
        with self._lock:
            # Id exposto pela API é a única credencial da sessão: 128 bits aleatórios.
            session_id = secrets.token_urlsafe(16)
            while session_id in self._entries:  # colisão praticamente impossível
                session_id = secrets.token_urlsafe(16)
            session = Session(started_at=started_at, session_id=session_id)
            self._entries[session.id] = _Entry(session)
            self._evict_locked(keep=session.id)
            return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            if self._entries.pop(session_id, None) is None:
                raise SessionNotFound(session_id)

    @contextmanager
    def use(self, session_id: str) -> Iterator[Session]:
        """Reserva a sessão com exclusividade enquanto o bloco executa.

        Lança ``SessionNotFound`` ou ``SessionBusy`` (sem esperar).
        """
        with self._lock:
            entry = self._entries.get(session_id)
            if entry is None:
                raise SessionNotFound(session_id)
            if not entry.lock.acquire(blocking=False):
                raise SessionBusy(session_id)
            self._entries.move_to_end(session_id)
        try:
            yield entry.session
        finally:
            entry.lock.release()

    def _evict_locked(self, keep: str) -> None:
        if len(self._entries) <= self.max_sessions:
            return
        for session_id in list(self._entries):
            if len(self._entries) <= self.max_sessions:
                break
            if session_id != keep and not self._entries[session_id].lock.locked():
                del self._entries[session_id]
