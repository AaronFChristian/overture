import uuid

from overture.poc.blueprints import GROUNDED_DOCUMENT_QA, STRUCTURED_EXTRACTION, TRIAGE_AND_ROUTE
from overture.poc.compiler import select_blueprint
from overture.schemas import (
    Requirement,
    RequirementCategory,
    ScopeClassification,
    SolutionBrief,
    SourceSpan,
)


def _req(text: str, scope: ScopeClassification = ScopeClassification.IN_SCOPE) -> Requirement:
    return Requirement(
        session_id=uuid.uuid4(),
        category=RequirementCategory.REQUIREMENT,
        scope=scope,
        text=text,
        source_span=SourceSpan(start=0, end=len(text), quoted_text=text),
    )


def _brief(*requirements: Requirement) -> SolutionBrief:
    session_id = uuid.uuid4()
    return SolutionBrief(session_id=session_id, requirements=list(requirements))


def test_selects_document_qa_for_search_and_citation_language() -> None:
    brief = _brief(
        _req("Users should be able to search and query contracts"),
        _req("Answers need a citation back to the source document"),
    )
    assert select_blueprint(brief).id == GROUNDED_DOCUMENT_QA.id


def test_selects_triage_for_flagging_language() -> None:
    brief = _brief(
        _req("Flag unusual liability language for review"),
        _req("Escalate exceptions before they become a fire drill"),
    )
    assert select_blueprint(brief).id == TRIAGE_AND_ROUTE.id


def test_selects_structured_extraction_for_field_pulling_language() -> None:
    brief = _brief(
        _req("Extract key fields from scanned PDF forms"),
        _req("Populate structured records from unstructured intake forms"),
    )
    assert select_blueprint(brief).id == STRUCTURED_EXTRACTION.id


def test_out_of_scope_requirements_do_not_influence_scoring() -> None:
    # An out-of-scope requirement stuffed with triage keywords must not
    # sway selection away from what the in-scope text actually supports.
    brief = _brief(
        _req("Search and query contracts with citations", scope=ScopeClassification.IN_SCOPE),
        _req(
            "Flag, escalate, route, classify, triage, review exceptions",
            scope=ScopeClassification.OUT_OF_SCOPE,
        ),
    )
    assert select_blueprint(brief).id == GROUNDED_DOCUMENT_QA.id


def test_no_matching_keywords_falls_back_to_first_declared_blueprint() -> None:
    brief = _brief(_req("Something with no matching keywords at all"))
    assert select_blueprint(brief).id == GROUNDED_DOCUMENT_QA.id
