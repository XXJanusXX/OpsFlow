# Portfolio Demo Script

Target length: 3–4 minutes. Use synthetic incident data only. Do not show API keys, private environment variables, customer records or production systems.

## Before recording

- Start Ollama and confirm the configured model is available with `ollama list`.
- Start the FastAPI backend and Streamlit dashboard locally.
- Confirm the dashboard points to the local backend using `OPSFLOW_API_URL=http://127.0.0.1:8000`.
- Run `pytest -q` and confirm the automated suite passes.
- If live Ollama inference has not been verified, show the fallback honestly and describe live inference as pending; do not present fallback output as an LLM response.

## Suggested walkthrough

### 1. Problem and goal (20–30 seconds)

"OpsFlow is a portfolio MVP for evidence-grounded incident investigation. It demonstrates how an agent can collect information from tools, retrieve runbooks, produce a structured diagnosis and keep corrective actions behind human approval."

### 2. Architecture (30–40 seconds)

Show the architecture diagram in the README.

Explain the Streamlit interface, FastAPI orchestration layer, synthetic ERP and ticket tools, lexical runbook retrieval, configurable LLM provider, Pydantic validation, action policy and SQLite audit log. Mention that Ollama runs locally; OpenAI and Gemini are optional hosted Chat Completions-compatible providers.

### 3. Investigate a synthetic incident (45–60 seconds)

Submit the synthetic ERP queue incident. Point out the worker status, pending jobs, recent failures, latest timeout and ticket timeline. Show the retrieved runbook and explain how the evidence informs the diagnosis.

### 4. Explain the safety boundary (30–45 seconds)

Show that the worker is running and the recommended action is to validate database connectivity and inspect active processing rather than restart it. Explain that the policy blocks unjustified restarts, queue-clearing actions are disallowed, and any proposed action requires approval. All execution in this project is simulated.

### 5. Show auditability and tests (30–45 seconds)

Open the investigation audit and point out the investigation, evidence and LLM inference outcome events. Show the GitHub Actions CI result and the evaluation documentation.

### 6. Close with limitations (15–20 seconds)

"OpsFlow currently uses synthetic ERP/ticket data, lexical runbook retrieval and simulated actions. It is a portfolio MVP, not a production incident-management integration. The next engineering steps are representative evaluation, durable workflow state, authentication and secure real-system integrations."

## Claims checklist

Only claim what the recording demonstrates:

- Say "LLM-generated diagnosis" only if the dashboard shows successful inference and the audit contains `llm_inference_succeeded`.
- Otherwise say "deterministic fallback diagnosis".
- Say "automated tests pass" only after running the current test suite or verifying the latest CI run is successful.
- Do not claim production integration, autonomous remediation, measured accuracy or time savings.
