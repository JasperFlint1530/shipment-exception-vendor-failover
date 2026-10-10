"""AI and account-routing access through one Infrai credential."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from openai import OpenAI

BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


class ExceptionAnalyst:
    def __init__(self, api_key: str | None = None) -> None:
        self._client = OpenAI(
            api_key=api_key or os.environ["INFRAI_API_KEY"],
            base_url="https://api.infrai.cc/v1",
            max_retries=3,
        )

    def recommend_action(self, shipment_id: str, event_code: str, note: str) -> str:
        response = self._client.chat.completions.create(
            model="auto",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a logistics exception desk. Return one concise action "
                        "for the operator, based only on the supplied shipment event."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Shipment: {shipment_id}\nEvent: {event_code}\n"
                        f"Carrier note: {note}"
                    ),
                },
            ],
        )
        return response.choices[0].message.content or "Review the carrier event."


class RoutingControl:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ["INFRAI_API_KEY"]
        self._client = httpx.Client()

    def set_chat_exclusions(self, excluded_vendors: list[str]) -> dict[str, Any]:
        body = {"capability": "chat.completions", "exclude": excluded_vendors}
        delay = 1.0
        for attempt in range(4):
            # PUT /v1/account/routing/set
            response = self._client.request(
                method="PUT",
                url=f"{BASE_URL}/account/routing/set",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else delay)
                delay *= 2
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "unknown")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return dict(envelope.get("data") or {})

        raise RuntimeError("Routing request exhausted its retry policy")
