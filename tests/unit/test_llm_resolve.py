import pytest

from curricula.llm.client import FakeLLMClient, NoOpLLMClient, resolve_llm_client


def test_resolve_fake() -> None:
    client = resolve_llm_client("fake")
    assert isinstance(client, FakeLLMClient)
    text = client.complete("SELECT nedir?")
    assert "kaynak video" in text


def test_resolve_noop_raises() -> None:
    client = resolve_llm_client("noop")
    assert isinstance(client, NoOpLLMClient)
    with pytest.raises(RuntimeError):
        client.complete("x")


def test_resolve_unknown() -> None:
    with pytest.raises(ValueError):
        resolve_llm_client("not-a-backend")
