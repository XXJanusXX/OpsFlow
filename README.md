# OpsFlow AI

Evidence-grounded incident investigation with human-approved simulated actions.

Workflow: incident intake → runbook retrieval → read-only ERP/ticket tools → Ollama structured diagnosis → human approval → allow-listed simulated action → SQLite audit.

## Safety boundary
Synthetic portfolio data only. No real ERP, ticketing or production connection. The LLM cannot execute actions; API code enforces approval and an action allow-list.

## Setup
Python 3.11+ and Ollama.
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
ollama pull llama3.2:3b
```
Start Ollama with `ollama serve`. In separate terminals run `uvicorn app.main:app --reload` and `streamlit run frontend/dashboard.py`. API docs: http://localhost:8000/docs. Tests: `pytest -q`.

## Limitations
Active workflow state is in memory; retrieval is lexical rather than vector RAG; ERP/ticket data are synthetic; execution is simulated. Authentication, approver identity verification, tenant isolation, durable orchestration and production hardening are not implemented. This is a portfolio MVP, not production-ready software.
