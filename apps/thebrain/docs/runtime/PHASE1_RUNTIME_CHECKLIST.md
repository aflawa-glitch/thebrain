# TheBrain / Julian — Phase 1 checklist (runtime and integration)

## Runtime foundation
- [x] OS/architecture detection and root-relative path resolution.
- [x] Shared managed-runtime registry and manifest.
- [x] Per-application isolated environments for future modular apps.
- [x] Explicit fail-closed behavior when a managed runtime is missing.
- [x] Staged environment creation and opt-in replacement with previous environment preservation.
- [x] Linux workspace syntax, unit tests, and isolated-env smoke checks.
- [ ] Stage and validate actual macOS ARM64 managed Python runtime on the user's target machine.
- [ ] Validate Windows and Linux distributions on their native target systems.
- [ ] Confirm runtime package provenance, checksums, licensing, and reproducible provisioning policy.

## Phase 1 application acceptance (still active)
- [x] Offline test suite in the build workspace (35 passed, 6 subtests passed).
- [ ] Live local Qwen/llama.cpp inference, streaming, timeout, and cancellation.
- [ ] Live web search/page open, URL provenance, verbatim quotes, publication-date relevance, and historical regression questions.
- [ ] Browser end-to-end and mobile UI tests.
- [ ] Independent semantic claim verification beyond lexical candidate mapping.
- [ ] Target-machine data/database compatibility, backup, migration, rollback, and smoke tests.

No estimate or target date is assigned. Do not mark Phase 1 complete until the open acceptance gates have test evidence.
