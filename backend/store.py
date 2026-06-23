"""Persistence layer.

Every underwriting case is saved here so the app has a real database backing it.
Default is SQLite (stdlib, zero-dependency) at UW_DB_PATH. To move to a managed
database on Google Cloud, point UW_DB_PATH at a mounted Cloud SQL volume or swap the
two SQL helpers below for a Postgres driver — the rest of the app is unchanged.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = os.environ.get("UW_DB_PATH", str(Path(__file__).parent / "underwriting.db"))


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id              TEXT PRIMARY KEY,
                created_at      TEXT NOT NULL,
                applicant       TEXT,
                applicant_type  TEXT,
                product         TEXT,
                sum_assured     REAL,
                decision        TEXT,
                rating_pct      INTEGER,
                requires_referral INTEGER,
                llm_used        INTEGER,
                request_json    TEXT,
                decision_json   TEXT
            )
            """
        )


def save_case(request: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    case_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = {
        "id": case_id,
        "created_at": created,
        "applicant": decision.get("applicant"),
        "applicant_type": request.get("applicant_type"),
        "product": decision.get("product"),
        "sum_assured": decision.get("sum_assured"),
        "decision": decision.get("overall_decision"),
        "rating_pct": decision.get("total_rating_pct", 0),
        "requires_referral": int(bool(decision.get("requires_referral"))),
        "llm_used": int(bool(decision.get("llm_used"))),
        "request_json": json.dumps(request),
        "decision_json": json.dumps(decision),
    }
    with _conn() as c:
        c.execute(
            """INSERT INTO cases
               (id, created_at, applicant, applicant_type, product, sum_assured,
                decision, rating_pct, requires_referral, llm_used, request_json, decision_json)
               VALUES (:id,:created_at,:applicant,:applicant_type,:product,:sum_assured,
                :decision,:rating_pct,:requires_referral,:llm_used,:request_json,:decision_json)""",
            row,
        )
    return {"id": case_id, "created_at": created}


def list_cases(limit: int = 100) -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            """SELECT id, created_at, applicant, applicant_type, product, sum_assured,
                      decision, rating_pct, requires_referral, llm_used
               FROM cases ORDER BY created_at DESC, rowid DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_case(case_id: str) -> dict[str, Any] | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["request"] = json.loads(d.pop("request_json"))
    d["decision_detail"] = json.loads(d.pop("decision_json"))
    return d


def stats() -> dict[str, Any]:
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) n FROM cases").fetchone()["n"]
        by_decision = {
            r["decision"]: r["n"]
            for r in c.execute(
                "SELECT decision, COUNT(*) n FROM cases GROUP BY decision"
            ).fetchall()
        }
        agg = c.execute(
            """SELECT COALESCE(AVG(rating_pct),0) avg_rating,
                      COALESCE(SUM(sum_assured),0) total_sa,
                      COALESCE(SUM(requires_referral),0) referrals
               FROM cases"""
        ).fetchone()
    accepted = sum(
        v for k, v in by_decision.items() if k and k not in ("DECL", "POST")
    )
    return {
        "total_cases": total,
        "by_decision": by_decision,
        "avg_rating_pct": round(agg["avg_rating"], 1),
        "total_sum_assured": agg["total_sa"],
        "referrals": agg["referrals"],
        "acceptance_rate": round(100 * accepted / total, 1) if total else 0.0,
    }
