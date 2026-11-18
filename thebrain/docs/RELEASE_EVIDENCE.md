# Build and Verification Evidence

## Artifact scope

This repository is a fresh TheBrain / Julian implementation based on the handover, roadmap, and additional requirements. It does not import the earlier application source as an implementation dependency or fallback. It includes a runnable FastAPI app, web UI, central orchestrator, capability registry, OpenAI-compatible model client, public-web research pipeline, deterministic evidence checks, SQLite persistence, settings/glossary/memory APIs, file ingestion, audit traces, and safe maintenance scripts.

## Changes verified in this build pass

- Fixed a mutable-default settings bug: callers editing a returned settings object could mutate process-wide defaults. Settings trees are now deep-copied and a regression test protects this behavior.
- Fixed routing for privacy-preserving ephemeral uploads. Their contents now trigger file-analysis routing even though they are intentionally absent from the database.
- Added text-based PDF extraction with per-page markers, a page-count cap, encrypted-PDF rejection, and explicit rejection of PDFs without extractable text. OCR is not included.
- Ensured ephemeral upload content is discarded in a `finally` block, including when execution is cancelled or fails.
- Research results remain `partial` until semantic entailment is independently verified; deterministic URL/quote checks alone cannot label a factual answer fully verified.
- Changed the cancellation endpoint to `async def`, so task/event cancellation runs on the server event loop instead of a synchronous worker thread.
- Fixed read-only preflight so a missing data directory is distinguished from an unwritable location; it checks the nearest existing ancestor without creating directories.
- Added fail-closed research behavior: if no source page was actually opened and read, Julian returns an explicit retrieval-stage failure/partial result without asking the model to synthesize factual claims from model priors.

## Checks executed in this build pass

| Check | Result | Scope |
|---|---|---|
| `./julianrebuild.sh check` | PASS | Python compilation, shell syntax, JavaScript syntax |
| `./julianrebuild.sh test` | PASS — 37 tests | Unit/API tests including settings isolation, ephemeral upload routing and cleanup, PDF extraction, cancellation endpoint signaling, research metadata-only fail-closed behavior, quote fidelity, routing, contracts, and database guard |
| Live HTTP smoke with temporary data directory | PASS | Uvicorn startup, `/api/health`, 9 registered capabilities, `/api/chat/stream` result event, honest `llm_disabled` error, conversation history API |
| `./julianrebuild.sh preflight` | PASS | Read-only runtime/database path discovery; missing directories are not created and a writable ancestor is checked |
| Safe deploy smoke on a disposable target | PASS | Source suite passed; staged and activated app health/UI smoke passed; prior target marker was preserved in the backup; disposable target removed afterward |
| SQLite backup/restore smoke on disposable databases | PASS | Online backup integrity, explicit restore confirmation, restored content, and `PRAGMA integrity_check` verified; disposable files removed afterward |
| Browser-driven E2E | BLOCKED BY EXECUTION ENVIRONMENT | Chromium navigation to local app returned `ERR_BLOCKED_BY_ADMINISTRATOR`; UI interactions could not be claimed as verified |

## Test environment

- Python 3.13.5
- FastAPI/httpx/Pydantic/pytest versions are resolved from the active environment; use the installed dependency lock/environment for exact reproducibility.
- Local model inference was intentionally disabled during the isolated live HTTP smoke. This verifies honest error handling, not successful model inference.
- Live HTTP and deployment smoke tests used temporary data directories/targets. They did not access or modify the user's Mac runtime or database.

## Not verified; not to be treated as accepted

- Live connection to the target local Qwen/llama.cpp server, successful inference, or true interruption of that server during generation.
- Live public-web search/page opening against the target runtime/network, provider reliability, date metadata, redirect behavior, and independent source corroboration.
- Browser-driven UI interactions and mobile layout. Chromium navigation was blocked by the execution environment; no UI E2E pass is claimed.
- Semantic entailment verification of every factual claim. Deterministic QC checks URL provenance, quote fidelity, evidence eligibility, and lexical candidate support; they do not prove semantic entailment.
- Tokenizer-exact context budgeting. The current implementation uses a character budget and logs context truncation/omitted history.
- Target macOS deployment, compatibility with the user's external database, and rollback after a deliberately fault-injected live smoke failure.
- Scanned PDF OCR, voice/speaker verification, multimodal OCR, browser automation, authentication, multi-user authorization, and full autonomous tool execution.

## Release interpretation

The checks above prove a runnable fresh implementation and the listed local tests. They do **not** prove that all Phase 1 acceptance gates have passed. Phase 1 remains active and unaccepted until live model/web integrations, browser E2E, real cancellation, independent verification, and target-runtime update/rollback have fresh evidence. No estimate or delivery date is asserted here.

- Portable setup helper `scripts/configure_portable_runtime.sh`: syntax-checked; not executed against the user's device.
- Live acceptance harness `scripts/live_acceptance.sh`: added; intentionally not marked passed until executed against the real configured model and live research provider.
