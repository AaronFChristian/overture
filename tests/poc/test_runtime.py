import pytest

from overture.poc.runtime import answer_question
from overture.providers.base import CompletionResult, Message


class FakeAnswerProvider:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    async def complete(
        self, *, system: str, messages: list[Message], max_tokens: int = 1024
    ) -> CompletionResult:
        self.last_system = system
        self.last_prompt = messages[0].content
        return CompletionResult(
            text=self._response, input_tokens=10, output_tokens=10, model="fake"
        )


@pytest.mark.asyncio
async def test_answer_question_includes_all_chunks_numbered_from_one() -> None:
    provider = FakeAnswerProvider("Legal review takes three weeks [1].")
    chunks = [(5, "Legal review takes three weeks."), (12, "Contracts live in SharePoint.")]

    await answer_question(
        question="How long does review take?",
        system_prompt="You answer contract questions.",
        chunks=chunks,
        provider=provider,
    )

    assert provider.last_prompt is not None
    assert "[1] Legal review takes three weeks." in provider.last_prompt
    assert "[2] Contracts live in SharePoint." in provider.last_prompt


@pytest.mark.asyncio
async def test_answer_question_uses_position_not_chunk_index_for_citation_numbers() -> None:
    # chunk_index values (5, 12) are the chunk's position in the original
    # transcript, not necessarily contiguous in the retrieved set --
    # citation markers must be 1-indexed position in THIS list, not the
    # original chunk_index, or a prospect's citation would point nowhere.
    provider = FakeAnswerProvider("answer")
    chunks = [(5, "first retrieved"), (99, "second retrieved")]

    await answer_question(question="q", system_prompt="", chunks=chunks, provider=provider)

    assert provider.last_prompt is not None
    assert "[1] first retrieved" in provider.last_prompt
    assert "[2] second retrieved" in provider.last_prompt
    assert "[5]" not in provider.last_prompt
    assert "[99]" not in provider.last_prompt


@pytest.mark.asyncio
async def test_answer_question_falls_back_to_default_system_prompt_when_empty() -> None:
    provider = FakeAnswerProvider("answer")
    await answer_question(question="q", system_prompt="", chunks=[], provider=provider)
    assert provider.last_prompt is not None
    assert "You are a helpful assistant." in provider.last_prompt


@pytest.mark.asyncio
async def test_answer_question_returns_provider_response_text() -> None:
    provider = FakeAnswerProvider("Here is the grounded answer [1].")
    result = await answer_question(
        question="q", system_prompt="sys", chunks=[(0, "context")], provider=provider
    )
    assert result == "Here is the grounded answer [1]."
