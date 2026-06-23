"""Orchestration: deterministic rules + disclosure analysis -> combined Decision.
The single entry point used by the API.

Medical disclosures (Articles 6-10) get exactly ONE source of findings so a disclosed
condition is never assessed twice:
  - the Gemini LLM assessor when it is enabled (nuanced free-text reasoning), or
  - the deterministic impairment table as a fallback when it is not.
Everything else (build, vitals, substances, occupation, avocations, travel, family
history, financials) is handled deterministically inside `run_rules`.
"""
from __future__ import annotations

from .config import settings
from .decision.combiner import combine
from .llm.assessor import assess as llm_assess
from .models import Decision, Finding, UnderwriteRequest
from .rules.engine import run_rules
from .rules.impairments import assess_disclosures


def underwrite(req: UnderwriteRequest) -> Decision:
    findings, evidence = run_rules(req)
    findings.extend(_disclosure_findings(req))
    return combine(req, findings, evidence)


def _disclosure_findings(req: UnderwriteRequest) -> list[Finding]:
    """One source only for disclosed medical conditions: the LLM when enabled,
    otherwise the deterministic impairment table. Never both."""
    if settings.llm_enabled:
        return llm_assess(req)
    return assess_disclosures(req)
