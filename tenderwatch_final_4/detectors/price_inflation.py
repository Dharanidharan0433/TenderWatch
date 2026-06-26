"""
detectors/price_inflation.py
------------------------------
Detector: Price Inflation

Flags tenders where the awarded value significantly exceeds the
estimated value, beyond normal negotiation variance. A large overage
does not by itself indicate anything improper -- scope changes, market
price shifts, or underestimated original budgets can all legitimately
push awarded value above estimate -- so the explanation always states
the measured overage percentage rather than asserting impropriety.

Input contract:
    tenders_df must contain at least:
        tender_id, estimated_value, awarded_value

Output:
    list[DetectorResult], one per row in tenders_df.
"""

import pandas as pd

from detectors.base_detector import DetectorResult, not_triggered

DETECTOR_NAME = "Price Inflation"

# Normal negotiation variance observed in clean procurement data is
# roughly +/-8%. An overage beyond this threshold is flagged.
OVERAGE_THRESHOLD = 0.20  # 20% above estimate

SEVERITY_HIGH_THRESHOLD = 0.50    # 50%+ above estimate
SEVERITY_MEDIUM_THRESHOLD = 0.30  # 30%+ above estimate


def _severity_for_overage(overage_ratio: float) -> str:
    """Larger overage ratios map to higher severity."""
    if overage_ratio >= SEVERITY_HIGH_THRESHOLD:
        return "High"
    if overage_ratio >= SEVERITY_MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def detect(tenders_df: pd.DataFrame) -> list[DetectorResult]:
    """
    Evaluates Price Inflation risk for every tender in tenders_df.

    Method:
        overage_ratio = (awarded_value - estimated_value) / estimated_value
        A tender is flagged when overage_ratio exceeds OVERAGE_THRESHOLD.
        Awarded values below or equal to the estimate are never
        flagged by this detector (under-budget awards are not a price
        inflation concern).

    Args:
        tenders_df: DataFrame with at least tender_id, estimated_value,
            awarded_value columns.

    Returns:
        One DetectorResult per row in tenders_df.
    """
    required_cols = {"tender_id", "estimated_value", "awarded_value"}
    missing = required_cols - set(tenders_df.columns)
    if missing:
        raise ValueError(f"tenders_df is missing required columns: {missing}")

    results: list[DetectorResult] = []

    for _, row in tenders_df.iterrows():
        tender_id = row["tender_id"]
        estimated_value = row["estimated_value"]
        awarded_value = row["awarded_value"]

        if pd.isna(estimated_value) or pd.isna(awarded_value):
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                "Estimated or awarded value missing; price inflation cannot be assessed.",
            ))
            continue

        if estimated_value <= 0:
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                "Estimated value is zero or negative; overage ratio cannot be computed.",
            ))
            continue

        overage_ratio = (awarded_value - estimated_value) / estimated_value
        overage_pct = round(overage_ratio * 100, 1)
        threshold_pct = round(OVERAGE_THRESHOLD * 100, 1)

        if overage_ratio > OVERAGE_THRESHOLD:
            severity = _severity_for_overage(overage_ratio)
            results.append(DetectorResult(
                tender_id=tender_id,
                detector_name=DETECTOR_NAME,
                triggered=True,
                severity=severity,
                explanation=(
                    f"Awarded value is {overage_pct}% above the estimated value, "
                    f"exceeding the {threshold_pct}% threshold for normal "
                    f"negotiation variance."
                ),
                supporting_metric=(
                    f"overage_pct={overage_pct}%;threshold={threshold_pct}%;"
                    f"estimated_value={estimated_value};awarded_value={awarded_value}"
                ),
            ))
        else:
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                f"Awarded value is {overage_pct}% relative to the estimated value, "
                f"within the normal negotiation range.",
                supporting_metric=(
                    f"overage_pct={overage_pct}%;threshold={threshold_pct}%"
                ),
            ))

    return results
