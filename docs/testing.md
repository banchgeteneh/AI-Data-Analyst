# Testing and Verification

## Automated Checks

Run commands from the indicated project directory with the backend virtual environment active (or call its Python executable directly):

```powershell
Set-Location backend
python -m pytest -q
python -m pytest tests/api/test_auth.py -q
python -m pytest tests/api/test_datasets.py -q
python -m pytest tests/api/test_analysis.py tests/api/test_ai.py -q
python -m compileall app tests
python -m pip check
```

Build the frontend from `frontend/`:

```powershell
npm run build
```

## Coverage Areas

The current backend suite includes authentication, dataset endpoints, analysis, AI behavior, CORS, health, configuration, dashboard data, exploration recommendations, and CSV/XLSX/TXT/DOCX/PDF extractor cases. Test AI provider behavior with mocks; a passing automated suite does not prove live Groq availability. The frontend currently exposes a Vite production build check; no separate frontend unit-test script is defined in `package.json`.

## Regression and Security Review

For releases, include checks that missing/invalid tokens are rejected, one account cannot access another account's dataset, unsupported or oversized uploads fail safely, malformed input returns a controlled error, and provider errors do not disclose secrets or raw exception details. Confirm production config rejects unsafe debug, JWT, database, and CORS settings. Avoid using real credentials or sensitive production data in test fixtures.

## Manual Verification

Use a disposable account and a representative unfamiliar tabular dataset. Confirm registration/login, upload, dataset list, analysis/dashboard, insights, exploration changes and filters, chat with and without current exploration context, report generation/download, logout behavior, light/dark theme, empty/error/loading states, and mobile layout. Verify the health endpoint separately from database-dependent routes. See [demo guide](demo-guide.md).

Record results with the runtime versions and environment used. Automated checks do not replace end-to-end verification against a live database or Groq provider.