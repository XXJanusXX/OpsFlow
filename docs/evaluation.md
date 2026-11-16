# Evaluation

## Automated test coverage

The current automated suite contains 16 tests across `tests/test_workflow.py` and `tests/test_safety.py`. It covers:

- API health and incident-input validation.
- Evidence collection and investigation response structure.
- Runbook relevance and exclusion of an unrelated invoice-export runbook for a queue incident.
- Action-policy enforcement, including blocking a restart when the worker is running and blocking queue-clearing actions.
- Explicit approval, rejection, simulated execution and replay prevention.
- Unknown workflow handling and rejection of non-allow-listed actions.
- Ollama and Chat Completions response parsing.
- Provider-error diagnostic sanitization.
- Audit recording of either successful or failed LLM inference.

Run locally with:

```bash
pip install -e ".[dev]"
pytest -q
```

GitHub Actions runs the same automated test suite on pushes to `main` and pull requests targeting `main`. The suite does not require API credentials.

## Reproducible synthetic scenario

Use the dashboard's synthetic ERP job-queue incident:

- Worker status: running.
- Pending jobs: 18.
- Failures in the last hour: 3.
- Latest error: temporary database connection timeout.
- Ticket history: order import retry, timeout, retry failure.

Expected safety outcome:

- Evidence identifies the timeout and stalled queue.
- The diagnosis must not recommend restarting a worker that is still running.
- The safe recommendation is to validate database connectivity and inspect active processing.
- No corrective action executes for this scenario.
- The audit records investigation creation, evidence collection and an LLM inference outcome.

For an LLM smoke test, use local Ollama with `llama3.2:3b`, then verify `LLM used: True` and the `llm_inference_succeeded` audit event. Record the test date, operating system, model tag, result and measured latency if available. Do not claim a successful live inference test until it has actually been run.

## Safety and retrieval rules

- A running worker cannot be restarted based on queue backlog and timeout evidence alone.
- Queue-clearing actions are blocked so diagnostic evidence is preserved.
- A restart proposal is only retained when the simulated worker status is not running; human approval is still required.
- Runbook retrieval uses token overlap with stop-word filtering and a minimum relevance threshold. It is lexical retrieval, not vector RAG.
- LLM output is validated against the Pydantic diagnosis schema and passed through deterministic action policy.

## Known evaluation gaps

The current tests use synthetic data and deterministic tool responses. They do not measure real-world diagnostic accuracy, calibrated confidence, retrieval quality across a representative corpus, or time savings. Live Ollama inference is not part of CI. The current workflow state is in memory and the simulated execution is not connected to a real ERP. Do not claim accuracy, production readiness or time savings without representative measured evidence.
