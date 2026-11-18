# Phase 1 — Fresh Rebuild Status Ledger

Statuses are evidence labels, not promises. This ledger reflects tests performed on this repository only.

| ID | Requirement | Current status | Evidence / remaining gate |
|---|---|---|---|
| P1-A01 | Source/artifact identity | IMPLEMENTED | Fresh repository; release report records hash |
| P1-A02 | `julianrebuild.sh` entry point | IMPLEMENTED | install/check/test/run/preflight/backup/restore commands |
| P1-A03 | Runtime/database path discovery | UNIT-TESTED | Config/env-based; target Mac path not assumed |
| P1-A04 | Live startup/model/search record | BLOCKED | Must be run against target runtime and live services |
| P1-A05 | Reproducible test suite | UNIT-TESTED | `./julianrebuild.sh check` and `test`; results in release report |
| P1-A06 | Update preflight/backup/restore | PARTIAL | Database operations included; source deployment rollback not validated |
| P1-B01/B02 | Central request lifecycle | UNIT-TESTED | Orchestrator stages and trace events; live trace inspection still needed |
| P1-B03/B04 | Capability contracts/central policy | UNIT-TESTED | Registry and bounded execution; no capability can silently replace coordinator |
| P1-B05 | Route coverage | UNIT-TESTED | Chat, research, coding, file analysis, app builder, URL open |
| P1-B06 | Failure/cancel/timeout paths | PARTIAL | Error and timeout wrappers exist; real model cancellation needs live test |
| P1-C01 | Consistent persona | IMPLEMENTED | Global profile and language setting |
| P1-C02/C03 | Token budget/compaction | PARTIAL | Character budget and history retention; exact tokenizer-aware budgeting pending |
| P1-C04 | Context overflow diagnosis | IMPLEMENTED | Trace event and user-visible partial warning |
| P1-D01/D02 | URL/open/read provenance | IMPLEMENTED | Evidence schema stores retrieval/open/read states |
| P1-D03/D04 | Claim mapping and quote fidelity | PARTIAL | Exact quote and candidate claim mapping checks are present; no-readable-content research now fails closed; semantic entailment and independent verifier remain open |
| P1-D05/D06/D07/D09 | Temporal/source independence/conflicts | PARTIAL | Captured metadata supports review; robust evaluation and conflict resolution pending |
| P1-D08 | Independent verifier | BLOCKED | Not integrated yet |
| P1-E01–E05 | Existing UX contracts | IMPLEMENTED | Responsive UI, sticky sidebar, composer, status, history, uploads |
| P1-E06 | Stop/cancel real inference | PARTIAL | Cancellation endpoint runs on the event loop and is unit-tested; actual model-server interruption must be live-verified |
| P1-E07/E08 | History, uploads, stream E2E | UNIT-TESTED/PARTIAL | API tests cover history, streaming result, text/PDF ingestion, privacy-preserving upload cleanup; browser navigation is blocked by this environment and mobile verification remains pending |
| P1-F01 | Learning outcome → decision policy | BLOCKED | Memory/outcome schema groundwork only; no auto-learning policy changes |
| P1-F02/F03 | Regression/audit trail | UNIT-TESTED | Expanded regression suite and SQLite stage audit; no-readable-source fail-closed behavior is covered |
| P1-F04 | Retry/idempotency/recovery | PARTIAL | Bounded timeout/failure handling; broader side-effect idempotency pending |
| P1-F05 | Release evidence | IMPLEMENTED | See release report and SHA-256 file |

## Required next gates before Phase 1 acceptance

- Start the configured local model server and verify chat, coding, research synthesis, timeout, and cancellation against it.
- Verify public web search and page-open behavior against the live network; test inaccessible pages, redirects, date metadata, and independent sources.
- Run browser E2E for streaming, history, uploads, mobile layout, stop button, and latest-answer visibility.
- Add independent claim verification and end-to-end claim-to-evidence mapping; run the historical presidency and recent-news regression corpus.
- Validate deployment, database backup, source rollback, smoke test, and restoration on the intended runtime.
- Reconcile and close all roadmap gates with exact commands/results. Until then Phase 1 remains active and not accepted.


## Current candidate verification update
- 44 unit/API/contract tests pass in the isolated build environment.
- Disposable staged deployment and post-activation smoke pass with LLM disabled; this proves app/API deployment behavior, not real inference.
- Health now reports `degraded` when model API is unavailable.
- Mac runtime discovery helper and live acceptance harness are present. They remain unexecuted on the user device; no actual model/web E2E acceptance is claimed.
