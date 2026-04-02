from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AgentType(str, Enum):
    PEER = "peer_agent"
    DISCOVERY = "discovery_agent"
    STRUCTURING = "structuring_agent"


class TaskRequest(BaseModel):
    task: str
    session_id: Optional[str] = None
    agent_type: Optional[AgentType] = AgentType.PEER


class PeerAgentResponse(BaseModel):
    agent: str = "peer_agent"
    response_type: str  # "direct_answer", "redirect", "out_of_scope"
    message: str
    references: Optional[List[str]] = []
    redirected_to: Optional[str] = None


class DiscoveryOutput(BaseModel):
    customer_stated_problem: str
    identified_business_problem: str
    hidden_root_risk: str
    customer_chat_summary: str
    questions_asked: List[str] = []


class ProblemNode(BaseModel):
    root_cause: str
    sub_causes: List[str]


class StructuringOutput(BaseModel):
    problem_type: str
    main_problem: str
    problem_tree: List[ProblemNode]


class TaskLog(BaseModel):
    session_id: str
    agent_type: str
    input_task: str
    output: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = "completed"