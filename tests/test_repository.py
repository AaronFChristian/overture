import uuid

from overture.db.repository import _requirement_to_kwargs
from overture.schemas import (
    Requirement,
    RequirementCategory,
    ScopeClassification,
    SourceSpan,
)


def test_requirement_to_kwargs_maps_all_fields() -> None:
    req = Requirement(
        session_id=uuid.uuid4(),
        category=RequirementCategory.PAIN,
        scope=ScopeClassification.IN_SCOPE,
        text="Legal review is slow",
        source_span=SourceSpan(start=5, end=15, quoted_text="0123456789"),
        confidence=0.8,
    )

    kwargs = _requirement_to_kwargs(req)

    assert kwargs["id"] == req.id
    assert kwargs["session_id"] == req.session_id
    assert kwargs["category"] == "pain"
    assert kwargs["scope"] == "in_scope"
    assert kwargs["text"] == "Legal review is slow"
    assert kwargs["span_start"] == 5
    assert kwargs["span_end"] == 15
    assert kwargs["span_text"] == "0123456789"
    assert kwargs["confidence"] == 0.8


def test_requirement_to_kwargs_uses_plain_enum_values_not_enum_objects() -> None:
    # Storage columns are plain strings (see db/models.py) -- this
    # guards against accidentally storing a StrEnum member instead of
    # its .value, which would still *look* right in a quick manual
    # check but breaks equality against rows read back with pure str.
    req = Requirement(
        session_id=uuid.uuid4(),
        category=RequirementCategory.VOCABULARY,
        scope=ScopeClassification.NEEDS_CLARIFICATION,
        text="SharePoint",
        source_span=SourceSpan(start=0, end=10, quoted_text="SharePoint"),
    )

    kwargs = _requirement_to_kwargs(req)

    assert isinstance(kwargs["category"], str)
    assert isinstance(kwargs["scope"], str)
    assert kwargs["category"] == "vocabulary"
    assert kwargs["scope"] == "needs_clarification"
