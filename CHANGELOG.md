# Changelog

## v0.2.0 - 2026-03-06

Adaptive evaluator release for `Signal`.

### Added

- Evaluator mode alongside the existing mentor chat flow.
- Bounded adaptive assessments with `10`, `15`, or `20` question budgets.
- Hybrid answer scoring across comprehension, logic, evidence, quantification, and clarity.
- Final evaluator report with success score, why the score landed there, and concrete fixes.
- Session-scoped provider, model, and API-key support for local and external inference providers.
- Single-page website ingestion as an evaluator input source.
- Evaluator-specific admin metrics for starts, completions, scores, provider mix, and fetch failures.

### Kept intact

- Existing mentor chat flow and session resume behavior.
- Local-first Ollama runtime as the default open-source path.
- Outline route, admin dashboard, and one-command local launcher.

## v0.1.0 - 2026-03-06

Initial private MVP snapshot of `Signal`.

### Included

- React + FastAPI app shell replacing the Gradio-first prototype as the primary user experience.
- Local-first chat workflow with Ollama-backed model routing and streamed responses.
- Compact onboarding flow, landing screen, session history, resume flow, and exit session controls.
- Separate outline route for transcript-to-outline generation.
- Admin dashboard for usage and latency monitoring.
- Monochrome responsive UI for desktop, tablet, and mobile.
- Local launcher with `signal_app.py`, plus `vk.py` kept as a compatibility wrapper.
- Architecture, execution, and platform overview docs in `docs/`.

### Runtime defaults

- Provider: `ollama`
- Speed profile: `llama3.2:latest`
- Balanced profile: `qwen3:4b`

### Known constraints

- Local MVP mode stores state in SQLite and local disk.
- Google and Apple sign-in are not wired yet.
- GitHub deployment automation is not part of this snapshot.
