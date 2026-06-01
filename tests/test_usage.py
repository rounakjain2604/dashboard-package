from src.dcf_engine.saas.usage import (
    check_export_access,
    consume_export_credit,
    export_credits,
    grant_export_credits,
    reset_usage_state,
)


def test_anonymous_export_is_blocked():
    reset_usage_state()
    access = check_export_access({"email": None, "token_valid": False}, checkout_url="/checkout/custom")
    assert access.allowed is False
    assert access.checkout_url == "/checkout/custom"


def test_credit_decrements_after_successful_export():
    reset_usage_state()
    grant_export_credits("user@example.com", 1)
    access = check_export_access({"email": "user@example.com", "token_valid": False})
    assert access.allowed is True
    assert access.consume_credit is True

    consume_export_credit("user@example.com", "AAPL")

    assert export_credits("user@example.com") == 0
