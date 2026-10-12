from pathlib import Path
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, engine, get_db
from app.models import (
    Customer,
    ReconciliationCase,
    AgentFinding,
    InvestigationRun,
    InvestigationCase,
)
from app.services.reconciliation import run_reconciliation
from app.graph.workflow import run_investigation
from app.services.investigation_persistence import persist_investigation

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = PROJECT_ROOT / "metermind_synthetic_fixture.json"

app = FastAPI(
    title="MeterMind API",
    description="Usage billing reconciliation and evidence-backed anomaly investigation.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_fixture() -> dict[str, Any]:
    if not FIXTURE_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Fixture not found: {FIXTURE_PATH}")
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Fixture JSON is invalid") from exc


@app.get("/")
def root():
    return {"name": "MeterMind API", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "metermind-api"}


@app.get("/api/v1/database/status")
def database_status(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "connected", "database": "PostgreSQL"}
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL connection failed. Check backend/.env and docker compose ps.",
        ) from exc


@app.post("/api/v1/database/initialize")
def initialize_database():
    try:
        # Importing models registers their tables with SQLAlchemy metadata.
        Base.metadata.create_all(bind=engine)
        return {"status": "initialized", "tables": sorted(Base.metadata.tables.keys())}
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"Database initialization failed: {exc.__class__.__name__}") from exc


@app.get("/api/v1/dashboard/summary")
def dashboard_summary():
    report = run_reconciliation(load_fixture())
    return {
        "project": "MeterMind",
        "case_id": report["case_id"],
        "status": report["status"],
        "finding_count": report["finding_count"],
        "counts": {name: len(items) for name, items in report["findings"].items()},
        "source": "synthetic_fixture",
    }


@app.post("/api/v1/reconciliation/run")
def reconcile(db: Session = Depends(get_db)):
    report = run_reconciliation(load_fixture())
    try:
        existing = db.get(ReconciliationCase, report["case_id"])
        if existing:
            db.delete(existing)
            db.flush()

        case = ReconciliationCase(
            case_id=report["case_id"],
            status=report["status"],
            finding_count=report["finding_count"],
            summary_json={
                "counts": {name: len(items) for name, items in report["findings"].items()},
                "limitations": report.get("limitations", []),
            },
        )
        db.add(case)

        saved_count = 0
        for group_name, findings in report["findings"].items():
            for finding in findings:
                db.add(AgentFinding(
                    case_id=report["case_id"],
                    finding_type=str(finding.get("finding_type", group_name)),
                    severity=str(finding.get("severity", "medium")),
                    customer_id=str(finding["customer_id"]) if finding.get("customer_id") is not None else None,
                    event_id=str(finding["event_id"]) if finding.get("event_id") is not None else None,
                    description=(
                        f"{finding.get('finding_type', group_name)}; "
                        f"direction={finding.get('direction', 'n/a')}; "
                        f"difference={finding.get('difference', 'n/a')}"
                    ),
                    evidence_json=finding.get("evidence", {}),
                    requires_review=bool(finding.get("requires_review", True)),
                ))
                saved_count += 1
        db.commit()
        report["persistence"] = {"case_saved": True, "findings_saved": saved_count}
        return report
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not save reconciliation: {exc.__class__.__name__}") from exc


@app.get("/api/v1/reconciliation/cases")
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(ReconciliationCase).order_by(ReconciliationCase.created_at.desc()).limit(100).all()
    return [
        {
            "case_id": case.case_id,
            "status": case.status,
            "finding_count": case.finding_count,
            "created_at": case.created_at.isoformat(),
        }
        for case in cases
    ]


@app.get("/api/v1/reconciliation/cases/{case_id}/findings")
def list_case_findings(case_id: str, db: Session = Depends(get_db)):
    case = db.get(ReconciliationCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return [
        {
            "id": finding.id,
            "finding_type": finding.finding_type,
            "severity": finding.severity,
            "customer_id": finding.customer_id,
            "event_id": finding.event_id,
            "description": finding.description,
            "evidence": finding.evidence_json,
            "requires_review": finding.requires_review,
        }
        for finding in case.findings
    ]


@app.get("/api/v1/fixture/overview")
def fixture_overview():
    fixture = load_fixture()
    return {
        "fixture_path": str(FIXTURE_PATH),
        "available_fields": list(fixture.keys()),
        "record_counts": {
            key: len(value) for key, value in fixture.items() if isinstance(value, list)
        },
    }


@app.post("/api/v1/investigations/run")
def run_and_save_investigation(
    db: Session = Depends(get_db),
):
    try:
        result = run_investigation()
        persistence = persist_investigation(db, result)

        return {
            **result,
            "persistence": persistence,
        }

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not persist investigation results.",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Investigation execution failed.",
        ) from exc


@app.get("/api/v1/investigations")
def list_investigations(db: Session = Depends(get_db)):
    runs = (
        db.query(InvestigationRun)
        .order_by(InvestigationRun.created_at.desc())
        .limit(100)
        .all()
    )

    return [
        {
            "case_id": run.case_id,
            "audit_status": run.audit_status,
            "supervisor_decision": run.supervisor_decision,
            "supervisor_reason": run.supervisor_reason,
            "retry_count": run.retry_count,
            "case_count": run.case_count,
            "created_at": (
                run.created_at.isoformat()
                if run.created_at
                else None
            ),
        }
        for run in runs
    ]


@app.get("/api/v1/investigations/{case_id}")
def get_investigation(
    case_id: str,
    db: Session = Depends(get_db),
):
    run = db.get(InvestigationRun, case_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Investigation {case_id} not found",
        )

    cases = (
        db.query(InvestigationCase)
        .filter(InvestigationCase.run_id == case_id)
        .order_by(InvestigationCase.id.asc())
        .all()
    )

    return {
        "case_id": run.case_id,
        "audit_status": run.audit_status,
        "supervisor_decision": run.supervisor_decision,
        "supervisor_reason": run.supervisor_reason,
        "retry_count": run.retry_count,
        "case_count": run.case_count,
        "summary": run.summary_json,
        "created_at": (
            run.created_at.isoformat()
            if run.created_at
            else None
        ),
        "investigation_cases": [
            {
                "group_key": case.group_key,
                "customer_id": case.customer_id,
                "finding_count": case.finding_count,
                "categories": case.categories_json,
                "finding_ids": case.finding_ids_json,
                "invoice_line_ids": case.invoice_line_ids_json,
                "findings": case.findings_json,
                "evidence": case.evidence_json,
                "requires_review": case.requires_review,
            }
            for case in cases
        ],
    }


@app.get("/api/v1/investigations/{case_id}/cases")
def list_investigation_cases(
    case_id: str,
    db: Session = Depends(get_db),
):
    run = db.get(InvestigationRun, case_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Investigation {case_id} not found",
        )

    cases = (
        db.query(InvestigationCase)
        .filter(InvestigationCase.run_id == case_id)
        .order_by(InvestigationCase.id.asc())
        .all()
    )

    return [
        {
            "group_key": case.group_key,
            "customer_id": case.customer_id,
            "finding_count": case.finding_count,
            "categories": case.categories_json,
            "finding_ids": case.finding_ids_json,
            "invoice_line_ids": case.invoice_line_ids_json,
            "findings": case.findings_json,
            "evidence": case.evidence_json,
            "requires_review": case.requires_review,
        }
        for case in cases
    ]
