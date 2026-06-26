"""
database/schema.py
--------------------
Defines the full SQLite schema for TenderWatch as a list of DDL
statements. Expressed in Python (rather than a standalone .sql file)
so it can be imported directly by database/db.py without a separate
file-read step, and so schema changes are tracked in normal code
review/diffs.

Tables:
    vendors            - master vendor registry
    tenders            - master tender registry
    bids               - individual bids submitted against tenders
    risk_assessments   - one row per tender per risk-scoring run
    risk_indicators    - individual detector results feeding an assessment

Design notes:
    - is_synthetic_anomaly / is_flagged_entity are GROUND-TRUTH markers
      used only during dataset generation and detector validation.
      They are never shown to end users as a verdict (e.g. "fraud
      confirmed") -- the platform's detectors must independently infer
      risk from the actual data (bid amounts, dates, win rates), not
      from these flags. Their sole purpose is allowing developers to
      measure detector precision/recall against known synthetic cases.
    - risk_indicators.explanation is NOT NULL: every risk indicator
      must carry a human-readable justification. This enforces the
      platform's explainability requirement at the schema level,
      not just as a UI convention.
"""

SCHEMA_STATEMENTS = [
    # ------------------------------------------------------------------
    # VENDORS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS vendors (
        vendor_id               INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_name             TEXT NOT NULL,
        registration_number     TEXT UNIQUE NOT NULL,
        region                  TEXT NOT NULL,
        category_specialization TEXT NOT NULL,
        date_registered         DATE NOT NULL,
        is_flagged_entity       BOOLEAN NOT NULL DEFAULT 0
    );
    """,

    # ------------------------------------------------------------------
    # TENDERS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS tenders (
        tender_id            INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_reference     TEXT UNIQUE NOT NULL,
        title                TEXT NOT NULL,
        category             TEXT NOT NULL,
        region               TEXT NOT NULL,
        department           TEXT NOT NULL,
        estimated_value      REAL NOT NULL,
        publish_date         DATE NOT NULL,
        submission_deadline  DATE NOT NULL,
        tender_window_days   INTEGER NOT NULL,
        awarded_vendor_id    INTEGER,
        awarded_value        REAL,
        status               TEXT NOT NULL DEFAULT 'Awarded'
                             CHECK (status IN ('Open', 'Awarded', 'Cancelled')),
        is_synthetic_anomaly BOOLEAN NOT NULL DEFAULT 0,
        anomaly_type         TEXT,
        FOREIGN KEY (awarded_vendor_id) REFERENCES vendors(vendor_id)
    );
    """,

    # ------------------------------------------------------------------
    # BIDS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS bids (
        bid_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_id      INTEGER NOT NULL,
        vendor_id      INTEGER NOT NULL,
        bid_amount     REAL NOT NULL,
        bid_date       DATE NOT NULL,
        is_winning_bid BOOLEAN NOT NULL DEFAULT 0,
        FOREIGN KEY (tender_id) REFERENCES tenders(tender_id),
        FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
    );
    """,

    # ------------------------------------------------------------------
    # RISK_ASSESSMENTS  (populated later by detectors/risk_aggregator.py;
    # created here so the schema is complete and FK-consistent from day one)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS risk_assessments (
        assessment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_id        INTEGER NOT NULL,
        total_risk_score INTEGER NOT NULL CHECK (total_risk_score BETWEEN 0 AND 5),
        risk_level       TEXT NOT NULL
                         CHECK (risk_level IN ('Low Risk', 'Moderate Risk', 'High Risk', 'Critical Risk')),
        assessment_date  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tender_id) REFERENCES tenders(tender_id)
    );
    """,

    # ------------------------------------------------------------------
    # RISK_INDICATORS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS risk_indicators (
        indicator_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id      INTEGER NOT NULL,
        detector_name      TEXT NOT NULL,
        triggered          BOOLEAN NOT NULL,
        explanation        TEXT NOT NULL,
        supporting_metric  TEXT,
        FOREIGN KEY (assessment_id) REFERENCES risk_assessments(assessment_id)
    );
    """,

    # ------------------------------------------------------------------
    # INDEXES
    # ------------------------------------------------------------------
    "CREATE INDEX IF NOT EXISTS idx_bids_tender ON bids(tender_id);",
    "CREATE INDEX IF NOT EXISTS idx_bids_vendor ON bids(vendor_id);",
    "CREATE INDEX IF NOT EXISTS idx_tenders_region_category ON tenders(region, category);",
    "CREATE INDEX IF NOT EXISTS idx_tenders_awarded_vendor ON tenders(awarded_vendor_id);",
    "CREATE INDEX IF NOT EXISTS idx_risk_assessments_tender ON risk_assessments(tender_id);",
    "CREATE INDEX IF NOT EXISTS idx_risk_indicators_assessment ON risk_indicators(assessment_id);",
]
