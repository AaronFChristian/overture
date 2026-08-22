"""Blueprint selection and slot filling.

`select_blueprint` is pure and deterministic -- the same brief always
selects the same blueprint, with no LLM call involved. `fill_config`
calls the LLM exactly once, to write slot *contents* (system prompt
wording, sample questions) in the prospect's own vocabulary -- it
never touches which blueprint was picked or which tools get attached;
those come from the Blueprint definition selected above, not the
model. See decisions.md D-0017.
"""

import json

from overture.graph.llm_output import strip_code_fences
from overture.poc.blueprints import ALL_BLUEPRINTS, Blueprint
from overture.providers.base import LLMProvider, Message
from overture.schemas import (
    DemoConfig,
    DemoConfigStatus,
    RequirementCategory,
    ScopeClassification,
    SolutionBrief,
)


def select_blueprint(brief: SolutionBrief) -> Blueprint:
    """Score each blueprint against in-scope requirement text and pick the highest.

    Scoring: count capability-tag hits as case-insensitive substrings
    of the concatenated in-scope requirement text. Ties are broken by
    declaration order in ALL_BLUEPRINTS (first-declared wins) -- fixed
    and repeatable, never random.
    """
    in_scope_text = " ".join(
        req.text.lower() for req in brief.requirements if req.scope == ScopeClassification.IN_SCOPE
    )

    best = ALL_BLUEPRINTS[0]
    best_score = -1
    for blueprint in ALL_BLUEPRINTS:
        score = sum(1 for tag in blueprint.capability_tags if tag in in_scope_text)
        if score > best_score:
            best = blueprint
            best_score = score
    return best


_FILL_SLOTS_PROMPT = """You are drafting the configuration for a proof-of-concept
demo based on a "{blueprint_name}" blueprint: {blueprint_description}

Use the prospect's own vocabulary below wherever possible -- the demo
should sound like it was built specifically for them, not generic.

In-scope needs:
{in_scope_items}

Prospect's own vocabulary and terms:
{vocabulary_items}

Respond with a JSON object only -- no prose, no markdown fences --
with exactly these fields:
  "system_prompt": a system prompt (2-4 sentences) for an AI assistant
                    that addresses these in-scope needs, written in the
                    prospect's vocabulary.
  "sample_questions": an array of exactly {question_count} example
                       questions a user of this demo might ask,
                       phrased the way this specific prospect would
                       phrase them."""


async def fill_config(
    brief: SolutionBrief, blueprint: Blueprint, provider: LLMProvider
) -> DemoConfig:
    in_scope = [r.text for r in brief.requirements if r.scope == ScopeClassification.IN_SCOPE]
    # Vocabulary items' .text is a PARAPHRASED LABEL (e.g. "Company name"),
    # not the actual term -- the real value lives in source_span.quoted_text.
    # Passing only .text here was the root cause of a real hallucination:
    # the model, handed "Company name" with no actual name attached,
    # invented one ("Harlow Industrial Group" for a transcript that never
    # mentions any company but "Meridian Fabrication Group"). See D-0019.
    vocabulary = [
        f'"{r.source_span.quoted_text}" ({r.text})'
        for r in brief.requirements
        if r.category == RequirementCategory.VOCABULARY
    ]

    prompt = _FILL_SLOTS_PROMPT.format(
        blueprint_name=blueprint.name,
        blueprint_description=blueprint.description,
        in_scope_items="\n".join(f"- {item}" for item in in_scope) or "(none)",
        vocabulary_items="\n".join(f"- {item}" for item in vocabulary) or "(none)",
        question_count=blueprint.sample_question_count,
    )

    result = await provider.complete(
        system="You write concise, grounded demo configuration content. No filler.",
        messages=[Message(role="user", content=prompt)],
        max_tokens=2048,
    )

    system_prompt = ""
    sample_questions: list[str] = []
    try:
        parsed = json.loads(strip_code_fences(result.text))
        if isinstance(parsed, dict):
            system_prompt = str(parsed.get("system_prompt", "")).strip()
            raw_questions = parsed.get("sample_questions", [])
            if isinstance(raw_questions, list):
                sample_questions = [str(q).strip() for q in raw_questions if str(q).strip()]
    except json.JSONDecodeError:
        # Leave system_prompt empty and sample_questions empty -- the
        # validator (poc/validator.py) will catch both and reject this
        # config rather than silently shipping a broken one.
        pass

    return DemoConfig(
        session_id=brief.session_id,
        blueprint_id=blueprint.id,
        system_prompt=system_prompt,
        tools=list(blueprint.default_tools),
        sample_questions=sample_questions[: blueprint.sample_question_count],
        status=DemoConfigStatus.DRAFT,
    )
