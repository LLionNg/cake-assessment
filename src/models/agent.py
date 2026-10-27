import asyncio
import json
import logging
import threading
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError, ModelAPIError, UserError
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from src.core.config import LLMSettings
from src.models.base import LLM, LLMError, T

log = logging.getLogger(__name__)

CLOUD_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def build_model(settings: LLMSettings) -> Model:
    if settings.provider == "openai":
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key=settings.openai.api_key)
        return OpenAIResponsesModel(settings.openai.model, provider=provider)

    if settings.provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key=settings.anthropic.api_key)
        return AnthropicModel(settings.anthropic.model, provider=provider)

    from google import genai
    from google.oauth2 import service_account
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    vertex = settings.google_vertex
    if not Path(vertex.credentials_file).is_file():
        raise LLMError(f"Vertex AI credentials file not found: {vertex.credentials_file}")
    credentials = service_account.Credentials.from_service_account_file(
        vertex.credentials_file, scopes=[CLOUD_SCOPE]
    )
    client = genai.Client(
        vertexai=True,
        credentials=credentials,
        project=vertex.project_id or credentials.project_id,
        location=vertex.location,
    )
    return GoogleModel(vertex.model, provider=GoogleProvider(client=client))


def build_model_settings(settings: LLMSettings) -> ModelSettings:
    # An explicit timeout also skips the Anthropic SDK 10 minute guard for a large max_tokens.
    model_settings: dict = {"max_tokens": settings.max_tokens, "timeout": settings.timeout_s}
    if settings.effort:
        model_settings["thinking"] = settings.effort
    if settings.provider == "anthropic":
        # OpenAI and Gemini cache repeated prefixes automatically; Anthropic needs a marker.
        model_settings["anthropic_cache_instructions"] = True
    return ModelSettings(**model_settings)


class PydanticAILLM(LLM):
    """Pydantic AI is async. One background event loop serves every caller thread, so the
    pipeline stays synchronous and the provider's HTTP client is reused across calls."""

    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.model = build_model(settings)
        self.model_settings = build_model_settings(settings)
        self.agents: dict[tuple[str, type], Agent] = {}
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

    def parse(self, system: str, payload: dict, schema: type[T]) -> T:
        agent = self._agent(system, schema)
        prompt = json.dumps(payload, ensure_ascii=False)
        try:
            result = asyncio.run_coroutine_threadsafe(agent.run(prompt), self.loop).result()
        except (AgentRunError, ModelAPIError, UserError) as e:
            raise LLMError(f"{self.settings.provider} {self.settings.model}: {e}") from e

        usage = result.usage
        log.info(
            "%s %s: input=%d cache_read=%d cache_write=%d output=%d",
            self.settings.provider,
            schema.__name__,
            usage.input_tokens,
            usage.cache_read_tokens,
            usage.cache_write_tokens,
            usage.output_tokens,
        )
        return result.output

    def _agent(self, system: str, schema: type[T]) -> Agent:
        key = (system, schema)
        if key not in self.agents:
            self.agents[key] = Agent(
                self.model,
                output_type=schema,
                instructions=system,
                model_settings=self.model_settings,
                retries=2,
            )
        return self.agents[key]
