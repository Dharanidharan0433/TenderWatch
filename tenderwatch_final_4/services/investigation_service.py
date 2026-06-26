"""
services/investigation_service.py
------------------------------------
Business logic for the Investigation Center — the prioritized case
queue that helps vigilance officers and auditors decide which tenders
to examine first.

Responsibilities:
  - Rank tenders by risk severity for the investigator priority queue.
  - Generate explainable investigation summaries (what triggered, why
    it matters, what to look at).
  - Produce actionable, non-accusatory investigation recommendations.
  - Provide vendor-level investigation context when a specific vendor
    is under review.

CRITICAL — language discipline:
  Every string this module produces must stay within the approved
  terminology. This module NEVER uses: "fraud", "corrupt*", "criminal",
  "illegal", "theft". It ALWAYS uses: "procurement risk", "risk
  indicator", "procurement anomaly", "suspicious pattern",
  "investigation recommended", "audit recommended".
"""

from __future__ import annotations

import pandas as pd

from database import queries


# ─────────────────────────────────────────────────────────────────────
# RISK LEVEL CONSTANTS
# ─────────────────────────────────────────────────────────────────────

RISK_LEVEL_ORDER = {
    "Critical Risk": 4,
    "High Risk":     3,
    "Moderate Risk": 2,
    "Low Risk":      1,
}

HIGH_RISK_THRESHOLD = 3   # total_risk_score >= this is "High Risk" or above


# ─────────────────────────────────────────────────────────────────────
# CASE QUEUE (Investigation Center main list)
# ─────────────────────────────────────────────────────────────────────

def get_investigation_queue(
    risk_level_filter: str = "",
    region: str = "",
    category: str = "",
    department: str = "",
    date_from: str = "",
    date_to: str = "",
    sort_by: str = "risk_score",
    limit: int = 200,
) -> pd.DataFrame:
    """
    Returns a prioritized list of tenders for the Investigation Center.

    By default returns all tenders with total_risk_score >= 1 (i.e.
    at least one indicator triggered), sorted by risk severity then
    contract value. Investigators can filter this list further to
    focus their workload.

    Args:
        risk_level_filter: One of "Moderate Risk", "High Risk",
            "Critical Risk", or "" (all non-zero-risk tenders).
        region, category, department: Optional exact-match filters.
        date_from, date_to: ISO date strings ("YYYY-MM-DD") for
            publish_date filtering.
        sort_by: "risk_score" (default) | "value" | "date".
        limit: Maximum rows to return.

    Returns:
        DataFrame with columns: tender_id, tender_reference, title,
        category, region, department, estimated_value, awarded_value,
        awarded_vendor_name, publish_date, total_risk_score, risk_level,
        triggered_count, investigation_priority.
    """
    all_tenders = queries.get_all_tenders()
    if all_tenders.empty:
        return pd.DataFrame()

    # Start with only tenders that have at least one triggered indicator.
    df = all_tenders[all_tenders["total_risk_score"] >= 1].copy()

    # Apply filters.
    if risk_level_filter:
        df = df[df["risk_level"] == risk_level_filter]
    if region:
        df = df[df["region"] == region]
    if category:
        df = df[df["category"] == category]
    if department:
        df = df[df["department"] == department]
    if date_from:
        df = df[df["publish_date"] >= date_from]
    if date_to:
        df = df[df["publish_date"] <= date_to]

    if df.empty:
        return df

    # Sort.
    if sort_by == "value":
        df = df.sort_values(
            ["total_risk_score", "awarded_value"],
            ascending=[False, False],
        )
    elif sort_by == "date":
        df = df.sort_values(
            ["total_risk_score", "publish_date"],
            ascending=[False, False],
        )
    else:
        # Default: risk score first, then contract value as tiebreaker
        # (high-value tenders with the same risk score are more material).
        df = df.sort_values(
            ["total_risk_score", "awarded_value"],
            ascending=[False, False],
        )

    # Add a human-readable priority label for the UI badge.
    df["investigation_priority"] = df["risk_level"].apply(_priority_label)

    return df.head(limit).reset_index(drop=True)


def get_high_risk_count() -> dict:
    """
    Returns count of tenders at each risk level above Low Risk.
    Used for the Investigation Center header cards.
    """
    all_tenders = queries.get_all_tenders()
    if all_tenders.empty:
        return {"Moderate Risk": 0, "High Risk": 0, "Critical Risk": 0}

    return {
        "Moderate Risk": int(((all_tenders["total_risk_score"] >= 1)
                               & (all_tenders["total_risk_score"] <= 2)).sum()),
        "High Risk":     int(((all_tenders["total_risk_score"] >= 3)
                               & (all_tenders["total_risk_score"] <= 4)).sum()),
        "Critical Risk": int((all_tenders["total_risk_score"] == 5).sum()),
    }


