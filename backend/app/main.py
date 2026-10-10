from pathlib import Path
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.services.reconciliation import run_reconciliation

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = PROJECT_ROOT / "metermind_synthetic_fixture.json"

app = FastAPI(
    title="MeterMind API",
    description="Usage billing reconciliation and evidence-backed anomaly investigation.",
    version="0.1.0",
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
        raise HTTPException(
            status_code=404,
            detail=f"Fixture not found at {FIXTURE_PATH}. Keep metermind_synthetic_fixture.json in C:\\Projects\\MeterMind.",
        )
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Fixture JSON is invalid: {exc}") from exc


@app.get("/")
def root():
    return {
        "name": "MeterMind API",
        "status": "running",
        "docs": "/docs",
        "next": "Open /docs and try GET /api/v1/dashboard/summary",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "metermind-api"}


@app.get("/api/v1/dashboard/summary")
def dashboard_summary():
    fixture = load_fixture()
    report = run_reconciliation(fixture)
    return {
        "project": "MeterMind",
        "case_id": report["case_id"],
        "status": report["status"],
        "finding_count": report["finding_count"],
        "counts": {name: len(items) for name, items in report["findings"].items()},
        "source": "synthetic_fixture",
    }


@app.post("/api/v1/reconciliation/run")
def reconcile():
    fixture = load_fixture()
    return run_reconciliation(fixture)


@app.get("/api/v1/fixture/overview")
def fixture_overview():
    fixture = load_fixture()
    list_fields = {
        key: len(value)
        for key, value in fixture.items()
        if isinstance(value, list)
    }
    return {
        "fixture_path": str(FIXTURE_PATH),
        "available_fields": list(fixture.keys()),
        "record_counts": list_fields,
    }
