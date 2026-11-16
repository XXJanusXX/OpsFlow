import json
import logging
import re
import uuid
from copy import deepcopy

import httpx
from pydantic import ValidationError

from app.config import settings
from app.models import Diagnosis

logger = logging.getLogger(__name__)

# Synthetic data only; tools are read-only except the explicit simulator.
RUNBOOKS = [
    {
        "id": "RB-ERP-001",
        "title": "ERP job queue failures",
        "text": "Check service health, recent job errors and queue progress. Transient database timeouts can cause retries. Do not restart production services without approval. Capture queue state first.",
    },
    {
        "id": "RB-ERP-002",
        "title": "Controlled worker restart",
        "text": "Consider restart only when worker is unresponsive and evidence supports it. Check active processing, obtain approval, record reason. Rollback restores previous configuration and resumes monitoring.",
    },
    {
        "id": "RB-ERP-003",
        "title": "Invoice export backlog",
        "text": "Inspect pending and failed exports. Confirm downstream endpoint reachability before retry. Do not delete queue records; preserve evidence.",
    },
]

ERP = {
    "service": {
        "name": "ERP-Job-Worker",
        "status": "running",
        "last_heartbeat": "2026-11-16T08:55:00Z",
    },
    "job_queue": {
        "pending": 18,
        "failed_last_hour": 3,
        "last_error": "Temporary database connection timeout",
        "progressing": False,
    },
    "environment": "SYNTHETIC-DEMO",
}
TICKET = {
    "incident": "INC-DEMO-1001",
    "recent_updates": [
        "08:40Z order import entered retry",
        "08:47Z temporary database connection timeout",
        "08:52Z retry failed; queue pending",
    ],
}
STOP_WORDS = {
    "this", "that", "with", "from", "have", "been", "after", "into",
    "the", "and", "for", "are", "was", "were", "failed", "failure",
    "failing", "incident", "system", "latest",
}


def _tokens(text):
    return {
        token for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def retrieve(query):
    """Retrieve runbooks with a lightweight domain gate before lexical ranking.

    Queue/worker incidents should not pull in invoice-export procedures merely
    because both documents mention pending or failed work. Invoice/export
    procedures are eligible only when the incident itself mentions that domain.
    """
    query_terms = _tokens(query)
    invoice_export_terms = {"invoice", "export", "exports", "outbound"}
    queue_terms = {"queue", "worker", "job", "jobs", "order", "import", "timeout", "retry"}
    is_invoice_export = bool(query_terms & invoice_export_terms)
    is_queue_incident = bool(query_terms & queue_terms)

    ranked = []
    for document in RUNBOOKS:
        if document["id"] == "RB-ERP-003" and is_queue_incident and not is_invoice_export:
            continue
        document_terms = _tokens(document["title"] + " " + document["text"])
        score = len(query_terms & document_terms)
        if score >= 2:
            ranked.append((score, document["id"], document))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [document for _, _, document in ranked[:2]]


def erp_status():
    return deepcopy(ERP)


def ticket_history(incident_id):
    result = deepcopy(TICKET)
    result["requested_incident"] = incident_id
    return result


def fallback(erp, ticket):
    return {
        "summary": "ERP job queue is not progressing and recent failures are recorded.",
        "likely_cause": (
            "Temporary database connection timeout is the leading hypothesis; "
            "evidence does not prove a persistent database outage."
        ),
        "confidence": 0.72,
        "evidence": [
            {
                "source": "ERP service tool",
                "finding": f"Worker status: {erp['service']['status']}.",
            },
            {
                "source": "ERP queue tool",
                "finding": (
                    f"{erp['job_queue']['failed_last_hour']} failures; "
                    f"progressing={erp['job_queue']['progressing']}."
                ),
            },
            {
                "source": "ERP queue tool",
                "finding": f"Latest error: {erp['job_queue']['last_error']}.",
            },
            {
                "source": "Ticket tool",
                "finding": f"{len(ticket['recent_updates'])} recent updates retrieved.",
            },
        ],
        "recommended_action": (
            "Validate database connectivity and inspect active processing. "
            "The worker is running, so a restart is not justified by the available evidence."
            if erp["service"]["status"].lower() == "running"
            else "The worker is not running; verify the failure evidence and obtain approval before a controlled restart."
        ),
        "action_type": "restart_job" if erp["service"]["status"].lower() != "running" else "no_action",
        "risk": "medium" if erp["service"]["status"].lower() != "running" else "low",
        "rollback_plan": (
            "Restore previous worker configuration, resume monitoring and verify queue progress."
            if erp["service"]["status"].lower() != "running"
            else "No change has been made; preserve the queue and continue monitoring."
        ),
        "llm_used": False,
    }


def apply_action_policy(data, erp):
    """Fail closed when action prerequisites are not established by tool evidence."""
    action = data.get("action_type")
    worker_status = erp["service"]["status"].lower()
    if action == "restart_job" and worker_status == "running":
        data["action_type"] = "no_action"
        data["recommended_action"] = (
            "The worker is running. Validate database connectivity and inspect "
            "active processing before considering any restart."
        )
        data["risk"] = "low"
        data["rollback_plan"] = (
            "No change has been made; preserve queue records and continue monitoring."
        )
    elif action == "clear_test_queue":
        data["action_type"] = "no_action"
        data["recommended_action"] = (
            "Do not clear queue records. Preserve evidence and investigate "
            "the underlying failure before retrying."
        )
        data["risk"] = "low"
        data["rollback_plan"] = "No queue records were changed."
    return data


def _llm_content(payload, provider):
    """Extract generated text from Ollama or Chat Completions responses."""
    if provider == "ollama":
        return payload["response"]
    return payload["choices"][0]["message"]["content"]


def _log_llm_failure(exc):
    """Log useful failure metadata without logging credentials or request headers."""
    provider = settings.llm_provider
    model = settings.compatible_model if provider == "openai_compatible" else settings.ollama_model

    if isinstance(exc, httpx.HTTPStatusError):
        logger.warning(
            "LLM request rejected: provider=%s model=%s http_status=%s",
            provider, model, exc.response.status_code,
        )
    elif isinstance(exc, httpx.TimeoutException):
        logger.warning(
            "LLM request timed out: provider=%s model=%s timeout_seconds=%s",
            provider, model, settings.llm_timeout_seconds,
        )
    elif isinstance(exc, httpx.RequestError):
        logger.warning(
            "LLM transport failure: provider=%s model=%s error_type=%s",
            provider, model, type(exc).__name__,
        )
    elif isinstance(exc, ValidationError):
        logger.warning(
            "LLM response failed diagnosis schema validation: provider=%s model=%s",
            provider, model,
        )
    elif isinstance(exc, (KeyError, TypeError, json.JSONDecodeError)):
        logger.warning(
            "LLM response parsing failed: provider=%s model=%s error_type=%s",
            provider, model, type(exc).__name__,
        )
    else:
        # Do not include exception text: configuration errors can contain URLs
        # or other deployment-specific values.
        logger.warning(
            "LLM inference unavailable: provider=%s model=%s error_type=%s",
            provider, model, type(exc).__name__,
        )


def _generate_llm_response(prompt):
    provider = settings.llm_provider
    if provider == "openai_compatible":
        if not settings.compatible_base_url or not settings.compatible_model:
            raise ValueError("Hosted LLM URL and model must be configured")
        headers = {"Content-Type": "application/json"}
        if settings.compatible_api_key:
            headers["Authorization"] = f"Bearer {settings.compatible_api_key}"
        response = httpx.post(
            f"{settings.compatible_base_url}/chat/completions",
            headers=headers,
            json={
                "model": settings.compatible_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an evidence-grounded incident analyst. "
                            "Return only valid JSON matching the requested schema. "
                            "Never claim to execute actions."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=settings.llm_timeout_seconds,
        )
    elif provider == "ollama":
        response = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1},
            },
            timeout=settings.llm_timeout_seconds,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    response.raise_for_status()
    return json.loads(_llm_content(response.json(), provider))


