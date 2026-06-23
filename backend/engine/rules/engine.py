"""Deterministic rules engine: turns a request into cited Findings + evidence + referrals.

Only handles what is numerically decidable from the manual. Free-text disclosures,
unusual impairments, avocations and country risk are left to the LLM assessor.
"""
from __future__ import annotations

from ..models import (
    DecisionCode,
    Finding,
    Product,
    UnderwriteRequest,
)
from . import qualitative, tables


def _finding(factor: str, article: str, res: tuple[DecisionCode, int, str], **extra) -> Finding:
    code, rating, note = res
    return Finding(
        factor=factor,
        assessment=note,
        decision_code=code,
        rating_pct=rating,
        article=article,
        source="rules",
        requires_referral=(code == DecisionCode.REFER),
        referral_reason=note if code == DecisionCode.REFER else None,
        **extra,
    )


def run_rules(req: UnderwriteRequest) -> tuple[list[Finding], list[str]]:
    """Return (findings, evidence_required)."""
    findings: list[Finding] = []
    evidence = tables.evidence_required(req.sum_assured)

    # Article 3 - financial justification (income multiple, with a net-worth uplift
    # per Article 3.4: assets net of liabilities can justify additional cover).
    if req.financials and req.financials.annual_income > 0:
        limit = tables.income_multiple_limit(req.financials.annual_income)
        net_worth = req.financials.effective_net_worth()
        allowed = limit + max(0.0, net_worth)
        total_cover = req.sum_assured + req.financials.existing_life_cover
        if total_cover > allowed:
            nw_note = f" + net worth {net_worth:,.0f}" if net_worth > 0 else ""
            findings.append(
                Finding(
                    factor="Financial (income multiple)",
                    assessment=(
                        f"Total cover {total_cover:,.0f} exceeds the permitted "
                        f"{allowed:,.0f} ({limit / req.financials.annual_income:.0f}x income{nw_note}). "
                        "Financial justification required."
                    ),
                    decision_code=DecisionCode.REFER,
                    article="Article 3",
                    source="rules",
                    requires_referral=True,
                    referral_reason="Cover exceeds income multiple limit.",
                )
            )

    if req.applicant_type.value == "individual" and req.individual:
        findings.extend(_run_individual(req))

    if req.applicant_type.value == "group" and req.group:
        findings.extend(_run_group(req))

    return findings, evidence


def _run_individual(req: UnderwriteRequest) -> list[Finding]:
    ind = req.individual
    assert ind is not None
    out: list[Finding] = []

    if ind.metrics.bmi is not None:
        out.append(_finding("Build (BMI)", "Article 5", tables.bmi_decision(ind.metrics.bmi)))

    if ind.metrics.hba1c is not None:
        out.append(_finding("Diabetes (HbA1c)", "Article 7", tables.hba1c_decision(ind.metrics.hba1c)))
    elif ind.metrics.fasting_glucose is not None:
        # Fall back to fasting glucose only when HbA1c is absent (no double-rating).
        out.append(_finding("Diabetes (fasting glucose)", "Article 7", tables.fasting_glucose_decision(ind.metrics.fasting_glucose)))

    if ind.metrics.systolic_bp and ind.metrics.diastolic_bp:
        out.append(
            _finding(
                "Cardiovascular (BP)",
                "Article 6",
                tables.blood_pressure_decision(ind.metrics.systolic_bp, ind.metrics.diastolic_bp),
            )
        )

    out.append(_finding("Substance use (smoking)", "Article 14", tables.smoking_decision(ind.smoking.value)))
    out.append(_finding("Substance use (alcohol)", "Article 14", tables.alcohol_decision(ind.alcohol.value)))

    if ind.occupation_class is not None:
        out.append(_occupation_finding(ind.occupation_class))

    # Articles 12/13/15: lightweight deterministic assessment of avocations, foreign
    # travel and family history. (Disclosed medical conditions are handled separately
    # in service.py — LLM when enabled, deterministic impairment table otherwise.)
    out.extend(qualitative.assess_qualitative(req))

    return out


def _occupation_finding(occ_class: int) -> Finding:
    """Article 11. Classes 1-4 standard; class 5 is high hazard -> a flat extra plus a
    referral to confirm pricing; class 6 -> referral. For life cover occupational
    hazard is priced as a flat extra per 1,000 SA, not a mortality %."""
    res = tables.occupation_decision(occ_class)
    if res[0] == DecisionCode.FE:  # class 5
        return Finding(
            factor="Occupation",
            assessment=(
                f"Occupation class {occ_class} (high hazard) -> flat extra "
                f"{tables.OCCUPATION_FLAT_EXTRA_PER_MILLE:.1f} per 1,000 SA; refer to confirm."
            ),
            decision_code=DecisionCode.FE,
            flat_extra_per_mille=tables.OCCUPATION_FLAT_EXTRA_PER_MILLE,
            article="Article 11",
            source="rules",
            requires_referral=True,
            referral_reason="High-hazard occupation (class 5) -> confirm flat extra.",
        )
    return _finding("Occupation", "Article 11", res)


def _run_group(req: UnderwriteRequest) -> list[Finding]:
    grp = req.group
    assert grp is not None
    out: list[Finding] = []

    # Free cover limit / catastrophe concentration -> reinsurance referral (Article 16).
    if grp.free_cover_limit_requested and grp.free_cover_limit_requested > 250_000:
        out.append(
            Finding(
                factor="Group free cover limit",
                assessment=(
                    f"Requested free cover limit {grp.free_cover_limit_requested:,.0f} "
                    "exceeds the auto-acceptance threshold; refer for treaty/facultative review."
                ),
                decision_code=DecisionCode.REFER,
                article="Article 16",
                source="rules",
                requires_referral=True,
                referral_reason="Free cover limit above retention.",
            )
        )

    # High-hazard occupation classes in the scheme.
    if any(c > 4 for c in grp.occupation_classes):
        out.append(
            Finding(
                factor="Group occupation mix",
                assessment="Scheme includes occupation classes above 4 (high hazard).",
                decision_code=DecisionCode.REFER,
                article="Article 11",
                source="rules",
                requires_referral=True,
                referral_reason="High-hazard occupation classes present.",
            )
        )

    # Anti-selection: small schemes carry concentration risk.
    if grp.num_employees < 10:
        out.append(
            Finding(
                factor="Group size",
                assessment=f"Small scheme ({grp.num_employees} lives) -> anti-selection / concentration risk.",
                decision_code=DecisionCode.REFER,
                article="Article 16",
                source="rules",
                requires_referral=True,
                referral_reason="Small group size.",
            )
        )

    if grp.average_age and grp.average_age >= 50:
        out.append(
            Finding(
                factor="Group average age",
                assessment=f"Average age {grp.average_age} elevated -> price for mortality.",
                decision_code=DecisionCode.R25,
                rating_pct=25,
                article="Article 16",
                source="rules",
            )
        )

    return out
