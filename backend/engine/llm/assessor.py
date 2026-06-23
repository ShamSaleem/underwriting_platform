"""LLM assessor — Google Gemini.

Reads the manual + the applicant's free-text fields and returns structured, manual-
cited findings for what the deterministic rules can't decide: free-text conditions
(cancer, mental health, respiratory, neurological...), avocations, foreign travel,
family history, and inferring an occupation class from a job title.

Design rules:
- Only called when there is actually free text to assess (saves quota/latency).
- Structured JSON output (Gemini responseSchema) — no brittle parsing.
- Advisory only: every finding here is marked source="llm"; the combiner forces a
  human referral and never lets an LLM finding auto-bind or auto-decline.
- Any error/timeout degrades to a single referral finding — never crashes a decision.
"""
from __future__ import annotations

import json
from typing import Any

from ..config import settings
from ..manual import MANUAL_TEXT
from ..models import DecisionCode, Finding, UnderwriteRequest

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# JSON schema Gemini must return.
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "factor": {"type": "string"},
                    "assessment": {"type": "string"},
                    "decision_code": {
                        "type": "string",
                        "enum": ["STD", "R25", "R50", "R100", "RATED", "FE", "EXCL", "POST", "DECL", "REFER"],
                    },
                    "rating_pct": {"type": "integer"},
                    "flat_extra_per_mille": {"type": "number"},
                    "exclusion": {"type": "string"},
                    "article": {"type": "string"},
                    "referral_reason": {"type": "string"},
                },
                "required": ["factor", "assessment", "decision_code", "article"],
            },
        }
    },
    "required": ["findings"],
}

INSTRUCTIONS = """\
You are a Life & Health underwriting assistant. Apply ONLY the underwriting manual \
below. For each material risk factor in the applicant's FREE-TEXT data, output one \
finding: a decision code, any mortality rating % (rating_pct) or flat extra, and the \
exact manual Article you relied on (e.g. "Article 8").

Rules:
- Assess only free-text items: disclosed medical conditions (cancer, mental health, \
respiratory, neurological, etc.), avocations, foreign travel/residency, family \
history, and inferring an occupation class from a job title if no class was given.
- Do NOT re-assess BMI, HbA1c, blood pressure, smoking status, the income multiple, \
or a supplied occupation class — those are handled separately. Skip them.
- Be conservative. If evidence is insufficient to rate, use POST or REFER and explain.
- Cite the most specific applicable Article. Never invent article numbers.
- Use rating_pct for loadings (e.g. 50 for +50%); 0 if not a rating.
- If nothing in your scope is material, return an empty findings list.

UNDERWRITING MANUAL:
""" + MANUAL_TEXT


def _has_free_text(req: UnderwriteRequest) -> bool:
    ind = req.individual
    if ind:
        if ind.medical_disclosures or ind.avocations or ind.foreign_travel or ind.family_history:
            return True
        if ind.occupation and ind.occupation_class is None:
            return True
    if req.group and req.group.notes:
        return True
    return False


def _applicant_brief(req: UnderwriteRequest) -> str:
    lines = [
        f"Applicant type: {req.applicant_type.value}",
        f"Product: {req.product.value}",
        f"Sum assured: {req.sum_assured:,.0f}",
    ]
    if req.individual:
        ind = req.individual
        lines += [
            f"Age: {ind.age}, Sex: {ind.sex.value}",
            f"Occupation: {ind.occupation or 'n/a'} "
            f"(class {ind.occupation_class if ind.occupation_class is not None else 'NOT SUPPLIED — infer'})",
            f"Avocations: {', '.join(ind.avocations) or 'none'}",
            f"Foreign travel/residency: {', '.join(ind.foreign_travel) or 'none'}",
            f"Family history: {', '.join(ind.family_history) or 'none'}",
        ]
        if ind.medical_disclosures:
            lines.append("Medical disclosures:")
            for m in ind.medical_disclosures:
                extra = []
                if m.age_at_diagnosis is not None:
                    extra.append(f"dx age {m.age_at_diagnosis}")
                if m.treated is not None:
                    extra.append("treated" if m.treated else "untreated")
                suffix = f" ({'; '.join(extra)})" if extra else ""
                lines.append(f"  - {m.condition}: {m.details or 'no detail'}{suffix}")
        else:
            lines.append("Medical disclosures: none")
    if req.group:
        lines.append(f"Group notes: {req.group.notes or 'none'}")
    return "\n".join(lines)


