"""Documentation requirements checklist, driven by the manual (Articles 3, 4, 16).

Used by the staged intake wizard: before the file can advance past the documents
stage it must carry the evidence the manual mandates for this case. Kept on the
backend (not duplicated in the frontend) so the checklist and the final decision
cite the same source of truth as `tables.evidence_required`.
"""
from __future__ import annotations

from .tables import evidence_required

# Treaty retention assumption for the sample manual (Article 16). Cover at or above
# this is taken to exceed retention and trigger a facultative referral pack.
RETENTION_LIMIT = 1_000_000

# Cover above this needs fuller financial substantiation (Article 3).
HIGH_COVER = 500_000


def _item(key: str, label: str, required: bool) -> dict:
    return {"key": key, "label": label, "required": required}


def document_requirements(
    applicant_type: str,
    sum_assured: float,
    annual_income: float = 0.0,
) -> list[dict]:
    """Return checklist groups: [{title, article, note, items:[{key,label,required}]}].

    `required` items gate progression in the wizard; optional items are advisory.
    """
    sum_assured = float(sum_assured or 0)
    high_cover = sum_assured > HIGH_COVER
    over_retention = sum_assured > RETENTION_LIMIT
    groups: list[dict] = []

    # ---- Article 4: medical evidence scales with sum assured -----------------
    groups.append(
        {
            "title": "Medical evidence",
            "article": "Article 4",
            "note": "Mandatory evidence for this sum assured band.",
            "items": [
                _item(f"med:{i}", label, True)
                for i, label in enumerate(evidence_required(sum_assured))
            ],
        }
    )

    # ---- Article 3: financial justification documents ------------------------
    if applicant_type == "group":
        fin_items = [
            _item("fin:audited", "Audited financial statements", True),
            _item("fin:census", "Scheme membership / census data", True),
            _item("fin:bank", "Company bank statements", over_retention),
        ]
    else:
        fin_items = [
            _item("fin:salary", "Salary slips (last 3 months)", True),
            _item("fin:tax", "Tax returns (last 2 years)", high_cover),
            _item("fin:bank", "Bank statements (last 6 months)", high_cover),
            _item("fin:audited", "Audited financials (business owners)", over_retention),
        ]
    groups.append(
        {
            "title": "Financial documentation",
            "article": "Article 3",
            "note": "Substantiates the economic justification for the cover.",
            "items": fin_items,
        }
    )

    # ---- Article 16: reinsurance referral pack once retention is exceeded -----
    if over_retention:
        groups.append(
            {
                "title": "Reinsurance referral pack",
                "article": "Article 16",
                "note": "Cover exceeds treaty retention — facultative referral required.",
                "items": [
                    _item("ref:proposal", "Completed proposal form", True),
                    _item("ref:medical", "Medical reports", True),
                    _item("ref:financial", "Financial evidence", True),
                    _item("ref:summary", "Underwriter summary", True),
                ],
            }
        )

    return groups
