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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import store
from engine.config import settings
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
        "llm_enabled": settings.llm_enabled,
        "mode": "hybrid (rules + LLM)" if settings.llm_enabled else "rules-only",
    }


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
