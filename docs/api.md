# API Reference

Base path: `/api/v1`. FastAPI's generated OpenAPI UI is available at `/docs` when the API is running. Unless marked public, endpoints require `Authorization: Bearer <access_token>`. Responses are JSON except successful dataset deletion (`204 No Content`). Request and response models in `backend/app/schemas/` are authoritative.

Common errors include `401` for invalid/missing authentication, `404` for unknown or non-owned datasets, `422` for invalid request or unprocessable dataset content, and `500` for unexpected server failures. Upload can return `400` for missing/unsupported files and `413` for files exceeding the configured limit. AI operations may return `429`, `502`, `503`, or `504` for provider/configuration conditions.

## Authentication

| Method | Path | Auth | Purpose and key fields |
|---|---|---|---|
| POST | `/auth/register` | Public | Body: `name`, `email`, `password` (8-72 characters). Returns `message` and `user`; duplicate email returns `409`. |
| POST | `/auth/login` | Public | Body: `email`, `password`. Returns `access_token`, `token_type`, and `user`; invalid credentials return `401`. |
| GET | `/auth/me` | Required | Returns the current `user`. |

There is no server-side logout endpoint; the frontend clears its stored token.

## Datasets and Analysis

| Method | Path | Auth | Purpose and response |
|---|---|---|---|
| POST | `/datasets/upload` | Required | Multipart form field `file`; returns dataset metadata (`id`, `original_filename`, `file_type`, `file_size`, `created_at`). |
| GET | `/datasets` | Required | Returns the current user's dataset metadata array. |
| DELETE | `/datasets/{dataset_id}` | Required | Deletes the owned dataset metadata and stored upload; returns `204`. |
| GET | `/datasets/{dataset_id}/analysis` | Required | Returns analysis including dataset summary, column profiles, statistics, relationships, quality, dashboard data, and automatic insights. |
| GET | `/datasets/{dataset_id}/insights` | Required | Returns an array of automatic insight objects. |

Analysis and insights may return `404` if the dataset or file is unavailable and `422` when extraction or analysis cannot process the content.

## Exploration

| Method | Path | Auth | Purpose and key fields |
|---|---|---|---|
| GET | `/datasets/{dataset_id}/explore/capabilities` | Required | Returns detected `dimensions`, `measures`, `time_fields`, `filter_fields`, `relationships`, and `recommended_explorations`. |
| POST | `/datasets/{dataset_id}/explore` | Required | Body may include `exploration_type`, `dimension`, `measure`, `secondary_measure`, `aggregation`, `x_field`, `y_field`, `date_field`, date bounds, `filters`, `sort`, `limit` (1-200), and `visualization`. Returns summary, points, chart configuration, capabilities, and limit/empty-state details. |

Filters support equality/membership, numeric bounds, date comparisons, and boolean checks. Invalid fields, values, or unsupported analysis combinations return `422`.

## AI Chat and Report

| Method | Path | Auth | Purpose and key fields |
|---|---|---|---|
| POST | `/datasets/{dataset_id}/ai/chat` | Required | Body: `message` (1-4000 chars), optional `history` (up to 10 user/assistant turns, each up to 2000 chars), optional `exploration_context`. Returns `answer` and `dataset_id`. |
| POST | `/datasets/{dataset_id}/ai/report` | Required | No request body. Returns validated report fields (`title`, `executive_summary`, `key_findings`, `data_quality`, `trends`, `business_insights`, `recommendations`, `conclusion`) plus dataset metadata and generation timestamp. |

AI-specific errors may include `429` (provider rate limit), `502` (unexpected provider failure), `503` (configuration/unavailable provider), and `504` (timeout). A simple conversational greeting may receive a local response without a provider call.

## Health

| Method | Path | Auth | Purpose and response |
|---|---|---|---|
| GET | `/health` | Public | Returns `{"status":"ok","service":"AI Data Analyst API"}`. This process health response does not guarantee database or Groq availability. |