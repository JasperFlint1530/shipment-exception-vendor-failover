"""FastAPI entry point for shipment events and proof-of-delivery records."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_gateway import ExceptionAnalyst, InfraiError


class EventCode(str, Enum):
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    DELIVERY_EXCEPTION = "DELIVERY_EXCEPTION"


class ProofOfDelivery(BaseModel):
    object_key: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str = Field(pattern=r"^(image/jpeg|image/png|application/pdf)$")


class ShipmentEvent(BaseModel):
    shipment_id: str = Field(min_length=1)
    event_code: EventCode
    occurred_at: datetime
    carrier_note: str = Field(min_length=1, max_length=1000)
    proof_of_delivery: ProofOfDelivery | None = None


class EventDecision(BaseModel):
    shipment_id: str
    state: str
    operator_action: str | None
    proof_recorded: bool


def decide_event(event: ShipmentEvent, analyst: ExceptionAnalyst) -> EventDecision:
    if event.event_code == EventCode.DELIVERY_EXCEPTION:
        action = analyst.recommend_action(
            event.shipment_id,
            event.event_code.value,
            event.carrier_note,
        )
        return EventDecision(
            shipment_id=event.shipment_id,
            state="needs_operator",
            operator_action=action,
            proof_recorded=False,
        )

    if event.event_code == EventCode.DELIVERED:
        return EventDecision(
            shipment_id=event.shipment_id,
            state="delivered",
            operator_action=None,
            proof_recorded=event.proof_of_delivery is not None,
        )

    return EventDecision(
        shipment_id=event.shipment_id,
        state="moving",
        operator_action=None,
        proof_recorded=False,
    )


def get_analyst() -> ExceptionAnalyst:
    return ExceptionAnalyst()


app = FastAPI(title="Shipment exception desk")


@app.post("/shipment-events", response_model=EventDecision)
def record_shipment_event(
    event: ShipmentEvent,
    analyst: Annotated[ExceptionAnalyst, Depends(get_analyst)],
) -> EventDecision:
    try:
        return decide_event(event, analyst)
    except InfraiError as error:
        client_status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": error.code, "message": str(error)},
        ) from error
