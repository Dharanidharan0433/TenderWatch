"""
detectors/bid_clustering.py
------------------------------
Detector: Bid Clustering

Flags tenders where competing bid amounts are unusually close together
(low spread relative to the average bid), which can indicate reduced
genuine price competition. A tight cluster does not by itself prove
coordination -- commodity goods with well-known market prices can
legitimately produce close bids -- so the explanation always states
the measured spread rather than asserting collusion.

Input contract:
    bids_df must contain at least:
        tender_id, bid_amount

Output:
    list[DetectorResult], one per unique tender_id present in bids_df.
    Tenders with fewer than MIN_BIDS_FOR_ASSESSMENT bids are evaluated
    as not-triggered with an explanation noting insufficient data
    (Single Bidder tenders, in particular, are out of scope for this
    detector and are handled by detectors/single_bidder.py instead).
"""

import pandas as pd

from detectors.base_detector import DetectorResult, not_triggered

DETECTOR_NAME = "Bid Clustering"

# Spread ratio = (max_bid - min_bid) / avg_bid. Below this ratio, bids
# are considered "tightly clustered". Chosen based on the natural
# spread observed in normal multi-bidder tenders (typically 10%-25%
# spread) versus deliberately coordinated-looking bids (typically
# under 3% spread) -- 5% sits clearly between the two.
SPREAD_RATIO_THRESHOLD = 0.05

SEVERITY_HIGH_THRESHOLD = 0.02   # extremely tight -- under 2% spread
SEVERITY_MEDIUM_THRESHOLD = 0.035

# Need at least this many competing bids for "clustering" to be a
# meaningful concept at all; a single bid has no spread to measure.
MIN_BIDS_FOR_ASSESSMENT = 2


def _severity_for_spread(spread_ratio: float) -> str:
    """Tighter clustering (lower spread ratio) maps to higher severity."""
    if spread_ratio <= SEVERITY_HIGH_THRESHOLD:
        return "High"
    if spread_ratio <= SEVERITY_MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def detect(bids_df: pd.DataFrame) -> list[DetectorResult]:
    """
    Evaluates Bid Clustering risk for every tender present in bids_df.

    Method:
        For each tender_id, compute:
            spread_ratio = (max(bid_amount) - min(bid_amount)) / mean(bid_amount)
        A low spread_ratio means all competing bids landed close to
        the average, which is the statistical signature of clustering.

    Args:
        bids_df: DataFrame with at least tender_id, bid_amount columns,
            containing all bids (winning and losing) for one or more
            tenders.

    Returns:
        One DetectorResult per unique tender_id in bids_df.
    """
    required_cols = {"tender_id", "bid_amount"}
    missing = required_cols - set(bids_df.columns)
    if missing:
        raise ValueError(f"bids_df is missing required columns: {missing}")

    results: list[DetectorResult] = []

    grouped = bids_df.groupby("tender_id")["bid_amount"].agg(
        bid_count="count", min_bid="min", max_bid="max", avg_bid="mean"
    )

    for tender_id, row in grouped.iterrows():
        bid_count = int(row["bid_count"])

        if bid_count < MIN_BIDS_FOR_ASSESSMENT:
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                f"Only {bid_count} bid recorded; bid clustering requires multiple "
                f"competing bids to assess.",
                supporting_metric=f"bid_count={bid_count}",
            ))
            continue

        avg_bid = float(row["avg_bid"])
        if avg_bid == 0:
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                "Average bid amount is zero; spread ratio cannot be computed.",
            ))
            continue

        spread = float(row["max_bid"] - row["min_bid"])
        spread_ratio = spread / avg_bid
        spread_pct = round(spread_ratio * 100, 2)
        threshold_pct = round(SPREAD_RATIO_THRESHOLD * 100, 2)

        if spread_ratio < SPREAD_RATIO_THRESHOLD:
            severity = _severity_for_spread(spread_ratio)
            results.append(DetectorResult(
                tender_id=tender_id,
                detector_name=DETECTOR_NAME,
                triggered=True,
                severity=severity,
                explanation=(
                    f"Across {bid_count} bids, amounts varied by only {spread_pct}% "
                    f"of the average bid value, below the {threshold_pct}% clustering "
                    f"threshold expected under normal competitive bidding."
                ),
                supporting_metric=(
                    f"spread_ratio={spread_pct}%;threshold={threshold_pct}%;bid_count={bid_count}"
                ),
            ))
        else:
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                f"Across {bid_count} bids, amounts varied by {spread_pct}% of the "
                f"average bid value, within the normal competitive range.",
                supporting_metric=(
                    f"spread_ratio={spread_pct}%;threshold={threshold_pct}%;bid_count={bid_count}"
                ),
            ))

    return results
