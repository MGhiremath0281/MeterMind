
from typing import Any

from sqlalchemy.orm import Session

from app.models import InvestigationCase, InvestigationRun


def _serialize_agent_results(
    agent_results: dict[str, Any],
) -> dict[str, Any]:
    """Convert structured agent results into JSON-compatible dictionaries."""
    serialized: dict[str, Any] = {}

    for agent_name, agent_result in agent_results.items():
        if hasattr(agent_result, "model_dump"):
            serialized[agent_name] = agent_result.model_dump(mode="json")
        elif isinstance(agent_result, dict):
            serialized[agent_name] = agent_result
        else:
            raise TypeError(
                f"Unsupported result type for agent {agent_name!r}: "
                f"{type(agent_result).__name__}"
            )

    return serialized


def persist_investigation(
    db: Session,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Persist one investigation run and its grouped cases atomically."""
    case_id = result["case_id"]
    cases = result.get("investigation_cases", [])
    agent_results = _serialize_agent_results(
        result.get("agent_results", {})
    )

    try:
        existing = db.get(InvestigationRun, case_id)

        if existing is not None:
            # Delete the previous run and its child cases together.
            db.delete(existing)
            db.flush()

        run = InvestigationRun(
            case_id=case_id,
            audit_status=result.get("audit_status", "unresolved"),
            supervisor_decision=result.get(
                "supervisor_decision", "unresolved"
            ),
            supervisor_reason=result.get("supervisor_reason", ""),
            retry_count=result.get("retry_count", 0),
            case_count=len(cases),
            summary_json={
                "errors": result.get("errors", []),
                "agent_names": sorted(agent_results.keys()),
                "agent_results": agent_results,
            },
        )
        db.add(run)
        db.flush()

        for item in cases:
            db.add(
                InvestigationCase(
                    run_id=case_id,
                    group_key=item["group_key"],
                    customer_id=item.get("affected_customer_id"),
                    finding_count=len(item.get("findings", [])),
                    categories_json=item.get("categories", []),
                    finding_ids_json=item.get("finding_ids", []),
                    invoice_line_ids_json=item.get(
                        "affected_invoice_line_ids", []
                    ),
                    findings_json=item.get("findings", []),
                    evidence_json=item.get("evidence", []),
                    requires_review=item.get("requires_review", True),
                )
            )

        db.commit()

        return {
            "run_saved": True,
            "case_id": case_id,
            "investigation_cases_saved": len(cases),
            "agent_results_saved": len(agent_results),
        }

    except Exception:
        db.rollback()
        raise
