"""
services/tender_service.py
----------------------------
Business logic for all tender-centric views in TenderWatch.

Responsibilities:
  - Search and filter the tender registry with multi-criteria support.
  - Return full tender detail with risk context and bid breakdown.
  - Provide bid analysis metrics (spread, competition level, price
    comparison) for the Tender Search detail panel and charts.
  - Return dataset-wide aggregations for the Dashboard.

Contract:
  - All public functions accept plain Python scalars and return
    DataFrames or plain dicts.
  - No Streamlit imports. No DB connection logic. No SQL.
  - Risk data is read from pre-computed DB rows; this service never
    calls detectors directly.
"""

import pandas as pd

from database import queries


# ─────────────────────────────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────────────────────────────

def search_tenders(
    keyword: str = "",
    region: str = "",
    category: str = "",
    department: str = "",
    risk_level: str = "",
    status: str = "Awarded",
    min_value: float = 0.0,
    max_value: float = 0.0,
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    """
    Multi-criteria tender search.

    All parameters are optional and combined with AND logic. Passing
    an empty string or 0 for any filter skips that constraint.

    Returns:
        DataFrame with tender rows enriched with awarded_vendor_name,
        total_risk_score, and risk_level from pre-computed assessments.
    """
    df = queries.search_tenders(
        keyword=keyword,
        region=region,
        category=category,
        department=department,
        risk_level=risk_level,
        status=status,
        min_value=min_value,
        max_value=max_value,
        date_from=date_from,
        date_to=date_to,
    )
    return df


def get_filter_options() -> dict:
    """
    Distinct values for every Tender Search dropdown filter.

    Returns:
        {
          "regions":     [...],
          "categories":  [...],
          "departments": [...],
          "risk_levels": [...],
          "statuses":    ["Awarded", "Open", "Cancelled"],
        }
    """
    return {
        "regions": queries.get_distinct_regions(),
        "categories": queries.get_distinct_categories(),
        "departments": queries.get_distinct_departments(),
        "risk_levels": queries.get_distinct_risk_levels(),
        "statuses": ["Awarded", "Open", "Cancelled"],
    }


# ─────────────────────────────────────────────────────────────────────
# TENDER DETAIL
# ─────────────────────────────────────────────────────────────────────

def get_tender_detail(tender_id: int) -> dict:
    """
    Returns a complete tender detail bundle as a plain dict, structured
    for the Tender Search detail panel and Investigation Center.

    Structure:
        {
          "tender":      { all tender fields + vendor name + risk summary },
          "bids":        DataFrame of all bids for this tender,
          "bid_stats":   { bid analysis metrics dict },
          "indicators":  DataFrame of all 5 detector results,
          "found":       bool
        }
    """
    tender_df = queries.get_tender_by_id(tender_id)
    if tender_df.empty:
        return {"found": False}

    tender = tender_df.iloc[0].to_dict()

    bids_df = queries.get_bids_for_tender(tender_id)
    bid_stats = _compute_bid_stats(tender, bids_df)
    indicators_df = queries.get_risk_indicators_for_tender(tender_id)

    return {
        "found": True,
        "tender": tender,
        "bids": bids_df,
        "bid_stats": bid_stats,
        "indicators": indicators_df,
    }


def get_tender_bids(tender_id: int) -> pd.DataFrame:
    """
    Returns just the bid records for a tender (no full detail bundle).
    Useful for chart functions that only need bid data.
    """
    return queries.get_bids_for_tender(tender_id)


def get_tender_indicators(tender_id: int) -> pd.DataFrame:
    """
    Returns just the risk indicator rows for a tender.
    Useful for building the risk explanation panel independently.
    """
    return queries.get_risk_indicators_for_tender(tender_id)


# ─────────────────────────────────────────────────────────────────────
# DASHBOARD AGGREGATIONS
# ─────────────────────────────────────────────────────────────────────

def get_dashboard_summary() -> dict:
    """
    Returns system-wide KPI metrics for the Dashboard header cards.

    Returns:
        {
          "total_tenders":    int,
          "total_vendors":    int,
          "high_risk_count":  int,   # score >= 3
          "critical_count":   int,   # score == 5
          "moderate_count":   int,   # score 1-2
          "low_risk_count":   int,   # score == 0
          "avg_risk_score":   float,
          "total_value":      float, # sum of all awarded_value
        }
    """
    all_tenders = queries.get_all_tenders()
    all_vendors = queries.get_all_vendors()

    if all_tenders.empty:
        return {
            "total_tenders": 0, "total_vendors": 0, "high_risk_count": 0,
            "critical_count": 0, "moderate_count": 0, "low_risk_count": 0,
            "avg_risk_score": 0.0, "total_value": 0.0,
        }

    scores = all_tenders["total_risk_score"]
    return {
        "total_tenders":   len(all_tenders),
        "total_vendors":   len(all_vendors),
        "high_risk_count": int((scores >= 3).sum()),
        "critical_count":  int((scores == 5).sum()),
        "moderate_count":  int(((scores >= 1) & (scores <= 2)).sum()),
        "low_risk_count":  int((scores == 0).sum()),
        "avg_risk_score":  round(float(scores.mean()), 2),
        "total_value":     round(float(all_tenders["awarded_value"].sum()), 2),
    }


def get_risk_distribution() -> pd.DataFrame:
    """
    Returns tender counts grouped by risk_level, ordered by severity.
    Used for the Dashboard risk distribution bar/pie chart.
    """
    all_tenders = queries.get_all_tenders()
    if all_tenders.empty:
        return pd.DataFrame(columns=["risk_level", "count"])

    dist = (
        all_tenders.groupby("risk_level")["tender_id"]
        .count()
        .reset_index()
        .rename(columns={"tender_id": "count"})
    )

    # Enforce severity order for chart display.
    order = ["Low Risk", "Moderate Risk", "High Risk", "Critical Risk"]
    dist["sort_key"] = dist["risk_level"].apply(
        lambda x: order.index(x) if x in order else 99
    )
    return dist.sort_values("sort_key").drop(columns="sort_key")


def get_tenders_by_region() -> pd.DataFrame:
    """
    Returns tender counts and average risk score per region.
    Used for the Dashboard regional breakdown chart.
    """
    all_tenders = queries.get_all_tenders()
    if all_tenders.empty:
        return pd.DataFrame(columns=["region", "count", "avg_risk_score"])

    return (
        all_tenders.groupby("region")
        .agg(count=("tender_id", "count"),
             avg_risk_score=("total_risk_score", "mean"))
        .reset_index()
        .round({"avg_risk_score": 2})
        .sort_values("count", ascending=False)
    )


def get_tenders_by_category() -> pd.DataFrame:
    """
    Returns tender counts and high-risk count per category.
    Used for the Dashboard category breakdown chart.
    """
    all_tenders = queries.get_all_tenders()
    if all_tenders.empty:
        return pd.DataFrame(columns=["category", "count", "high_risk_count"])

    category_df = (
        all_tenders.groupby("category")
        .agg(count=("tender_id", "count"),
             avg_risk_score=("total_risk_score", "mean"))
        .reset_index()
        .round({"avg_risk_score": 2})
        .sort_values("count", ascending=False)
    )

    high_risk = (
        all_tenders[all_tenders["total_risk_score"] >= 3]
        .groupby("category")["tender_id"]
        .count()
        .reset_index()
        .rename(columns={"tender_id": "high_risk_count"})
    )
    category_df = category_df.merge(high_risk, on="category", how="left")
    category_df["high_risk_count"] = category_df["high_risk_count"].fillna(0).astype(int)
    return category_df


def get_monthly_trend() -> pd.DataFrame:
    """
    Returns monthly tender count and average risk score time-series.
    Used for the Dashboard trend chart.
    """
    all_tenders = queries.get_all_tenders()
    if all_tenders.empty:
        return pd.DataFrame(columns=["month", "count", "avg_risk_score"])

    all_tenders["publish_date"] = pd.to_datetime(all_tenders["publish_date"])
    all_tenders["month"] = all_tenders["publish_date"].dt.to_period("M").astype(str)

    return (
        all_tenders.groupby("month")
        .agg(count=("tender_id", "count"),
             avg_risk_score=("total_risk_score", "mean"))
        .reset_index()
        .round({"avg_risk_score": 2})
        .sort_values("month")
    )


# ─────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────

def _compute_bid_stats(tender: dict, bids_df: pd.DataFrame) -> dict:
    """
    Computes bid analysis metrics for the tender detail panel.

    Returns a dict with:
        bidder_count, lowest_bid, highest_bid, avg_bid,
        bid_spread_pct, winning_bid, overage_pct,
        competition_level ("High" / "Moderate" / "Low" / "None")
    """
    if bids_df.empty:
        return {
            "bidder_count": 0,
            "lowest_bid": None,
            "highest_bid": None,
            "avg_bid": None,
            "bid_spread_pct": None,
            "winning_bid": tender.get("awarded_value"),
            "overage_pct": _overage_pct(tender),
            "competition_level": "None",
        }

    bidder_count = bids_df["vendor_id"].nunique()
    amounts = bids_df["bid_amount"]
    avg_bid = float(amounts.mean())
    lowest_bid = float(amounts.min())
    highest_bid = float(amounts.max())
    spread_pct = round(
        ((highest_bid - lowest_bid) / avg_bid * 100), 2
    ) if avg_bid > 0 else 0.0

    if bidder_count >= 5:
        competition_level = "High"
    elif bidder_count >= 3:
        competition_level = "Moderate"
    elif bidder_count == 2:
        competition_level = "Low"
    else:
        competition_level = "None"

    return {
        "bidder_count":      bidder_count,
        "lowest_bid":        round(lowest_bid, 2),
        "highest_bid":       round(highest_bid, 2),
        "avg_bid":           round(avg_bid, 2),
        "bid_spread_pct":    spread_pct,
        "winning_bid":       tender.get("awarded_value"),
        "overage_pct":       _overage_pct(tender),
        "competition_level": competition_level,
    }


def _overage_pct(tender: dict) -> float | None:
    """Computes awarded_value vs estimated_value overage as a percentage."""
    estimated = tender.get("estimated_value")
    awarded = tender.get("awarded_value")
    if not estimated or not awarded or estimated == 0:
        return None
    return round(((awarded - estimated) / estimated) * 100, 1)
