import json
import re
import uuid
from copy import deepcopy

import httpx
from pydantic import ValidationError

from app.config import settings
from app.models import Diagnosis

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
    query_terms = _tokens(query)
    ranked = []
    for document in RUNBOOKS:
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
            "The worker is currently running, so a restart is not justified "
            "by the available evidence."
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
        response = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1},
            },
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        data = json.loads(response.json()["response"])
        data["llm_used"] = True
        diagnosis = Diagnosis.model_validate(apply_action_policy(data, erp))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError):
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
