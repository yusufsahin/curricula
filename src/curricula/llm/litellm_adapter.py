"""LiteLLM production adapter (optional dependency)."""

from __future__ import annotations


class LiteLLMClient:
    """Thin wrapper around litellm.completion."""

    name = "litellm"
    version = "1"

    def __init__(self, *, default_model: str = "gpt-4o-mini") -> None:
        self.default_model = default_model

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        try:
            import litellm
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "litellm is not installed. Install with: pip install 'curricula[llm]'"
            ) from exc

        response = litellm.completion(
            model=model or self.default_model,
            messages=[{"role": "user", "content": prompt}],
        )
        choice = response.choices[0]
        content = choice.message.content
        if not content:
            return ""
        return str(content)
