# TheBrain / Julian — Rebuild Requirements

## Mission and authority
Julian is the single authoritative brain/orchestrator, not merely a chat interface. It interprets goals, creates plans, selects registered capabilities, coordinates bounded work, verifies observable results, recovers from failure, and explains outcomes. Subprocesses cannot bypass central policy.

## Non-negotiable engineering rules
- Evidence before claims; distinguish facts, user instructions, inference, unknowns, and failed checks.
- Never fabricate source URLs, access dates, quotes, test results, code changes, or completion claims.
- Track implementation, unit tests, integration tests, live verification, and acceptance as distinct states.
- Capability contracts declare inputs, outputs, permissions, side effects, timeouts, cancellation behavior, and verification requirements.
- Preserve provenance for user files, URLs, research pages, memory, corrections, and outputs.
- Explain failures with stage, category, trace/log evidence, impact, and next diagnostic step.
- Learning outcomes must not silently change policy; future policy changes require measured evaluation, versioning, approval gates, and rollback.
- Discover runtime and database paths from explicit configuration; never assume an external disk path.
- Updates require preflight, backup, smoke test, and a tested rollback path before release acceptance.
- Do not use a deadline to waive a quality gate. No unvalidated delivery estimates are included in this rebuild.

## Persona and language
- Default response style: casual modern Indonesian slang with consistent `gue/lo` pronouns.
- Understand Indonesian, English, and multilingual input without forcing the user to translate.
- Allow global persona/profile/language settings and separate module-level settings.
- Be proactive rather than reflexively agreeable; offer alternatives when useful, ask only when a missing detail blocks safe/correct progress.
- Let the user define new terms in a persistent glossary. Glossary content is injected into relevant context.
- Never state a guess as verified fact.

## User interface contract
- Elegant, simple, white-background interface inspired by familiar chat applications.
- Fixed/sticky left navigation and conversation history while the main chat scrolls.
- The latest answer remains visible above the composer; the composer is multiline and auto-grows to a sensible maximum.
- Attachment control is symmetric and accessible; support text/source files and public links with provenance.
- Display meaningful process status in the output area.
- Provide a stop/cancel action during processing and a jump-to-latest control.
- Keep chat history and ensure absent context is never falsely assumed.
- All UI labels, buttons, menus, and notifications are in English. Response language is controlled by the persona settings.

## Roadmap sequencing
- **Phase 1 — Brain Foundation:** orchestrator, routing, capability contracts, persona/context, evidence/research verification, chat flow, status, cancellation, integration, recovery, update safety, regression tests. Keep this phase active until all acceptance gates pass.
- **Phase 2 — Memory & Knowledge Intelligence:** session/project/preference/episodic/sourced knowledge, ingestion, provenance, retrieval evaluation, corrections and supersession history.
- **Phase 3 — Adaptive Reasoning & Planning:** decomposition, dependencies, budgets, stop conditions, alternatives, uncertainty-aware routing and replanning.
- **Phase 4 — Controlled Learning & Evolution:** attributed outcomes, evaluated LearningEngine-to-DecisionPolicy path, versioned policies, regression gates, approval, drift monitoring and rollback.
- **Phase 5 — Tools, Execution & Automation:** capability-driven tools, permissions, checkpoints, idempotency, retries, cancellation, side-effect handling, audit logs and multi-step workflows under Julian.
- **Phase 6 — Multimodal & Voice:** image/document/audio, OCR/transcription confidence, consent-based voice enrollment and authorization, safe fallbacks.
- **Phase 7 — Production Hardening & Security:** runtime/config discovery, secrets, permissions, dependency integrity, database migration safety, backup/rollback, health checks, logs/metrics, packaging and recovery.
- **Phase 8 — Advanced Intelligence & Optimization:** benchmark-driven routing/retrieval/context packing/resource allocation and safe parallelism without weakening evidence quality.

Phase 1 must be stabilized before the roadmap is treated as ready for broad expansion. The later phases are design targets, not claims of completed functionality.