# ─────────────────────────────────────────────────────────────────────
# INVESTIGATION SUMMARY (per-tender)
# ─────────────────────────────────────────────────────────────────────

def get_investigation_summary(tender_id: int) -> dict:
    """
    Builds a structured investigation summary for a single tender,
    suitable for display in the Investigation Center detail panel and
    for inclusion in PDF investigation reports.

    Structure:
        {
          "tender":           { tender fields },
          "risk_score":       int,
          "risk_level":       str,
          "triggered_indicators": [ { detector detail dicts } ],
          "narrative":        str,   # plain English investigation summary
          "recommendations":  [ str, ... ],   # actionable next steps
          "found":            bool
        }
    """
    tender_df = queries.get_tender_by_id(tender_id)
    if tender_df.empty:
        return {"found": False}

    tender = tender_df.iloc[0].to_dict()
    indicators_df = queries.get_risk_indicators_for_tender(tender_id)

    triggered = (
        indicators_df[indicators_df["triggered"] == 1].to_dict("records")
        if not indicators_df.empty else []
    )
    not_triggered = (
        indicators_df[indicators_df["triggered"] == 0].to_dict("records")
        if not indicators_df.empty else []
    )

    risk_score = tender.get("total_risk_score", 0)
    risk_level = tender.get("risk_level", "Low Risk")

    narrative = _build_narrative(tender, triggered)
    recommendations = _build_recommendations(tender, triggered)

    return {
        "found":                True,
        "tender":               tender,
        "risk_score":           risk_score,
        "risk_level":           risk_level,
        "triggered_indicators": triggered,
        "clear_indicators":     not_triggered,
        "narrative":            narrative,
        "recommendations":      recommendations,
    }


# ─────────────────────────────────────────────────────────────────────
# VENDOR INVESTIGATION CONTEXT
# ─────────────────────────────────────────────────────────────────────

def get_vendor_investigation_context(vendor_id: int) -> dict:
    """
    Returns a vendor-level investigation summary for use in Reports
    and the Vendor Search detail panel "Investigation" tab.

    Structure:
        {
          "vendor":             { vendor fields },
          "risk_tender_count":  int,
          "flagged_tenders":    DataFrame,
          "pattern_summary":    { detector_name -> triggered_count },
          "narrative":          str,
          "recommendations":    [ str, ... ],
          "found":              bool
        }
    """
    vendor_df = queries.get_vendor_by_id(vendor_id)
    if vendor_df.empty:
        return {"found": False}

    vendor = vendor_df.iloc[0].to_dict()
    history_df = queries.get_vendor_tender_history(vendor_id)

    if history_df.empty:
        return {
            "found": True,
            "vendor": vendor,
            "risk_tender_count": 0,
            "flagged_tenders": pd.DataFrame(),
            "pattern_summary": {},
            "narrative": (
                f"No awarded tenders on record for {vendor['vendor_name']}. "
                "No procurement risk indicators can be assessed at this time."
            ),
            "recommendations": [
                "Verify vendor registration records are current.",
                "Confirm whether the vendor has participated in tenders under an alternate name or registration.",
            ],
        }

    # Tenders with at least one triggered indicator.
    flagged = history_df[history_df["total_risk_score"] >= 1].copy()
    risk_tender_count = len(flagged)

    # Aggregate which detectors most frequently trigger for this vendor.
    pattern_summary = _compute_vendor_pattern_summary(history_df)

    # Build narrative and recommendations.
    narrative = _build_vendor_narrative(vendor, history_df, flagged, pattern_summary)
    recommendations = _build_vendor_recommendations(vendor, flagged, pattern_summary)

    return {
        "found":             True,
        "vendor":            vendor,
        "risk_tender_count": risk_tender_count,
        "flagged_tenders":   flagged,
        "pattern_summary":   pattern_summary,
        "narrative":         narrative,
        "recommendations":   recommendations,
    }


# ─────────────────────────────────────────────────────────────────────
# INTERNAL — NARRATIVE BUILDERS
# ─────────────────────────────────────────────────────────────────────

