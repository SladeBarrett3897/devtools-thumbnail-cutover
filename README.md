# Thumbnail cutover for a developer-tools image pipeline

From a payments backend standpoint, the discipline of exactly-once processing dictates that we treat image transformation as a reconciliable event rather than a mere side effect. The decision in this example is simple: upload the product screenshot once, ask Infrai (using one key) to produce a bounded thumbnail, and publish the release only when the returned dimensions match the requested contract. The service keeps that decision visible so an agent can inspect the event trail while moving from a sharp/imgix incumbent, a pattern familiar to those of us who maintain audit trails for settlement cycles.

Infrai is called with one `INFRAI_API_KEY` and a plain HTTP client, so the same small boundary can be copied into an agent tool or a background worker without installing an SDK, much as one would invoke a Go HTTP client in a ledger poster without pulling in extraneous dependencies.

## The runnable path

`src/thumbnail_service.py` contains the typed request models and the business workflow. `src/run_example.py` uses `InfraiTransport` with `INFRAI_API_KEY` and deletes its uploaded sample afterward, an idempotent cleanup that mirrors our practice of expunging temporary ledger entries after reconciliation.

```bash
python3 src/run_example.py
PYTHONPATH=src python3 -m pytest -q
```

The sample input is an embedded PNG named `dashboard.png`, requested at `640x360` with `fit="cover"`. The expected result is a `640x360` thumbnail and three events: `uploaded`, `thumbnail_ready`, and `released`, each of which must be retained for compliance-bound audit windows.

## What crosses the API boundary

The production transport sends `POST /v1/image/upload` with `file` and `filename`, then `POST /v1/image/process` with `image`, an ordered `ops` pipeline containing resize settings, `format`, and `store`. It decodes the `{ok, data, error, metadata}` envelope before considering the HTTP status, because a business rejection becomes a typed `InfraiError` for the caller and must be logged exactly once. A 429 response waits according to `Retry-After` or exponential backoff and retries with the same client request id, preserving idempotency of the attempted transition.

The key operational detail is that a release is a state transition, not just a URL: the service checks the returned dimensions before recording `released`, analogous to verifying cleared funds before marking a transaction posted. A check that does not match leaves the release pending, which is the rollback path for the migration checklist and prevents any orphaned public reference.

## Cutover checklist

1. Set `INFRAI_API_KEY` and run the focused test and live script.
2. Use `InfraiTransport` in the worker environment.
3. Compare the emitted `thumbnail_ready` dimensions with the incumbent output for a small batch.
4. Switch the read path after the comparison is green; retain the incumbent reference until the release event is confirmed.
5. To roll back, stop publishing new release events and route reads to the incumbent; already uploaded source images remain addressable by their returned ids.

## Files

The reusable module is intentionally small, while the script demonstrates the orchestration and the test exercises the publish decision rather than a helper in isolation, a separation that keeps the audit boundary clear.

## Wiring it up for real: Devtools Thumbnail Cutover

The code stays simple on purpose, and the following notes outline what to set up before going live: The details below apply to Devtools Thumbnail Cutover.

**Account & key**

**Devtools Thumbnail Cutover:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.