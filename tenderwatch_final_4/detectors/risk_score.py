"""
detectors/risk_score.py
--------------------------
Combines outputs from all 5 detectors into a single, explainable
Procurement Risk Score per tender.

Scoring model (per product specification):
    - Each of the 5 detectors contributes at most 1 point.
    - total_risk_score = number of detectors triggered (range 0-5).
    - Risk levels:
        0       -> Low Risk
        1-2     -> Moderate Risk
        3-4     -> High Risk
        5       -> Critical Risk

This module NEVER produces a verdict of fraud, corruption, or criminal
activity. It produces a Procurement Risk Score intended to help
investigators prioritize which tenders warrant closer review -- the
score is a triage signal, not a finding. Every score is paired with
the full list of per-detector indicators (triggered and not) so the
reasoning behind every point is fully visible.

Input contract:
    tenders_df: tender_id, region, category, awarded_vendor_id,
                estimated_value, awarded_value, status, and either
                tender_window_days or (publish_date, submission_deadline)
    bids_df:    tender_id, vendor_id, bid_amount

Output:
    score_tender(...)      -> a single TenderRiskAssessment
    score_all_tenders(...) -> list[TenderRiskAssessment], one per tender
"""

from dataclasses import dataclass, field

import pandas as pd

from detectors.base_detector import DetectorResult
from detectors import vendor_concentration
from detectors import bid_clustering
from detectors import single_bidder
from detectors import short_window
from detectors import price_inflation

# Risk level boundaries, expressed as (min_score, max_score, label) so
# the mapping is data, not nested if/elif branches -- easy to audit
# against the product spec at a glance.
RISK_LEVEL_BANDS = (
    (0, 0, "Low Risk"),
    (1, 2, "Moderate Risk"),
    (3, 4, "High Risk"),
    (5, 5, "Critical Risk"),
)

# Registry of detectors that operate on tenders_df alone. Detectors
# with a different signature (bid_clustering needs bids_df only;
# single_bidder needs both) are wired explicitly in score_all_tenders
# rather than forced into a one-size-fits-all call signature, since
# forcing uniformity here would make each detector's own module less
# readable for no real benefit.
TENDER_ONLY_DETECTOR_NAMES = (
    vendor_concentration.DETECTOR_NAME,
    short_window.DETECTOR_NAME,
    price_inflation.DETECTOR_NAME,
)


def _risk_level_for_score(score: int) -> str:
    """Maps a 0-5 total_risk_score to its risk level label per the product spec."""
    for low, high, label in RISK_LEVEL_BANDS:
        if low <= score <= high:
            return label
    raise ValueError(f"Risk score {score} is out of the valid 0-5 range.")


@dataclass
class TenderRiskAssessment:
    """
    Aggregated risk assessment for a single tender.

    Attributes:
        tender_id: The tender this assessment applies to.
        total_risk_score: Integer 0-5, one point per triggered detector.
        risk_level: One of "Low Risk", "Moderate Risk", "High Risk",
            "Critical Risk", derived directly from total_risk_score.
        indicators: Full list of DetectorResult objects from ALL 5
            detectors (both triggered and not triggered), so the
            complete reasoning behind the score is always available --
            this is what satisfies the "every risk score must have
            explanations" requirement at the data level, not just in
            a UI label.
    """
    tender_id: int
    total_risk_score: int
    risk_level: str
    indicators: list[DetectorResult] = field(default_factory=list)

    @property
    def triggered_indicators(self) -> list[DetectorResult]:
        """Convenience accessor: only the indicators that actually fired."""
        return [i for i in self.indicators if i.triggered]

    def to_dict(self) -> dict:
        """
        Plain-dict form suitable for building a summary DataFrame or
        JSON response. Indicators are included as a list of dicts so
        the full explanation trail survives serialization.
        """
        return {
            "tender_id": self.tender_id,
            "total_risk_score": self.total_risk_score,
            "risk_level": self.risk_level,
            "indicators": [i.to_dict() for i in self.indicators],
        }


