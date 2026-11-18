# Julian Architecture and Contracts

## Central lifecycle

1. **Interpret** — normalize request and record trace ID.
2. **Plan** — choose route based on intent, settings, and available registered capabilities.
3. **Select** — capability registry describes permissions, side effects, timeouts, cancellation, and verification requirements.
4. **Execute** — run a bounded capability under a timeout; record start/result/failure in the audit ledger.
5. **Verify/QC** — inspect capability status, source open/read status, quote eligibility, context truncation, and result integrity.
6. **Recover or complete** — preserve partial result and explicit warning; do not retry indefinitely or invent a result.
7. **Explain** — return response, route, evidence metadata, warnings, and trace ID.

The orchestrator is the only request router. Capabilities do not independently take over the lifecycle or rewrite global policy.

## Capability contract

Each registered capability declares name, purpose, input/output schema, permissions, side effects, timeout, cancellation behavior, and verification rule. The registry rejects duplicate registrations and missing handlers. Capability execution is wrapped by the orchestrator with stage audit events and a timeout.

## Evidence model

Evidence stores exact URL, retrieval timestamp, open status, content status, source domain, publisher-provided publication metadata when found, extracted content, snippet, and error. Snippets/metadata are never promoted to `content_read`. Verbatim quote validation is exact normalized substring matching. Claim support scoring is a candidate-evidence aid, not a substitute for a verifier or a guarantee of entailment.

## Memory and settings

Memory records are typed (session, project, preference, episodic, sourced knowledge, correction), source-attributed, timestamped, and support supersession. Retrieval is lexical and provenance-preserving in this build; it is not yet a semantic vector store. Learning is not allowed to auto-apply policy changes; a correction/outcome loop needs evaluation and regression gates before future activation.

Settings are split into global persona/language/context/privacy and module-level enablement. The glossary is explicit user-maintained domain vocabulary. User input can be multilingual; the configured default response style is applied in the system prompt.

## Context safety

The system keeps the system prompt and current request, then includes bounded recent conversation turns and captured evidence. If the assembled current input exceeds the configured budget, the low-priority tail is truncated and a trace event plus user-visible warning is produced. This first implementation uses character budgeting as a conservative proxy, not exact tokenizer accounting; exact model-token budgeting remains a required hardening task.

## Runtime and data safety

Database discovery is configuration-driven and does not assume the user's historical external disk path. `julianrebuild.sh preflight` is read-only. Backup requires an existing configured database and explicit destination. Restore requires an explicit absolute path and typed confirmation, saves a pre-restore copy when the target exists, and checks SQLite integrity.

## Known design limitations

- Research search currently uses a public HTML search endpoint; provider reliability and source ranking need live evaluation and a provider abstraction/metrics.
- DNS/public-host checks reduce accidental local-network access but need hardened connection-time SSRF defenses for untrusted multi-user deployment.
- Claim verification is not a full entailment checker; independent verifier/model separation is not yet integrated.
- No authentication or multi-user authorization layer is included.
- PDF parsing, voice, multimodal OCR, browser automation, and autonomous tool execution are not implemented.
- Cancellation is wired through asyncio task cancellation and capability boundaries, but true inference interruption depends on client/server disconnect behavior and needs live validation.
