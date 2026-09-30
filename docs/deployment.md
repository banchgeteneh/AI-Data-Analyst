# Deployment Guide

## Suggested Topology

```text
Browser -> HTTPS static frontend or reverse proxy
        -> HTTPS FastAPI service
FastAPI -> production MySQL
        -> private persistent upload storage
        -> Groq API (AI features only)
```

This is a deployment design, not a claim that the project is deployed. The supplied Compose file runs only local MySQL. The backend Dockerfile builds the API image but does not provision MySQL, persistent file storage, or automatically apply migrations.

## Development and Production

Development uses Vite, FastAPI reload mode, local MySQL/optional Compose MySQL, and local private upload storage. Production should use HTTPS, an explicit frontend origin, `APP_ENV=production`, `DEBUG=false`, a managed/production MySQL service, private durable upload storage, and a production ASGI process manager/reverse proxy appropriate to the host. Do not use development passwords, reload mode, wildcard CORS, or a publicly served upload directory.

## Configuration

Backend settings are loaded from `backend/.env` or the project-root `.env`. Use the actual names in `.env.example`:

- `APP_ENV`, `DEBUG`, `BACKEND_HOST`, `BACKEND_PORT`.
- `DATABASE_URL` for the SQLAlchemy connection. `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_ROOT_PASSWORD` are used by the optional Compose database service.
- `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`.
- `FRONTEND_URL`, `FRONTEND_ORIGINS` (comma-separated explicit origins).
- `GROQ_API_KEY`, `GROQ_MODEL`.
- `MAX_DATASET_SIZE_MB` (bounded in settings to 1-250 MB), `UPLOAD_DIRECTORY`.

The frontend reads `VITE_API_BASE_URL` at build time. It must point to the public API base path, normally `https://<api-host>/api/v1`, or use a same-origin proxy path. Only public configuration belongs in the frontend environment; never put database credentials, JWT secrets, or Groq keys into `VITE_*` values.

Production settings validation rejects debug mode, short/default JWT secrets, placeholder database credentials, wildcard origins, and non-HTTPS/local frontend origins. Configure a unique random JWT secret of at least 32 characters and exact HTTPS CORS origins. The frontend origin and CORS allow-list must agree.

## Database and Migrations

Provision MySQL and a dedicated database/user, then configure `DATABASE_URL`. On a fresh database, from `backend/` and with the backend environment active, run:

```powershell
python -m alembic upgrade head
```

Run migrations as a controlled deployment step before serving code that depends on the new schema. Review new migration scripts before applying them. Migration configuration takes its URL from application settings.

## Files and Secrets

Set `UPLOAD_DIRECTORY` to private durable storage accessible by the API process. Back it up and monitor capacity according to operational needs. Dataset deletion removes the stored file. Do not mount or serve this directory as public frontend content. Secure backups and restrict filesystem permissions.

Provide secrets through the hosting platform's secret/environment mechanism. `.env.example` is a template only. Rotate any credential that may have been exposed; ignoring an env file does not remove a secret from repository history.

## Build and Runtime

Build the frontend in `frontend/` with `npm run build`, then serve the generated `dist/` directory from static hosting or a web server with SPA route fallback. Build with the production `VITE_API_BASE_URL` configured. Build/run the backend using `backend/Dockerfile` or an equivalent Python 3.13 environment; install `requirements.txt` and serve `app.main:app` with an appropriate production ASGI setup. Terminate TLS at the host or reverse proxy. Apply migrations separately.

The API startup logs a warning if the database is unavailable and still starts, but database-backed functionality will fail. Include database connectivity in deployment health monitoring; `/api/v1/health` only indicates that the API process responds, not that dependencies are healthy.

## Docker Status

`docker compose up -d mysql` is an optional local database workflow. It publishes MySQL on host port 3306 and contains placeholder fallback passwords; replace them for local use and do not use this Compose configuration as a production deployment. `backend/Dockerfile` packages the backend only. No production frontend, API, migration job, or durable storage orchestration is configured in Compose.