import requests,streamlit as st
st.set_page_config(page_title="OpsFlow AI",page_icon="🛠️",layout="wide")
api=st.sidebar.text_input("API base URL","http://localhost:8000").rstrip("/")
st.title("OpsFlow AI"); st.caption("Evidence-grounded incident investigation • Human-approved simulated actions")
try: st.sidebar.success("API: "+requests.get(f"{api}/health",timeout=3).json()["status"])
except requests.RequestException: st.sidebar.error("Start FastAPI in another terminal.")
with st.form("incident"):
 iid=st.text_input("Incident ID","INC-DEMO-1001"); title=st.text_input("Title","ERP order processing job is failing")
 desc=st.text_area("Description","The nightly order import job failed three times. Latest log reports temporary database connection timeout. Queue is not progressing.")
 sev=st.selectbox("Severity",["P1","P2","P3","P4"],index=1); submit=st.form_submit_button("Investigate",type="primary")
if submit:
 try:
  r=requests.post(f"{api}/investigate",json={"incident_id":iid,"title":title,"description":desc,"severity":sev,"system":"ERP"},timeout=90); r.raise_for_status(); st.session_state["inv"]=r.json()
 except requests.RequestException as e: st.error(str(e))
res=st.session_state.get("inv")
if res:
 d=res["diagnosis"]; st.subheader("Diagnosis")
 a,b,c=st.columns(3); a.metric("Confidence",f"{d['confidence']:.0%}"); b.metric("Risk",d["risk"]); c.metric("LLM used","Yes" if d["llm_used"] else "Fallback")
 st.write("**Summary**",d["summary"]); st.write("**Likely cause**",d["likely_cause"]); st.write("**Recommended action**",d["recommended_action"]); st.write("**Rollback**",d["rollback_plan"])
 with st.expander("Evidence and tool responses",expanded=True): st.write(res["retrieved_runbooks"]); st.json(d["evidence"]); st.json(res["tool_results"])
 st.warning("No corrective action executes until explicit approval.")
 approver=st.text_input("Approver","Demo Approver"); comment=st.text_input("Comment","Reviewed synthetic evidence")
 x,y=st.columns(2)
 with x:
  if st.button("Approve",disabled=not res["approval_required"]):
   try:
    r=requests.post(f"{api}/approvals/{res['investigation_id']}",json={"approved_by":approver,"approved":True,"comment":comment}); r.raise_for_status(); st.session_state["approval"]="approved"; st.success(r.json()["message"])
   except requests.RequestException as e: st.error(str(e))
 with y:
  if st.button("Reject",disabled=not res["approval_required"]):
   try:
    r=requests.post(f"{api}/approvals/{res['investigation_id']}",json={"approved_by":approver,"approved":False,"comment":comment}); r.raise_for_status(); st.session_state["approval"]="rejected"; st.info(r.json()["message"])
   except requests.RequestException as e: st.error(str(e))
 if st.session_state.get("approval")=="approved" and st.button("Execute approved simulated action",type="primary"):
  try:
   r=requests.post(f"{api}/execute/{res['investigation_id']}"); r.raise_for_status(); st.success(r.json()["message"])
  except requests.RequestException as e: st.error(str(e))
 if st.button("Show audit trail"):
  try: st.json(requests.get(f"{api}/audit/{res['investigation_id']}").json()["events"])
  except requests.RequestException as e: st.error(str(e))
