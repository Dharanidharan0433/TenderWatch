"""
database/queries.py
---------------------
Centralized, parametrized SQL query functions for TenderWatch.

All database reads and writes performed by the service layer go through
this module -- detectors, services, and scoring never open sqlite3
connections directly. This single-point-of-access approach means:

  - SQL is never scattered across business-logic modules.
  - Column names and table joins are auditable in one file.
  - Any query can be optimized here without touching service code.

Every read function returns a pandas DataFrame (not raw sqlite3 Rows)
because services and detectors already work in pandas idioms. Write
functions return the newly assigned primary key (lastrowid) or None.
"""

import pandas as pd

from database.db import execute_query, execute_write, execute_many


# ─────────────────────────────────────────────────────────────────────
# VENDORS
# ─────────────────────────────────────────────────────────────────────

def get_all_vendors() -> pd.DataFrame:
    """Returns all vendor records as a DataFrame."""
    rows = execute_query("SELECT * FROM vendors ORDER BY vendor_name;")
    return pd.DataFrame(rows)


def get_vendor_by_id(vendor_id: int) -> pd.DataFrame:
    """Returns the single vendor matching vendor_id (empty DF if not found)."""
    rows = execute_query(
        "SELECT * FROM vendors WHERE vendor_id = ?;",
        (vendor_id,),
    )
    return pd.DataFrame(rows)


def search_vendors(
    name: str = "",
    region: str = "",
    category: str = "",
) -> pd.DataFrame:
    """
    Full-text-style vendor search with optional filters.

    All filters are ANDed together. Passing an empty string for any
    filter skips that constraint entirely (i.e. returns all values
    for that column).
    """
    clauses = []
    params = []

    if name:
        clauses.append("LOWER(vendor_name) LIKE LOWER(?)")
        params.append(f"%{name}%")
    if region:
        clauses.append("region = ?")
        params.append(region)
    if category:
        clauses.append("category_specialization = ?")
        params.append(category)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM vendors {where} ORDER BY vendor_name;"
    rows = execute_query(sql, tuple(params))
    return pd.DataFrame(rows)


def get_vendor_tender_history(vendor_id: int) -> pd.DataFrame:
    """
    All tenders where vendor_id was the awarded vendor, joined with
    their risk assessment summary for display in vendor profiles.
    """
    rows = execute_query(
        """
        SELECT
            t.tender_id,
            t.tender_reference,
            t.title,
            t.category,
            t.region,
            t.department,
            t.estimated_value,
            t.awarded_value,
            t.publish_date,
            t.submission_deadline,
            t.tender_window_days,
            t.status,
            COALESCE(ra.total_risk_score, 0)  AS total_risk_score,
            COALESCE(ra.risk_level, 'Low Risk') AS risk_level,
            ra.assessment_date
        FROM tenders t
        LEFT JOIN risk_assessments ra ON ra.tender_id = t.tender_id
        WHERE t.awarded_vendor_id = ?
        ORDER BY t.publish_date DESC;
        """,
        (vendor_id,),
    )
    return pd.DataFrame(rows)


def get_vendor_bid_history(vendor_id: int) -> pd.DataFrame:
    """
    All bids submitted by vendor_id (winning and losing), joined with
    tender metadata for context in bid-analysis views.
    """
    rows = execute_query(
        """
        SELECT
            b.bid_id,
            b.tender_id,
            b.bid_amount,
            b.bid_date,
            b.is_winning_bid,
            t.tender_reference,
            t.title,
            t.category,
            t.region,
            t.estimated_value,
            t.awarded_value
        FROM bids b
        JOIN tenders t ON t.tender_id = b.tender_id
        WHERE b.vendor_id = ?
        ORDER BY b.bid_date DESC;
        """,
        (vendor_id,),
    )
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────
# TENDERS
# ─────────────────────────────────────────────────────────────────────

def get_all_tenders() -> pd.DataFrame:
    """
    Returns all tenders joined with their risk assessment summary.
    Used by investigation_service and dashboard aggregations.
    """
    rows = execute_query(
        """
        SELECT
            t.*,
            v.vendor_name             AS awarded_vendor_name,
            COALESCE(ra.total_risk_score, 0)  AS total_risk_score,
            COALESCE(ra.risk_level, 'Low Risk') AS risk_level,
            ra.assessment_date
        FROM tenders t
        LEFT JOIN vendors v  ON v.vendor_id  = t.awarded_vendor_id
        LEFT JOIN risk_assessments ra ON ra.tender_id = t.tender_id
        ORDER BY t.publish_date DESC;
        """
    )
    return pd.DataFrame(rows)


def get_tender_by_id(tender_id: int) -> pd.DataFrame:
    """Full tender detail row plus risk summary for a single tender."""
    rows = execute_query(
        """
        SELECT
            t.*,
            v.vendor_name             AS awarded_vendor_name,
            v.registration_number     AS awarded_vendor_reg,
            v.region                  AS awarded_vendor_region,
            COALESCE(ra.total_risk_score, 0)  AS total_risk_score,
            COALESCE(ra.risk_level, 'Low Risk') AS risk_level,
            ra.assessment_id,
            ra.assessment_date
        FROM tenders t
        LEFT JOIN vendors v  ON v.vendor_id  = t.awarded_vendor_id
        LEFT JOIN risk_assessments ra ON ra.tender_id = t.tender_id
        WHERE t.tender_id = ?;
        """,
        (tender_id,),
    )
    return pd.DataFrame(rows)


