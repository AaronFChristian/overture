"""Anthropic provider — the primary LLM backend for this project.

One thing to never do here, hard-won the expensive way on prior
projects: never pass `temperature` to a Claude Sonnet 5-family model.
It rejects the parameter outright rather than ignoring it. If a future
session needs temperature control, that has to come from a different
knob (top_p, or prompt-level instruction), not this parameter.
"""

from anthropic import AsyncAnthropic

from overture.providers.base import CompletionResult, Message


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        max_tokens: int = 1024,
    ) -> CompletionResult:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            # No `temperature` param — see module docstring.
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return CompletionResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self._model,
            stop_reason=response.stop_reason,
            content_block_types=[block.type for block in response.content],
        )
