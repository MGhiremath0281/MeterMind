import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
from app.models import InvestigationCase, InvestigationRun


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
def client(db):
  def override_get_db():
    try:
      yield db
    finally:
      pass

  app.dependency_overrides[get_db] = override_get_db

  with TestClient(app) as test_client:
    yield test_client

  app.dependency_overrides.clear()


@pytest.fixture
def saved_investigation(db):
  run = InvestigationRun(
      case_id="TEST-INV-001",
      audit_status="review_required",
      supervisor_decision="review_required",
      supervisor_reason="Evidence requires human review.",
      retry_count=0,
      case_count=1,
      summary_json={
          "errors": [],
          "agent_names": ["event_agent"],
      },
  )
  db.add(run)
  db.flush()
  db.add(
      InvestigationCase(
          run_id="TEST-INV-001",
          group_key="CUS-1001:LINE-0001",
          customer_id="CUS-1001",
          finding_count=1,
          categories_json=["invoice_discrepancy"],
          finding_ids_json=["finding-001"],
          invoice_line_ids_json=["LINE-0001"],
          findings_json=[
              {
                  "finding_id": "finding-001",
                  "description": "Invoice amount mismatch.",
              }
          ],
          evidence_json=[
              {
                  "evidence_id": "evidence-001",
                  "source": "test",
                  "description": "Test evidence.",
              }
          ],
          requires_review=True,
      )
  )
  db.commit()

  return "TEST-INV-001"


def test_list_investigations(client, saved_investigation):
  response = client.get("/api/v1/investigations")
  assert response.status_code == 200
  payload = response.json()

  assert len(payload) == 1
  assert payload[0]["case_id"] == saved_investigation
  assert payload[0]["audit_status"] == "review_required"
  assert payload[0]["case_count"] == 1


def test_get_investigation_includes_cases_and_evidence(
    client,
    saved_investigation,
):
  response = client.get(f"/api/v1/investigations/{saved_investigation}")
  assert response.status_code == 200
  payload = response.json()

  assert payload["case_id"] == saved_investigation
  assert payload["supervisor_decision"] == "review_required"
  assert payload["summary"]["agent_names"] == ["event_agent"]

  cases = payload["investigation_cases"]
  assert len(cases) == 1
  assert cases[0]["group_key"] == "CUS-1001:LINE-0001"
  assert cases[0]["findings"][0]["finding_id"] == "finding-001"
  assert cases[0]["evidence"][0]["evidence_id"] == "evidence-001"
  assert cases[0]["requires_review"] is True


def test_list_investigation_cases(client, saved_investigation):
  response = client.get(f"/api/v1/investigations/{saved_investigation}/cases")
  assert response.status_code == 200
  payload = response.json()

  assert len(payload) == 1
  assert payload[0]["customer_id"] == "CUS-1001"
  assert payload[0]["invoice_line_ids"] == ["LINE-0001"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/investigations/DOES-NOT-EXIST",
        "/api/v1/investigations/DOES-NOT-EXIST/cases",
    ],
)
def test_unknown_investigation_returns_404(client, path):
  response = client.get(path)
  assert response.status_code == 404
  assert "not found" in response.json()["detail"].lower()