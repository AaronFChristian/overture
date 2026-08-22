import pytest

from overture.config import Settings
from overture.providers.anthropic_provider import AnthropicProvider
from overture.providers.azure_openai_provider import AzureOpenAIProvider
from overture.providers.factory import get_llm_provider


def test_factory_returns_anthropic_provider_by_default() -> None:
    settings = Settings(anthropic_api_key="test-key")
    provider = get_llm_provider(settings)
    assert isinstance(provider, AnthropicProvider)


def test_factory_raises_when_anthropic_key_missing() -> None:
    settings = Settings(llm_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        get_llm_provider(settings)


def test_factory_returns_azure_openai_provider_when_configured() -> None:
    settings = Settings(
        llm_provider="azure_openai",
        azure_openai_api_key="test-key",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_deployment="gpt-4.1-mini",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, AzureOpenAIProvider)


def test_factory_raises_when_azure_settings_incomplete() -> None:
    settings = Settings(
        llm_provider="azure_openai",
        azure_openai_api_key="test-key",
        azure_openai_endpoint=None,
        azure_openai_deployment=None,
    )
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        get_llm_provider(settings)
