# Security Policy

## Supported Practices

The application uses bcrypt password hashing, signed JWT access tokens, protected API dependencies, owner-scoped dataset queries, server-side upload extension and size checks, generated storage filenames, and safe AI provider error responses. Production settings validate debug mode, JWT secret strength, database placeholder values, and explicit HTTPS frontend origins.

These controls do not replace deployment-level TLS, least-privilege database accounts, filesystem isolation, dependency updates, backups, and monitoring.

## Secret and Data Handling

- Keep `.env` files, database credentials, JWT secrets, and Groq API keys out of source control and frontend build variables.
- Use secret management provided by the deployment platform. Rotate credentials if exposure is suspected; `.gitignore` does not erase Git history.
- Store uploads in a private directory with restricted access. Do not expose upload storage as static content.
- Treat uploaded data as sensitive. AI requests send a bounded analytical context to Groq; follow organizational data handling requirements before using confidential datasets.

## Reporting a Vulnerability

Do not disclose suspected vulnerabilities, secrets, or exploit details in public issues. Contact the project maintainers through a private channel with a concise description, impact, and reproducible steps. Allow time for assessment and remediation before public disclosure. No formal bug bounty or guaranteed response SLA is currently specified.