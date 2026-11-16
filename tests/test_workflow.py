from fastapi.testclient import TestClient

from app.agent import ERP
from app.main import app, WORKFLOWS

client = TestClient(app)


def setup_function():
    WORKFLOWS.clear()
    ERP["service"]["status"] = "running"


def payload():
    return {
        "incident_id": "INC-TEST-001",
        "title": "ERP order processing job is failing",
        "description": "Order import failed after a database connection timeout.",
        "severity": "P2",
        "system": "ERP",
    }


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["environment"] == "SYNTHETIC-DEMO"


def test_investigation_has_evidence_and_no_unsafe_action():
    response = client.post("/investigate", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["diagnosis"]["evidence"]
    assert body["diagnosis"]["action_type"] == "no_action"
    assert body["approval_required"] is False
    assert body["status"] == "investigated"
    assert [item.split(":")[0] for item in body["retrieved_runbooks"]] == ["RB-ERP-001"]


def test_running_worker_cannot_be_restarted():
    from app.agent import apply_action_policy

    proposed = {
        "action_type": "restart_job",
        "recommended_action": "Restart the worker.",
        "risk": "medium",
        "rollback_plan": "Restore configuration.",
    }
    safe = apply_action_policy(proposed, {"service": {"status": "running"}})
    assert safe["action_type"] == "no_action"
    assert "worker is running" in safe["recommended_action"]


def test_stopped_worker_can_have_restart_proposal():
    from app.agent import apply_action_policy

    proposed = {
        "action_type": "restart_job",
        "recommended_action": "Restart the worker.",
        "risk": "medium",
        "rollback_plan": "Restore configuration.",
    }
    safe = apply_action_policy(proposed, {"service": {"status": "stopped"}})
    assert safe["action_type"] == "restart_job"


def test_execution_requires_approval():
    from app.main import execute

    result = client.post("/investigate", json=payload()).json()
    assert result["approval_required"] is False
    assert client.post(f"/execute/{result['investigation_id']}").status_code == 403


def test_rejection_blocks_execution():
    ERP["service"]["status"] = "stopped"
    result = client.post("/investigate", json=payload()).json()
    investigation_id = result["investigation_id"]
    assert result["approval_required"] is True
    client.post(
        f"/approvals/{investigation_id}",
        json={"approved_by": "Reviewer", "approved": False, "comment": "Rejected"},
    )
    assert client.post(f"/execute/{investigation_id}").status_code == 403


def test_approved_execution_is_simulated():
    ERP["service"]["status"] = "stopped"
    result = client.post("/investigate", json=payload()).json()
    investigation_id = result["investigation_id"]
    approval = client.post(
        f"/approvals/{investigation_id}",
        json={
            "approved_by": "Reviewer",
            "approved": True,
            "comment": "Demo approval",
        },
    )
    assert approval.status_code == 200
    execution = client.post(f"/execute/{investigation_id}")
    assert execution.status_code == 200
    assert "Simulated" in execution.json()["message"]


def test_unknown_workflow():
    assert client.post("/execute/unknown-id").status_code == 404



def test_queue_incident_excludes_invoice_export_runbook():
    from app.agent import retrieve

    books = retrieve(
        "ERP order processing job queue worker retry after database timeout"
    )
    ids = [book["id"] for book in books]
    assert "RB-ERP-001" in ids
    assert "RB-ERP-003" not in ids


def test_invoice_export_incident_can_retrieve_export_runbook():
    from app.agent import retrieve

    books = retrieve("Invoice export backlog failed outbound export retries")
    ids = [book["id"] for book in books]
    assert "RB-ERP-003" in ids


def test_llm_response_parser_supports_ollama():
    from app.agent import _llm_content

    assert _llm_content({"response": '{"confidence": 0.8}'}, "ollama") == (
        '{"confidence": 0.8}'
    )


def test_llm_response_parser_supports_chat_completions():
    from app.agent import _llm_content

    payload = {"choices": [{"message": {"content": '{"confidence": 0.8}'}}]}
    assert _llm_content(payload, "openai_compatible") == '{"confidence": 0.8}'
