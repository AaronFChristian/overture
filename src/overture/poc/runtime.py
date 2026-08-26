"""Demo runtime -- answers a question grounded in retrieved chunks.

This is the one function in the whole codebase where an LLM writes
prose that a prospect directly reads. The prompt is deliberately strict
about citing only the numbered context provided and saying so
explicitly when the context doesn't answer the question -- the closest
this project gets to a runtime hallucination guard for free-text
answers, as opposed to the structural validation validator.py does for
DemoConfig.
"""

from overture.providers.base import LLMProvider, Message

_ANSWER_PROMPT = """{system_prompt}

Answer the question using ONLY the numbered context below. Cite which
chunk number(s) support your answer using [1], [2] style markers. If
the context does not contain the answer, say so explicitly rather than
guessing or using outside knowledge.

Context:
{context}

Question: {question}"""


async def answer_question(
    *,
    question: str,
    system_prompt: str,
    chunks: list[tuple[int, str]],
    provider: LLMProvider,
) -> str:
    """chunks is a list of (chunk_index, text), in the order to present them.

    Not necessarily the order they'll be cited in -- citation numbers
    in the answer refer to position in this list (1-indexed), not to
    chunk_index, since chunk_index is the chunk's position in the
    original transcript and the retrieved set is rarely contiguous.
    """
    context = "\n\n".join(f"[{position}] {text}" for position, (_, text) in enumerate(chunks, 1))

    prompt = _ANSWER_PROMPT.format(
        system_prompt=system_prompt or "You are a helpful assistant.",
        context=context or "(no context available)",
        question=question,
    )

    result = await provider.complete(
        system="You answer strictly from the provided context, with citations.",
        messages=[Message(role="user", content=prompt)],
        max_tokens=1024,
    )
    return result.text
