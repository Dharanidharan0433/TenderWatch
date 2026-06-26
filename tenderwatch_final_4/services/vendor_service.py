"""
services/vendor_service.py
----------------------------
Business logic for all vendor-centric views in TenderWatch.

Responsibilities:
  - Search and filter the vendor registry.
  - Build a complete vendor profile (identity + participation stats +
    risk summary) suitable for the Vendor Search detail panel.
  - Return a vendor's full tender history with risk context.
  - Return bid-level history showing wins vs. losses.
  - Compute aggregated statistics (win rate, average risk score, etc.)
    displayed in the vendor profile header cards.

Contract:
  - All public functions accept plain Python scalars (filter strings,
    vendor IDs) and return pandas DataFrames or plain dicts.
  - No Streamlit imports. No DB connection logic. No SQL.
  - Risk data is READ from pre-computed DB rows (written by
    scoring_service.py); this service never calls detectors directly.
"""

import pandas as pd

from database import queries


# ─────────────────────────────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────────────────────────────

def search_vendors(
    name: str = "",
    region: str = "",
    category: str = "",
) -> pd.DataFrame:
    """
    Returns vendors matching all supplied filters (any filter omitted
    or passed as "" is ignored).

    Enriches the raw vendor list with participation stats so the search
    results table can show "tenders won / participated" without needing
    a separate round-trip.

    Args:
        name:     Substring match against vendor_name (case-insensitive).
        region:   Exact match against vendor.region.
        category: Exact match against vendor.category_specialization.

    Returns:
        DataFrame with columns: vendor_id, vendor_name,
        registration_number, region, category_specialization,
        date_registered, tenders_participated, tenders_won, win_rate,
        avg_risk_score, high_risk_count.
    """
    vendors_df = queries.search_vendors(name=name, region=region, category=category)
    if vendors_df.empty:
        return vendors_df

    # Enrich each vendor with participation/risk summary.
    summary = _build_participation_summary()
    vendors_df = vendors_df.merge(summary, on="vendor_id", how="left")

    # Fill missing summary stats for vendors with zero participation.
    fill_cols = ["tenders_participated", "tenders_won", "win_rate",
                 "avg_risk_score", "high_risk_count"]
    for col in fill_cols:
        if col in vendors_df.columns:
            vendors_df[col] = vendors_df[col].fillna(0)

    return vendors_df


def get_all_vendor_options() -> list[dict]:
    """
    Returns (vendor_id, vendor_name) pairs for UI select boxes.
    Sorted alphabetically.
    """
    df = queries.get_all_vendors()
    if df.empty:
        return []
    return df[["vendor_id", "vendor_name"]].to_dict("records")


# ─────────────────────────────────────────────────────────────────────
# VENDOR PROFILE
# ─────────────────────────────────────────────────────────────────────

def get_vendor_profile(vendor_id: int) -> dict:
    """
    Returns a complete vendor profile as a plain dict, structured for
    the Vendor Search detail panel.

    Structure:
        {
          "identity":     { vendor fields ... },
          "stats":        { tenders_participated, tenders_won, win_rate,
                            avg_risk_score, high_risk_count,
                            critical_risk_count, total_bid_value },
          "risk_summary": { risk_level_distribution dict },
          "found":        bool   # False if vendor_id doesn't exist
        }
    """
    vendor_df = queries.get_vendor_by_id(vendor_id)
    if vendor_df.empty:
        return {"found": False}

    vendor = vendor_df.iloc[0].to_dict()

    # Tender history gives us the raw material for all stats.
    history_df = queries.get_vendor_tender_history(vendor_id)
    bids_df = queries.get_vendor_bid_history(vendor_id)

    stats = _compute_vendor_stats(vendor_id, history_df, bids_df)
    risk_summary = _compute_risk_distribution(history_df)

    return {
        "found": True,
        "identity": vendor,
        "stats": stats,
        "risk_summary": risk_summary,
    }


