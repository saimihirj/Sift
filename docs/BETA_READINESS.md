# Beta Readiness Checklist

This checklist is for running Sift with early users before investing in managed production infrastructure.

## Ready Now

- Keep the app framed as a beta during user testing.
- Run with `npm run mvp:api` for hosted model testing or `npm run mvp` for local Ollama testing.
- Use the built-in upload limits for files: PDF, PPTX, DOCX, and TXT up to 20MB.
- Use `Evaluate` for idea scoring and deck review.
- Use `Expert` for concept explanation and pre-screening.
- Export reports as Markdown from the report page.
- Give each tester their own email/handle plus Sift key; the same pair is required to resume that tester's sessions.
- Collect tester feedback manually using the copied beta feedback note from the landing screen.

## Before Inviting Testers

- Confirm the selected model provider is configured and reachable.
- Try one idea review, one deck review, and one Expert question.
- Upload a small PDF or PPTX deck and confirm the report page opens.
- Confirm `/api/health` returns `status: ok`.
- Keep `SIFT_ADMIN_MODE=false` unless intentionally reviewing local admin analytics.
- If admin mode is enabled, set `SIFT_ADMIN_TOKEN`.

## Current Beta Guardrails

- Uploads are limited by type, size, and count per session.
- API routes have a lightweight local rate limit.
- Sessions are scoped by a beta Sift key instead of full authentication.
- Website context is single-page only.
- PPTX deck review uses extracted slide text; visual feedback is unverified unless a renderable PDF and vision model are used.
- Local session data and uploads live under `data/`.

## Later Production Work

These are intentionally outside the no-cost beta pass:

- Managed database
- Managed object storage
- Production authentication
- Custom domain
- Payment and billing
- Full observability stack
- Formal security audit
