"""Criação do cliente LLM a partir de ``Settings`` (ARCHITECTURE §5.6.1)."""

from __future__ import annotations

from collections.abc import Mapping

from emporio_agent.config import Settings, read_env
from emporio_agent.llm.base import LLMClient, LLMError

SUPPORTED_PROVIDERS = ("anthropic",)


def create_llm_client(settings: Settings, env: Mapping[str, str] | None = None) -> LLMClient:
    env = read_env() if env is None else env
    if settings.llm_provider == "anthropic":
        import anthropic

        from emporio_agent.llm.anthropic_client import AnthropicClient

        api_key = env.get("ANTHROPIC_API_KEY", "").strip()
        auth_token = env.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        if not api_key and not auth_token:
            raise LLMError(
                "auth",
                "Chave da API não configurada. Copie .env.example para .env e preencha "
                "ANTHROPIC_API_KEY.",
            )
        common = {
            "model": settings.llm_model,
            "effort": settings.llm_effort,
            "refusal_fallback": settings.llm_refusal_fallback,
        }
        if api_key:
            return AnthropicClient(api_key=api_key, **common)
        return AnthropicClient(client=anthropic.Anthropic(auth_token=auth_token), **common)
    raise LLMError(
        "config",
        f"LLM_PROVIDER desconhecido: {settings.llm_provider!r}. "
        f"Suportados: {', '.join(SUPPORTED_PROVIDERS)}.",
    )
