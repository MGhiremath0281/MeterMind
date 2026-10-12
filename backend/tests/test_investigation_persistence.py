
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import InvestigationRun, InvestigationCase
from app.services.investigation_persistence import persist_investigation


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    session = TestingSession()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def investigation_result():
    return {
        "case_id": "TEST-INV-001",
        "audit_status": "review_required",
        "supervisor_decision": "review_required",
        "supervisor_reason": "Evidence requires human review.",
        "retry_count": 0,
        "errors": [],
        "agent_results": {"event_agent": {}},
        "investigation_cases": [
            {
                "group_key": "CUS-1001:LINE-0001",
                "affected_customer_id": "CUS-1001",
                "finding_ids": ["invoice_mismatches:0"],
                "categories": ["invoice_discrepancy"],
                "affected_invoice_line_ids": ["LINE-0001"],
                "findings": [
                    {
                        "finding_id": "invoice_mismatches:0",
                        "description": "Invoice amount mismatch.",
                    }
                ],
                "evidence": [
                    {
                        "evidence_id": "evidence-001",
                        "source": "test",
                        "description": "Test evidence.",
                    }
                ],
                "requires_review": True,
            }
        ],
    }


def test_persists_run_and_grouped_cases(db, investigation_result):
    saved = persist_investigation(db, investigation_result)

    assert saved["run_saved"] is True
    assert saved["investigation_cases_saved"] == 1

    run = db.get(InvestigationRun, "TEST-INV-001")
    assert run is not None
    assert run.supervisor_decision == "review_required"

    cases = (
        db.query(InvestigationCase)
        .filter_by(run_id="TEST-INV-001")
        .all()
    )
    assert len(cases) == 1
    assert cases[0].group_key == "CUS-1001:LINE-0001"


def test_preserves_findings_and_evidence(db, investigation_result):
    persist_investigation(db, investigation_result)

    saved_case = (
        db.query(InvestigationCase)
        .filter_by(run_id="TEST-INV-001")
        .one()
    )

    assert saved_case.finding_ids_json == ["invoice_mismatches:0"]
    assert saved_case.findings_json[0]["description"] == (
        "Invoice amount mismatch."
    )
    assert saved_case.evidence_json[0]["evidence_id"] == "evidence-001"
    assert saved_case.requires_review is True


def test_rerun_replaces_previous_cases(db, investigation_result):
    persist_investigation(db, investigation_result)

    updated_result = {
        **investigation_result,
        "investigation_cases": [
            {
                **investigation_result["investigation_cases"][0],
                "group_key": "CUS-1001:LINE-0002",
            },
            {
                **investigation_result["investigation_cases"][0],
                "group_key": "CUS-1002:LINE-0003",
                "affected_customer_id": "CUS-1002",
            },
        ],
    }

    persist_investigation(db, updated_result)

    assert (
        db.query(InvestigationRun)
        .filter_by(case_id="TEST-INV-001")
        .count()
        == 1
    )

    cases = (
        db.query(InvestigationCase)
        .filter_by(run_id="TEST-INV-001")
        .all()
    )
    assert len(cases) == 2
    assert {case.group_key for case in cases} == {
        "CUS-1001:LINE-0002",
        "CUS-1002:LINE-0003",
    }



def test_failed_persistence_rolls_back(db, investigation_result):
    from unittest.mock import patch

    from app.models import InvestigationCase

    original_add = db.add

    def fail_when_adding_case(instance):
        if isinstance(instance, InvestigationCase):
            raise RuntimeError("Simulated database persistence failure")
        original_add(instance)

    with patch.object(db, "add", side_effect=fail_when_adding_case):
        with pytest.raises(
            RuntimeError,
            match="Simulated database persistence failure",
        ):
            persist_investigation(db, investigation_result)

    assert db.get(InvestigationRun, "TEST-INV-001") is None
    assert (
        db.query(InvestigationCase)
        .filter_by(run_id="TEST-INV-001")
        .count()
        == 0
    )