# ─────────────────────────────────────────────────────────────────────
# VENDOR HISTORY
# ─────────────────────────────────────────────────────────────────────

def get_vendor_tender_history(vendor_id: int) -> pd.DataFrame:
    """
    Returns the full list of tenders awarded to this vendor, with
    their risk assessment context.

    Columns include: tender_id, tender_reference, title, category,
    region, department, estimated_value, awarded_value,
    publish_date, submission_deadline, status,
    total_risk_score, risk_level.
    """
    df = queries.get_vendor_tender_history(vendor_id)
    if df.empty:
        return df

    # Compute overage_pct so the history table can show it as a column.
    df["overage_pct"] = (
        (df["awarded_value"] - df["estimated_value"])
        / df["estimated_value"].replace(0, float("nan"))
        * 100
    ).round(1)

    return df


def get_vendor_bid_history(vendor_id: int) -> pd.DataFrame:
    """
    Returns the full bid-level history for this vendor (winning + losing
    bids), enriched with whether they won each tender.

    Used by vendor_charts.py to plot bid amounts over time vs. award
    outcomes.
    """
    return queries.get_vendor_bid_history(vendor_id)


def get_vendor_win_rate_over_time(vendor_id: int) -> pd.DataFrame:
    """
    Returns a monthly time-series of bids submitted and bids won for
    this vendor — input for the win-rate trend chart.

    Returns DataFrame with columns: month, bids_submitted, bids_won,
    win_rate_pct.
    """
    bids_df = queries.get_vendor_bid_history(vendor_id)
    if bids_df.empty:
        return pd.DataFrame(
            columns=["month", "bids_submitted", "bids_won", "win_rate_pct"]
        )

    bids_df["bid_date"] = pd.to_datetime(bids_df["bid_date"])
    bids_df["month"] = bids_df["bid_date"].dt.to_period("M").astype(str)

    monthly = (
        bids_df.groupby("month")
        .agg(
            bids_submitted=("bid_id", "count"),
            bids_won=("is_winning_bid", "sum"),
        )
        .reset_index()
    )
    monthly["win_rate_pct"] = (
        (monthly["bids_won"] / monthly["bids_submitted"]) * 100
    ).round(1)

    return monthly.sort_values("month")


def get_vendor_risk_trend(vendor_id: int) -> pd.DataFrame:
    """
    Returns a chronological list of the vendor's won tenders with their
    risk scores — used to plot whether risk scores are trending up over
    time (a pattern of concern for investigators).

    Returns DataFrame with columns: publish_date, tender_reference,
    total_risk_score, risk_level.
    """
    history_df = queries.get_vendor_tender_history(vendor_id)
    if history_df.empty:
        return pd.DataFrame(
            columns=["publish_date", "tender_reference",
                     "total_risk_score", "risk_level"]
        )

    return (
        history_df[["publish_date", "tender_reference",
                     "total_risk_score", "risk_level"]]
        .sort_values("publish_date")
    )


# ─────────────────────────────────────────────────────────────────────
# REFERENCE LISTS (for UI dropdowns)
# ─────────────────────────────────────────────────────────────────────

def get_filter_options() -> dict:
    """
    Returns all distinct regions and categories present in the vendor
    table — used to populate Vendor Search filter dropdowns.
    """
    all_vendors = queries.get_all_vendors()
    regions = sorted(all_vendors["region"].dropna().unique().tolist()) if not all_vendors.empty else []
    categories = sorted(all_vendors["category_specialization"].dropna().unique().tolist()) if not all_vendors.empty else []
    return {"regions": regions, "categories": categories}


# ─────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────

