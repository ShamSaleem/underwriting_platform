"""Lightweight deterministic rules for the qualitative free-text factors:
avocations (Article 12), foreign travel/residency (Article 13), and family history
(Article 15).

These are deliberately coarse keyword/heuristic rules — enough that a disclosed
hazard actually moves the decision rather than sitting in the form unused. Anything
they flag is routed to an underwriter, since the nuance (frequency, certification,
country specifics, number of affected relatives) is beyond a keyword match.

Medical conditions are NOT handled here — those go to the LLM assessor (or the
deterministic impairment table as a fallback). See `impairments.py` / `service.py`.
"""
from __future__ import annotations

import re

from ..models import DecisionCode, Finding, Individual, UnderwriteRequest

# Article 12 - hazardous avocations -> flat extra (per 1,000 SA) + referral.
_AVOCATION_RULES: list[tuple[tuple[str, ...], float, str]] = [
    (("skydiv", "parachut", "base jump", "base-jump"), 5.0, "Skydiving / parachuting"),
    (("scuba", "diving", "freediv", "free-div"), 3.0, "Diving"),
    (("mountaineer", "climbing", "alpin"), 3.0, "Mountaineering / climbing"),
    (("racing", "motorsport", "rally", "motocross", "motorbike racing"), 4.0, "Motor racing"),
    (("aviation", "private pilot", "microlight", "paraglid", "hang glid", "hang-glid"), 4.0, "Private aviation"),
]

# Article 13 - elevated-risk locations -> referral for country-risk assessment.
_HIGH_RISK_LOCATIONS: tuple[str, ...] = (
    "afghanistan", "syria", "yemen", "somalia", "libya", "iraq", "sudan", "south sudan",
    "mali", "central african republic", "dr congo", "democratic republic of the congo",
    "north korea", "venezuela", "ukraine", "gaza", "haiti", "myanmar", "burkina faso", "niger",
)

# Article 15 - family-history conditions that matter when onset is early (< 60).
_FAMILY_CONDITIONS: tuple[str, ...] = (
    "heart", "cardiac", "coronary", "cancer", "tumour", "tumor", "carcinoma",
    "diabet", "stroke", "huntington", "polycystic", "genetic", "hereditary",
)
_EARLY_ONSET_AGE = 60


def assess_qualitative(req: UnderwriteRequest) -> list[Finding]:
    ind = req.individual
    if not ind:
        return []
    return _avocations(ind) + _travel(ind) + _family_history(ind)


def _avocations(ind: Individual) -> list[Finding]:
    out: list[Finding] = []
    for line in ind.avocations:
        t = line.lower()
        for keywords, flat_extra, label in _AVOCATION_RULES:
            if any(k in t for k in keywords):
                out.append(
                    Finding(
                        factor=f"Avocation: {label}",
                        assessment=f"{label} disclosed ('{line.strip()[:80]}') -> flat extra {flat_extra:.1f} per 1,000 SA; refer to confirm.",
                        decision_code=DecisionCode.FE,
                        flat_extra_per_mille=flat_extra,
                        article="Article 12",
                        source="rules",
                        requires_referral=True,
                        referral_reason=f"{label} -> confirm flat extra / exclusion option.",
                    )
                )
                break  # one finding per disclosed avocation line
    return out


def _travel(ind: Individual) -> list[Finding]:
    out: list[Finding] = []
    for line in ind.foreign_travel:
        t = line.lower()
        # Whole-word match so e.g. "Niger" does not fire on "Nigeria".
        if any(re.search(rf"\b{re.escape(loc)}\b", t) for loc in _HIGH_RISK_LOCATIONS):
            out.append(
                Finding(
                    factor="Foreign travel / residency",
                    assessment=f"Travel/residency in an elevated-risk location ('{line.strip()[:80]}') -> refer for country-risk assessment.",
                    decision_code=DecisionCode.REFER,
                    article="Article 13",
                    source="rules",
                    requires_referral=True,
                    referral_reason="Elevated-risk country travel / residency.",
                )
            )
    return out


def _family_history(ind: Individual) -> list[Finding]:
    out: list[Finding] = []
    for line in ind.family_history:
        t = line.lower()
        if not any(c in t for c in _FAMILY_CONDITIONS):
            continue
        ages = [int(n) for n in re.findall(r"\b(\d{1,3})\b", t)]
        if any(a < _EARLY_ONSET_AGE for a in ages):
            out.append(
                Finding(
                    factor="Family history",
                    assessment=f"First-degree family history with early onset ('{line.strip()[:80]}') -> mild rating.",
                    decision_code=DecisionCode.R25,
                    rating_pct=25,
                    article="Article 15",
                    source="rules",
                    requires_referral=True,
                    referral_reason="Early-onset family history -> confirm relatives / age at onset.",
                )
            )
        # Relevant condition but no early-onset cue -> informational only, no rating.
    return out