def investigate(incident):
    investigation_id = str(uuid.uuid4())
    runbooks = retrieve(incident["title"] + " " + incident["description"])
    erp = erp_status()
    ticket = ticket_history(incident["incident_id"])
    prompt = f"""Use ONLY supplied evidence. Do not claim action execution.
If evidence is insufficient, choose no_action.
A restart is permitted only if the ERP worker status is not running and evidence supports it.
Never choose clear_test_queue; preserve queue records.
Return JSON keys summary, likely_cause, confidence (0..1), evidence array of {{source,finding}},
recommended_action, action_type (restart_job|clear_test_queue|no_action),
risk (low|medium|high), rollback_plan.
INCIDENT={json.dumps(incident)}
ERP_TOOL={json.dumps(erp)}
TICKET_TOOL={json.dumps(ticket)}
RUNBOOKS={json.dumps(runbooks)}"""
    try:
        data = _generate_llm_response(prompt)
        data["llm_used"] = True
        diagnosis = Diagnosis.model_validate(apply_action_policy(data, erp))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError) as exc:
        _log_llm_failure(exc)
        diagnosis = Diagnosis.model_validate(fallback(erp, ticket))

    approval_required = diagnosis.action_type != "no_action"
    return {
        "investigation_id": investigation_id,
        "incident_id": incident["incident_id"],
        "diagnosis": diagnosis,
        "retrieved_runbooks": [
            f"{book['id']}: {book['title']}" for book in runbooks
        ],
        "tool_results": {"erp_status": erp, "ticket_history": ticket},
        "approval_required": approval_required,
        "status": "awaiting_approval" if approval_required else "investigated",
    }


def execute_simulated(action, incident_id):
    if action not in {"restart_job", "clear_test_queue"}:
        return {"executed": False, "result": "Action not allow-listed"}
    return {
        "executed": True,
        "environment": "SYNTHETIC-DEMO",
        "action": action,
        "incident_id": incident_id,
        "result": f"Simulated {action} accepted; monitoring required.",
    }
