from src.dcf_engine.saas.payments import process_local_payment_event, reset_payment_state
from src.dcf_engine.saas.usage import export_credits, reset_usage_state


def test_duplicate_payment_event_does_not_double_credit():
    reset_usage_state()
    reset_payment_state()
    event = {"provider_event_id": "evt_1", "email": "user@example.com", "credits": 2}

    first = process_local_payment_event(event)
    second = process_local_payment_event(event)

    assert first["processed"] is True
    assert second["processed"] is False
    assert second["duplicate"] is True
    assert export_credits("user@example.com") == 2
