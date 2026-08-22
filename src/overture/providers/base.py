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


class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        max_tokens: int = 1024,
    ) -> CompletionResult: ...
