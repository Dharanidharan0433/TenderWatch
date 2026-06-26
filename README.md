#  TenderWatch

**Government Procurement Risk Intelligence Platform**

TenderWatch is a statistical analysis platform that helps vigilance officers, auditors, and procurement review committees identify unusual tender patterns and prioritise investigations. Every risk score is fully explained — no black-box verdicts.

> ⚠️ TenderWatch produces a **Procurement Risk Score** intended as a triage signal to help investigators prioritise which tenders warrant closer review. It never produces a verdict of fraud, corruption, or criminal activity.

---

##  Features

| Feature | Description |
|---|---|
| **Dashboard** | At-a-glance KPIs, risk distribution charts, and flagged tender summaries |
| **Vendor Search** | Profile any vendor — win rates, bid history, network connections |
| **Tender Search** | Filter and drill into individual tenders with full risk breakdowns |
| **Investigation Center** | Deep-dive workspace linking vendors, tenders, and risk indicators |
| **Vendor Network** | Interactive graph of vendor participation and co-bidding patterns |
| **Reports** | Generate and export PDF investigation reports |

###  Risk Detectors (5 independent modules)

Each detector contributes **at most 1 point** to the overall score (range 0–5):

| Score | Risk Level |
|---|---|
| 0 | Low Risk |
| 1–2 | Moderate Risk |
| 3–4 | High Risk |
| 5 | Critical Risk |

- **Single Bidder** — Detects tenders that received only one bid
- **Bid Clustering** — Flags suspiciously close bid amounts across vendors
- **Price Inflation** — Identifies awarded values significantly above estimates
- **Short Window** — Catches abnormally short tender submission windows
- **Vendor Concentration** — Spots excessive win rates by a single vendor per category/region

---

## Project Structure

```
tenderwatch_final_4/
├── app.py                          # Entry point — Streamlit multi-page app
├── config.py                       # Global constants (colours, risk thresholds, DB path)
├── requirements.txt
│
├── database/
│   ├── db.py                       # DB connection & initialisation
│   ├── schema.py                   # SQLite DDL (vendors, tenders, bids, risk tables)
│   ├── queries.py                  # All read queries (returns pandas DataFrames)
│   └── seed_data.py                # Synthetic dataset generator (Faker-based)
│
├── detectors/
│   ├── base_detector.py            # Abstract base class for all detectors
│   ├── single_bidder.py
│   ├── bid_clustering.py
│   ├── price_inflation.py
│   ├── short_window.py
│   ├── vendor_concentration.py
│   └── risk_score.py               # Aggregates all 5 detectors → TenderRiskAssessment
│
├── services/
│   ├── scoring_service.py          # Orchestrates risk scoring runs
│   ├── tender_service.py           # Business logic for tender queries
│   ├── vendor_service.py           # Business logic for vendor queries
│   ├── investigation_service.py    # Links entities for investigation views
│   ├── network_service.py          # Builds vendor co-bidding graph (NetworkX)
│   └── report_service.py           # PDF report generation (ReportLab)
│
├── pages/
│   ├── 1_Dashboard.py
│   ├── 2_Vendor_Search.py
│   ├── 3_Tender_Search.py
│   ├── 4_Investigation_Center.py
│   ├── 6_Reports.py
│   └── vendor_participation_network.py
│
├── visualizations/
│   ├── charts.py                   # Plotly chart builders
│   └── network_graph.py            # NetworkX → Plotly network visualisation
│
├── utils/
│   └── styling.py                  # CSS injection, sidebar branding, colour tokens
│
└── data/
    ├── tenderwatch.db              # SQLite database (auto-created on first run, git-ignored)
    └── exports/                    # Generated PDF reports (git-ignored)
```

---

##  Technical Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit Frontend                  │
│  app.py  +  pages/1_Dashboard … pages/6_Reports     │
└────────────────────────┬────────────────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │        Service Layer         │
          │  scoring · tender · vendor   │
          │  investigation · network     │
          │  report                      │
          └──────────────┬──────────────┘
                         │
        ┌────────────────▼─────────────────┐
        │           Detector Engine         │
        │  base_detector (ABC)              │
        │  ├── single_bidder               │
        │  ├── bid_clustering              │
        │  ├── price_inflation             │
        │  ├── short_window                │
        │  ├── vendor_concentration        │
        │  └── risk_score (aggregator)     │
        └────────────────┬─────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │        Database Layer        │
          │  SQLite  ·  db.py            │
          │  schema.py  ·  queries.py    │
          │  seed_data.py (Faker)        │
          └─────────────────────────────┘
```

**Technology stack:**

| Layer | Technology |
|---|---|
| UI framework | [Streamlit](https://streamlit.io/) ≥ 1.35 |
| Data manipulation | [pandas](https://pandas.pydata.org/) ≥ 2.0 |
| Charts | [Plotly](https://plotly.com/python/) ≥ 5.18 |
| Network graphs | [NetworkX](https://networkx.org/) ≥ 3.2 |
| PDF reports | [ReportLab](https://www.reportlab.com/) ≥ 4.1 |
| Synthetic data | [Faker](https://faker.readthedocs.io/) ≥ 24.0 |
| Numerics | [NumPy](https://numpy.org/) ≥ 1.26 |
| Database | SQLite (stdlib — no server required) |

---

##  Setup & Installation

### Prerequisites

- Python **3.9 or higher**
- `pip` (comes with Python)
- Git

---

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/tenderwatch.git
cd tenderwatch
```

### 2. Create and activate a virtual environment

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`.

> **First run:** The app will automatically create the SQLite database and seed it with a synthetic procurement dataset. This takes about 10–20 seconds and only happens once.

---

##  Database

TenderWatch uses **SQLite** — no external database server is required. The database file is created automatically at `data/tenderwatch.db` on first launch.

### Schema overview

| Table | Description |
|---|---|
| `vendors` | Master vendor registry |
| `tenders` | Master tender registry with estimated and awarded values |
| `bids` | Individual bids submitted per tender per vendor |
| `risk_assessments` | One row per tender per scoring run |
| `risk_indicators` | Individual detector results with human-readable explanations |

To reset the database and re-seed with fresh synthetic data, delete `data/tenderwatch.db` and restart the app.

---

##  Running with Your Own Data

The app ships with synthetic data generated by `database/seed_data.py`. To load real procurement data:

1. Study the schema in `database/schema.py` to understand the expected table structure.
2. Populate the `vendors`, `tenders`, and `bids` tables (via SQL or a custom ingestion script).
3. Delete any existing `risk_assessments` and `risk_indicators` rows — the scoring service will re-score on next launch.

---

##  Deployment

TenderWatch can be deployed to [Streamlit Community Cloud](https://streamlit.io/cloud) for free:

1. Push this repository to GitHub (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **New app**.
3. Select your repository, set the main file path to `app.py`, and click **Deploy**.

> **Note:** Streamlit Community Cloud uses an ephemeral filesystem — the SQLite database resets on each deploy. For persistent storage, replace `database/db.py` with a connection to a managed database (e.g. PostgreSQL via `psycopg2`).

---

##  Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "feat: add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

##  License

This project is released under the [MIT License](LICENSE).

---

##  Acknowledgements

Built with [Streamlit](https://streamlit.io/), [Plotly](https://plotly.com/python/), [NetworkX](https://networkx.org/), and [ReportLab](https://www.reportlab.com/).
