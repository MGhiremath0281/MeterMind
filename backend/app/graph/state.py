from typing import Any, TypedDict

from app.schemas.agent_result import AgentResult


class AgentExecution(TypedDict, total=False):
    status: str
    result: dict[str, Any]
    output: str
    error: str



class MeterMindState(TypedDict, total=False):
    case_id: str
    agent_outputs: dict[str, AgentExecution]
    agent_results: dict[str, AgentResult]
    audit_status: str
    errors: list[str]
    retry_count: int
    supervisor_decision: str
    supervisor_reason: str