def _build_narrative(tender: dict, triggered: list[dict]) -> str:
    """
    Generates a plain-English investigation narrative for a single
    tender based on which indicators were triggered.
    """
    ref = tender.get("tender_reference", "Unknown")
    title = tender.get("title", "Unknown")
    region = tender.get("region", "")
    category = tender.get("category", "")
    risk_level = tender.get("risk_level", "Low Risk")
    vendor_name = tender.get("awarded_vendor_name", "the awarded vendor")
    awarded_value = tender.get("awarded_value", 0)

    if not triggered:
        return (
            f"Tender {ref} ({title}) in {region} / {category} has a risk score "
            f"of 0 (Low Risk). No procurement risk indicators were triggered. "
            f"No investigation action is recommended at this time."
        )

    triggered_names = [t["detector_name"] for t in triggered]
    indicators_text = ", ".join(triggered_names)

    narrative = (
        f"Tender {ref} — {title} — is rated {risk_level} based on {len(triggered)} "
        f"triggered procurement risk indicator(s): {indicators_text}. "
        f"The tender, valued at ₹{awarded_value:,.0f}, was awarded to {vendor_name} "
        f"in {region} / {category}.\n\n"
    )

    for item in triggered:
        narrative += f"• {item['detector_name']}: {item['explanation']}\n"

    narrative += (
        "\nThis summary is a procurement risk triage signal generated from "
        "statistical patterns in the tender data. It does not constitute a "
        "finding of irregularity and should be reviewed by a qualified "
        "investigator before any action is taken."
    )
    return narrative


def _build_vendor_narrative(
    vendor: dict,
    history_df: pd.DataFrame,
    flagged_df: pd.DataFrame,
    pattern_summary: dict,
) -> str:
    """
    Generates a vendor-level investigation narrative summarising the
    risk pattern across all of the vendor's awarded tenders.
    """
    name = vendor.get("vendor_name", "Unknown Vendor")
    total_won = len(history_df)
    risk_count = len(flagged_df)
    avg_risk = round(history_df["total_risk_score"].mean(), 2) if total_won > 0 else 0

    if risk_count == 0:
        return (
            f"{name} has been awarded {total_won} tender(s) with an average "
            f"risk score of {avg_risk}. No procurement risk indicators were "
            f"triggered across this vendor's awarded tenders."
        )

    top_patterns = sorted(pattern_summary.items(), key=lambda x: x[1], reverse=True)
    pattern_text = "; ".join(
        f"{name_} ({count} tender(s))" for name_, count in top_patterns if count > 0
    )

    narrative = (
        f"{name} has been awarded {total_won} tender(s), of which {risk_count} "
        f"({round(risk_count / total_won * 100, 1)}%) have at least one triggered "
        f"procurement risk indicator. The average risk score across all awarded "
        f"tenders is {avg_risk}.\n\n"
        f"Predominant risk patterns: {pattern_text}.\n\n"
        "This summary is based on automated statistical pattern analysis and "
        "should be reviewed alongside primary procurement records before any "
        "investigative or audit action is initiated."
    )
    return narrative


# ─────────────────────────────────────────────────────────────────────
# INTERNAL — RECOMMENDATION BUILDERS
# ─────────────────────────────────────────────────────────────────────

_DETECTOR_RECOMMENDATIONS: dict[str, list[str]] = {
    "Vendor Concentration": [
        "Review the full list of tenders awarded to this vendor in the same region and category "
        "to assess whether the concentration exceeds what competitive conditions would explain.",
        "Examine whether bid evaluation criteria or scoring was applied consistently across "
        "competing vendors in this peer group.",
        "Verify whether any pre-qualification or technical requirements were applied that "
        "may have legitimately limited competition.",
        "Audit Recommended: vendor concentration pattern warrants review of award evaluation records.",
    ],
    "Bid Clustering": [
        "Obtain and review original bid submission records to verify the reported bid amounts.",
        "Assess whether the category has well-known market pricing that could legitimately "
        "explain close bid values, or whether the spread is statistically unlikely.",
        "Review communication records or any pre-bid meetings for evidence of shared information "
        "between participating vendors.",
        "Investigation Recommended: tightly clustered bids across multiple vendors warrant "
        "closer scrutiny of the bidding process.",
    ],
    "Single Bidder": [
        "Review whether the tender was adequately publicised with sufficient notice period "
        "to allow broad vendor participation.",
        "Examine whether technical specifications or pre-qualification criteria were set in "
        "a way that may have limited eligible vendors.",
        "Check tender records for any prior market engagement or justification for limited competition.",
        "Audit Recommended: single-bidder awards should be documented with a written justification "
        "for the absence of competition.",
    ],
    "Short Tender Window": [
        "Review the internal approval chain to determine who authorised the shortened notice period "
        "and what justification was recorded.",
        "Assess whether emergency or urgency provisions were invoked and whether the circumstances "
        "meet the threshold for those provisions.",
        "Verify whether the successful vendor had any prior engagement with the procuring department "
        "that may have given them advance knowledge of the tender.",
        "Audit Recommended: tender windows significantly shorter than category norms require "
        "written justification on file.",
    ],
    "Price Inflation": [
        "Obtain the original cost estimate and review the methodology used to arrive at it.",
        "Compare the awarded value against independent market benchmarks for similar contracts "
        "in the same region and time period.",
        "Review whether a formal variation or scope-change justification was filed for the "
        "difference between estimated and awarded values.",
        "Investigation Recommended: overages significantly above negotiation norms should be "
        "supported by documented scope or market justification.",
    ],
}

