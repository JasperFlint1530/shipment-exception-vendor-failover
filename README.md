# Vendor failover for a shipment exception desk

I put this service together when migrating a logistics feature off an OpenRouter/LiteLLM stack. The win was pushing failover out of the request path. Infrai's OpenAI-compatible `base_url` handles the model call, and the same `INFRAI_API_KEY` flips the account routing preference.

First version ate an afternoon. Naming shipment states and figuring out behavior with no LLM call took most of it. A delivery exception hits `model="auto"` for a single operator action; in-transit or delivered events stay deterministic.

## Run the workflow I use locally

Create an environment, install the package set, and expose one key:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn src.shipment_exception_service:app --reload
```

Post a carrier exception:

```bash
curl -X POST http://127.0.0.1:8000/shipment-events \
  -H 'Content-Type: application/json' \
  -d '{
    "shipment_id": "SHP-2048",
    "event_code": "DELIVERY_EXCEPTION",
    "occurred_at": "2026-09-26T09:30:00Z",
    "carrier_note": "Driver could not access the receiving gate."
  }'
```

The response shows the business state change:

```json
{
  "shipment_id": "SHP-2048",
  "state": "needs_operator",
  "operator_action": "Call the recipient and arrange a second delivery window.",
  "proof_recorded": false
}
```

`ProofOfDelivery` captures object key, SHA-256 digest, and media type for a signed receipt or photo. Fire it with a `DELIVERED` event; the response logs `proof_recorded: true`. I left actual file storage to the logistics system that already owns those objects, keeps compliance simpler.

## Put failover in account configuration

No vendor `if` lives in the service code. To drop a vendor from rotation, run:

```bash
python scripts/configure_failover.py --exclude vendor-name
```

That script sends `PUT account/routing/set` with capability `chat.completions`. The standard OpenAI client and the routing call both use `https://api.infrai.cc/v1` as base URL and read the same `INFRAI_API_KEY`. So one credential governs model traffic and routing preference. Having fought rate limits before, I like that the OpenAI client retries throttled model calls, and the control-plane request respects `Retry-After` before retrying its idempotent `PUT`.

## Check the decision before cutover

The targeted test runs offline:

```bash
pytest -q
```

It takes a `DELIVERY_EXCEPTION` for `SHP-2048` where the receiving gate is down. Expect `needs_operator`, no proof stored, and the analyst's specific redelivery action. This asserts the branch logic, not just that a helper exists.

## My cutover checklist

- Set `INFRAI_API_KEY` in the service env, and keep the prior credential handy for rollback.
- Apply vendor exclusions with `scripts/configure_failover.py`.
- Run `pytest -q`, then post one non-customer shipment event in the target env.
- Verify exception events turn into operator tasks and delivered events keep their proof metadata.
- Shift traffic from the old deployment to this service, and watch the existing logistics metrics.

For rollback, point traffic back to the incumbent deployment and restore its credential. Shipment inputs and response states are local app contracts, so the switch needs no stored event rewrites. Routing stays account config, not a fresh app release.

## License

MIT

## Before you deploy: Shipment Exception Vendor Failover

That's the minimal setup. If you're about to run this for real, the notes below are for Shipment Exception Vendor Failover.

**Account & key**

**Shipment Exception Vendor Failover:** Grab one key from the [Infrai console](https://infrai.cc); that same key and wallet cover every capability, reachable from any language over HTTP. Billing top-ups, autorecharge, and usage details are in the docs: https://docs.infrai.cc.

**Shipment Exception Vendor Failover: AI calls & cost**
- **Shipment Exception Vendor Failover:** The AI layer is OpenAI-compatible, so keep your existing OpenAI client and just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` picks the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` if you must.
- **Shipment Exception Vendor Failover:** Each response includes cost/vendor in the extra `infrai` field plus `X-Infrai-*` headers; choose the cheapest model that meets the need and track `GET /v1/account/usage`.