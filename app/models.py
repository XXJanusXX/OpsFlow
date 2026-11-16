from typing import Literal
from pydantic import BaseModel,Field
class IncidentInput(BaseModel):
 incident_id:str=Field(min_length=3,max_length=40)
 title:str=Field(min_length=5,max_length=200)
 description:str=Field(min_length=10,max_length=2000)
 severity:Literal["P1","P2","P3","P4"]="P2"
 system:str="ERP"
class Evidence(BaseModel):
 source:str
 finding:str
class Diagnosis(BaseModel):
 summary:str
 likely_cause:str
 confidence:float=Field(ge=0,le=1)
 evidence:list[Evidence]
 recommended_action:str
 action_type:Literal["restart_job","clear_test_queue","no_action"]
 risk:Literal["low","medium","high"]
 rollback_plan:str
 llm_used:bool=False
class InvestigationResponse(BaseModel):
 investigation_id:str
 incident_id:str
 diagnosis:Diagnosis
 retrieved_runbooks:list[str]
 tool_results:dict
 approval_required:bool
 status:str
class ApprovalInput(BaseModel):
 approved_by:str=Field(min_length=2,max_length=100)
 approved:bool
 comment:str=""
class ExecutionResponse(BaseModel):
 investigation_id:str
 status:str
 message:str
 audit_id:int|None=None
