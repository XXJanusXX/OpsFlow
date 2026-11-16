from fastapi.testclient import TestClient
from app.main import app, WORKFLOWS
from app.agent import execute_simulated

client = TestClient(app)

def setup_function():
    WORKFLOWS.clear()

def incident():
    return {
        "incident_id": "INC-SAFETY-001",
        "title": "ERP order import job failure",
        "description": "Order import retries failed after a temporary database connection timeout.",
        "severity": "P2",
        "system": "ERP",
    }

def test_invalid_incident_is_rejected():
    response = client.post("/investigate", json={"incident_id": "x"})
    assert response.status_code == 422

def test_execution_cannot_be_replayed_after_success():
    result = client.post("/investigate", json=incident()).json()
    iid = result["investigation_id"]
    approval = client.post(
        f"/approvals/{iid}",
        json={"approved_by": "Reviewer", "approved": True, "comment": "Approved"},
    )
    assert approval.status_code == 200
    first = client.post(f"/execute/{iid}")
    second = client.post(f"/execute/{iid}")
    assert first.status_code == 200
    assert second.status_code == 403

def test_executor_rejects_unknown_action():
    result = execute_simulated("delete_production_data", "INC-SAFETY-002")
    assert result["executed"] is False
    assert "allow-listed" in result["result"]