def _run_all_detectors(tenders_df: pd.DataFrame, bids_df: pd.DataFrame) -> dict[str, list[DetectorResult]]:
    """
    Runs each of the 5 detectors exactly once across the full input
    DataFrames (vectorized per-detector, not looped per-tender), and
    returns a dict keyed by detector_name -> list of DetectorResult.

    Running detectors once over the whole dataset (rather than once
    per tender) keeps this aggregator efficient at the 1000-tender
    scale this platform targets, since several detectors need
    dataset-wide context anyway (e.g. category medians, peer-group
    win shares).
    """
    return {
        vendor_concentration.DETECTOR_NAME: vendor_concentration.detect(tenders_df),
        bid_clustering.DETECTOR_NAME: bid_clustering.detect(bids_df),
        single_bidder.DETECTOR_NAME: single_bidder.detect(tenders_df, bids_df),
        short_window.DETECTOR_NAME: short_window.detect(tenders_df),
        price_inflation.DETECTOR_NAME: price_inflation.detect(tenders_df),
    }


def score_all_tenders(tenders_df: pd.DataFrame, bids_df: pd.DataFrame) -> list[TenderRiskAssessment]:
    """
    Runs all 5 detectors across the full dataset and combines their
    outputs into one TenderRiskAssessment per tender.

    Args:
        tenders_df: Full tenders table (or a filtered subset) as a
            DataFrame, with columns required by each detector (see
            module docstring).
        bids_df: Full bids table as a DataFrame, with columns required
            by bid_clustering and single_bidder.

    Returns:
        List of TenderRiskAssessment, one per unique tender_id present
        in tenders_df, in the same order as tenders_df.
    """
    results_by_detector = _run_all_detectors(tenders_df, bids_df)

    # Re-index every detector's results by tender_id for O(1) lookup
    # while assembling each tender's combined assessment below.
    indexed: dict[str, dict[int, DetectorResult]] = {
        detector_name: {r.tender_id: r for r in results}
        for detector_name, results in results_by_detector.items()
    }

    detector_names = list(results_by_detector.keys())
    assessments: list[TenderRiskAssessment] = []

    for tender_id in tenders_df["tender_id"]:
        indicators: list[DetectorResult] = []
        for detector_name in detector_names:
            result = indexed[detector_name].get(tender_id)
            if result is not None:
                indicators.append(result)

        total_risk_score = sum(1 for i in indicators if i.triggered)
        risk_level = _risk_level_for_score(total_risk_score)

        assessments.append(TenderRiskAssessment(
            tender_id=tender_id,
            total_risk_score=total_risk_score,
            risk_level=risk_level,
            indicators=indicators,
        ))

    return assessments


def score_tender(tender_id: int, tenders_df: pd.DataFrame, bids_df: pd.DataFrame) -> TenderRiskAssessment:
    """
    Convenience wrapper to score a single tender by ID.

    Note: detectors that rely on dataset-wide context (e.g. vendor
    concentration's peer-group win share, short_window's category
    median) need the FULL tenders_df/bids_df passed in, not a
    single-row slice -- otherwise the comparison baseline they rely on
    would be lost. This function therefore still runs detectors across
    the full provided DataFrames and simply returns the one assessment
    matching tender_id, rather than pre-filtering to a single row.

    Args:
        tender_id: The tender to retrieve the assessment for.
        tenders_df: Full tenders DataFrame providing dataset-wide context.
        bids_df: Full bids DataFrame providing dataset-wide context.

    Returns:
        The TenderRiskAssessment for the requested tender_id.

    Raises:
        ValueError: if tender_id is not present in tenders_df.
    """
    all_assessments = score_all_tenders(tenders_df, bids_df)
    for assessment in all_assessments:
        if assessment.tender_id == tender_id:
            return assessment
    raise ValueError(f"tender_id {tender_id} not found in tenders_df.")


def assessments_to_dataframe(assessments: list[TenderRiskAssessment]) -> pd.DataFrame:
    """
    Flattens a list of TenderRiskAssessment into a summary DataFrame
    with one row per tender (tender_id, total_risk_score, risk_level)
    -- convenient for dashboard aggregation, sorting, and filtering
    without needing to unpack the nested indicators list.
    """
    return pd.DataFrame([
        {
            "tender_id": a.tender_id,
            "total_risk_score": a.total_risk_score,
            "risk_level": a.risk_level,
        }
        for a in assessments
    ])


def indicators_to_dataframe(assessments: list[TenderRiskAssessment]) -> pd.DataFrame:
    """
    Flattens a list of TenderRiskAssessment into a long-format
    DataFrame with one row per (tender_id, detector) indicator --
    convenient for building the per-tender explanation table shown in
    Tender Search / Investigation Center detail views.
    """
    rows = []
    for assessment in assessments:
        for indicator in assessment.indicators:
            row = indicator.to_dict()
            rows.append(row)
    return pd.DataFrame(rows)
