# MeterMind API â€” local development

## 1. Prerequisites
- Python 3.11+
- Existing `C:\Projects\MeterMind\metermind_synthetic_fixture.json`

## 2. Create and activate a virtual environment
```powershell
cd C:\Projects\MeterMind\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Start the API
```powershell
uvicorn app.main:app --reload
```

Open:
- API root: http://127.0.0.1:8000/
- Interactive API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- Dashboard summary: http://127.0.0.1:8000/api/v1/dashboard/summary
- Fixture overview: http://127.0.0.1:8000/api/v1/fixture/overview

Use **POST** `/api/v1/reconciliation/run` in Swagger to run reconciliation.

## Notes
This is the first real application layer. It is deliberately read-only. The next work is tests, proper database persistence, then LangChain tools/agents and a LangGraph supervisor. The frontend comes after the API contract is stable.
