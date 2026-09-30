# Current Limitations

- Inputs must yield structured tabular data. CSV and XLSX are the most direct formats. XLSX extraction uses the first non-empty worksheet; multiple worksheets are not combined.
- TXT extraction expects delimited lines with a header-like first row. DOCX extraction reads tables, not arbitrary prose. PDF extraction relies on embedded extractable text and delimiter-separated table-like lines; scanned/image PDFs and complex layouts are not OCR'd and may not parse.
- Upload size is configurable from 1 to 250 MB, with a default of 250 MB. Actual performance depends on available memory, storage, database, and request timeouts; large-file processing is synchronous in API requests.
- AI chat/report depend on Groq configuration and provider availability, rate limits, and timeouts. AI uses bounded summaries and selected exploration values, so it may not have every raw row or every chart point as evidence.
- Exploration response limits bound returned points (request `limit` maximum 200). High-cardinality fields and ambiguous inferred types can make a view less useful; detected roles are heuristics.
- The production frontend build currently emits a Vite warning because the analytics chart JavaScript chunk exceeds 500 kB before gzip. The build succeeds; further chart code splitting is a performance improvement area.
- Uploaded files are stored on the backend filesystem. Production requires durable private storage and operational backup/retention decisions; no cloud object-storage integration is configured.
- Reports are generated on demand and are not stored in a report-history service. No email/password-reset workflow is configured.
- The API health endpoint reports process availability but does not verify database or AI-provider readiness.
- Docker Compose is a local MySQL helper, not a complete production stack. No real deployment is included in this repository configuration.