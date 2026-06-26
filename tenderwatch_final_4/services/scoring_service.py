"""
services/scoring_service.py
-----------------------------
Bridges the stateless detector layer (detectors/risk_score.py) and the
persistent database layer (risk_assessments / risk_indicators tables).

Responsibilities:
  - Run all 5 detectors across the full dataset in one batch pass.
  - Persist the resulting TenderRiskAssessment objects into the DB so
    every other service and page can read pre-computed scores cheaply
    (a SELECT vs. rerunning all detectors on every page load).
  - Provide a safe "run if not already scored" helper so app.py can
    call this on startup without worrying about double-scoring.
  - Provide a "force rescore" path for the optional Recalculate Risk
    button in the UI.

This module is the ONLY place that writes to risk_assessments and
risk_indicators. All other services are read-only consumers of those
tables.
"""

import pandas as pd

from detectors import risk_score as risk_scorer
from database import queries


def score_and_persist_all(force: bool = False) -> int:
    """
    Runs all 5 detectors over the full tender+bid dataset and persists
    one risk_assessments row + five risk_indicators rows per tender.

    Args:
        force: If True, wipes existing risk data before scoring so the
            results are always fresh. If False (default), skips scoring
            entirely when risk data already exists (idempotent on
            repeated app startups).

    Returns:
        Number of tenders scored (0 if skipped because data existed
        and force=False).
    """
    if not force and queries.risk_assessments_exist():
        return 0  # already scored, nothing to do

    if force:
        queries.delete_all_risk_data()

    # Load full dataset — detectors need dataset-wide context (peer-group
    # win shares, category medians) so we must pass the complete tables,
    # not slices.
    tenders_df = queries.get_all_tenders()
    bids_df = queries.get_all_bids()

    # Run all detectors in one vectorised batch pass.
    assessments = risk_scorer.score_all_tenders(tenders_df, bids_df)

    # Persist: one assessment row + one indicator row per detector per tender.
    for assessment in assessments:
        assessment_id = queries.insert_risk_assessment(
            tender_id=assessment.tender_id,
            total_risk_score=assessment.total_risk_score,
            risk_level=assessment.risk_level,
        )

        indicator_rows = [
            (
                assessment_id,
                indicator.detector_name,
                int(indicator.triggered),   # SQLite stores booleans as integers
                indicator.explanation,
                indicator.supporting_metric,
            )
            for indicator in assessment.indicators
        ]
        queries.insert_risk_indicators_bulk(indicator_rows)

    return len(assessments)


def ensure_scored() -> None:
    """
    Guarantees risk data exists in the DB; idempotent.

    Called from app.py on startup and from any service function that
    needs risk data but cannot assume it has been populated yet (e.g.
    if seed_data was just re-run without triggering a rescore).
    """
    scored = score_and_persist_all(force=False)
    if scored:
        print(f"[scoring_service] Scored {scored} tenders and persisted results.")
    else:
        print("[scoring_service] Risk data already present — skipping rescore.")


def rescore_all() -> int:
    """
    Forces a full rescore, discarding any previously persisted risk
    data. Intended for the 'Recalculate Risk' UI button.

    Returns:
        Number of tenders rescored.
    """
    count = score_and_persist_all(force=True)
    print(f"[scoring_service] Rescored {count} tenders.")
    return count
