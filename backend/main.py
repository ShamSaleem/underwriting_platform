"""Underwriting service API + static SPA host (single Cloud Run container).

Endpoints:
  GET  /api/health
  GET  /api/stats
  POST /api/underwrite      run engine, persist case, return decision
  GET  /api/cases           recent case history
  GET  /api/cases/{id}      full case (request + decision)
The built React app is served from ./static for everything else.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

import excel_io
import store
from engine.config import settings
from engine.manual import MANUAL_EFFECTIVE_DATE, MANUAL_VERSION
from engine.models import Decision, UnderwriteRequest
from engine.service import underwrite

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Aegis Underwriting Platform", version="1.0.0")

# Allow the Vite dev server (5173) to call the API during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    store.init_db()


# Demo credentials — override via env vars in production (or Secret Manager).
AUTH_USER = os.environ.get("UW_AUTH_USER", "admin")
AUTH_PASS = os.environ.get("UW_AUTH_PASS", "aegis2024")


@app.post("/api/login")
def login(body: dict) -> dict:
    if body.get("username") == AUTH_USER and body.get("password") == AUTH_PASS:
        return {"ok": True, "user": AUTH_USER, "token": "demo-session"}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": settings.model,
        "llm_provider": "gemini",
        "llm_enabled": settings.llm_enabled,
        "mode": "hybrid (rules + Gemini AI)" if settings.llm_enabled else "rules-only",
        "manual_version": MANUAL_VERSION,
        "manual_effective_date": MANUAL_EFFECTIVE_DATE,
    }


@app.get("/api/template")
def excel_template() -> Response:
    """Download a pre-filled .xlsx the user fills in and uploads."""
    return Response(
        content=excel_io.build_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="underwriting_template.xlsx"'},
    )


@app.post("/api/upload")
async def upload_excel(file: UploadFile) -> dict:
    """Assess every applicant row in an uploaded .xlsx (single or multi-person)."""
    data = await file.read()
    try:
        requests = excel_io.parse_workbook(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not read spreadsheet: {exc}")

    results = []
    for i, raw in enumerate(requests, start=1):
        try:
            req = UnderwriteRequest(**raw)
            decision = underwrite(req)
            dec = decision.model_dump(mode="json")
            saved = store.save_case(req.model_dump(mode="json"), dec)
            results.append({"row": i, "id": saved["id"], "ok": True, "decision": dec})
        except ValidationError as exc:
            results.append({"row": i, "ok": False, "error": "; ".join(e["msg"] for e in exc.errors()[:3])})
        except Exception as exc:  # noqa: BLE001
            results.append({"row": i, "ok": False, "error": str(exc)})

    ok = sum(1 for r in results if r["ok"])
    return {"total": len(results), "succeeded": ok, "failed": len(results) - ok, "results": results}


@app.get("/api/stats")
def get_stats() -> dict:
    return store.stats()


@app.post("/api/underwrite")
def post_underwrite(req: UnderwriteRequest) -> dict:
    decision: Decision = underwrite(req)
    req_dict = req.model_dump(mode="json")
    dec_dict = decision.model_dump(mode="json")
    saved = store.save_case(req_dict, dec_dict)
    return {"id": saved["id"], "created_at": saved["created_at"], "decision": dec_dict}


@app.get("/api/cases")
def get_cases(limit: int = 100) -> list[dict]:
    return store.list_cases(limit)


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    return case


# ---- static SPA (must be mounted last so /api/* wins) ----------------------- #
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        # Serve real files when present; otherwise index.html (client-side routing).
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
