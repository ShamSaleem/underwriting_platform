"""Deterministic decision tables — the numeric thresholds from the manual.

Each function returns a (DecisionCode, rating_pct, note) tuple so the engine can
build a cited Finding. These are pure and unit-tested; no LLM involved.
"""
from __future__ import annotations

from ..models import DecisionCode

Result = tuple[DecisionCode, int, str]


def evidence_required(sum_assured: float) -> list[str]:
    """Article 4 - medical evidence by sum assured."""
    if sum_assured <= 250_000:
        return ["Health Declaration"]
    if sum_assured <= 500_000:
        return ["Medical Questionnaire"]
    if sum_assured <= 1_000_000:
        return ["Blood & Urine tests"]
    return ["Full Medical Examination"]


def income_multiple_limit(annual_income: float) -> float:
    """Article 3 - maximum life cover as a multiple of income."""
    if annual_income <= 50_000:
        return annual_income * 15
    if annual_income <= 100_000:
        return annual_income * 20
    return annual_income * 25


def bmi_decision(bmi: float) -> Result:
    """Article 5 - build underwriting."""
    if bmi < 18.5:
        return DecisionCode.REFER, 0, f"BMI {bmi} underweight; refer for assessment."
    if bmi < 30:
        return DecisionCode.STD, 0, f"BMI {bmi} within standard range."
    if bmi < 35:
        return DecisionCode.R25, 25, f"BMI {bmi} -> mild extra."
    if bmi < 40:
        return DecisionCode.R75, 75, f"BMI {bmi} -> moderate rating."
    return DecisionCode.DECL, 0, f"BMI {bmi} exceeds 40 -> decline/postpone."


def hba1c_decision(hba1c: float) -> Result:
    """Article 7 - diabetes control (HbA1c only; complications handled by LLM)."""
    if hba1c < 7:
        return DecisionCode.R25, 25, f"HbA1c {hba1c}% well controlled."
    if hba1c < 8:
        return DecisionCode.R50, 50, f"HbA1c {hba1c}% -> rating."
    if hba1c < 9:
        return DecisionCode.R100, 100, f"HbA1c {hba1c}% poorly controlled -> higher rating."
    return DecisionCode.DECL, 0, f"HbA1c {hba1c}% very poorly controlled -> decline."


def blood_pressure_decision(systolic: int, diastolic: int) -> Result:
    """Article 6 - hypertension severity from latest reading."""
    if systolic >= 180 or diastolic >= 110:
        return DecisionCode.R100, 100, f"BP {systolic}/{diastolic} severe -> high rating."
    if systolic >= 160 or diastolic >= 100:
        return DecisionCode.R50, 50, f"BP {systolic}/{diastolic} stage 2 -> rating."
    if systolic >= 140 or diastolic >= 90:
        return DecisionCode.R25, 25, f"BP {systolic}/{diastolic} stage 1 -> mild rating."
    return DecisionCode.STD, 0, f"BP {systolic}/{diastolic} controlled."


def smoking_decision(status: str) -> Result:
    """Article 14 - smoking status."""
    if status == "non_smoker":
        return DecisionCode.STD, 0, "Non-smoker."
    if status == "occasional":
        return DecisionCode.R25, 25, "Occasional smoker -> rating."
    return DecisionCode.STD, 0, "Regular smoker -> smoker premium rates apply."


def occupation_decision(occ_class: int) -> Result:
    """Article 11 - occupational risk class."""
    if occ_class <= 3:
        return DecisionCode.STD, 0, f"Occupation class {occ_class} -> standard."
    if occ_class == 4:
        return DecisionCode.STD, 0, f"Occupation class {occ_class} -> standard (monitor)."
    if occ_class == 5:
        return DecisionCode.FE, 0, f"Occupation class {occ_class} -> flat extra; refer."
    return DecisionCode.REFER, 0, f"Occupation class {occ_class} -> refer (high hazard)."
