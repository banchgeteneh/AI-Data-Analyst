# Demonstration Guide

## Preparation

- Start MySQL, apply Alembic migrations, start the FastAPI backend and Vite frontend, and confirm `/api/v1/health` responds.
- Use a disposable account and a clean dataset with a header row, several columns of mixed numeric/categorical/date types, and enough rows to make aggregations meaningful. Avoid personal or confidential data.
- Configure a valid Groq API key if demonstrating AI; provider availability is external and should not be presented as guaranteed.

## Product Walkthrough

1. Open the application and register or log in.
2. Upload the representative dataset without tailoring it to a single domain.
3. Review the detected columns, types, dimensions, quality indicators, and summary statistics.
4. Show the adaptive dashboard and explain that available metrics/charts depend on detected data.
5. Review automatic insights and follow one of their suggested explorations.
6. Open exploration, select a recommendation, and adjust a dimension, measure, aggregation, visualization, or filter.
7. Explain the resulting visualization, summary, and any limits/top-N indication.
8. Ask AI a question answerable from the dataset context and identify evidence versus interpretation.
9. Ask a second question about the current exploration to demonstrate exploration-aware context.
10. Generate the AI report, review its structured sections, and download it.
11. Log out and note that the current client clears its browser token; the API has no token-revocation endpoint.

Use examples that reflect columns actually present. Emphasize that CSV, XLSX, and structured table extraction from TXT, DOCX, and PDF are supported, while extraction suitability varies by layout. Do not imply that the application has been deployed or that every file/document can be analyzed successfully.