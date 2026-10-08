# AI Architecture

## Provider Integration

AI chat and report generation are implemented in `backend/app/services/ai.py` and called through the dataset AI routes. The backend uses the Groq Python client with `GROQ_API_KEY` and `GROQ_MODEL`; the key is not sent to the browser. If the key is missing or the provider is unavailable, the API returns an appropriate service error rather than claiming a generated result.

Provider rate limits, timeouts, unavailable responses, and unexpected provider errors are mapped to safe HTTP errors. Provider exception details are handled server-side and are not intentionally returned as raw exception content to the user. The application does not substitute canned analysis for failed provider output.

## Chat and Exploration Context

Chat is requested with a message, up to ten validated history turns, and optional exploration context. The service constructs a compact JSON context from analysis metadata, selected summary statistics, quality indicators, correlations, and limited distribution/trend values. It bounds the number and length of included items. Current exploration context is reduced to selected fields, at most twelve points, up to ten filters, and a limited number of series/limitations.

The system instruction tells the model to answer using supplied context, treat dataset values as data rather than instructions, avoid inventing evidence, distinguish correlation from causation, and describe limitations. This is a prompt-level instruction and data-minimization approach, not a claim that arbitrary adversarial input can be perfectly detected or neutralized.

The app does not intentionally send the complete raw dataset to the provider as chat context. Analysis itself may read the uploaded file on the backend. Protect dataset files and configure provider/data handling according to the deployment's privacy requirements.

## Reports and Validation

The report endpoint sends the bounded analysis context and requests a JSON object with fixed report fields. Pydantic validates the returned report structure, required strings, and non-empty lists before an API response is constructed. The report is generated on demand; it is not persisted as a server-side report history. The frontend renders and offers the response for download.

## Limits and Privacy

Context limits are implementation bounds, not a promise that every dataset attribute or every exploration result reaches the model. The provider remains an external service dependency. Do not include secrets or confidential data in dataset contents unless organizational policy permits processing through the configured Groq account. See [deployment guidance](deployment.md) and [limitations](limitations.md).