# MeterMind API Documentation

**Project:** MeterMind — AI-Powered Usage Billing Reconciliation and Investigation System  
**Backend:** FastAPI  
**Database:** PostgreSQL  
**Cache:** Redis  
**AI workflow:** LangChain, LangGraph concepts, Ollama  
**Base URL:** `http://127.0.0.1:8000`  
**Interactive API documentation:** `http://127.0.0.1:8000/docs`

---

## 1. Introduction

MeterMind is a usage-based billing reconciliation and investigation system designed for SaaS businesses. It identifies discrepancies between authoritative usage records, observed usage events, pricing rules, and customer invoices.

The system combines deterministic billing reconciliation with a multi-agent investigation workflow and retrieval-augmented generation (RAG) for billing policy context.

### Key capabilities

- Reconcile customer usage and invoice records.
- Detect missing, duplicated, or inconsistent usage events.
- Reconstruct expected invoice amounts using effective-dated pricing.
- Investigate discrepancies using specialized agents.
- Retrieve relevant billing policies using RAG.
- Persist investigation results and evidence references.
- Provide API endpoints for dashboard and investigation monitoring.
- Apply deterministic supervisor policies to prevent an AI agent from independently authorizing billing corrections.

## 2. Architecture Overview

The high-level processing flow is:

1. **Input data:** Load the synthetic billing reconciliation case.
2. **Reconciliation engine:** Compare observed usage with authoritative records and reconstruct expected billing.
3. **Specialist agents:** Investigate event, pricing, and invoice discrepancies.
4. **Policy retrieval:** Retrieve relevant billing policy documents from the vector store.
5. **Supervisor:** Evaluate specialist results and determine whether further investigation or human review is required.
6. **Persistence:** Save investigation runs, findings, agent results, and evidence references.
7. **Frontend:** Display reconciliation status, findings, investigation results, and evidence.

### Main components

- **FastAPI:** Exposes REST API endpoints.
- **PostgreSQL:** Stores persisted reconciliation and investigation records.
- **Redis:** Configured as supporting infrastructure.
- **Ollama:** Runs the configured local language model.
- **Chroma:** Stores and retrieves billing policy embeddings.
- **React + TypeScript:** Provides the frontend dashboard and landing page.

## 3. Getting Started

### Prerequisites

- Python and the project's virtual environment
- PostgreSQL
- Redis, if required by the configured application services
- Ollama with the configured model available
- Node.js and npm for the frontend

### Start the backend

From the project root, open a terminal:

```powershell
cd C:\Projects\MeterMind\backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Backend URL:

`http://127.0.0.1:8000`

Interactive Swagger UI:

`http://127.0.0.1:8000/docs`

### Start the frontend

Open a second terminal:

```powershell
cd C:\Projects\MeterMind\frontend
npm run dev
```

The frontend is typically available at:

`http://localhost:5173`

Ensure that the backend dependencies and database are running before using database-backed endpoints.

## 4. API Conventions

### Base URL

```text
http://127.0.0.1:8000
```

### HTTP methods

| Method | Purpose |
|---|---|
| GET | Retrieve records or information |
| POST | Execute an operation or submit a request |

### Content type

For JSON requests, use:

```http
Content-Type: application/json
```

### Case identifier

The primary synthetic demonstration case is:

```text
RECON-DEMO-001
```

The examples below use this case identifier.

## 5. API Endpoint Reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/dashboard/summary` | Retrieve dashboard summary information |
| POST | `/api/v1/reconciliation/run` | Execute deterministic billing reconciliation |
| GET | `/api/v1/reconciliation/cases` | Retrieve persisted reconciliation cases |
| GET | `/api/v1/reconciliation/cases/{case_id}/findings` | Retrieve findings for a reconciliation case |
| GET | `/api/v1/fixture/overview` | Retrieve information about the configured demo fixture |
| POST | `/api/v1/investigations/run` | Execute and persist an investigation |
| GET | `/api/v1/investigations` | Retrieve investigation records |
| GET | `/api/v1/investigations/{case_id}` | Retrieve investigation details and persisted summary |
| GET | `/api/v1/investigations/{case_id}/cases` | Retrieve grouped investigation cases |

The exact response schemas should be confirmed against the running application's Swagger UI.

---

## 6. Dashboard API

### 6.1 Retrieve dashboard summary

**Endpoint**

```http
GET /api/v1/dashboard/summary
```

**Purpose**

Returns summary information used by the dashboard, including the demo case identifier, status, finding count, available counts, and data source.

**Example request**

```bash
curl http://127.0.0.1:8000/api/v1/dashboard/summary
```

**Illustrative response**

```json
{
  "case_id": "RECON-DEMO-001",
  "status": "review_required",
  "finding_count": 4,
  "source": "fixture"
}
```

