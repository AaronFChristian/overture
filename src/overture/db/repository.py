"""Persistence layer -- turns graph output into database rows.

Split deliberately in two: `_requirement_to_kwargs` is a pure function
with no I/O, so it's unit tested directly (see tests/test_repository.py).
`persist_extraction_result` touches a real AsyncSession and can only be
proven against a live Postgres instance -- that's Aaron's step, the
same split used for the Alembic migration in session 2.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from overture.db import models as db_models
from overture.schemas import DiscoverySession as DiscoverySessionSchema
from overture.schemas import Requirement as RequirementSchema
from overture.schemas import SolutionBrief as SolutionBriefSchema


def _requirement_to_kwargs(req: RequirementSchema) -> dict[str, object]:
    """Map a Requirement schema to db_models.Requirement constructor kwargs.

    Pure function, no DB access -- flattens SourceSpan into the three
    span_* columns (see db/models.py) and converts enums to their
    plain string values for storage.
    """
    return {
        "id": req.id,
        "session_id": req.session_id,
        "category": req.category.value,
        "scope": req.scope.value,
        "text": req.text,
        "span_start": req.source_span.start,
        "span_end": req.source_span.end,
        "span_text": req.source_span.quoted_text,
        "confidence": req.confidence,
    }


async def persist_extraction_result(
    db: AsyncSession,
    session: DiscoverySessionSchema,
    brief: SolutionBriefSchema,
) -> None:
    """Stage a DiscoverySession, its Requirements, and its SolutionBrief.

    Does not commit -- the caller controls the transaction boundary,
    so a partial extraction can't leave a half-written session row and
    zero requirement rows if something fails between calls.
    """
    db_session = db_models.DiscoverySession(
        id=session.id,
        raw_transcript=session.raw_transcript,
        status=session.status.value,
    )
    db.add(db_session)

    for req in brief.requirements:
        db.add(db_models.Requirement(**_requirement_to_kwargs(req)))

    db.add(
        db_models.SolutionBrief(
            id=brief.id,
            session_id=brief.session_id,
            summary=brief.summary,
        )
    )
