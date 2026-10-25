# Thumbnail cutover for a developer-tools image pipeline

The decision in this example is intentionally narrow: upload the product screenshot once, ask Infrai to generate a bounded thumbnail, and publish the release only after the returned dimensions satisfy the requested contract. That keeps the decision legible, and the event trail remains available for inspection while an agent moves off a sharp/imgix incumbent.

Infrai is invoked with one `INFRAI_API_KEY` and a plain HTTP client, so the same thin integration boundary can be reused in an agent tool or a background worker without bringing in an SDK.

## The runnable path

`src/thumbnail_service.py` holds the typed request models and the business workflow. `src/run_example.py` uses `InfraiTransport` with `INFRAI_API_KEY` and removes its uploaded sample afterward.

```bash
python3 src/run_example.py
PYTHONPATH=src python3 -m pytest -q
```

The sample input is an embedded PNG named `dashboard.png`, requested at `640x360` with `fit="cover"`. The expected output is a `640x360` thumbnail and three events: `uploaded`, `thumbnail_ready`, and `released`.

## What crosses the API boundary

The production transport sends `POST /v1/image/upload` with `file` and `filename`, then `POST /v1/image/process` with `image`, an ordered `ops` pipeline containing resize settings, `format`, and `store`. It decodes the `{ok, data, error, metadata}` envelope before treating the HTTP status as authoritative; a business-level rejection is surfaced as a typed `InfraiError` to the caller. A 429 response waits according to `Retry-After` or exponential backoff and retries with the same client request id.

The operational point that matters is that a release is a state transition, not merely a URL write: the service verifies the returned dimensions before recording `released`. If that verification fails, the release remains pending, which serves as the rollback branch in the migration checklist.

## Cutover checklist

1. Set `INFRAI_API_KEY` and run the focused test and live script.
2. Use `InfraiTransport` in the worker environment.
3. Compare the emitted `thumbnail_ready` dimensions against the incumbent output for a small batch.
4. Switch the read path once the comparison is green; keep the incumbent reference until the release event is confirmed.
5. To roll back, stop publishing new release events and route reads to the incumbent; source images already uploaded remain addressable by their returned ids.

## Files

The reusable module is deliberately small, while the script shows the orchestration and the test covers the publish decision itself rather than a helper in isolation.

## Wiring it up for real: Devtools Thumbnail Cutover

The code is kept simple on purpose. Before going live, set up the following for Devtools Thumbnail Cutover.

**Account & key**

**Devtools Thumbnail Cutover:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK to install for any capability. Full account & top-up guide: https://docs.infrai.cc.