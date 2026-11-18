# Release Evidence

## Candidate under test
`TheBrain_Julian_Phase1_Build_Candidate` source extracted from the available conversation artifact and updated with portable launch scaffolding.

## Reproducible checks

```bash
./julianrebuild.sh check
./julianrebuild.sh test
./julianrebuild.sh preflight
JULIAN_DEPLOY_CONFIRM=YES JULIAN_RUNTIME_STOPPED=YES ./julianrebuild.sh deploy /absolute/path/to/a-disposable-target
```

Recorded in this build environment:
- Syntax checks: PASS.
- Unit/API/portable-contract tests: 44 passed.
- Read-only database preflight: `ready_for_review`, no database existed at the candidate's configured path and no write/migration was performed.
- Disposable deployment: PASS, including staging and activation smoke tests.
- Local API smoke: PASS for UI/health/capability listing/conversation/history/audit and explicit failure when LLM was disabled. This is not successful model inference.
- Portable launcher fail-closed test: exit 1 with a specific missing configured Python runtime message. No system-Python fallback occurred.

## Verification boundary
No access to the user's Mac, external flash drive, local Qwen model, live llama-server, or actual existing runtime/database was available. Successful inference, live research, quote/date/claim verification, true generation cancellation, browser E2E, Windows, and multi-device portability remain unverified. Do not label Phase 1 accepted until those gates pass with recorded evidence.