def _referral_fallback(reason: str) -> list[Finding]:
    return [
        Finding(
            factor="AI assessment",
            assessment=reason,
            decision_code=DecisionCode.REFER,
            article="Article 16",
            source="llm",
            requires_referral=True,
            referral_reason="Automated free-text assessment unavailable — manual review.",
        )
    ]


def assess(req: UnderwriteRequest) -> list[Finding]:
    """Run the Gemini assessment. Returns [] when there's nothing to assess or the
    LLM is disabled; a referral finding on error (never raises)."""
    if not settings.llm_enabled:
        return []
    if not _has_free_text(req):
        return []  # nothing free-text to reason about — don't spend a call

    import httpx

    body = {
        "system_instruction": {"parts": [{"text": INSTRUCTIONS}]},
        "contents": [
            {"role": "user", "parts": [{"text": "Assess this applicant:\n\n" + _applicant_brief(req)}]}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
            "temperature": 0.2,
        },
    }
    import time

    # Free-tier models throw transient 503 (overloaded) / 429. Try the configured
    # model, then fall back to alternates, retrying each a couple of times.
    candidates: list[str] = []
    for m in (settings.model, "gemini-2.5-flash", "gemini-2.5-flash-lite"):
        if m not in candidates:
            candidates.append(m)

    last_status = "overloaded"
    for model in candidates:
        url = GEMINI_URL.format(model=model)
        for attempt in range(2):
            try:
                resp = httpx.post(
                    url, params={"key": settings.gemini_api_key},
                    json=body, timeout=settings.llm_timeout_seconds,
                )
            except Exception as exc:  # network/timeout
                last_status = type(exc).__name__
                break
            if resp.status_code == 200:
                try:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return _to_findings(json.loads(text).get("findings", []))
                except Exception as exc:  # malformed body
                    last_status = type(exc).__name__
                    break
            last_status = f"HTTP {resp.status_code}"
            if resp.status_code in (429, 503):
                time.sleep(1.2 * (attempt + 1))
                continue
            break  # non-retryable status -> try next model

    return _referral_fallback(f"AI call failed ({last_status}); rules-only decision.")


_VALID_CODES = {c.value for c in DecisionCode}


def _to_findings(raw: list[dict]) -> list[Finding]:
    """Validate LLM output: drop garbage, clamp ratings, reject unknown codes."""
    out: list[Finding] = []
    for f in raw:
        code = f.get("decision_code")
        if code not in _VALID_CODES:
            continue  # unknown code -> drop
        article = str(f.get("article", "")).strip()
        if not article.lower().startswith("article"):
            article = "Article 16"  # force a sane citation
        rating = int(f.get("rating_pct") or 0)
        # If the model gave a named code but no %, use the code's implied loading.
        if rating == 0:
            rating = {"R25": 25, "R50": 50, "R100": 100}.get(code, 0)
        rating = max(0, min(rating, settings.max_rating_pct))  # clamp absurd values
        out.append(
            Finding(
                factor=str(f.get("factor", "Disclosed risk"))[:120],
                assessment=str(f.get("assessment", ""))[:600],
                decision_code=DecisionCode(code),
                rating_pct=rating,
                flat_extra_per_mille=float(f.get("flat_extra_per_mille") or 0),
                exclusion=(f.get("exclusion") or None),
                article=article,
                source="llm",
                referral_reason=f.get("referral_reason") or None,
            )
        )
    return out
