# Contributing

## Workflow

- Work on a focused branch and keep changes scoped to one behavior or documentation topic.
- Follow the existing Python and React conventions; avoid unrelated refactors and generated-file changes.
- Update or add tests for changed backend behavior. Run relevant tests, the backend test suite when practical, and `npm run build` for frontend changes.
- Keep API contracts and migrations deliberate. Review generated migrations before applying them.

## Security

- Never commit `.env` files, real credentials, tokens, or private datasets. Use `.env.example` placeholders and keep provider keys server-side.
- Validate uploads and user-controlled input on the server. Preserve dataset ownership checks and avoid exposing filesystem paths or provider errors.
- Report suspected vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Pull Requests

Describe the behavior/documentation change, note any migration or configuration impact, and include the checks run and any unverified manual scenarios. Keep screenshots or sample data free of secrets and personal information.