"""
detectors/base_detector.py
----------------------------
Shared result schema for every detector in the system.

Every detector (vendor_concentration, bid_clustering, single_bidder,
short_window, price_inflation) accepts pandas DataFrames and returns a
list of DetectorResult records -- one per tender it evaluated. This
shared structure is what lets risk_score.py combine outputs from five
independently-written detectors without needing to know anything
detector-specific.

IMPORTANT -- terminology discipline:
    This platform produces PROCUREMENT RISK INDICATORS, never verdicts
    of fraud, corruption, or criminal activity. Every field name and
    every explanation string in this module and its callers must stay
    within that framing. `triggered=True` means "this tender exhibits
    a statistical pattern worth investigating," not "wrongdoing
    confirmed."
"""

from dataclasses import dataclass, field
from typing import Optional


# Allowed severity levels for a single detector hit. These map to how
# much weight risk_score.py should consider when explaining priority
# within the (separate) 0-5 aggregate score -- the aggregate score
# itself is still a simple +1-per-triggered-detector count per the
# product spec, but severity gives investigators useful context on
# WHICH triggered indicators are more extreme cases.
SEVERITY_LEVELS = ("Low", "Medium", "High")


@dataclass
class DetectorResult:
    """
    Standardized output for a single tender from a single detector.

    Attributes:
        tender_id: The tender this result applies to.
        detector_name: Human-readable detector label, e.g.
            "Vendor Concentration". Used as a display label and as the
            key risk_score.py uses to assemble the indicator list.
        triggered: Whether this detector's pattern was found for this
            tender. False does not mean "clean" in any absolute sense
            -- it means this specific statistical check did not fire.
        severity: One of SEVERITY_LEVELS. Only meaningful when
            triggered=True; set to "Low" (not None) when not triggered
            so downstream code never has to null-check it.
        explanation: A plain-language, investigator-readable sentence
            explaining WHY this result was produced, always populated
            (even when triggered=False, e.g. "Tender window of 21 days
            is within the normal range for this category."). This is
            what makes the platform explainable rather than a black
            box score.
        supporting_metric: A short machine-and-human-readable string
            capturing the specific number(s) behind the explanation,
            e.g. "win_share=23.1%threshold=15%". Kept separate from
            `explanation` so UI code can show the explanation as prose
            and the metric as a compact badge/tooltip if desired.
    """
    tender_id: int
    detector_name: str
    triggered: bool
    severity: str
    explanation: str
    supporting_metric: str = ""

    def __post_init__(self):
        if self.severity not in SEVERITY_LEVELS:
            raise ValueError(
                f"severity must be one of {SEVERITY_LEVELS}, got {self.severity!r}"
            )

    def to_dict(self) -> dict:
        """Plain-dict form, convenient for DataFrame construction or JSON/UI use."""
        return {
            "tender_id": self.tender_id,
            "detector_name": self.detector_name,
            "triggered": self.triggered,
            "severity": self.severity,
            "explanation": self.explanation,
            "supporting_metric": self.supporting_metric,
        }


def not_triggered(tender_id: int, detector_name: str, explanation: str,
                   supporting_metric: str = "") -> DetectorResult:
    """
    Convenience constructor for the common "this check did not fire"
    case, so every detector doesn't repeat severity="Low",
    triggered=False boilerplate at each non-trigger return point.
    """
    return DetectorResult(
        tender_id=tender_id,
        detector_name=detector_name,
        triggered=False,
        severity="Low",
        explanation=explanation,
        supporting_metric=supporting_metric,
    )