The actual response may contain additional count fields.

## 7. Reconciliation APIs

### 7.1 Run billing reconciliation

**Endpoint**

```http
POST /api/v1/reconciliation/run
```

**Purpose**

Runs the deterministic reconciliation engine against a specified billing case. The engine compares source usage and billing information, reconstructs expected invoice values, and identifies discrepancies.

**Request body**

```json
{
  "case_id": "RECON-DEMO-001"
}
```

**Example request**

```bash
curl -X POST \
  http://127.0.0.1:8000/api/v1/reconciliation/run \
  -H "Content-Type: application/json" \
  -d '{"case_id":"RECON-DEMO-001"}'
```

**Example PowerShell request**

```powershell
$body = @{
    case_id = "RECON-DEMO-001"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/reconciliation/run" `
    -ContentType "application/json" `
    -Body $body
```

**Observed response fields**

The demo execution returned the following information:

- Status: `review_required`
- Finding count: `4`
- `case_saved`: `true`
- `findings_saved`: `4`

A simplified response representation is:

```json
{
  "case_id": "RECON-DEMO-001",
  "status": "review_required",
  "finding_count": 4,
  "case_saved": true,
  "findings_saved": 4
}
```

The JSON above is a simplified representation of the observed result, not a guarantee that every field is returned in exactly this shape.

### 7.2 List reconciliation cases

**Endpoint**

```http
GET /api/v1/reconciliation/cases
```

**Purpose**

Retrieves reconciliation cases that have been persisted.

**Example request**

```bash
curl http://127.0.0.1:8000/api/v1/reconciliation/cases
```

**Observed case information**

The demo case included fields equivalent to:

```json
[
  {
    "case_id": "RECON-DEMO-001",
    "status": "review_required",
    "finding_count": 4,
    "created_at": "2026-10-13T13:50:15.885535+00:00"
  }
]
```

The timestamp is an example from a previous test execution and will differ for new runs.

### 7.3 Retrieve findings for a case

**Endpoint**

```http
GET /api/v1/reconciliation/cases/{case_id}/findings
```

**Purpose**

Retrieves findings associated with a specific reconciliation case.

**Example request**

```bash
curl http://127.0.0.1:8000/api/v1/reconciliation/cases/RECON-DEMO-001/findings
```

The response contains persisted finding records. Consult Swagger UI for the exact finding schema and available fields.

## 8. Fixture API

### 8.1 Retrieve demo fixture overview

**Endpoint**

```http
GET /api/v1/fixture/overview
```

**Purpose**

Returns an overview of the configured synthetic billing fixture used to demonstrate reconciliation.

The fixture includes billing-related data such as customer information, pricing versions, authoritative usage events, observed usage events, and invoice records.

**Example request**

```bash
curl http://127.0.0.1:8000/api/v1/fixture/overview
```

**Demo case**

- Case ID: `RECON-DEMO-001`
- Example customer: Acme AI
- Customer ID: `CUS-1001`
- Example plan: `STARTER`
- Demonstration billing period: July 2026

These are synthetic demonstration records, not real customer billing data.

## 9. Investigation APIs

### 9.1 Run an investigation

**Endpoint**

```http
POST /api/v1/investigations/run
```

**Purpose**

Executes the multi-agent investigation workflow for a billing case and persists the resulting investigation summary and grouped investigation records.

The workflow includes:

- Event specialist
- Pricing specialist
- Invoice specialist
- Supervisor and audit processing

The pricing investigation also retrieves relevant billing policy context from the RAG system.

**Request body**

```json
{
  "case_id": "RECON-DEMO-001"
}
```

**Example request**

```bash
curl -X POST \
  http://127.0.0.1:8000/api/v1/investigations/run \
  -H "Content-Type: application/json" \
  -d '{"case_id":"RECON-DEMO-001"}'
```

**Example PowerShell request**

```powershell
$body = @{
    case_id = "RECON-DEMO-001"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/investigations/run" `
    -ContentType "application/json" `
    -Body $body
```

**Previously observed execution results**

The demo execution returned:

- `run_saved`: `true`
- Case ID: `RECON-DEMO-001`
- `investigation_cases_saved`: `3`
- `agent_results_saved`: `4`

These counts describe the previously tested demo run; future results depend on the current case and workflow execution.

### 9.2 List investigations

**Endpoint**

```http
GET /api/v1/investigations
```

**Purpose**

Retrieves persisted investigation records.

**Example request**

```bash
curl http://127.0.0.1:8000/api/v1/investigations
```

Use this endpoint to populate the investigation listing in the frontend.

### 9.3 Retrieve investigation details

**Endpoint**

```http
GET /api/v1/investigations/{case_id}
```

**Purpose**

