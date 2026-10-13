# Smart QR-Based Hospital Patient Journey Management System

A final-year CSE project for managing hospital patient journeys through secure QR queue tokens, live queue synchronization, and a proposed Dynamic Hybrid Queue Prediction Model (DHQPM).

## Current scope

- Role-based patient, reception, nurse, doctor, and admin workflows
- QR token generation and one-time patient verification
- Queue lifecycle management, nurse triage, and consultation records
- Hybrid waiting-time prediction with a graceful service boundary
- MongoDB-backed FastAPI API and a React/Vite frontend

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

## Configuration

Copy each `.env.example` file before starting its application. The frontend API
endpoint is configured by `VITE_API_BASE_URL`; the backend accepts a
comma-separated `FRONTEND_ORIGIN` list for CORS.

Never commit a real `JWT_SECRET`. `ENVIRONMENT=production` rejects the default
development secret at startup.

## Health endpoints

- `GET /api/health` — API process health
- `GET /api/db-health` — MongoDB connectivity

## Development notes

- MongoDB indexes are verified when the API starts. They cover user email,
  queue lookups, QR expiry, and consultation uniqueness.
- Login and QR verification have in-memory rate limits. For multiple API
  workers, replace these with a shared rate limiter such as Redis or an API
  gateway.
- QR tokens expire after 15 minutes and are consumed after a successful
  verification.
- The ML API endpoint defaults to `http://127.0.0.1:8001/predict` and can be
  changed with `ML_API_URL`.

## Recommended next work

1. Add API tests for auth, queue transitions, concurrent token allocation,
   QR expiry/reuse, and role authorization.
2. Move the route groups out of `backend/app/main.py` into FastAPI routers.
3. Add WebSocket or Server-Sent Event updates for live queue changes.
4. Lazy-load dashboard routes to reduce the current frontend production bundle.
