"""The underwriting manual, condensed into the rules and reference text the engine cites.

`MANUAL_TEXT` is fed to the LLM assessor as cached system context so its findings
quote real article numbers. The deterministic tables in `app/rules/tables.py`
implement the numeric thresholds from the same manual.

This is the sample L&H manual structure — replace with your organisation's real
manual to put it into production.
"""

MANUAL_TEXT = """\
SAMPLE LIFE & HEALTH UNDERWRITING MANUAL (condensed for automated assessment)

Article 2 - Risk categories: Preferred (PREF), Standard (STD), Substandard (rated),
Decline (DECL), Postpone (POST).

Article 3 - Financial underwriting. Maximum life cover by annual income:
  income up to 50,000          -> 15x income
  income 50,001 - 100,000      -> 20x income
  income above 100,000         -> 25x income
Cover requested above the multiple, or total in-force + applied cover above it,
requires financial justification and referral. Gross over-insurance may be declined.

Article 4 - Medical evidence requirements by sum assured:
  <= 250,000           -> Health Declaration
  250,001 - 500,000    -> Medical Questionnaire
  500,001 - 1,000,000  -> Blood & Urine tests
  > 1,000,000          -> Full Medical Examination

Article 5 - Build underwriting (BMI):
  BMI 18.5 - 30  -> Standard
  BMI 30 - 35    -> Mild extra (about +25%)
  BMI 35 - 40    -> Moderate rating (about +50% to +100%)
  BMI > 40       -> Decline / Postpone
  BMI < 18.5     -> Underweight, refer / possible rating

Article 6 - Cardiovascular (hypertension, CAD, MI, arrhythmia, heart failure).
Assess age at diagnosis, severity, treatment, compliance, investigations.
Controlled BP (<140/90) -> Standard. Stage 2 hypertension (>=160/100) -> rating.
Severe / uncontrolled (>=180/110) or recent MI / heart failure -> high rating or decline.
Outcomes range Standard, +25% to +300%, or Decline.

Article 7 - Diabetes mellitus. Evidence: HbA1c, fasting glucose, duration, complications.
  HbA1c < 7%   -> Standard / mild rating
  HbA1c 7 - 8% -> Rating
  HbA1c > 8%   -> Higher rating
  Significant complications (nephropathy, retinopathy, neuropathy, CAD) -> Decline.

Article 8 - Cancer. Assess type, stage, treatment history, recurrence, survival duration.
  Fully recovered, long disease-free interval -> Standard / rating
  Recent treatment / active surveillance       -> Postpone
  Metastatic disease                           -> Decline

Article 9 - Respiratory (asthma, COPD, sleep apnea, TB). Require PFTs / specialist reports.
Mild controlled asthma -> Standard. COPD / active TB -> rating or postpone.

Article 10 - Mental health (anxiety, depression, bipolar, schizophrenia). Assess severity,
hospitalisation history, medication, occupational impact. Severe / recent hospitalisation
or self-harm -> rating, postpone, or decline.

Article 11 - Occupational risk classes:
  1 office workers, 2 teachers, 3 sales professionals,
  4 factory workers, 5 construction workers, 6 mining / offshore.
Classes 1-3 generally Standard. Classes 4-6 attract flat extras and may require referral.

Article 12 - Avocations (scuba, mountaineering, racing, skydiving, aviation).
Outcomes: flat extra, exclusion, or decline depending on frequency, depth/altitude,
certification and experience.

Article 13 - Foreign travel & residency. Assess country risk, duration, purpose,
political stability. Outcomes: Standard, extra premium, exclusion, or decline.

Article 14 - Substance use.
  Smoking: non-smoker -> Standard; occasional -> rating; regular -> smoker rates.
  Alcohol: assess consumption, treatment history, liver function.

Article 15 - Family history (heart disease, cancer, diabetes, genetic disorders).
Assess number of affected first-degree relatives and age at diagnosis. Multiple
first-degree relatives with early onset (<60) may attract a rating.

Article 16 - Reinsurance referral. Refer (facultative) when retention is exceeded,
a significant impairment exists, or special risks are involved.

Article 17 - Decision codes: STD, PREF, R25 (+25%), R50 (+50%), R100 (+100%),
FE (flat extra), EXCL (exclusion), POST (postpone), DECL (decline).

Article 19 - Automated underwriting. Straight-through to Standard when: age <= 45,
sum assured <= 500,000, BMI < 30, no medical disclosures. Refer to a human underwriter
when diabetes or cancer history is disclosed, or occupation class > 4.
"""
