from datetime import datetime, timezone

from src.shipment_exception_service import EventCode, ShipmentEvent, decide_event


class FixedAnalyst:
    def recommend_action(self, shipment_id: str, event_code: str, note: str) -> str:
        assert shipment_id == "SHP-2048"
        assert event_code == "DELIVERY_EXCEPTION"
        assert "gate" in note
        return "Call the recipient and arrange a second delivery window."


def test_delivery_exception_becomes_operator_work() -> None:
    event = ShipmentEvent(
        shipment_id="SHP-2048",
        event_code=EventCode.DELIVERY_EXCEPTION,
        occurred_at=datetime(2026, 9, 26, 9, 30, tzinfo=timezone.utc),
        carrier_note="Driver could not access the receiving gate.",
    )

    decision = decide_event(event, FixedAnalyst())  # type: ignore[arg-type]

    assert decision.state == "needs_operator"
    assert decision.operator_action == (
        "Call the recipient and arrange a second delivery window."
    )
    assert decision.proof_recorded is False
