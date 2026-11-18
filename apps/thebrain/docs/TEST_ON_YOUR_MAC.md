# Run the Julian Phase 1 candidate on your Mac

This procedure configures the candidate to use an already existing app-owned runtime/model. It does not claim the runtime is relocatable or that Phase 1 is accepted. It does not install dependencies or change system settings.

1. Extract the ZIP into a writable folder or onto the intended USB drive.
2. Open Terminal and `cd` into the extracted `TheBrain_Julian_Phase1_Portable_Candidate` directory.
3. Run `bash scripts/configure_portable_runtime.sh`. It searches only known app-owned locations and the bundle for `my_python_env`, `llama-server`, and a GGUF model. It stops if it cannot verify all three.
4. Inspect `config/portable.env`; make sure paths and selected model are correct. It contains absolute paths if the assets are outside the USB bundle, so this config is suitable for testing on this Mac but is not yet a self-contained portable install.
5. Run `bash launcher/julian-portable.sh`.
6. Confirm `/api/health` returns `status: ok` and `model.status: reachable`. The launcher does not declare ready from an open port alone.
7. In the browser, test a normal chat, a request for current research with URLs and verbatim quotes, a file upload, chat history, settings/glossary, cancellation, and the audit trace. A failed source open must remain an explicit partial/failure rather than being replaced with a guess.
8. Stop with Ctrl+C. Only the two processes started by this launcher should be stopped.

If step 3 or 5 fails, preserve the complete terminal output and the relevant `logs/` files. Do not repair a stale micromamba environment or install packages until the exact failing interpreter and missing import are identified. The current environment is expected to have the required imports (`fastapi`, `uvicorn`, `httpx`, `pypdf`, and the other `requirements.txt` dependencies).

## Important limitations

- This candidate does not bundle the model or platform-specific runtime binaries.
- The helper supports a practical test run on a Mac when the required app-owned assets already exist. It does not establish USB portability across devices.
- The live web search provider can fail due to network, blocking, or page-format changes; the app should report this explicitly.
- Passing local unit tests does not prove inference or web research is live-verified.

## Live acceptance report

After the launcher has started Julian and the model and `/api/health` reports the model as reachable, run `bash scripts/live_acceptance.sh`. It sends a real prompt to the configured model, checks the capability registry, verifies the audit lifecycle and saved history, then exercises the live research path. The report is written to `logs/live-acceptance/report.json`. This script is intentionally strict: a reachable HTTP server alone is not considered a successful test. If the web provider or a source is unavailable, inspect the report and logs; a truthful failure is better than a fabricated answer, but it does not count as successful research acceptance.
