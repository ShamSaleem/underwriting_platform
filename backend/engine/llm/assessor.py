"""LLM assessor — Claude reads the manual plus free-text disclosures and returns
structured, manual-cited findings for things the deterministic engine can't decide:
free-text conditions, cancer/mental-health histories, avocations, country risk,
family history, and inferring occupation class from a job title.

Uses `claude-opus-4-8` with structured outputs so the result is always a validated
schema — no brittle JSON parsing. The manual is sent as a cached system block.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ..config import settings
from ..manual import MANUAL_TEXT
from ..models import DecisionCode, Finding, UnderwriteRequest


# Schema Claude is forced to return. Kept separate from Finding so the model only
# fills underwriting-relevant fields; we convert to Finding afterwards.
class LLMFinding(BaseModel):
    factor: str = Field(..., description="risk factor assessed, e.g. 'Cancer history'")
    assessment: str = Field(..., description="one or two sentence rationale")
    decision_code: DecisionCode
    rating_pct: int = Field(default=0, description="mortality loading %, 0 if not a rating")
    flat_extra_per_mille: float = Field(default=0, description="flat extra per 1000 SA, e.g. for avocations")
    exclusion: Optional[str] = Field(default=None, description="exclusion wording if EXCL")
    article: str = Field(..., description="manual article cited, e.g. 'Article 8'")
    requires_referral: bool = False
    referral_reason: Optional[str] = None


class LLMAssessment(BaseModel):
    findings: list[LLMFinding] = Field(default_factory=list)
    notes: str = Field(default="", description="anything notable not captured as a finding")


SYSTEM_INSTRUCTIONS = """\
You are a Life & Health underwriting assistant. Apply ONLY the underwriting manual \
provided. For each material risk factor in the applicant data, produce one finding with \
a decision code, any mortality rating % or flat extra, and the exact manual Article you \
relied on.

Rules:
- Assess only what the deterministic engine cannot: free-text medical conditions \
(cancer, mental health, respiratory, neurological, etc.), avocations, foreign travel/ \
residency, family history, and inferring an occupation class from a job title when no \
class number was supplied.
- Do NOT re-assess BMI, HbA1c, blood pressure, smoking status, the income multiple, or a \
supplied occupation class — those are handled deterministically. Skip them.
- Be conservative. If evidence is insufficient to rate, POSTpone or REFER and say why.
- Cite the most specific applicable Article. Never invent Article numbers.
- If nothing in your scope is material, return an empty findings list.
"""


def _applicant_brief(req: UnderwriteRequest) -> str:
    """Compact, deterministic serialisation of the applicant for the prompt."""
    lines = [
        f"Applicant type: {req.applicant_type.value}",
        f"Product: {req.product.value}",
        f"Sum assured: {req.sum_assured:,.0f}",
    ]
    if req.individual:
        ind = req.individual
        lines += [
            f"Name: {ind.full_name}",
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
        grp = req.group
        lines += [
            f"Company: {grp.company_name} ({grp.industry or 'industry n/a'})",
            f"Employees: {grp.num_employees}, avg age: {grp.average_age or 'n/a'}",
            f"Occupation classes in scheme: {grp.occupation_classes or 'n/a'}",
            f"Group notes: {grp.notes or 'none'}",
        ]
    return "\n".join(lines)


def assess(req: UnderwriteRequest) -> list[Finding]:
    """Run the LLM assessment. Returns [] if disabled or on error (rules still apply)."""
    if not settings.llm_enabled:
        return []

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        resp = client.messages.parse(
            model=settings.model,
            max_tokens=settings.max_tokens,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_INSTRUCTIONS,
                },
                {
                    "type": "text",
                    "text": "UNDERWRITING MANUAL:\n\n" + MANUAL_TEXT,
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[
                {
                    "role": "user",
                    "content": "Assess this applicant:\n\n" + _applicant_brief(req),
                }
            ],
            output_format=LLMAssessment,
        )
    except Exception as exc:  # noqa: BLE001 — never let the LLM break the decision
        return [
            Finding(
                factor="LLM assessment",
                assessment=f"LLM assessment unavailable ({type(exc).__name__}); rules-only decision. Manual review advised.",
                decision_code=DecisionCode.REFER,
                article="Article 16",
                source="llm",
                requires_referral=True,
                referral_reason="Automated free-text assessment failed.",
            )
        ]

    parsed = resp.parsed_output
    if parsed is None:
        return []

    return [
        Finding(
            factor=f.factor,
            assessment=f.assessment,
            decision_code=f.decision_code,
            rating_pct=f.rating_pct,
            flat_extra_per_mille=f.flat_extra_per_mille,
            exclusion=f.exclusion,
            article=f.article,
            source="llm",
            requires_referral=f.requires_referral,
            referral_reason=f.referral_reason,
        )
        for f in parsed.findings
    ]
