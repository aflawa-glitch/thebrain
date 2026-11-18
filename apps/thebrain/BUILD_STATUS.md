# TheBrain / Julian — Build and Verification Status

## Release identity

- Package: `TheBrain_Julian_Phase1_Portable_Candidate`
- Version label: `0.2.1-phase1-candidate`
- Scope: independently structured Phase 1 application candidate plus portable launcher scaffolding.
- This package is **not marked ACCEPTED** and is not represented as a full, live-verified deployment on the user's Mac or across devices.

## Implemented in this candidate

- FastAPI backend; ChatGPT-like white UI; chat history; multiline composer; attachment/upload entry point; streaming/status events; stop/cancel endpoint.
- Central orchestrator with registered capabilities, trace IDs, audit events, stage-specific failures, local OpenAI-compatible model client, research/page-opening flow, memory/settings/glossary APIs, file parsing, and source evidence records.
- SQLite storage, read-only database preflight, backup/restore paths, and opt-in staged deployment with smoke tests and rollback.
- Relocatable root marker and macOS/Linux Bash + Windows PowerShell portable launchers. Launchers avoid `source`/dot-sourcing the config, system-Python fallback, automatic package installation, global OS mutation, and killing unrelated processes. Readiness requires both model and backend health checks.
- Portable support matrix and explicit verification limitations.

## Tests run for this package

| Check | Result | What it proves |
|---|---|---|
| `./julianrebuild.sh check` | PASS | Python compile check, Bash syntax check, JavaScript syntax check where Node is available |
| `./julianrebuild.sh test` | PASS — 44 tests | Unit/API tests for current candidate code and portable contract assertions |
| `./julianrebuild.sh preflight` | PASS — `ready_for_review` | Read-only database path discovery; no migration/write performed |
| Disposable deployment via `JULIAN_DEPLOY_CONFIRM=YES JULIAN_RUNTIME_STOPPED=YES ./julianrebuild.sh deploy <temporary-target>` | PASS | Test suite, staging smoke, activation smoke; no pre-existing target/data to preserve |
| Live local HTTP smoke with `JULIAN_LLM_ENABLED=false` | PASS for app/API; model intentionally unavailable | UI response, health, 9 capability registry entries, conversation creation/history, chat trace, audit endpoint, explicit failed inference path |
| `launcher/julian-portable.sh` with the package's sample config | BLOCKED as designed | Correctly refuses startup because the platform Python runtime is not bundled; no fallback to system Python |
| Bash syntax for portable launcher and setup helper | PASS | Syntax only; not a macOS runtime test |
| Windows PowerShell launcher | NOT TESTED | No Windows PowerShell runtime available in this build environment |
| Live acceptance harness | IMPLEMENTED, not run against user runtime | `scripts/live_acceptance.sh` checks real model health, chat, lifecycle audit, history, and live research/evidence-or-failure behavior |

## Critical items not verified / not included

- Successful inference against the user's Qwen model/llama-server on the actual M1. The new setup helper can configure existing app-owned assets if found, but does not make an external environment self-contained or portable.
- Successful live web search, source opening, verbatim quote validation, historical-date regression suite, independent semantic claim verification, and end-to-end claim-to-evidence proof.
- Real interruption/cancellation during active model generation, browser-driven UI E2E, mobile layout, and file-upload tests in the user's runtime.
- Portable relocation on the user's flash drive and second device/OS/architecture.
- Windows PowerShell syntax/runtime; Windows binaries and a matching Python environment.
- The GGUF model and platform-specific Python/llama.cpp runtimes are not included.
- Full Phase 1 acceptance against the actual existing runtime/data/updater and fault-injected rollback.

## Status

**IMPLEMENTED + 44 UNIT/API TESTS PASS + DISPOSABLE DEPLOYMENT SMOKE PASS; NOT LIVE-VERIFIED OR ACCEPTED.**

This is a real source artifact with repeatable tests, not proof that all functions are currently working on the user's device. Do not deploy over the user's existing runtime until the actual target paths, runtime, model, database, backup, and rollback plan have been checked. No system Python, global PATH/profile, macOS components, or user runtime was changed by this build.
