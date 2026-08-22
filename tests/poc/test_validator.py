import uuid

from overture.poc.validator import MAX_TOKEN_BUDGET, validate_config
from overture.schemas import DemoConfig, DemoConfigStatus


def _valid_config(**overrides: object) -> DemoConfig:
    base: dict[str, object] = {
        "session_id": uuid.uuid4(),
        "blueprint_id": "grounded_document_qa",
        "system_prompt": "You answer questions about vendor contracts.",
        "tools": ["document_search", "citation_lookup"],
        "sample_questions": ["Which contracts renew in 90 days?"],
        "token_budget": 100_000,
    }
    base.update(overrides)
    return DemoConfig(**base)  # type: ignore[arg-type]


def test_valid_config_is_validated() -> None:
    result = validate_config(_valid_config())
    assert result.status == DemoConfigStatus.VALIDATED
    assert result.validation_errors == []


def test_unknown_blueprint_id_is_rejected() -> None:
    result = validate_config(_valid_config(blueprint_id="made_up_blueprint"))
    assert result.status == DemoConfigStatus.REJECTED
    assert any("unknown blueprint_id" in e for e in result.validation_errors)


def test_disallowed_tool_is_rejected() -> None:
    result = validate_config(_valid_config(tools=["document_search", "delete_everything"]))
    assert result.status == DemoConfigStatus.REJECTED
    assert any("delete_everything" in e for e in result.validation_errors)


def test_token_budget_over_ceiling_is_rejected() -> None:
    result = validate_config(_valid_config(token_budget=MAX_TOKEN_BUDGET + 1))
    assert result.status == DemoConfigStatus.REJECTED
    assert any("token_budget" in e for e in result.validation_errors)


def test_empty_system_prompt_is_rejected() -> None:
    result = validate_config(_valid_config(system_prompt="   "))
    assert result.status == DemoConfigStatus.REJECTED
    assert any("system_prompt is empty" in e for e in result.validation_errors)


def test_zero_sample_questions_is_rejected() -> None:
    result = validate_config(_valid_config(sample_questions=[]))
    assert result.status == DemoConfigStatus.REJECTED
    assert any("sample question" in e for e in result.validation_errors)


def test_multiple_failures_are_all_reported_not_just_the_first() -> None:
    result = validate_config(
        _valid_config(system_prompt="", sample_questions=[], tools=["not_allowed"])
    )
    assert result.status == DemoConfigStatus.REJECTED
    assert len(result.validation_errors) == 3


def test_original_config_is_not_mutated() -> None:
    original = _valid_config()
    assert original.status == DemoConfigStatus.DRAFT
    validate_config(original)
    assert original.status == DemoConfigStatus.DRAFT  # unchanged -- model_copy, not mutation


def test_validator_module_imports_no_provider_or_network_client() -> None:
    # Static proof this module cannot make an LLM call: neither the
    # provider Protocol nor either concrete implementation is imported
    # anywhere in poc.validator.
    import overture.poc.validator as validator_module

    source = validator_module.__file__
    assert source is not None
    with open(source) as f:
        contents = f.read()
    assert "anthropic" not in contents.lower()
    assert "openai" not in contents.lower()
    assert "provider" not in contents.lower()
