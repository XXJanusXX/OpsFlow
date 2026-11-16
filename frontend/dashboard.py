import os
import requests
import streamlit as st

st.set_page_config(page_title="OpsFlow AI", page_icon="🛠️", layout="wide")

DEFAULT_API_URL = os.getenv("OPSFLOW_API_URL", "https://opsflow-6lje.onrender.com")
api = st.sidebar.text_input("API base URL", DEFAULT_API_URL).rstrip("/")
st.title("OpsFlow AI")
st.caption("Evidence-grounded incident investigation • Human-approved simulated actions")

try:
    health = requests.get(f"{api}/health", timeout=15)
    health.raise_for_status()
    health_data = health.json()
    st.sidebar.success(f"API: {health_data.get('status', 'unknown')}")
except (requests.RequestException, ValueError) as exc:
    st.sidebar.error(f"API unavailable: {exc}")

with st.form("incident"):
    iid = st.text_input("Incident ID", "INC-DEMO-1001")
    title = st.text_input("Title", "ERP order processing job is failing")
    desc = st.text_area(
        "Description",
        "The nightly order import job failed three times. Latest log reports temporary database connection timeout. Queue is not progressing.",
    )
    sev = st.selectbox("Severity", ["P1", "P2", "P3", "P4"], index=1)
    submit = st.form_submit_button("Investigate", type="primary")

if submit:
    try:
        response = requests.post(
            f"{api}/investigate",
            json={
                "incident_id": iid,
                "title": title,
                "description": desc,
                "severity": sev,
                "system": "ERP",
            },
            timeout=90,
        )
        response.raise_for_status()
        st.session_state["inv"] = response.json()
        st.session_state.pop("approval", None)
    except requests.RequestException as exc:
        st.error(f"Investigation request failed: {exc}")

res = st.session_state.get("inv")
if res:
    d = res["diagnosis"]
    st.subheader("Diagnosis")
    a, b, c = st.columns(3)
    a.metric("Confidence", f"{d['confidence']:.0%}")
    b.metric("Risk", d["risk"])
    c.metric("LLM used", "Yes" if d["llm_used"] else "Fallback")
    st.write("**Summary**", d["summary"])
    st.write("**Likely cause**", d["likely_cause"])
    st.write("**Recommended action**", d["recommended_action"])
    st.write("**Rollback**", d["rollback_plan"])
    with st.expander("Evidence and tool responses", expanded=True):
        st.write(res["retrieved_runbooks"])
        st.json(d["evidence"])
        st.json(res["tool_results"])
    st.warning("No corrective action executes until explicit approval.")
    approver = st.text_input("Approver", "Demo Approver")
    comment = st.text_input("Comment", "Reviewed synthetic evidence")
    x, y = st.columns(2)
    with x:
        if st.button("Approve", disabled=not res["approval_required"]):
            try:
                response = requests.post(
                    f"{api}/approvals/{res['investigation_id']}",
                    json={"approved_by": approver, "approved": True, "comment": comment},
                    timeout=20,
                )
                response.raise_for_status()
                st.session_state["approval"] = "approved"
                st.success(response.json()["message"])
            except requests.RequestException as exc:
                st.error(f"Approval request failed: {exc}")
    with y:
        if st.button("Reject", disabled=not res["approval_required"]):
            try:
                response = requests.post(
                    f"{api}/approvals/{res['investigation_id']}",
                    json={"approved_by": approver, "approved": False, "comment": comment},
                    timeout=20,
                )
                response.raise_for_status()
                st.session_state["approval"] = "rejected"
                st.info(response.json()["message"])
            except requests.RequestException as exc:
                st.error(f"Rejection request failed: {exc}")
    if st.session_state.get("approval") == "approved":
        if st.button("Execute approved simulated action", type="primary"):
            try:
                response = requests.post(f"{api}/execute/{res['investigation_id']}", timeout=20)
                response.raise_for_status()
                st.success(response.json()["message"])
            except requests.RequestException as exc:
                st.error(f"Execution request failed: {exc}")
    if st.button("Show audit trail"):
        try:
            response = requests.get(f"{api}/audit/{res['investigation_id']}", timeout=20)
            response.raise_for_status()
            st.json(response.json()["events"])
        except requests.RequestException as exc:
            st.error(f"Audit request failed: {exc}")
