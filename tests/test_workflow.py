from fastapi.testclient import TestClient
from app.main import app,WORKFLOWS
client=TestClient(app)
def setup_function(): WORKFLOWS.clear()
def payload(): return {"incident_id":"INC-TEST-001","title":"ERP order processing job is failing","description":"Order import failed after a database connection timeout.","severity":"P2","system":"ERP"}
def test_health():
 r=client.get("/health"); assert r.status_code==200 and r.json()["environment"]=="SYNTHETIC-DEMO"
def test_investigation_has_evidence():
 r=client.post("/investigate",json=payload()); assert r.status_code==200
 b=r.json(); assert b["diagnosis"]["evidence"] and b["approval_required"] is True
def test_execution_requires_approval():
 inv=client.post("/investigate",json=payload()).json()
 assert client.post(f"/execute/{inv['investigation_id']}").status_code==403
def test_rejection_blocks_execution():
 inv=client.post("/investigate",json=payload()).json(); iid=inv["investigation_id"]
 client.post(f"/approvals/{iid}",json={"approved_by":"Reviewer","approved":False,"comment":"Rejected"})
 assert client.post(f"/execute/{iid}").status_code==403
def test_approved_execution_is_simulated():
 inv=client.post("/investigate",json=payload()).json(); iid=inv["investigation_id"]
 client.post(f"/approvals/{iid}",json={"approved_by":"Reviewer","approved":True,"comment":"Demo approval"})
 r=client.post(f"/execute/{iid}"); assert r.status_code==200 and "Simulated" in r.json()["message"]
def test_unknown_workflow():
 assert client.post("/execute/unknown-id").status_code==404
