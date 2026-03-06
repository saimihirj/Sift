# Changelog

## v0.1.0 - 2026-03-06

Initial private MVP snapshot of `Vishwakarma (VK)`.

### Included

- React + FastAPI app shell replacing the Gradio-first prototype as the primary user experience.
- Local-first chat workflow with Ollama-backed model routing and streamed responses.
- Compact onboarding flow, landing screen, session history, resume flow, and exit session controls.
- Separate outline route for transcript-to-outline generation.
- Admin dashboard for usage and latency monitoring.
- Monochrome responsive UI for desktop, tablet, and mobile.
- Local launcher via `vk.py` for one-command MVP startup.
- Architecture, execution, and platform overview docs in `docs/`.

### Runtime defaults

- Provider: `ollama`
- Speed profile: `llama3.2:latest`
- Balanced profile: `qwen3:4b`

### Known constraints

- Local MVP mode stores state in SQLite and local disk.
- Google and Apple sign-in are not wired yet.
- GitHub deployment automation is not part of this snapshot.
