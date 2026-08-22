"""Prompt templates for the extraction graph.

Every extraction prompt instructs the model to quote verbatim from the
transcript specifically because llm_output.locate_span() needs an
exact substring match -- a paraphrased "quote" silently drops that
signal (see D-0005). This is stated explicitly in every prompt rather
than assumed, because it's the one instruction the whole pipeline's
correctness depends on.
"""

_OUTPUT_CONTRACT = """
Respond with a JSON array only -- no prose before or after, no markdown
code fences. Each item must have exactly these fields:
  "quoted_text": the EXACT verbatim substring from the transcript that
                 supports this item. Copy it character-for-character.
                 Do not paraphrase, summarize, or fix grammar in this
                 field -- it must be findable as an exact substring of
                 the transcript below.
  "paraphrase":  a short, plain-language restatement of the same idea,
                 for display purposes.
  "confidence":  a number from 0.0 to 1.0.
If nothing in the transcript matches this category, return [].
"""

PAIN_EXTRACTION_PROMPT = f"""You are extracting business pains from a sales
discovery call transcript. A pain is a problem, frustration, cost, or
inefficiency the prospect describes -- something that is currently
going wrong for them.
{_OUTPUT_CONTRACT}
Transcript:
{{transcript}}"""

CONSTRAINT_EXTRACTION_PROMPT = f"""You are extracting constraints from a sales
discovery call transcript. A constraint is a limitation on the
solution -- a platform requirement, compliance rule, budget ceiling,
timeline, or anything that restricts what can be built or how.
{_OUTPUT_CONTRACT}
Transcript:
{{transcript}}"""

REQUIREMENT_EXTRACTION_PROMPT = f"""You are extracting explicit requirements
from a sales discovery call transcript. A requirement is something the
prospect explicitly asks for or says the solution must do.
{_OUTPUT_CONTRACT}
Transcript:
{{transcript}}"""

VOCABULARY_EXTRACTION_PROMPT = f"""You are extracting domain vocabulary from a
sales discovery call transcript -- the prospect's own terms for their
systems, roles, document types, and processes. This vocabulary will be
reused later to make a generated demo sound like it was built for this
specific prospect, not a generic one.
{_OUTPUT_CONTRACT}
Transcript:
{{transcript}}"""

SCOPE_CLASSIFICATION_PROMPT = """You are scoping a list of extracted items
against what a rapid proof-of-concept can realistically demonstrate.
For each item, classify it as exactly one of:
  "in_scope"            -- a grounded document-QA / retrieval-style demo
                            can plausibly show this
  "out_of_scope"         -- this is clearly beyond what a POC would
                            attempt (e.g. a full production integration,
                            a different product line, a named other
                            country's regulatory regime)
  "needs_clarification"  -- genuinely ambiguous; could go either way
                            without more information from the prospect

Respond with a JSON array of strings only, one per item, in the exact
same order as the items below. Do not add, remove, or reorder items.
The array must have exactly {count} elements.

Items:
{items}"""
