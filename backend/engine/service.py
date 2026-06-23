"""Orchestration: rules + LLM -> combined Decision. The single entry point used by the API."""
from __future__ import annotations

from .decision.combiner import combine
from .llm.assessor import assess
from .models import Decision, UnderwriteRequest
from .rules.engine import run_rules


def underwrite(req: UnderwriteRequest) -> Decision:
    findings, evidence = run_rules(req)
    findings.extend(assess(req))  # LLM findings appended; no-op when disabled
    return combine(req, findings, evidence)
