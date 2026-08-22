"""Azure OpenAI provider — swappable second backend.

Exists to prove the provider abstraction is real, not decorative, and
to give a working Azure-native path for the parts of the report that
specifically ask for Azure OpenAI Service. Not the default — see
`llm_provider` in config.py.
"""

from typing import cast

from openai import AsyncAzureOpenAI
from openai.types.chat import ChatCompletionMessageParam

from overture.providers.base import CompletionResult, Message


class AzureOpenAIProvider:
    def __init__(self, api_key: str, endpoint: str, deployment: str, api_version: str) -> None:
        self._client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self._deployment = deployment

    async def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        max_tokens: int = 1024,
    ) -> CompletionResult:
        full_messages: list[ChatCompletionMessageParam] = [
            cast(ChatCompletionMessageParam, {"role": "system", "content": system})
        ]
        full_messages.extend(
            cast(ChatCompletionMessageParam, {"role": m.role, "content": m.content})
            for m in messages
        )
        response = await self._client.chat.completions.create(
            model=self._deployment,
            max_tokens=max_tokens,
            messages=full_messages,
        )
        choice = response.choices[0]
        usage = response.usage
        return CompletionResult(
            text=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=self._deployment,
        )