def search_tenders(
    keyword: str = "",
    region: str = "",
    category: str = "",
    department: str = "",
    risk_level: str = "",
    status: str = "",
    min_value: float = 0.0,
    max_value: float = 0.0,
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    """
    Multi-filter tender search.  All filters are optional (ANDed).
    max_value=0 means no upper bound.
    """
    clauses = []
    params: list = []

    if keyword:
        clauses.append(
            "(LOWER(t.title) LIKE LOWER(?) OR LOWER(t.tender_reference) LIKE LOWER(?))"
        )
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if region:
        clauses.append("t.region = ?")
        params.append(region)
    if category:
        clauses.append("t.category = ?")
        params.append(category)
    if department:
        clauses.append("t.department = ?")
        params.append(department)
    if status:
        clauses.append("t.status = ?")
        params.append(status)
    if risk_level:
        clauses.append("ra.risk_level = ?")
        params.append(risk_level)
    if min_value > 0:
        clauses.append("t.estimated_value >= ?")
        params.append(min_value)
    if max_value > 0:
        clauses.append("t.estimated_value <= ?")
        params.append(max_value)
    if date_from:
        clauses.append("t.publish_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("t.publish_date <= ?")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT
            t.*,
            v.vendor_name AS awarded_vendor_name,
            COALESCE(ra.total_risk_score, 0)  AS total_risk_score,
            COALESCE(ra.risk_level, 'Low Risk') AS risk_level
        FROM tenders t
        LEFT JOIN vendors v  ON v.vendor_id  = t.awarded_vendor_id
        LEFT JOIN risk_assessments ra ON ra.tender_id = t.tender_id
        {where}
        ORDER BY t.publish_date DESC;
    """
    rows = execute_query(sql, tuple(params))
    return pd.DataFrame(rows)


def get_bids_for_tender(tender_id: int) -> pd.DataFrame:
    """All bids submitted against a specific tender, with vendor name."""
    rows = execute_query(
        """
        SELECT
            b.bid_id,
            b.vendor_id,
            v.vendor_name,
            b.bid_amount,
            b.bid_date,
            b.is_winning_bid
        FROM bids b
        JOIN vendors v ON v.vendor_id = b.vendor_id
        WHERE b.tender_id = ?
        ORDER BY b.bid_amount ASC;
        """,
        (tender_id,),
    )
    return pd.DataFrame(rows)


def get_all_bids() -> pd.DataFrame:
    """Full bids table — used by detectors and scoring service."""
    rows = execute_query("SELECT * FROM bids;")
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────
# RISK ASSESSMENTS & INDICATORS
# ─────────────────────────────────────────────────────────────────────

def get_risk_indicators_for_tender(tender_id: int) -> pd.DataFrame:
    """
    All 5 detector results (triggered and not) for a given tender,
    joined through risk_assessments -> risk_indicators.
    """
    rows = execute_query(
        """
        SELECT
            ri.indicator_id,
            ri.detector_name,
            ri.triggered,
            ri.explanation,
            ri.supporting_metric,
            ra.total_risk_score,
            ra.risk_level,
            ra.assessment_date
        FROM risk_indicators ri
        JOIN risk_assessments ra ON ra.assessment_id = ri.assessment_id
        WHERE ra.tender_id = ?
        ORDER BY ri.triggered DESC, ri.detector_name;
        """,
        (tender_id,),
    )
    return pd.DataFrame(rows)


def get_all_risk_assessments() -> pd.DataFrame:
    """All assessment summary rows — one per tender."""
    rows = execute_query(
        """
        SELECT ra.*, t.tender_reference, t.category, t.region
        FROM risk_assessments ra
        JOIN tenders t ON t.tender_id = ra.tender_id
        ORDER BY ra.total_risk_score DESC;
        """
    )
    return pd.DataFrame(rows)


def insert_risk_assessment(tender_id: int, total_risk_score: int, risk_level: str) -> int:
    """Inserts a risk_assessments row and returns its new assessment_id."""
    return execute_write(
        """
        INSERT INTO risk_assessments (tender_id, total_risk_score, risk_level)
        VALUES (?, ?, ?);
        """,
        (tender_id, total_risk_score, risk_level),
    )


def insert_risk_indicators_bulk(indicator_rows: list[tuple]) -> None:
    """
    Bulk-inserts risk_indicators rows.

    Each tuple: (assessment_id, detector_name, triggered, explanation, supporting_metric)
    """
    execute_many(
        """
        INSERT INTO risk_indicators
            (assessment_id, detector_name, triggered, explanation, supporting_metric)
        VALUES (?, ?, ?, ?, ?);
        """,
        indicator_rows,
    )


def risk_assessments_exist() -> bool:
    """Returns True if any risk_assessments rows have been persisted."""
    rows = execute_query("SELECT COUNT(*) AS cnt FROM risk_assessments;")
    return rows[0]["cnt"] > 0


def delete_all_risk_data() -> None:
    """Wipes risk_indicators and risk_assessments for a clean re-score."""
    execute_write("DELETE FROM risk_indicators;")
    execute_write("DELETE FROM risk_assessments;")


# ─────────────────────────────────────────────────────────────────────
# REFERENCE / FILTER LISTS  (for UI dropdowns)
# ─────────────────────────────────────────────────────────────────────

def get_distinct_regions() -> list[str]:
    rows = execute_query("SELECT DISTINCT region FROM tenders ORDER BY region;")
    return [r["region"] for r in rows]


def get_distinct_categories() -> list[str]:
    rows = execute_query("SELECT DISTINCT category FROM tenders ORDER BY category;")
    return [r["category"] for r in rows]


def get_distinct_departments() -> list[str]:
    rows = execute_query("SELECT DISTINCT department FROM tenders ORDER BY department;")
    return [r["department"] for r in rows]


def get_distinct_risk_levels() -> list[str]:
    """Returns risk level options in severity order."""
    return ["Low Risk", "Moderate Risk", "High Risk", "Critical Risk"]
