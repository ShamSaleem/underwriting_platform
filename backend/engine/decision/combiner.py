"""Combine rules + LLM findings into one terminal Decision.

Severity ordering (worst wins): DECL > POST > rating > flat-extra/exclusion > STD.
Ratings from independent factors are summed (capped); above the cap -> decline.
Referrals are collected separately — a referral does not by itself block a rating.
"""
from __future__ import annotations

from ..config import settings
from ..models import Decision, DecisionCode, Finding, UnderwriteRequest

# Map a summed mortality loading to the nearest standard rating code.
_RATING_BANDS: list[tuple[int, DecisionCode]] = [
    (25, DecisionCode.R25),
    (50, DecisionCode.R50),
    (75, DecisionCode.R75),
    (100, DecisionCode.R100),
    (150, DecisionCode.R150),
    (200, DecisionCode.R200),
    (300, DecisionCode.R300),
]


def _rating_to_code(total: int) -> DecisionCode:
    for ceiling, code in _RATING_BANDS:
        if total <= ceiling:
            return code
    return DecisionCode.R300


def combine(req: UnderwriteRequest, findings: list[Finding], evidence: list[str]) -> Decision:
    applicant_name = (
        req.individual.full_name
        if req.individual
        else req.group.company_name
        if req.group
        else "unknown"
    )

    decline = [f for f in findings if f.decision_code == DecisionCode.DECL]
    postpone = [f for f in findings if f.decision_code == DecisionCode.POST]

    total_rating = sum(f.rating_pct for f in findings)
    total_flat_extra = sum(f.flat_extra_per_mille for f in findings)
    exclusions = [f.exclusion for f in findings if f.exclusion]

    referrals = [f for f in findings if f.requires_referral]
    referral_reasons = [
        f.referral_reason or f.assessment for f in referrals
    ]

    # Decide the terminal code.
    if decline:
        overall = DecisionCode.DECL
    elif total_rating > settings.max_rating_pct:
        overall = DecisionCode.DECL
        referral_reasons.append(
            f"Cumulative rating {total_rating}% exceeds the {settings.max_rating_pct}% ceiling."
        )
    elif postpone:
        overall = DecisionCode.POST
    elif total_rating > 0:
        overall = _rating_to_code(total_rating)
    elif total_flat_extra > 0:
        overall = DecisionCode.FE
    elif exclusions:
        overall = DecisionCode.EXCL
    else:
        overall = _maybe_preferred(req)

    explanation = _build_explanation(
        overall, total_rating, total_flat_extra, exclusions, referral_reasons, findings
    )

    return Decision(
        applicant=applicant_name,
        product=req.product,
        sum_assured=req.sum_assured,
        overall_decision=overall,
        total_rating_pct=min(total_rating, settings.max_rating_pct),
        flat_extra_per_mille=round(total_flat_extra, 2),
        exclusions=exclusions,
        requires_referral=bool(referrals) or overall in (DecisionCode.DECL, DecisionCode.POST),
        referral_reasons=_dedupe(referral_reasons),
        evidence_required=evidence,
        findings=findings,
        explanation=explanation,
        llm_used=any(f.source == "llm" for f in findings),
    )


def _maybe_preferred(req: UnderwriteRequest) -> DecisionCode:
    """Article 19 straight-through to Standard; Preferred for clean young low-cover lives."""
    ind = req.individual
    if (
        ind
        and ind.age <= 45
        and req.sum_assured <= 500_000
        and ind.smoking.value == "non_smoker"
        and (ind.metrics.bmi is None or ind.metrics.bmi < 27)
        and not ind.medical_disclosures
    ):
        return DecisionCode.PREF
    return DecisionCode.STD


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _build_explanation(
    overall: DecisionCode,
    total_rating: int,
    flat_extra: float,
    exclusions: list[str],
    referral_reasons: list[str],
    findings: list[Finding],
) -> str:
    headline = {
        DecisionCode.PREF: "Accepted at Preferred rates.",
        DecisionCode.STD: "Accepted at Standard rates.",
        DecisionCode.FE: f"Accepted with a flat extra of {flat_extra:.2f} per 1,000 sum assured.",
        DecisionCode.EXCL: "Accepted at Standard rates with exclusion(s).",
        DecisionCode.POST: "Postponed pending further evidence.",
        DecisionCode.DECL: "Declined.",
    }.get(overall, f"Accepted at a {total_rating}% mortality rating ({overall.value}).")

    parts = [headline]
    drivers = [
        f"{f.factor}: {f.assessment} [{f.article}, {f.source}]"
        for f in findings
        if f.decision_code not in (DecisionCode.STD, DecisionCode.PREF)
    ]
    if drivers:
        parts.append("Rating drivers — " + " | ".join(drivers))
    if exclusions:
        parts.append("Exclusions: " + "; ".join(exclusions))
    if referral_reasons:
        parts.append("Referral: " + "; ".join(_dedupe(referral_reasons)))
    if not drivers and overall in (DecisionCode.STD, DecisionCode.PREF):
        parts.append("No material adverse findings.")
    return " ".join(parts)