_GENERAL_RECOMMENDATIONS = [
    "Retain all original tender documentation (notice, submissions, evaluation records, "
    "award decision) pending review.",
    "Do not share this risk assessment with vendors or external parties prior to completing "
    "the investigation review.",
]


def _build_recommendations(tender: dict, triggered: list[dict]) -> list[str]:
    """
    Builds a deduplicated list of investigation recommendations based
    on which detectors triggered for this tender.
    """
    if not triggered:
        return ["No investigation action recommended. File for routine record-keeping."]

    recs: list[str] = []
    seen: set[str] = set()

    for item in triggered:
        for rec in _DETECTOR_RECOMMENDATIONS.get(item["detector_name"], []):
            if rec not in seen:
                recs.append(rec)
                seen.add(rec)

    for rec in _GENERAL_RECOMMENDATIONS:
        if rec not in seen:
            recs.append(rec)
            seen.add(rec)

    return recs


def _build_vendor_recommendations(
    vendor: dict,
    flagged_df: pd.DataFrame,
    pattern_summary: dict,
) -> list[str]:
    """
    Builds vendor-level investigation recommendations based on which
    patterns appear most frequently across the vendor's tender history.
    """
    if flagged_df.empty:
        return [
            "No investigation action recommended based on current tender records.",
            "Continue standard periodic review of vendor registration and compliance status.",
        ]

    recs: list[str] = []
    seen: set[str] = set()

    for detector_name, count in sorted(
        pattern_summary.items(), key=lambda x: x[1], reverse=True
    ):
        if count > 0:
            for rec in _DETECTOR_RECOMMENDATIONS.get(detector_name, []):
                if rec not in seen:
                    recs.append(rec)
                    seen.add(rec)

    for rec in _GENERAL_RECOMMENDATIONS:
        if rec not in seen:
            recs.append(rec)
            seen.add(rec)

    return recs


# ─────────────────────────────────────────────────────────────────────
# INTERNAL — HELPERS
# ─────────────────────────────────────────────────────────────────────

def _priority_label(risk_level: str) -> str:
    """Maps risk level to a short investigation priority label."""
    return {
        "Critical Risk": "Priority 1 – Immediate Review",
        "High Risk":     "Priority 2 – Urgent Review",
        "Moderate Risk": "Priority 3 – Scheduled Review",
        "Low Risk":      "Priority 4 – Routine",
    }.get(risk_level, "Priority 4 – Routine")


def _compute_vendor_pattern_summary(history_df: pd.DataFrame) -> dict[str, int]:
    """
    For each detector, counts how many of this vendor's won tenders
    triggered that detector. Requires joining through risk_indicators.

    Returns dict: { detector_name: trigger_count }
    """
    detector_names = [
        "Vendor Concentration",
        "Bid Clustering",
        "Single Bidder",
        "Short Tender Window",
        "Price Inflation",
    ]
    pattern_counts: dict[str, int] = {d: 0 for d in detector_names}

    for tender_id in history_df["tender_id"]:
        indicators_df = queries.get_risk_indicators_for_tender(int(tender_id))
        if indicators_df.empty:
            continue
        triggered_df = indicators_df[indicators_df["triggered"] == 1]
        for _, row in triggered_df.iterrows():
            if row["detector_name"] in pattern_counts:
                pattern_counts[row["detector_name"]] += 1

    return pattern_counts

# ── PATCH: add stats to get_vendor_investigation_context ─────────────
# The original function was missing the `stats` key that report_service
# uses to populate Participation Statistics in the vendor PDF report.
# We monkey-patch it here without touching the original function body.

_original_get_vendor_investigation_context = get_vendor_investigation_context

def get_vendor_investigation_context(vendor_id: int) -> dict:          # noqa: F811
    ctx = _original_get_vendor_investigation_context(vendor_id)
    if not ctx.get("found"):
        return ctx
    if "stats" not in ctx:
        # Pull stats from vendor_service to avoid duplicating logic.
        try:
            from services import vendor_service as _vs
            profile = _vs.get_vendor_profile(vendor_id)
            ctx["stats"] = profile.get("stats", {})
        except Exception:
            ctx["stats"] = {}
    return ctx
