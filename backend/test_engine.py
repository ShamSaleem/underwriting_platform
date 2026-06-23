"""Golden-case tests for the deterministic underwriting engine (LLM disabled).

Run from the backend/ directory:
    python test_engine.py        # standalone, no pytest needed
    python -m pytest test_engine.py
"""
from __future__ import annotations

from engine.models import (
    ApplicantType,
    DecisionCode,
    Group,
    HealthMetrics,
    Individual,
    Product,
    Smoking,
    UnderwriteRequest,
)
from engine.models import Financials, MedicalDisclosure
from engine.rules import tables
from engine.service import underwrite


def _individual(**kw) -> Individual:
    base = dict(full_name="Test", age=35, sex="male", smoking="non_smoker")
    base.update(kw)
    return Individual(**base)


def _req(ind: Individual | None = None, group: Group | None = None, **kw) -> UnderwriteRequest:
    atype = ApplicantType.group if group else ApplicantType.individual
    return UnderwriteRequest(
        applicant_type=atype,
        product=Product.individual_life,
        sum_assured=kw.pop("sum_assured", 200_000),
        individual=ind if group is None else None,
        group=group,
        **kw,
    )


# ---- Fix #3: normal/prediabetic HbA1c must NOT be rated --------------------- #
def test_normal_hba1c_is_standard():
    assert tables.hba1c_decision(5.2)[0] == DecisionCode.STD
    assert tables.hba1c_decision(6.0)[0] == DecisionCode.STD
    # A healthy applicant who merely had the test should come out PREF/STD, not rated.
    d = underwrite(_req(_individual(metrics=HealthMetrics(hba1c=5.2))))
    assert d.total_rating_pct == 0
    assert d.overall_decision in (DecisionCode.STD, DecisionCode.PREF)


def test_diabetic_hba1c_still_rates():
    assert tables.hba1c_decision(6.7) == (DecisionCode.R25, 25, tables.hba1c_decision(6.7)[2])
    assert tables.hba1c_decision(7.5)[0] == DecisionCode.R50
    assert tables.hba1c_decision(9.5)[0] == DecisionCode.DECL


# ---- Fix #4: smoking loadings monotonic ------------------------------------ #
def test_smoking_monotonic():
    occ = tables.smoking_decision("occasional")[1]
    reg = tables.smoking_decision("regular")[1]
    assert tables.smoking_decision("non_smoker")[1] == 0
    assert reg >= occ > 0  # a regular smoker is never rated better than an occasional one


# ---- Fix #2: class-5 occupation contributes a flat extra and a referral ----- #
def test_class5_occupation_flat_extra_and_referral():
    d = underwrite(_req(_individual(occupation="Roofer", occupation_class=5)))
    assert d.flat_extra_per_mille == tables.OCCUPATION_FLAT_EXTRA_PER_MILLE
    assert d.flat_extra_per_mille > 0
    assert d.requires_referral is True
    assert d.overall_decision in (DecisionCode.FE, DecisionCode.REFER)


# ---- Fix #1: referral-only case surfaces REFER, not a Standard accept ------- #
def test_income_multiple_breach_surfaces_refer():
    from engine.models import Financials

    d = underwrite(
        _req(
            _individual(),
            sum_assured=2_000_000,
            financials=Financials(annual_income=50_000, existing_life_cover=0),
        )
    )
    assert d.overall_decision == DecisionCode.REFER
    assert d.requires_referral is True
    assert "Accepted" not in d.explanation


def test_class6_occupation_surfaces_refer():
    d = underwrite(_req(_individual(occupation="Demolition", occupation_class=6)))
    assert d.overall_decision == DecisionCode.REFER
    assert d.requires_referral is True


# ---- New field: alcohol (Article 14) --------------------------------------- #
def test_alcohol_heavy_rates():
    assert tables.alcohol_decision("none")[1] == 0
    assert tables.alcohol_decision("moderate")[1] == 0
    assert tables.alcohol_decision("heavy")[0] == DecisionCode.R50
    d = underwrite(_req(_individual(alcohol="heavy")))
    assert d.total_rating_pct >= 50


# ---- New field: fasting glucose only when no HbA1c ------------------------- #
def test_fasting_glucose_used_only_without_hba1c():
    # No HbA1c -> fasting glucose drives the diabetes finding.
    d = underwrite(_req(_individual(metrics=HealthMetrics(fasting_glucose=150))))
    assert any("fasting glucose" in f.factor.lower() for f in d.findings)
    assert d.total_rating_pct >= 25
    # HbA1c present -> fasting glucose ignored (no double-rating from glucose).
    d2 = underwrite(_req(_individual(metrics=HealthMetrics(hba1c=6.7, fasting_glucose=150))))
    assert not any("fasting glucose" in f.factor.lower() for f in d2.findings)


# ---- New: net-worth uplift to the income multiple (Article 3.4) ------------ #
def test_net_worth_uplift_avoids_financial_referral():
    base = dict(sum_assured=2_000_000)
    # 50k income -> 15x = 750k limit; 2M cover would breach...
    breached = underwrite(_req(_individual(), financials=Financials(annual_income=50_000), **base))
    assert any(f.factor.startswith("Financial") for f in breached.findings)
    # ...but 1.5M net worth lifts the allowance enough to clear it.
    ok = underwrite(_req(_individual(), financials=Financials(annual_income=50_000, assets=1_500_000), **base))
    assert not any(f.factor.startswith("Financial") for f in ok.findings)


# ---- New: deterministic impairment table (Articles 6-10) ------------------- #
def test_impairment_cancer_recent_postpones():
    d = underwrite(_req(_individual(age=50, medical_disclosures=[
        MedicalDisclosure(condition="Breast cancer", age_at_diagnosis=48, treated=True)])))
    assert d.overall_decision == DecisionCode.POST


def test_impairment_cancer_old_treated_rates():
    d = underwrite(_req(_individual(age=50, medical_disclosures=[
        MedicalDisclosure(condition="Breast cancer", age_at_diagnosis=40, treated=True)])))
    assert d.total_rating_pct >= 50
    assert d.requires_referral is True


def test_impairment_metastatic_declines():
    d = underwrite(_req(_individual(medical_disclosures=[
        MedicalDisclosure(condition="Lung cancer", details="metastatic disease")])))
    assert d.overall_decision == DecisionCode.DECL


def test_impairment_unknown_condition_refers():
    d = underwrite(_req(_individual(medical_disclosures=[
        MedicalDisclosure(condition="Rare autoimmune disorder")])))
    assert d.overall_decision == DecisionCode.REFER


# ---- Fix #5: block must match applicant_type ------------------------------- #
def test_missing_block_rejected():
    raised = False
    try:
        UnderwriteRequest(
            applicant_type=ApplicantType.individual,
            product=Product.individual_life,
            sum_assured=100_000,
        )
    except Exception:
        raised = True
    assert raised, "individual request with no individual block should be rejected"


# ---- Sanity: a clean young life is still Preferred ------------------------- #
def test_clean_life_preferred():
    d = underwrite(_req(_individual(age=30, metrics=HealthMetrics(height_cm=180, weight_kg=75))))
    assert d.overall_decision == DecisionCode.PREF
    assert d.requires_referral is False


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL  {t.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)
