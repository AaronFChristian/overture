import time
import uuid

from overture.poc.tokens import mint_share_token, verify_share_token

SECRET = "test-secret-key"


def test_mint_and_verify_round_trip() -> None:
    session_id = str(uuid.uuid4())
    token = mint_share_token(session_id, SECRET)
    assert verify_share_token(token, SECRET) == session_id


def test_verify_rejects_wrong_secret() -> None:
    session_id = str(uuid.uuid4())
    token = mint_share_token(session_id, SECRET)
    assert verify_share_token(token, "a-different-secret") is None


def test_verify_rejects_tampered_token() -> None:
    session_id = str(uuid.uuid4())
    token = mint_share_token(session_id, SECRET)
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert verify_share_token(tampered, SECRET) is None


def test_verify_rejects_garbage_input() -> None:
    assert verify_share_token("not-a-real-token-at-all", SECRET) is None


def test_verify_rejects_expired_token() -> None:
    session_id = str(uuid.uuid4())
    token = mint_share_token(session_id, SECRET)
    # itsdangerous timestamps have 1-second granularity, so the sleep
    # must exceed 1 full second to guarantee the token's embedded
    # timestamp is actually older than "now" by more than max_age=0 --
    # a shorter sleep can land within the same integer second and
    # falsely appear unexpired regardless of max_age.
    time.sleep(1.1)
    assert verify_share_token(token, SECRET, max_age=0) is None


def test_different_session_ids_produce_different_tokens() -> None:
    token_a = mint_share_token(str(uuid.uuid4()), SECRET)
    token_b = mint_share_token(str(uuid.uuid4()), SECRET)
    assert token_a != token_b
