"""The Life & Health underwriting manual (sample), Articles 1-20.

`MANUAL_TEXT` is the reference fed to the LLM assessor as context so its findings
cite real article numbers. The deterministic tables in `engine/rules/tables.py`
implement the numeric thresholds (Articles 3-7, 11, 14); the qualitative articles
(8-10, 12, 13, 15) are assessed by the LLM from free text.

Replace this with your organisation's licensed manual to put it into production.
"""

MANUAL_TEXT = """\
SAMPLE LIFE & HEALTH (L&H) UNDERWRITING MANUAL — condensed for automated assessment.

Article 1 - Purpose and Scope. Establishes underwriting principles, risk-assessment
standards and decision-making guidelines for L&H products. Objectives: consistent
decisions, portfolio profitability, mortality/morbidity risk management, regulatory
compliance, and support for automated underwriting. Scope: Individual Life, Group
Life, Critical Illness, Disability Income, Medical Insurance, Credit Life.

Article 2 - Underwriting Philosophy. Fundamental principles: utmost good faith,
risk-based pricing, evidence-based assessment, consistency across markets, fair
customer treatment. Risk categories: Preferred, Standard, Substandard (rated),
Decline, Postpone.

Article 3 - Financial Underwriting. Purpose: assess economic justification of cover.
Documentation: salary slips, tax returns, bank statements, audited financials.
Maximum life cover by annual income:
  up to 50,000          -> 15x income
  50,001 - 100,000      -> 20x income
  above 100,000         -> 25x income
Cover (or in-force + applied) above the multiple needs financial justification and
referral; gross over-insurance may be declined. Net-worth assessment may add cover
based on assets, liabilities and existing insurance.

Article 4 - Medical Underwriting. Evidence by sum assured:
  <= 250,000           -> Health Declaration
  250,001 - 500,000    -> Medical Questionnaire
  500,001 - 1,000,000  -> Blood & Urine tests
  > 1,000,000          -> Full Medical Examination
Medical risk classification: Normal -> Standard; Mild impairment -> Standard/loading;
Moderate impairment -> Rating; Severe impairment -> Decline.

Article 5 - Build Underwriting (BMI):
  18.5 - 30  -> Standard
  30 - 35    -> Mild extra (~+25%)
  35 - 40    -> Moderate rating (~+50%)
  > 40       -> Decline / Postpone
  < 18.5     -> Underweight, refer.

Article 6 - Cardiovascular Disorders (hypertension, CAD, MI, arrhythmias, heart
failure). Assess age at diagnosis, severity, treatment, compliance, investigations.
Controlled BP (<140/90) -> Standard; stage 1 (140-159/90-99) -> mild rating;
stage 2 (>=160/100) -> rating; severe/uncontrolled (>=180/110), recent MI or heart
failure -> high rating or decline. Outcomes: Standard, +25% to +300%, or Decline.

Article 7 - Diabetes Mellitus. Evidence: HbA1c, fasting glucose, duration,
complications. HbA1c <7% -> Standard/mild rating; 7-8% -> rating; >8% -> higher
rating. Significant complications (nephropathy, retinopathy, neuropathy, CAD) ->
Decline.

Article 8 - Cancer. Assess type, stage, treatment history, recurrence, survival
duration. Fully recovered with long disease-free interval -> Standard/rating; recent
treatment / active surveillance -> Postpone; metastatic disease -> Decline.

Article 9 - Respiratory Disorders (asthma, COPD, sleep apnea, tuberculosis). Require
pulmonary function tests and specialist reports. Mild controlled asthma -> Standard;
COPD or active TB -> rating or postpone.

Article 10 - Mental Health (anxiety, depression, bipolar disorder, schizophrenia).
Assess severity, hospitalisation history, medication, occupational impact. Severe,
recent hospitalisation, or self-harm history -> rating, postpone, or decline.

Article 11 - Occupational Risk Classes: 1 office workers, 2 teachers, 3 sales
professionals, 4 factory workers, 5 construction workers, 6 mining/offshore. Classes
1-3 generally Standard; 4-6 attract flat extras and may require referral.

Article 12 - Avocation Underwriting (scuba diving, mountaineering, racing, skydiving,
aviation). Outcomes depending on frequency, depth/altitude, certification and
experience: flat extra, exclusion, or decline.

Article 13 - Foreign Travel & Residency. Assess country risk, duration, purpose,
political stability. Outcomes: Standard, extra premium, exclusion, or decline.

Article 14 - Substance Use. Smoking: non-smoker -> Standard; occasional -> rating;
regular -> smoker premium rates. Alcohol: assess consumption, treatment history,
liver function.

Article 15 - Family History (heart disease, cancer, diabetes, genetic disorders).
Assess number of affected first-degree relatives and age at diagnosis. Multiple
first-degree relatives with early onset (<60) may attract a rating.

Article 16 - Reinsurance Referral. Automatic acceptance within treaty retention
limits. Facultative referral required when retention is exceeded, a significant
impairment exists, or special risks are involved. Documents: proposal form, medical
reports, financial evidence, underwriter summary.

Article 17 - Decision Codes: STD Standard, PREF Preferred, R25 +25%, R50 +50%,
R100 +100%, FE flat extra, EXCL exclusion, POST postpone, DECL decline. (A
substandard total that is not exactly a named band is reported as RATED with the
exact percentage.)

Article 18 - Audit and Quality Assurance. Quality standards: decision consistency,
turnaround time, documentation completeness. Audit frequency: monthly case review,
quarterly portfolio review, annual manual update.

Article 19 - Automated Underwriting. Straight-through to Standard when age <= 45,
sum assured <= 500,000, BMI < 30, and no medical disclosures. Refer to a human
underwriter when diabetes or cancer is disclosed, or occupation class > 4.

Article 20 - Governance and Manual Maintenance. Ownership: Chief Underwriter. Review
cycle: annual review, plus regulatory-change and product-change triggers. Version
control: version number, effective date, change log, approval authority.
"""

# Surfaced in the app so users see which manual version is live (Article 20).
MANUAL_VERSION = "1.0"
MANUAL_EFFECTIVE_DATE = "2026-06-23"
