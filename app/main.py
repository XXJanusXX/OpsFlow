import json,sqlite3
from fastapi import FastAPI,HTTPException
from app.models import IncidentInput,InvestigationResponse,ApprovalInput,ExecutionResponse
from app.agent import investigate,execute_simulated
from app.config import settings
app=FastAPI(title="OpsFlow AI",version="0.1.0",description="Synthetic incident investigation with human-approved simulated actions.")
WORKFLOWS={}
def audit(iid,event,actor,details):
 with sqlite3.connect(settings.database_path) as c:
  c.execute("CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,investigation_id TEXT,event TEXT,actor TEXT,details TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
  cur=c.execute("INSERT INTO audit_log(investigation_id,event,actor,details) VALUES(?,?,?,?)",(iid,event,actor,json.dumps(details)))
  return cur.lastrowid
@app.get("/health")
def health(): return {"status":"ok","environment":"SYNTHETIC-DEMO"}
@app.post("/investigate",response_model=InvestigationResponse)
def create(incident:IncidentInput):
 r=investigate(incident.model_dump()); WORKFLOWS[r["investigation_id"]]={"incident":incident.model_dump(),"diagnosis":r["diagnosis"].model_dump(),"status":r["status"],"approval":None}
 audit(r["investigation_id"],"investigation_created","agent",{"incident_id":incident.incident_id})
 audit(r["investigation_id"],"evidence_collected","agent",{"tools":["erp_status","ticket_history"],"runbooks":r["retrieved_runbooks"]})
 return r
@app.post("/approvals/{iid}")
def approve(iid:str,p:ApprovalInput):
 w=WORKFLOWS.get(iid)
 if not w: raise HTTPException(404,"Investigation not found")
 if w["status"]!="awaiting_approval": raise HTTPException(409,"Not awaiting approval")
 w["approval"]=p.model_dump()
 if not p.approved:
  w["status"]="rejected"; audit(iid,"action_rejected",p.approved_by,p.model_dump()); return {"status":"rejected","message":"Rejected; no action executed."}
 w["status"]="approved"; audit(iid,"action_approved",p.approved_by,p.model_dump()); return {"status":"approved","message":"Approval recorded; execution is separate."}
@app.post("/execute/{iid}",response_model=ExecutionResponse)
def execute(iid:str):
 w=WORKFLOWS.get(iid)
 if not w: raise HTTPException(404,"Investigation not found")
 if w["status"]!="approved" or not w.get("approval",{}).get("approved"): raise HTTPException(403,"Explicit human approval required")
 result=execute_simulated(w["diagnosis"]["action_type"],w["incident"]["incident_id"])
 if not result["executed"]: raise HTTPException(400,result["result"])
 w["status"]="executed"; aid=audit(iid,"simulated_action_executed",w["approval"]["approved_by"],result)
 return ExecutionResponse(investigation_id=iid,status="executed",message=result["result"],audit_id=aid)
@app.get("/audit/{iid}")
def get_audit(iid:str):
 if iid not in WORKFLOWS: raise HTTPException(404,"Investigation not found in this process")
 with sqlite3.connect(settings.database_path) as c:
  rows=c.execute("SELECT id,event,actor,details,created_at FROM audit_log WHERE investigation_id=? ORDER BY id",(iid,)).fetchall()
 return {"events":[{"id":r[0],"event":r[1],"actor":r[2],"details":json.loads(r[3]),"created_at":r[4]} for r in rows]}
