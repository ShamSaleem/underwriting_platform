"""Excel intake: build a downloadable template, and parse an uploaded workbook into
underwriting requests. One row = one applicant (so a sheet can hold a single person
or hundreds). List fields accept multiple entries separated by ';'. Medical
disclosures use 'condition | details ; condition | details'.
"""
from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook, load_workbook

# Canonical columns. Order matters only for the template's readability.
COLUMNS = [
    "applicant_type",            # individual | group
    "product",                   # individual_life, group_life, ...
    "sum_assured",
    "annual_income",
    "existing_life_cover",
    # ---- individual ----
    "full_name",
    "age",
    "sex",                       # male | female | other
    "smoking",                   # non_smoker | occasional | regular
    "occupation",
    "occupation_class",          # 1-6 (leave blank to let the AI infer)
    "height_cm",
    "weight_kg",
    "hba1c",
    "systolic_bp",
    "diastolic_bp",
    "avocations",                # 'scuba diving; skydiving'
    "foreign_travel",            # 'Nigeria 3 months/yr'
    "family_history",            # 'father MI at 55'
    "disclosures",               # 'Type 2 diabetes | on metformin ; Asthma | mild'
    # ---- group ----
    "company_name",
    "industry",
    "num_employees",
    "average_age",
    "occupation_classes",        # '1,4,5'
    "free_cover_limit_requested",
    "notes",
]

_EXAMPLE_ROWS = [
    {
        "applicant_type": "individual", "product": "individual_life", "sum_assured": 300000,
        "annual_income": 80000, "existing_life_cover": 0,
        "full_name": "Aisha Bello", "age": 34, "sex": "female", "smoking": "non_smoker",
        "occupation": "software engineer", "occupation_class": 1,
        "height_cm": 165, "weight_kg": 60,
    },
    {
        "applicant_type": "individual", "product": "individual_life", "sum_assured": 750000,
        "annual_income": 90000, "existing_life_cover": 200000,
        "full_name": "John Carter", "age": 47, "sex": "male", "smoking": "occasional",
        "occupation": "warehouse supervisor", "occupation_class": 4,
        "height_cm": 178, "weight_kg": 104, "hba1c": 7.4, "systolic_bp": 148, "diastolic_bp": 92,
        "avocations": "recreational scuba diving to 30m",
        "family_history": "father had a heart attack at 55",
        "disclosures": "Type 2 diabetes | diagnosed 4 years ago, on metformin",
    },
    {
        "applicant_type": "group", "product": "group_life", "sum_assured": 5000000,
        "company_name": "Northwind Logistics", "industry": "freight",
        "num_employees": 8, "average_age": 51, "occupation_classes": "1,4,5",
        "free_cover_limit_requested": 300000, "notes": "new scheme, voluntary participation",
    },
]


def build_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "applicants"
    ws.append(COLUMNS)
    for ex in _EXAMPLE_ROWS:
        ws.append([ex.get(c, "") for c in COLUMNS])
    # widen columns a little
    for i, c in enumerate(COLUMNS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(12, len(c) + 2)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _num(v: Any):
    if v in (None, ""):
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return None


def _list(v: Any) -> list[str]:
    if not v:
        return []
    return [p.strip() for p in str(v).replace("\n", ";").split(";") if p.strip()]


def _row_to_request(row: dict[str, Any]) -> dict[str, Any]:
    atype = (str(row.get("applicant_type") or "individual")).strip().lower()
    req: dict[str, Any] = {
        "applicant_type": atype,
        "product": (str(row.get("product") or ("group_life" if atype == "group" else "individual_life"))).strip(),
        "sum_assured": _num(row.get("sum_assured")) or 0,
        "financials": {
            "annual_income": _num(row.get("annual_income")) or 0,
            "existing_life_cover": _num(row.get("existing_life_cover")) or 0,
        },
    }
    if atype == "group":
        req["group"] = {
            "company_name": str(row.get("company_name") or "Unnamed Co"),
            "industry": str(row.get("industry") or ""),
            "num_employees": _num(row.get("num_employees")) or 1,
            "average_age": _num(row.get("average_age")),
            "occupation_classes": [int(x) for x in _list(row.get("occupation_classes")) if x.lstrip("-").isdigit()],
            "free_cover_limit_requested": _num(row.get("free_cover_limit_requested")),
            "notes": str(row.get("notes") or "") or None,
        }
    else:
        disclosures = []
        for item in _list(row.get("disclosures")):
            cond, _, det = item.partition("|")
            disclosures.append({"condition": cond.strip(), "details": det.strip() or None})
        req["individual"] = {
            "full_name": str(row.get("full_name") or "Applicant"),
            "age": _num(row.get("age")) or 0,
            "sex": str(row.get("sex") or "other").strip().lower(),
            "smoking": str(row.get("smoking") or "non_smoker").strip().lower(),
            "occupation": str(row.get("occupation") or ""),
            "occupation_class": _num(row.get("occupation_class")),
            "avocations": _list(row.get("avocations")),
            "foreign_travel": _list(row.get("foreign_travel")),
            "family_history": _list(row.get("family_history")),
            "medical_disclosures": disclosures,
            "metrics": {
                "height_cm": _num(row.get("height_cm")),
                "weight_kg": _num(row.get("weight_kg")),
                "hba1c": _num(row.get("hba1c")),
                "systolic_bp": _num(row.get("systolic_bp")),
                "diastolic_bp": _num(row.get("diastolic_bp")),
            },
        }
    return req


def parse_workbook(data: bytes) -> list[dict[str, Any]]:
    """Return a list of underwriting-request dicts, one per non-empty row."""
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    try:
        header = [str(h).strip() if h is not None else "" for h in next(rows)]
    except StopIteration:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        if r is None or all(c in (None, "") for c in r):
            continue
        record = {header[i]: r[i] for i in range(min(len(header), len(r)))}
        out.append(_row_to_request(record))
    return out
