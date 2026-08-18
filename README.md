# Smart QR-Based Hospital Patient Journey Management System

A final-year CSE project for managing hospital patient journeys through secure QR queue tokens, live queue synchronization, and a proposed Dynamic Hybrid Queue Prediction Model (DHQPM).

## Phase 1 scope

- React frontend foundation with a mobile-first landing page
- FastAPI application with a health endpoint
- Environment-variable templates
- Validated architecture and ML methodology in `docs/`

## Repository layout

```text
frontend/       React application
backend/        FastAPI application
ml/             Future datasets, training, models, and evaluation
docs/           Architecture and research methodology decisions
```

## Run locally

Backend, from `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/api/health` to confirm the API is running.

Frontend, from `frontend/`:

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`.

`MONGODB_URI` and `JWT_SECRET` are placeholders in Phase 1. They will be required when database and authentication phases are implemented.
