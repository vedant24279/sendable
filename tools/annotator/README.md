# Cricket Delivery Video Annotator

A frame-exact local video annotation tool for creating ball tracker ground-truth answer keys across cricket delivery clips.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2, OpenCV (`opencv-python-headless`), pytest.
- **Frontend**: React 18, TypeScript, Vite, Zustand (stub listing page).
- **Storage**: `eval/labels/<clip_id>.json` (ground truth labels), `eval/labels/_audit.jsonl` (audit log), `tools/annotator/.cache/` (sequential frame JPEG cache).

---

## Quick Start (Windows PowerShell)

You can launch both the backend and frontend concurrently using the provided PowerShell script:

```powershell
.\tools\annotator\run.ps1
```

Or run each service individually in separate terminals:

### 1. Backend API (Runs on `http://127.0.0.1:8765`)

```powershell
# From repo root
cd tools/annotator/backend
uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
```

API documentation is available at `http://127.0.0.1:8765/docs`.

### 2. Frontend Development Server (Runs on `http://127.0.0.1:5173`)

```powershell
# From repo root
cd tools/annotator/frontend
npm install
npm run dev
```

The frontend uses Vite's dev proxy to route `/api/*` directly to `http://127.0.0.1:8765`.

---

## Building / Refreshing Manifest

To scan all jobs under `backend/_tracker_work/jobs/`, decode sequential frame counts, detect any metadata mismatches, and update `manifest.json`:

```powershell
python tools/annotator/backend/build_manifest.py
```

---

## Running Tests

Run the test suite using pytest from the repository root:

```powershell
pytest tools/annotator/backend/tests -q
```
