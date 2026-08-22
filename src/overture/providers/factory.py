"""Provider factory.

The only place in the codebase that branches on `settings.llm_provider`.
Everything else just calls `.complete()` on whatever this returns.
"""

from overture.config import Settings, get_settings
from overture.providers.anthropic_provider import AnthropicProvider
from overture.providers.azure_openai_provider import AzureOpenAIProvider
from overture.providers.base import LLMProvider


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()

    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )

    if settings.llm_provider == "azure_openai":
        missing = [
            name
            for name, value in (
                ("AZURE_OPENAI_API_KEY", settings.azure_openai_api_key),
                ("AZURE_OPENAI_ENDPOINT", settings.azure_openai_endpoint),
                ("AZURE_OPENAI_DEPLOYMENT", settings.azure_openai_deployment),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required settings for LLM_PROVIDER=azure_openai: {', '.join(missing)}"
            )
        # mypy can't see the None-checks above narrowed these to `str`;
        # asserting is cheaper here than restructuring the missing-list check.
        assert settings.azure_openai_api_key
        assert settings.azure_openai_endpoint
        assert settings.azure_openai_deployment
        return AzureOpenAIProvider(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
        )

    raise ValueError(f"Unknown llm_provider: {settings.llm_provider}")
