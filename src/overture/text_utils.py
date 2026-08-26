"""Shared text utilities.

`split_paragraphs` was originally inline in graph/nodes.py::segment.
Factored out here because session 6's ingestion chunker needs the
exact same splitting rule -- duplicating it would mean a future fix
to segmentation only landing in one of the two call sites, the same
class of drift D-0009 already called out for the extraction nodes.
"""


def split_paragraphs(text: str) -> list[str]:
    """Split text into non-empty, whitespace-trimmed blank-line-separated chunks.

    Falls back to the whole (trimmed) text as a single chunk if there
    are no blank lines to split on.
    """
    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    return chunks or [text.strip()]
