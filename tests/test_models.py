from concurrent.futures import ThreadPoolExecutor

import httpx2
import pytest
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from src.core.config import LLMSettings
from src.data.schemas import AssessmentBatch
from src.models import agent
from src.models.base import LLMError


def test_build_model_per_provider():
    openai = LLMSettings(provider="openai", openai={"api_key": "k", "model": "gpt-5.4-mini"})
    anthropic = LLMSettings(provider="anthropic", anthropic={"api_key": "k"})

    assert isinstance(agent.build_model(openai), OpenAIResponsesModel)
    assert isinstance(agent.build_model(anthropic), AnthropicModel)


def test_vertex_without_credentials_file_is_a_clear_error(tmp_path):
    missing = str(tmp_path / "missing.json")
    settings = LLMSettings(provider="google-vertex", google_vertex={"credentials_file": missing})

    with pytest.raises(LLMError, match="credentials file not found"):
        agent.build_model(settings)


def test_model_settings():
    anthropic = agent.build_model_settings(LLMSettings(provider="anthropic", effort="high"))
    openai = agent.build_model_settings(LLMSettings(provider="openai", effort=""))

    assert anthropic["thinking"] == "high"
    assert anthropic["anthropic_cache_instructions"] is True
    assert "thinking" not in openai
    assert "anthropic_cache_instructions" not in openai
    assert openai["timeout"] == 600


def test_parse_is_safe_from_many_threads(monkeypatch):
    monkeypatch.setattr(agent, "build_model", lambda settings: TestModel())
    llm = agent.PydanticAILLM(LLMSettings(provider="openai", openai={"api_key": "k"}))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: llm.parse("sys", {"i": i}, AssessmentBatch), range(8)))

    assert all(isinstance(r, AssessmentBatch) for r in results)


def test_anthropic_large_max_tokens_reaches_the_api(monkeypatch):
    """The SDK refuses non-streaming calls it estimates over 10 minutes unless a timeout is set."""
    sent = {}

    def handler(request):
        sent["path"] = request.url.path
        return httpx2.Response(
            401, json={"type": "error", "error": {"type": "auth", "message": "x"}}
        )

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    def fake_model(settings):
        provider = AnthropicProvider(api_key="k", http_client=http)
        return AnthropicModel(settings.anthropic.model, provider=provider)

    monkeypatch.setattr(agent, "build_model", fake_model)
    llm = agent.PydanticAILLM(LLMSettings(provider="anthropic", max_tokens=32000))

    with pytest.raises(LLMError):
        llm.parse("sys", {}, AssessmentBatch)
    assert sent["path"].endswith("/messages")
