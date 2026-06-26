"""
detectors/single_bidder.py
------------------------------
Detector: Single Bidder

Flags tenders that received only one bid (or zero bids on record for
an awarded tender), meaning the award faced no recorded direct price
competition. This is a structural observation about how many vendors
participated -- it does not, by itself, indicate anything improper
about why competition was limited (a highly specialized category may
legitimately have only one qualified vendor).

Input contract:
    tenders_df must contain at least:
        tender_id, status   (status used to skip non-awarded tenders)
    bids_df must contain at least:
        tender_id, vendor_id

Output:
    list[DetectorResult], one per row in tenders_df.
"""

import pandas as pd

from detectors.base_detector import DetectorResult, not_triggered

DETECTOR_NAME = "Single Bidder"


def detect(tenders_df: pd.DataFrame, bids_df: pd.DataFrame) -> list[DetectorResult]:
    """
    Evaluates Single Bidder risk for every tender in tenders_df.

    Method:
        Counts distinct vendor_id values per tender_id in bids_df.
        A count of exactly 1 triggers the detector at Medium severity.
        A count of 0 (a recorded award with no bid rows at all -- a
        data-quality edge case as much as a risk pattern) triggers at
        High severity, since it represents an even more extreme
        absence of recorded competition.

    Args:
        tenders_df: DataFrame with at least tender_id (status optional
            but used to label cancelled/open tenders appropriately).
        bids_df: DataFrame with at least tender_id, vendor_id, covering
            all bids for the tenders being evaluated.

    Returns:
        One DetectorResult per row in tenders_df.
    """
    required_tender_cols = {"tender_id"}
    missing_t = required_tender_cols - set(tenders_df.columns)
    if missing_t:
        raise ValueError(f"tenders_df is missing required columns: {missing_t}")

    required_bid_cols = {"tender_id", "vendor_id"}
    missing_b = required_bid_cols - set(bids_df.columns)
    if missing_b:
        raise ValueError(f"bids_df is missing required columns: {missing_b}")

    results: list[DetectorResult] = []

    bidder_counts = (
        bids_df.groupby("tender_id")["vendor_id"]
        .nunique()
        .rename("bidder_count")
    )

    for _, row in tenders_df.iterrows():
        tender_id = row["tender_id"]
        status = row.get("status", "Awarded")

        if status == "Cancelled":
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                "Tender was cancelled; bidder participation is not assessed.",
            ))
            continue

        bidder_count = int(bidder_counts.get(tender_id, 0))

        if bidder_count == 0:
            results.append(DetectorResult(
                tender_id=tender_id,
                detector_name=DETECTOR_NAME,
                triggered=True,
                severity="High",
                explanation=(
                    "No bid records found for this tender despite an award being "
                    "made, indicating either a complete absence of competing bids "
                    "or a possible data-recording gap."
                ),
                supporting_metric="bidder_count=0",
            ))
        elif bidder_count == 1:
            results.append(DetectorResult(
                tender_id=tender_id,
                detector_name=DETECTOR_NAME,
                triggered=True,
                severity="Medium",
                explanation=(
                    "Only one vendor submitted a bid for this tender, meaning the "
                    "award faced no recorded direct price competition."
                ),
                supporting_metric="bidder_count=1",
            ))
        else:
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                f"{bidder_count} distinct vendors submitted bids for this tender, "
                f"indicating normal competitive participation.",
                supporting_metric=f"bidder_count={bidder_count}",
            ))

    return results
