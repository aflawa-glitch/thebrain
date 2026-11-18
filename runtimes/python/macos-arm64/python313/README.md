# TheBrain / Julian Handover Package

All handover documents are in English.

## Documents
1. `documents/01_PROJECT_HANDOFF.md`
2. `documents/02_MASTER_ROADMAP.md`
3. `documents/03_DETAILED_ROADMAP_CHECKLIST.md`
4. `documents/04_CURRENT_STATE_EVIDENCE_REGISTER.md`
5. `documents/05_DECISION_LOG_AND_CHANGE_CONTROL.md`

## Source snapshots
- `source/latest_qwen_llama_integration/`: latest available Qwen/llama.cpp and runtime integration source snapshot.
- `source/phase1_full_application_candidate/`: full UI/API Phase 1 candidate snapshot.

The two source snapshots are deliberately kept separate. They have not been represented as a reconciled, canonical merged branch. Review diffs before combining them.

## Verification boundary
The package records historical test evidence and current workspace artifacts separately. It does not claim successful Qwen inference on the user's Mac, native Windows/Linux validation, or Phase 1 acceptance.

## Important
No user GGUF model, private database, secrets, or platform-native runtime binaries are included.
