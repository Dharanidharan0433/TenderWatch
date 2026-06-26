"""
detectors/short_window.py
------------------------------
Detector: Short Tender Window

Flags tenders where the gap between publish_date and
submission_deadline is unusually short, which can limit how many
vendors realistically have time to prepare and submit a competitive
bid. A short window does not by itself indicate anything improper --
urgent/emergency procurements can legitimately require a fast
timeline -- so the explanation always states the measured window
length and comparison basis rather than asserting impropriety.

Input contract:
    tenders_df must contain at least:
        tender_id, category, tender_window_days
    (tender_window_days is expected to already be computed as
     (submission_deadline - publish_date) in days; if absent, the
     detector will compute it from publish_date / submission_deadline
     columns when present.)

Output:
    list[DetectorResult], one per row in tenders_df.
"""

import pandas as pd

from detectors.base_detector import DetectorResult, not_triggered

DETECTOR_NAME = "Short Tender Window"

# Absolute floor: any tender window at or below this many days is
# flagged regardless of category, since this is short enough that
# almost no category could realistically expect fair competition.
ABSOLUTE_SHORT_WINDOW_DAYS = 5

# Relative check: a window significantly shorter than the category's
# OWN median window can also be a meaningful signal, since "normal"
# varies a lot by category (IT contracts may move faster than large
# infrastructure works). A window less than this fraction of the
# category median is flagged even if it's above the absolute floor.
# Set conservatively low (0.20) so that windows still within the
# platform's normal 10-45 day baseline range are not flagged purely
# for landing on the short side of a high-median category.
RELATIVE_THRESHOLD_RATIO = 0.20

SEVERITY_HIGH_DAYS = 2
SEVERITY_MEDIUM_DAYS = 4

# Category medians need a minimum sample size to be trustworthy.
MIN_CATEGORY_SAMPLE = 5


def _severity_for_window(window_days: int) -> str:
    """Shorter absolute windows map to higher severity."""
    if window_days <= SEVERITY_HIGH_DAYS:
        return "High"
    if window_days <= SEVERITY_MEDIUM_DAYS:
        return "Medium"
    return "Low"


def _ensure_window_days(tenders_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a copy of tenders_df guaranteed to have a numeric
    tender_window_days column, computing it from publish_date /
    submission_deadline if it isn't already present.
    """
    df = tenders_df.copy()
    if "tender_window_days" in df.columns:
        return df

    if {"publish_date", "submission_deadline"}.issubset(df.columns):
        df["publish_date"] = pd.to_datetime(df["publish_date"])
        df["submission_deadline"] = pd.to_datetime(df["submission_deadline"])
        df["tender_window_days"] = (
            df["submission_deadline"] - df["publish_date"]
        ).dt.days
        return df

    raise ValueError(
        "tenders_df must contain either 'tender_window_days', or both "
        "'publish_date' and 'submission_deadline' to derive it."
    )


def detect(tenders_df: pd.DataFrame) -> list[DetectorResult]:
    """
    Evaluates Short Tender Window risk for every tender in tenders_df.

    Method:
        A tender is flagged if EITHER:
          (a) its window is at or below ABSOLUTE_SHORT_WINDOW_DAYS, or
          (b) its window is below RELATIVE_THRESHOLD_RATIO times its
              category's median window (when the category has enough
              tenders to compute a reliable median).

    Args:
        tenders_df: DataFrame with at least tender_id, category, and
            either tender_window_days or (publish_date,
            submission_deadline).

    Returns:
        One DetectorResult per row in tenders_df.
    """
    required_cols = {"tender_id", "category"}
    missing = required_cols - set(tenders_df.columns)
    if missing:
        raise ValueError(f"tenders_df is missing required columns: {missing}")

    df = _ensure_window_days(tenders_df)

    # Category medians, only trusted when the category has enough
    # tenders on record.
    category_stats = df.groupby("category")["tender_window_days"].agg(
        median_window="median", sample_size="count"
    )

    results: list[DetectorResult] = []

    for _, row in df.iterrows():
        tender_id = row["tender_id"]
        category = row["category"]
        window_days = row["tender_window_days"]

        if pd.isna(window_days):
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                "Tender window could not be determined from available dates.",
            ))
            continue

        window_days = int(window_days)
        stats = category_stats.loc[category]
        median_window = float(stats["median_window"])
        sample_size = int(stats["sample_size"])

        absolute_trigger = window_days <= ABSOLUTE_SHORT_WINDOW_DAYS
        relative_trigger = (
            sample_size >= MIN_CATEGORY_SAMPLE
            and median_window > 0
            and window_days < median_window * RELATIVE_THRESHOLD_RATIO
        )

        if absolute_trigger or relative_trigger:
            severity = _severity_for_window(window_days)
            if absolute_trigger:
                explanation = (
                    f"Tender window of {window_days} day(s) is at or below the "
                    f"{ABSOLUTE_SHORT_WINDOW_DAYS}-day floor considered necessary "
                    f"for fair vendor participation."
                )
            else:
                explanation = (
                    f"Tender window of {window_days} day(s) is well below the "
                    f"{round(median_window)}-day median window for "
                    f"'{category}' tenders."
                )
            results.append(DetectorResult(
                tender_id=tender_id,
                detector_name=DETECTOR_NAME,
                triggered=True,
                severity=severity,
                explanation=explanation,
                supporting_metric=(
                    f"window_days={window_days};category_median={round(median_window, 1)};"
                    f"category_sample_size={sample_size}"
                ),
            ))
        else:
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                f"Tender window of {window_days} day(s) is within the normal range "
                f"for '{category}' tenders (category median: {round(median_window)} days).",
                supporting_metric=(
                    f"window_days={window_days};category_median={round(median_window, 1)}"
                ),
            ))

    return results
