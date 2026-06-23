"""Request and response schemas for the underwriting engine.

These cover both individual and group (company) applicants, per the manual scope.
The `Decision` object is the full output: a terminal code, total rating, exclusions,
referral routing, evidence requirements, and per-factor cited findings.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class ApplicantType(str, Enum):
    individual = "individual"
    group = "group"


class Product(str, Enum):
    individual_life = "individual_life"
    group_life = "group_life"
    critical_illness = "critical_illness"
    disability_income = "disability_income"
    medical = "medical"
    credit_life = "credit_life"


class Smoking(str, Enum):
    non_smoker = "non_smoker"
    occasional = "occasional"
    regular = "regular"


class Sex(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class DecisionCode(str, Enum):
    """Article 17 decision codes (only those the manual defines), plus operational
    routing codes. RATED is used for any substandard accept whose total loading is
    not exactly one of the named bands — the exact percentage is carried separately
    in `rating_pct`, so we never invent codes like R150."""

    PREF = "PREF"      # Preferred
    STD = "STD"        # Standard
    R25 = "R25"        # +25% mortality rating (manual Article 17)
    R50 = "R50"        # +50% (manual Article 17)
    R100 = "R100"      # +100% (manual Article 17)
    RATED = "RATED"    # Substandard accept at the exact rating_pct (not a named band)
    FE = "FE"          # Flat extra
    EXCL = "EXCL"      # Exclusion
    POST = "POST"      # Postpone
    DECL = "DECL"      # Decline
    REFER = "REFER"    # Refer to human underwriter / reinsurer


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
class Financials(BaseModel):
    annual_income: float = Field(..., ge=0)
    net_worth: Optional[float] = Field(default=None, ge=0)
    existing_life_cover: float = Field(default=0, ge=0)
    documents_provided: list[str] = Field(default_factory=list)


class MedicalDisclosure(BaseModel):
    """A disclosed condition. Free text is fine — the LLM assessor reads `details`.
    Structured metrics, when supplied, are also evaluated by the rules engine."""

    condition: str
    details: Optional[str] = None
    age_at_diagnosis: Optional[int] = None
    treated: Optional[bool] = None


class HealthMetrics(BaseModel):
    height_cm: Optional[float] = Field(default=None, gt=0)
    weight_kg: Optional[float] = Field(default=None, gt=0)
    hba1c: Optional[float] = Field(default=None, ge=0, description="latest HbA1c %")
    systolic_bp: Optional[int] = Field(default=None, ge=0)
    diastolic_bp: Optional[int] = Field(default=None, ge=0)

    @computed_field  # type: ignore[misc]
    @property
    def bmi(self) -> Optional[float]:
        if self.height_cm and self.weight_kg:
            m = self.height_cm / 100.0
            return round(self.weight_kg / (m * m), 1)
        return None


class Individual(BaseModel):
    full_name: str
    age: int = Field(..., ge=0, le=120)
    sex: Sex = Sex.other
    smoking: Smoking = Smoking.non_smoker
    occupation: str = ""
    occupation_class: Optional[int] = Field(
        default=None, ge=1, le=6, description="Article 11 class 1-6; LLM infers if omitted"
    )
    avocations: list[str] = Field(default_factory=list)
    foreign_travel: list[str] = Field(default_factory=list)
    family_history: list[str] = Field(default_factory=list)
    medical_disclosures: list[MedicalDisclosure] = Field(default_factory=list)
    metrics: HealthMetrics = Field(default_factory=HealthMetrics)


class Group(BaseModel):
    company_name: str
    industry: str = ""
    num_employees: int = Field(..., ge=1)
    average_age: Optional[float] = Field(default=None, ge=0)
    occupation_classes: list[int] = Field(default_factory=list)
    free_cover_limit_requested: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class UnderwriteRequest(BaseModel):
    applicant_type: ApplicantType
    product: Product
    sum_assured: float = Field(..., ge=0, description="requested benefit amount, USD")
    individual: Optional[Individual] = None
    group: Optional[Group] = None
    financials: Optional[Financials] = None


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #
class Finding(BaseModel):
    factor: str = Field(..., description="what was assessed, e.g. 'Build (BMI)'")
    assessment: str
    decision_code: DecisionCode
    rating_pct: int = Field(default=0, description="mortality loading contributed")
    flat_extra_per_mille: float = Field(default=0, description="flat extra per 1000 SA")
    exclusion: Optional[str] = None
    article: str = Field(..., description="manual article cited, e.g. 'Article 5'")
    source: str = Field(..., description="'rules' or 'llm'")
    requires_referral: bool = False
    referral_reason: Optional[str] = None


class Decision(BaseModel):
    applicant: str
    product: Product
    sum_assured: float
    overall_decision: DecisionCode
    total_rating_pct: int = 0
    flat_extra_per_mille: float = 0
    exclusions: list[str] = Field(default_factory=list)
    requires_referral: bool = False
    referral_reasons: list[str] = Field(default_factory=list)
    evidence_required: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    explanation: str = ""
    llm_used: bool = False
