
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InvestigationCase, InvestigationRun


def persist_investigation(
    db: Session,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Persist one investigation run and its grouped cases atomically."""
    case_id = result["case_id"]
    cases = result.get("investigation_cases", [])

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
                "agent_names": sorted(
                    result.get("agent_results", {}).keys()
                ),
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
        }

    except Exception:
        db.rollback()
        raise