Retrieves the persisted investigation summary for a particular case, including the available summary JSON and grouped case information.

**Example request**

```bash
curl http://127.0.0.1:8000/api/v1/investigations/RECON-DEMO-001
```

The stored summary can include specialist results, errors, agent names, and evidence references.

### 9.4 Retrieve grouped investigation cases

**Endpoint**

```http
GET /api/v1/investigations/{case_id}/cases
```

**Purpose**

Retrieves the grouped investigation case records associated with the specified investigation.

**Example request**

```bash
curl http://127.0.0.1:8000/api/v1/investigations/RECON-DEMO-001/cases
```

Consult Swagger UI for the exact response structure.

## 10. AI Investigation and RAG

### Specialist responsibilities

**Event agent**

Investigates discrepancies between authoritative usage and observed usage events.

**Pricing agent**

Investigates pricing rules and expected invoice reconstruction. It uses retrieved billing policy context alongside deterministic pricing evidence.

**Invoice agent**

Investigates invoice-related discrepancies against the reconstructed billing information.

**Supervisor**

Evaluates specialist outputs, missing results, failures, findings, and unresolved evidence. It determines the appropriate workflow outcome.

### Billing policy retrieval

MeterMind uses synthetic Markdown billing policy documents and embeddings generated with Ollama's `embeddinggemma:latest` model.

The Chroma collection is:

```text
metermind_billing_policies
```

The policy documents include:

- `BILLING-POLICY-001` — Usage billing
- `BILLING-POLICY-002` — Usage events
- `BILLING-POLICY-003` — Invoice investigation

Retrieved policy evidence is attached to the pricing specialist's structured result.

### Important safety rule

The language model does not independently authorize financial corrections. Deterministic reconciliation and supervisor policies govern the workflow decision. Cases requiring further investigation or approval remain subject to review.

## 11. Status Interpretation

The following is a conceptual interpretation of statuses used in the workflow; consult the actual API response and supervisor policy for the precise conditions.

| Status | Meaning |
|---|---|
| `review_required` | The case requires review before it can be resolved |
| `unresolved` | The investigation has not established a satisfactory resolution |
| `reinvestigate` | The workflow indicates that further investigation is needed |

A status indicating review or unresolved evidence should not be interpreted as approval to modify an invoice.

## 12. Error Handling and Troubleshooting

### Backend is unavailable

Check that Uvicorn is running:

```powershell
cd C:\Projects\MeterMind\backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

### PostgreSQL connection errors

Check that PostgreSQL is running and that the configured database connection settings are correct.

### Ollama model errors

Check the installed models:

```bash
ollama list
```

Confirm that the configured model in `backend/app/llm.py` is available.

### Frontend cannot reach the backend

Verify the frontend environment configuration:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Confirm that the backend CORS configuration allows the frontend origin:

```text
http://localhost:5173
```

Restart the frontend development server after changing environment variables.

### Investigation data is missing

Run an investigation and inspect the response:

```http
POST /api/v1/investigations/run
```

Then retrieve the persisted results:

```http
GET /api/v1/investigations
GET /api/v1/investigations/RECON-DEMO-001
```

### Reconciliation records are missing

Run the reconciliation endpoint before requesting the case list:

```http
POST /api/v1/reconciliation/run
GET /api/v1/reconciliation/cases
```

## 13. Testing and API Exploration

Open the interactive API documentation:

`http://127.0.0.1:8000/docs`

Recommended testing sequence:

1. Retrieve the fixture overview.
2. Retrieve the dashboard summary.
3. Run reconciliation for `RECON-DEMO-001`.
4. Retrieve reconciliation cases and findings.
5. Run an investigation for `RECON-DEMO-001`.
6. Retrieve investigation listings and details.
7. Verify that persisted results and evidence references are available.

This sequence validates both the deterministic reconciliation layer and the investigation workflow.

## 14. Limitations and Scope

- The documented demo uses synthetic billing data.
- The listed endpoints reflect the current known backend routes.
- Exact response schemas should be taken from the running FastAPI application.
- AI-generated investigative commentary does not replace deterministic billing calculations.
- The presence of findings does not itself authorize financial adjustments.
- Authentication, authorization, rate limits, and production deployment guarantees are not documented here as implemented features.

## 15. Conclusion

MeterMind combines deterministic usage-billing reconciliation, effective-dated pricing reconstruction, multi-agent investigation, billing policy retrieval, and persistent audit-oriented evidence.

Its API provides the foundation for executing reconciliation, investigating discrepancies, retrieving results, and integrating the workflow with a React frontend.

**Interactive API reference:** `http://127.0.0.1:8000/docs`

**Local backend:** `http://127.0.0.1:8000`

**Local frontend:** `http://localhost:5173`
