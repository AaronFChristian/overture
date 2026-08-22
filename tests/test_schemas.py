import uuid

import pytest
from pydantic import ValidationError

from overture.schemas import (
    Requirement as RequirementSchema,
)
from overture.schemas import (
    RequirementCategory,
    ScopeClassification,
    SourceSpan,
)


def _make_span(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {"start": 10, "end": 25, "quoted_text": "legal takes three weeks"}
    base.update(overrides)
    return base


def test_requirement_with_valid_source_span_constructs() -> None:
    req = RequirementSchema(
        session_id=uuid.uuid4(),
        category=RequirementCategory.PAIN,
        scope=ScopeClassification.IN_SCOPE,
        text="Legal review takes three weeks",
        source_span=SourceSpan(**_make_span()),  # type: ignore[arg-type]
    )
    assert req.confidence == 1.0
    assert req.category == "pain"


def test_requirement_missing_source_span_is_rejected() -> None:
    # source_span has no default -- omitting it must fail construction,
    # not silently produce a requirement with no traceable origin.
    with pytest.raises(ValidationError):
        RequirementSchema(  # type: ignore[call-arg]
            session_id=uuid.uuid4(),
            category=RequirementCategory.PAIN,
            scope=ScopeClassification.IN_SCOPE,
            text="Legal review takes three weeks",
        )


def test_source_span_end_must_exceed_start() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(**_make_span(start=30, end=20))  # type: ignore[arg-type]


def test_source_span_equal_start_end_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(**_make_span(start=10, end=10))  # type: ignore[arg-type]
