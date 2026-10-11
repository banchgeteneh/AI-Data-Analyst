# Deployment Guide

## Suggested Topology

```text
Browser -> HTTPS static frontend or reverse proxy
        -> HTTPS FastAPI service
FastAPI -> production Supabase PostgreSQL
        -> private persistent upload storage
        -> Groq API (AI features only)
```

This is a deployment design, not a claim that the project is deployed. The supplied Compose file runs only local MySQL. The backend Dockerfile builds the API image but does not provision MySQL, persistent file storage, or automatically apply migrations.

## Development and Production

Development uses Vite, FastAPI reload mode, local MySQL/optional Compose MySQL, and local private upload storage. Production uses HTTPS, an explicit frontend origin, `APP_ENV=production`, `DEBUG=false`, Supabase PostgreSQL, private durable upload storage, and the host's production ASGI process. Do not use development passwords, reload mode, wildcard CORS, or a publicly served upload directory.

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

The production API explicitly allows `https://ai-data-analyst-phi.vercel.app` in addition to the origins configured with `FRONTEND_URL` and `FRONTEND_ORIGINS`. CORS credentials remain enabled only for these explicit origins.

## Database and Migrations

Local development can use MySQL through `mysql+pymysql://...`; production must set `DATABASE_URL` to the Supabase PostgreSQL session-pooler URL. The application normalizes `postgresql://` and `postgres://` URLs to the installed psycopg 3 driver without changing the supplied pooler username. Keep special characters in the password URL-encoded. Production configuration rejects a MySQL URL so a missing production variable cannot silently use the local fallback.

On a fresh database, from `backend/` and with the backend environment active, run:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

The chain creates `users`, then `datasets`, then replaces the email unique index with a named unique constraint. Run migrations as a controlled deployment step before serving code that depends on the schema; do not run them in application startup or per worker. The local MySQL database is migrated forward in place and its existing records are not dropped or copied to production.

## Render Web Service

Set the Render service **Root Directory** to `backend`. `alembic upgrade head` must run against the same Render `DATABASE_URL` as the API, and a failed migration must prevent the new API process from starting.

If the current Render service plan supports a pre-deploy command, configure:

| Render field | Command |
| --- | --- |
| Build Command | `pip install -r requirements.txt` |
| Pre-Deploy Command | `alembic upgrade head` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

Render does not expose the current service plan in this repository, so verify that pre-deploy commands are supported before selecting this option. Otherwise set the Start Command to `sh start.sh`. That script runs `alembic upgrade head` first and starts Uvicorn only if the migration succeeds. It is also the backend Docker image's default command. The direct Uvicorn start command is appropriate only when the pre-deploy migration is configured.

Set the Render environment variables `APP_ENV=production`, `DEBUG=false`, `DATABASE_URL` (the Supabase session-pooler connection URL), a unique `JWT_SECRET_KEY` of at least 32 characters, and the frontend origin settings. Retain the pooler's exact username from Supabase. For the connection URL, select the **Session pooler** option in Supabase's Connect panel. Never place this URL in frontend variables, commit it, or include it in logs.

Before redeploying, confirm the Render `DATABASE_URL` points to the intended PostgreSQL database and run the migration once using the chosen pre-deploy or startup path. Do not use `alembic stamp` to conceal missing schema changes. After deployment, check the deploy logs for the successful Alembic upgrade and verify the API's database-backed endpoints.

## Files and Secrets

Set `UPLOAD_DIRECTORY` to private durable storage accessible by the API process. Back it up and monitor capacity according to operational needs. Dataset deletion removes the stored file. Do not mount or serve this directory as public frontend content. Secure backups and restrict filesystem permissions.

Provide secrets through the hosting platform's secret/environment mechanism. `.env.example` is a template only. Rotate any credential that may have been exposed; ignoring an env file does not remove a secret from repository history.

## Build and Runtime

Build the frontend in `frontend/` with `npm run build`, then serve the generated `dist/` directory from static hosting or a web server with SPA route fallback. Build with the production `VITE_API_BASE_URL` configured. Build/run the backend using `backend/Dockerfile` or an equivalent Python 3.13 environment; install `requirements.txt` and configure the Render migration/start commands above. Terminate TLS at the host or reverse proxy.

The API starts if the database is unavailable so the process health endpoint can respond, but database-backed requests return a controlled error. Startup diagnostics log only the error class, not the connection URL or driver error details. `/api/v1/health` indicates that the API process responds, not that the database is healthy.

## Docker Status

`docker compose up -d mysql` is an optional local database workflow. It publishes MySQL on host port 3306 and contains placeholder fallback passwords; replace them for local use and do not use this Compose configuration as a production deployment. `backend/Dockerfile` packages the backend only. No production frontend, API, migration job, or durable storage orchestration is configured in Compose.