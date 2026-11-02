"""LLM client protocol adapters."""

from __future__ import annotations

from curricula.domain.protocols import LLMClient
from curricula.llm.litellm_adapter import LiteLLMClient


class NoOpLLMClient:
    """Fails loudly when no generative backend is configured."""

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        _ = (prompt, model)
        raise RuntimeError("LLM client is not configured.")


class FakeLLMClient:
    """Deterministic offline generator for tests and local dry runs."""

    name = "fake"
    version = "1"

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        _ = model
        return (
            "Bu içerik yapay zeka tarafından taslak olarak üretilmiştir "
            "ve kaynak video içeriği değildir.\n\n"
            f"Bağlam: {prompt[:240]}"
        )


def resolve_llm_client(
    name: str,
    *,
    default_model: str = "gpt-4o-mini",
) -> LLMClient:
    normalized = name.lower().strip()
    if normalized in {"fake", "test"}:
        return FakeLLMClient()
    if normalized in {"noop", "none"}:
        return NoOpLLMClient()
    if normalized in {"litellm", "auto"}:
        if normalized == "auto":
            try:
                import litellm  # noqa: F401

                return LiteLLMClient(default_model=default_model)
            except ImportError:
                return FakeLLMClient()
        return LiteLLMClient(default_model=default_model)
    raise ValueError(f"Unknown LLM client: {name}")