def _build_participation_summary() -> pd.DataFrame:
    """
    Computes per-vendor participation and risk aggregates from the
    tenders + risk_assessments tables.

    Returns DataFrame keyed on vendor_id with columns:
    tenders_participated, tenders_won, win_rate, avg_risk_score,
    high_risk_count.

    "Participated" = submitted at least one bid (from the bids table).
    "Won" = is the awarded_vendor_id on a tender.
    """
    all_tenders = queries.get_all_tenders()
    all_bids = queries.get_all_bids()

    if all_tenders.empty:
        return pd.DataFrame(columns=["vendor_id", "tenders_participated",
                                     "tenders_won", "win_rate",
                                     "avg_risk_score", "high_risk_count"])

    # Tenders won per vendor.
    won = (
        all_tenders[all_tenders["awarded_vendor_id"].notna()]
        .groupby("awarded_vendor_id")
        .agg(
            tenders_won=("tender_id", "count"),
            avg_risk_score=("total_risk_score", "mean"),
        )
        .reset_index()
        .rename(columns={"awarded_vendor_id": "vendor_id"})
    )
    won["avg_risk_score"] = won["avg_risk_score"].round(2)

    # High-risk tender count per vendor (risk_score >= 3).
    high_risk = (
        all_tenders[
            (all_tenders["awarded_vendor_id"].notna())
            & (all_tenders["total_risk_score"] >= 3)
        ]
        .groupby("awarded_vendor_id")["tender_id"]
        .count()
        .reset_index()
        .rename(columns={"awarded_vendor_id": "vendor_id",
                         "tender_id": "high_risk_count"})
    )

    # Tenders participated in (bids submitted, may differ from won).
    participated = (
        all_bids.groupby("vendor_id")["tender_id"]
        .nunique()
        .reset_index()
        .rename(columns={"tender_id": "tenders_participated"})
    )

    summary = won.merge(participated, on="vendor_id", how="outer")
    summary = summary.merge(high_risk, on="vendor_id", how="left")
    summary = summary.fillna(0)

    summary["tenders_won"] = summary["tenders_won"].astype(int)
    summary["tenders_participated"] = summary["tenders_participated"].astype(int)
    summary["high_risk_count"] = summary["high_risk_count"].astype(int)
    summary["win_rate"] = (
        (summary["tenders_won"] / summary["tenders_participated"].replace(0, float("nan")))
        * 100
    ).round(1).fillna(0)

    return summary


def _compute_vendor_stats(
    vendor_id: int,
    history_df: pd.DataFrame,
    bids_df: pd.DataFrame,
) -> dict:
    """
    Computes the header-card metrics for a single vendor profile page.
    """
    tenders_won = len(history_df)
    tenders_participated = bids_df["tender_id"].nunique() if not bids_df.empty else 0
    win_rate = round((tenders_won / tenders_participated * 100), 1) if tenders_participated > 0 else 0.0

    avg_risk = round(history_df["total_risk_score"].mean(), 2) if not history_df.empty else 0.0
    high_risk_count = int((history_df["total_risk_score"] >= 3).sum()) if not history_df.empty else 0
    critical_risk_count = int((history_df["total_risk_score"] == 5).sum()) if not history_df.empty else 0

    total_bid_value = round(bids_df["bid_amount"].sum(), 2) if not bids_df.empty else 0.0
    total_contract_value = round(history_df["awarded_value"].sum(), 2) if not history_df.empty else 0.0

    return {
        "tenders_participated": tenders_participated,
        "tenders_won": tenders_won,
        "win_rate": win_rate,
        "avg_risk_score": avg_risk,
        "high_risk_count": high_risk_count,
        "critical_risk_count": critical_risk_count,
        "total_bid_value": total_bid_value,
        "total_contract_value": total_contract_value,
    }


def _compute_risk_distribution(history_df: pd.DataFrame) -> dict:
    """
    Returns a dict mapping risk level label -> count, for the
    risk distribution mini-chart on the vendor profile.
    """
    if history_df.empty:
        return {
            "Low Risk": 0,
            "Moderate Risk": 0,
            "High Risk": 0,
            "Critical Risk": 0,
        }

    dist = history_df["risk_level"].value_counts().to_dict()
    # Ensure all four levels are present even if count is 0.
    for level in ["Low Risk", "Moderate Risk", "High Risk", "Critical Risk"]:
        dist.setdefault(level, 0)

    return dist
