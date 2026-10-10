from typing import Any, TypedDict


class MeterMindState(TypedDict, total=False):
    case_id: str
    agent_outputs: dict[str, Any]
    audit_status: str
    errors: list[str]