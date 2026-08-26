"""LLM provider abstraction.

One interface, two implementations. Every place in this codebase that
needs a completion calls `LLMProvider.complete()` — nothing imports
`anthropic` or `openai` directly outside this package. That's what
makes the Claude/Azure OpenAI swap a config change (`LLM_PROVIDER=...`)
instead of a code change. See decisions.md D-0006.
"""

from typing import Literal, Protocol

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CompletionResult(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    # Why generation stopped: "end_turn", "max_tokens", etc. Added
    # specifically to disambiguate two very different failure modes
    # that otherwise look identical from output_tokens/text alone --
    # "genuinely truncated by the token ceiling" vs "the model decided
    # it was done and produced nothing," which need different fixes.
    # See decisions.md D-0042.
    stop_reason: str | None = None
    # What kind(s) of content block the response actually contained
    # (Anthropic: "text", "thinking", etc; Azure OpenAI has no
    # equivalent concept, so this is always ["text"] or [] there).
    # This is the field that actually answers "did the model spend its
    # whole budget on a thinking block and never reach text" instead
    # of inferring it from token counts alone. See D-0042.
    content_block_types: list[str] = []


class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        max_tokens: int = 1024,
    ) -> CompletionResult: ...
