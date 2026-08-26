"""Signed, expiring share tokens for prospect-facing demo access.

Two-tier access model (D-0022): the SE console that creates and manages
sessions gets real Entra ID auth once session 8 wires it up. The
prospect-facing demo itself uses these signed tokens instead -- no
login, just a link, matching the report's "leave-behind sandbox link
the prospect can revisit" requirement. A token proves possession of a
link, not identity -- that's an intentional, much weaker guarantee than
account auth, and appropriate for content a prospect was deliberately
handed to explore on their own.
"""

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

DEFAULT_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="overture-demo-share")


def mint_share_token(session_id: str, secret_key: str) -> str:
    return _serializer(secret_key).dumps(session_id)


def verify_share_token(
    token: str, secret_key: str, max_age: int = DEFAULT_TOKEN_MAX_AGE_SECONDS
) -> str | None:
    """Returns the session_id if the token is valid and unexpired, else None.

    Deliberately returns None rather than raising -- callers (the
    /demo/{token}/ask route) treat "invalid" and "expired" identically:
    both mean "this link doesn't work anymore," which is all a prospect
    needs to know.
    """
    try:
        result = _serializer(secret_key).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return str(result)
