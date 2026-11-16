import json,uuid,httpx
from copy import deepcopy
from app.config import settings
from app.models import Diagnosis
# Synthetic data only; tools are read-only except the explicit simulator.
RUNBOOKS=[
 {"id":"RB-ERP-001","title":"ERP job queue failures","text":"Check service health, recent job errors and queue progress. Transient database timeouts can cause retries. Do not restart production services without approval. Capture queue state first."},
 {"id":"RB-ERP-002","title":"Controlled worker restart","text":"Consider restart only when worker is unresponsive and evidence supports it. Check active processing, obtain approval, record reason. Rollback restores previous configuration and resumes monitoring."},
 {"id":"RB-ERP-003","title":"Invoice export backlog","text":"Inspect pending and failed exports. Confirm downstream endpoint reachability before retry. Do not delete queue records; preserve evidence."}]
ERP={"service":{"name":"ERP-Job-Worker","status":"running","last_heartbeat":"2026-11-16T08:55:00Z"},"job_queue":{"pending":18,"failed_last_hour":3,"last_error":"Temporary database connection timeout","progressing":False},"environment":"SYNTHETIC-DEMO"}
TICKET={"incident":"INC-DEMO-1001","recent_updates":["08:40Z order import entered retry","08:47Z temporary database connection timeout","08:52Z retry failed; queue pending"]}
def retrieve(query):
 terms={w.lower().strip(".,:;!?()") for w in query.split() if len(w)>3}
 ranked=[]
 for d in RUNBOOKS:
  score=sum(1 for t in terms if t in (d["title"]+" "+d["text"]).lower())
  if score: ranked.append((score,d))
 ranked.sort(key=lambda x:x[0],reverse=True)
 return [d for _,d in ranked[:2]]
def erp_status(): return deepcopy(ERP)
def ticket_history(iid):
 t=deepcopy(TICKET); t["requested_incident"]=iid; return t
def fallback(erp,ticket):
 return {"summary":"ERP job queue is not progressing and recent failures are recorded.","likely_cause":"Temporary database connection timeout is the leading hypothesis; evidence does not prove a persistent database outage.","confidence":0.72,"evidence":[{"source":"ERP service tool","finding":f"Worker status: {erp['service']['status']}."},{"source":"ERP queue tool","finding":f"{erp['job_queue']['failed_last_hour']} failures; progressing={erp['job_queue']['progressing']}."},{"source":"ERP queue tool","finding":f"Latest error: {erp['job_queue']['last_error']}."},{"source":"Ticket tool","finding":f"{len(ticket['recent_updates'])} recent updates retrieved."}],"recommended_action":"Validate database connectivity and active processing; consider a controlled restart only if confirmed unresponsive.","action_type":"restart_job","risk":"medium","rollback_plan":"Restore previous worker configuration if changed, resume monitoring and verify queue progress.","llm_used":False}
def investigate(incident):
 iid=str(uuid.uuid4()); books=retrieve(incident["title"]+" "+incident["description"])
 erp=erp_status(); ticket=ticket_history(incident["incident_id"])
 prompt=f"""Use ONLY supplied evidence. Do not claim action execution. If evidence insufficient choose no_action. Return JSON keys summary, likely_cause, confidence (0..1), evidence array of {{source,finding}}, recommended_action, action_type (restart_job|clear_test_queue|no_action), risk (low|medium|high), rollback_plan.
INCIDENT={json.dumps(incident)} ERP_TOOL={json.dumps(erp)} TICKET_TOOL={json.dumps(ticket)} RUNBOOKS={json.dumps(books)}"""
 try:
  r=httpx.post(f"{settings.ollama_base_url.rstrip('/')}/api/generate",json={"model":settings.ollama_model,"prompt":prompt,"stream":False,"format":"json","options":{"temperature":0.1}},timeout=settings.ollama_timeout_seconds)
  r.raise_for_status(); data=json.loads(r.json()["response"]); data["llm_used"]=True
 except (httpx.HTTPError,ValueError,KeyError,TypeError):
  data=fallback(erp,ticket)
 diagnosis=Diagnosis.model_validate(data)
 return {"investigation_id":iid,"incident_id":incident["incident_id"],"diagnosis":diagnosis,"retrieved_runbooks":[f"{b['id']}: {b['title']}" for b in books],"tool_results":{"erp_status":erp,"ticket_history":ticket},"approval_required":diagnosis.action_type!="no_action","status":"awaiting_approval" if diagnosis.action_type!="no_action" else "investigated"}
def execute_simulated(action,incident_id):
 if action not in {"restart_job","clear_test_queue"}: return {"executed":False,"result":"Action not allow-listed"}
 return {"executed":True,"environment":"SYNTHETIC-DEMO","action":action,"incident_id":incident_id,"result":f"Simulated {action} accepted; monitoring required."}
