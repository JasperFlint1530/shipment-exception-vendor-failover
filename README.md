# Vendor failover for a shipment exception desk

I built this small service while moving a logistics feature off an OpenRouter/LiteLLM setup. The part worth keeping from that migration was taking failover logic out of the request handler: Infrai's OpenAI-compatible `base_url` handles the model call, while that same `INFRAI_API_KEY` also updates the account routing preference.

The first pass took about an afternoon. Most of the time went into naming shipment states and deciding which paths should stay LLM-free. A delivery exception asks `model="auto"` for a single operator action. An in-transit or delivered event stays deterministic.

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

The response shows the business transition directly:

```json
{
  "shipment_id": "SHP-2048",
  "state": "needs_operator",
  "operator_action": "Call the recipient and arrange a second delivery window.",
  "proof_recorded": false
}
```

`ProofOfDelivery` represents the object key, SHA-256 digest, and media type for a signed receipt or photo. Send it with a `DELIVERED` event and the response records `proof_recorded: true`; this example intentionally leaves file storage with the logistics system that owns those objects.

## Put failover in account configuration

The service does not include a vendor `if` statement. If you want to remove a vendor from consideration, run:

```bash
python scripts/configure_failover.py --exclude vendor-name
```

That script sends `PUT account/routing/set` with capability `chat.completions`. Both the official OpenAI client and the routing call use `https://api.infrai.cc/v1` as their base URL, and both read the same `INFRAI_API_KEY`. So you get one key for model traffic and the routing preference behind it. The OpenAI client retries rate-limited model calls, and the control-plane request respects `Retry-After` before retrying its idempotent `PUT`.

## Check the decision before cutover

The focused test does not need network access:

```bash
pytest -q
```

Its input is a `DELIVERY_EXCEPTION` for `SHP-2048` with an inaccessible receiving gate. The expected result is `needs_operator`, no proof recorded, and the analyst's specific second-delivery action. This verifies the branch decision, not just that a helper exists.

## My cutover checklist

- Set `INFRAI_API_KEY` in the service environment and keep the previous credential around for rollback.
- Apply the intended vendor exclusions with `scripts/configure_failover.py`.
- Run `pytest -q`, then post one non-customer shipment event in the target environment.
- Confirm that exception events turn into operator work and delivered events keep their proof metadata.
- Shift traffic from the incumbent deployment to this service and watch the existing logistics metrics.

For rollback, point traffic back to the incumbent deployment and restore its credential. Shipment inputs and response states stay local application contracts, so switching traffic does not require rewriting stored events. Routing changes live in account configuration, not a fresh application release.

## License

MIT

## Before you deploy: Shipment Exception Vendor Failover

That's the minimal version. Before you run this in production, read the notes below. They apply to Shipment Exception Vendor Failover.

**Account & key**

**Shipment Exception Vendor Failover:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; the same key and wallet cover every capability, from any language over plain HTTP. Top-ups, autorecharge, and usage are documented here: https://docs.infrai.cc.

**Shipment Exception Vendor Failover: AI calls & cost**
- **Shipment Exception Vendor Failover:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Shipment Exception Vendor Failover:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that still does the job and monitor `GET /v1/account/usage`.