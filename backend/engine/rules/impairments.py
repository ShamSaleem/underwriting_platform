"""Deterministic impairment assessment from disclosed conditions (Articles 6-10).

A rules-only stand-in for the LLM's free-text reasoning: each disclosed condition is
mapped to a conservative, manual-cited finding from the limited structured data we
have — the condition category, years since diagnosis (current age minus age at
diagnosis), the treated flag, and a few severity keyword cues in the details.

This is intentionally coarse: it cannot read nuance the way the LLM did, so every
material finding is flagged for underwriter referral (Article 19 routes any disclosed
diabetes/cancer to a human anyway). It is wired into the deterministic rules path and
runs only because the LLM assessor is disabled in this POC; if the LLM is re-enabled,
pick one source of disclosure findings to avoid double-counting.
"""
from __future__ import annotations

from ..models import DecisionCode, Finding, Individual, MedicalDisclosure, UnderwriteRequest

# Keyword -> category. Short/ambiguous abbreviations are deliberately omitted so an
# unrecognised condition falls through to a safe REFER rather than a wrong rating.
_CANCER = ("cancer", "tumour", "tumor", "carcinoma", "leukemia", "leukaemia", "lymphoma", "melanoma", "sarcoma", "malignan")
_CARDIO = ("hypertension", "heart", "cardiac", "coronary", "arrhythmia", "infarction", "cardiovascular", "angina", "stroke")
_DIAB = ("diabet",)
_RESP = ("asthma", "copd", "respiratory", "tuberculosis", "sleep apnea", "sleep apnoea", "emphysema", "bronchitis")
_MENTAL = ("depress", "anxiet", "bipolar", "schizo", "mental", "psychos", "ptsd")

# Cues that escalate a finding to its worst band (decline / postpone).
_SEVERE = ("metasta", "stage iv", "stage 4", "heart failure", "hospitali", "self-harm",
           "self harm", "suicide", "nephropathy", "retinopathy", "neuropathy", "complication")


def _category(text: str) -> str:
    t = text.lower()
    if any(k in t for k in _CANCER): return "cancer"
    if any(k in t for k in _DIAB): return "diabetes"
    if any(k in t for k in _CARDIO): return "cardiovascular"
    if any(k in t for k in _RESP): return "respiratory"
    if any(k in t for k in _MENTAL): return "mental_health"
    return "other"


def assess_disclosures(req: UnderwriteRequest) -> list[Finding]:
    """One finding per disclosed condition (Articles 6-10)."""
    ind = req.individual
    if not ind or not ind.medical_disclosures:
        return []
    has_hba1c = ind.metrics.hba1c is not None
    out: list[Finding] = []
    for d in ind.medical_disclosures:
        if (d.condition or "").strip():
            out.append(_finding_for(ind, d, has_hba1c))
    return out


def _finding_for(ind: Individual, d: MedicalDisclosure, has_hba1c: bool) -> Finding:
    blob = f"{d.condition} {d.details or ''}".lower()
    cat = _category(blob)
    years = (ind.age - d.age_at_diagnosis) if d.age_at_diagnosis is not None else None
    severe = any(h in blob for h in _SEVERE)

    def mk(code: DecisionCode, rating: int, article: str, note: str, refer: bool = True) -> Finding:
        return Finding(
            factor=f"Disclosed: {d.condition.strip()}",
            assessment=note,
            decision_code=code,
            rating_pct=rating,
            article=article,
            source="rules",
            requires_referral=refer,
            referral_reason=note if refer else None,
        )

    if cat == "cancer":  # Article 8
        if severe:
            return mk(DecisionCode.DECL, 0, "Article 8", "Metastatic/advanced cancer disclosed -> decline.", refer=False)
        if years is None:
            return mk(DecisionCode.POST, 0, "Article 8", "Cancer history; staging / disease-free interval unknown -> postpone for evidence.")
        if years < 5 or d.treated is False:
            return mk(DecisionCode.POST, 0, "Article 8", f"Cancer diagnosed {years}y ago (<5y disease-free) -> postpone.")
        return mk(DecisionCode.R50, 50, "Article 8", f"Cancer, {years}y disease-free and treated -> rating.")

    if cat == "diabetes":  # Article 7
        if severe:
            return mk(DecisionCode.DECL, 0, "Article 7", "Diabetes with significant complications -> decline.", refer=False)
        if has_hba1c:
            return mk(DecisionCode.REFER, 0, "Article 7", "Diabetes disclosed; control rated from HbA1c — underwriter to confirm complications.")
        return mk(DecisionCode.R50, 50, "Article 7", "Diabetes disclosed without an HbA1c -> provisional rating pending evidence.")

    if cat == "cardiovascular":  # Article 6
        if severe:
            return mk(DecisionCode.DECL, 0, "Article 6", "Heart failure / severe cardiovascular disease disclosed -> decline.", refer=False)
        return mk(DecisionCode.R50, 50, "Article 6", "Cardiovascular condition disclosed -> rating pending investigations.")

    if cat == "respiratory":  # Article 9
        if "copd" in blob or "tuberculosis" in blob:
            return mk(DecisionCode.R50, 50, "Article 9", "COPD / TB disclosed -> rating pending pulmonary evidence.")
        return mk(DecisionCode.R25, 25, "Article 9", "Respiratory condition disclosed -> mild rating pending PFTs.")

    if cat == "mental_health":  # Article 10
        if severe or "bipolar" in blob or "schizo" in blob:
            return mk(DecisionCode.POST, 0, "Article 10", "Severe mental-health history disclosed -> postpone for specialist report.")
        return mk(DecisionCode.R25, 25, "Article 10", "Mental-health condition disclosed -> mild rating.")

    return mk(DecisionCode.REFER, 0, "Article 4", f"Disclosed condition '{d.condition.strip()}' not in the automated tables -> refer.")
