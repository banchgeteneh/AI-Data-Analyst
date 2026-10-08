# AI Data Analyst & Decision Assistant

## Overview

AI Data Analyst & Decision Assistant is a general-purpose web application for turning structured data files into profiles, summaries, visual explorations, and evidence-grounded AI explanations. It helps people inspect unfamiliar datasets without first writing analysis code or assuming a particular business domain. Users upload a file, review detected fields and data quality, explore dimensions and measures, and optionally ask the AI assistant for a contextual explanation or report.

The product separates the public landing page from the authenticated workspace. Dataset records and files are associated with their owning account.

## Key Features

### Authentication

- Account registration and email/password login.
- JWT bearer authentication for protected API operations.
- Logout clears the locally stored browser token; there is no server-side logout or token-revocation endpoint.
- Dataset reads, analysis, changes, and AI requests are scoped to the authenticated owner.

### Data Ingestion

- CSV, XLSX, TXT, DOCX, and PDF uploads.
- Server-side extension validation, generated storage names, and a configurable upload size limit.
- Tabular extraction and normalization before analysis. Document imports require extractable structured tables; see [limitations](docs/limitations.md).

### Automatic Analysis

- Dataset and column profiling, detected field roles, numeric and categorical summaries, correlations, missing values, duplicate rows, and data-quality indicators.
- Dashboard summaries, distributions, relationships, time trends, group comparisons, and automatic insights are derived from detected fields.

### Exploration

- Dataset-specific exploration capabilities and recommended analyses.
- Dimensions, measures, time fields, aggregation, sorting, top-N limits, and field/value/date filters.
- Adaptive bar, line, scatter, pie, and histogram visualizations, with summaries and limits included in responses.

### AI

- Groq-backed dataset chat and structured report generation.
- Optional context from the current exploration in chat.
- The server supplies bounded analysis summaries rather than unlimited raw rows.
- The report response is displayed and can be downloaded from the frontend; reports are generated on demand and not retained in a report-history store.

### Security

- Password hashing, JWT validation, owner-scoped dataset access, upload validation, size limits, and safe provider error responses.
- Backend-only secrets and private upload storage.
- See [SECURITY.md](SECURITY.md) and [AI design notes](docs/ai.md).

## Technology Stack

- Frontend: React, Vite, React Router, Axios, Apache ECharts, `echarts-for-react`, and `react-markdown`.
- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn, and PyMySQL.
- Analysis and ingestion: Pandas, NumPy (available in the analysis stack), openpyxl, python-docx, and pypdf.
- Database: MySQL.
- AI: Groq API and the server-side `groq` Python client.
- Authentication: bcrypt password hashes and JWT access tokens.

## Architecture

The React client calls a versioned FastAPI API. The API authenticates requests, enforces ownership, and coordinates dataset storage, extraction, analysis, exploration, and AI. MySQL stores user and dataset metadata; uploaded content is stored on the backend filesystem. See [architecture and data flow](docs/architecture.md), [API reference](docs/api.md), and [AI architecture](docs/ai.md).

## Prerequisites

- Python 3.13 or a compatible supported Python version.
- Node.js 20.19+ or 22.12+ and npm (Vite 7 requirement).
- MySQL 8.x. Docker Compose can optionally provide a local MySQL 8.4 service.
- Git.
- A Groq API key for live AI chat and report generation. Upload, analysis, and exploration do not require a working Groq connection.

## Local Development

Commands below use PowerShell and assume the terminal starts in the `AI-Data-Analyst` project directory.

1. Configure environment values. The backend reads `backend/.env` or the project-root `.env`; copy the template to the root and replace placeholders for your local database and JWT secret:

	```powershell
	Copy-Item .env.example .env
	```

	To use the optional local database container, set non-default `MYSQL_*` values and run `docker compose up -d mysql`. The Compose file starts MySQL only; it does not start or migrate the API or frontend.

2. Install backend dependencies, apply the database migrations, and run the API:

	```powershell
	Set-Location backend
	py -m venv .venv
	.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
	.\.venv\Scripts\python.exe -m alembic upgrade head
	.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
	```

	Ensure MySQL is running and `DATABASE_URL` points to it before applying migrations. The API loads backend settings from `backend/.env` or the project-root `.env`.

3. In a second terminal, configure and run the frontend:

	```powershell
	Set-Location frontend
	Copy-Item .env.example .env
	npm install
	npm run dev
	```

	The frontend's `VITE_API_BASE_URL` defaults to `http://localhost:8000/api/v1` in the supplied frontend template. Local API health is at `http://localhost:8000/api/v1/health`; interactive OpenAPI documentation is at `http://localhost:8000/docs`.

Environment variable descriptions and production requirements are in [.env.example](.env.example) and [deployment guide](docs/deployment.md). Never place backend secrets in frontend environment variables.

## Database and Migrations

MySQL is the configured database. Alembic migrations are under `backend/migrations/versions`; `alembic upgrade head` creates or updates the schema using `DATABASE_URL`. See [deployment guide](docs/deployment.md) for the migration workflow and production sequencing.

## Tests and Build

From `backend/`, run `python -m pytest -q`, `python -m compileall app tests`, and `python -m pip check` using the project virtual environment. From `frontend/`, run `npm run build`. Focused commands and current test coverage are listed in [docs/testing.md](docs/testing.md).

## Demonstration

See the [demo guide](docs/demo-guide.md) for a workflow using an unfamiliar, representative tabular dataset. The product is dataset-driven and is not limited to the example fields shown on the public landing page.

## Limitations and Future Work

Current constraints are documented in [docs/limitations.md](docs/limitations.md). Potential enhancements, explicitly separate from implemented functionality, are listed in [docs/future-work.md](docs/future-work.md).

## Project Structure

```text
AI-Data-Analyst/
|-- backend/       FastAPI application, services, migrations, and tests
|-- frontend/      React/Vite application and build configuration
|-- docs/          Architecture, API, AI, deployment, and project guides
|-- .env.example   Placeholder backend and local Compose settings
|-- docker-compose.yml  Optional local MySQL service
|-- CONTRIBUTING.md
|-- SECURITY.md
|-- CHANGELOG.md
└-- README.md
```

More detail is in [docs/architecture.md](docs/architecture.md).