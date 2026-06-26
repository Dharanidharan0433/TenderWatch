"""
app.py
-------
TenderWatch — Government Procurement Risk Intelligence Platform.
Run with:  streamlit run app.py
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.styling import inject_css, sidebar_brand, C_PRIMARY, C_ACCENT
from services import scoring_service
from database.db import initialize_database
from database import queries
from database.seed_data import seed_database

st.set_page_config(
    page_title="TenderWatch — Procurement Risk Platform",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
sidebar_brand()

# ── STARTUP ───────────────────────────────────────────────────────────
with st.spinner("Initialising database…"):
    initialize_database(drop_existing=False)

vendors_df = queries.get_all_vendors()
if vendors_df.empty:
    with st.spinner("Seeding synthetic procurement dataset (first run only)…"):
        seed_database(drop_existing=True)

with st.spinner("Loading risk data…"):
    scoring_service.ensure_scored()

# ── LANDING PAGE ──────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="text-align:center;padding:2.5rem 0 1rem">
        <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;
             letter-spacing:0.14em;color:#64748B;margin-bottom:0.5rem">
            Government Procurement Risk Intelligence Platform
        </div>
        <h1 style="font-size:2.4rem;font-weight:800;color:{C_PRIMARY};
             letter-spacing:-0.02em;margin:0 0 0.75rem">
            TenderWatch
        </h1>
        <p style="font-size:0.88rem;color:#475569;line-height:1.75;
             max-width:640px;margin:0 auto 2rem">
            A statistical analysis platform that helps vigilance officers, auditors, and
            procurement review committees identify unusual tender patterns and prioritise
            investigations. Every risk score is explained — no black-box verdicts.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Feature cards
fc1, fc2, fc3, fc4 = st.columns(4)
for col, title, color, desc in [
    (fc1, "Risk Scoring",    C_PRIMARY,  "5 detectors · 0–5 score per tender"),
    (fc2, "Explainable",     C_ACCENT,   "Every indicator shows supporting evidence"),
    (fc3, "PDF Reports",     "#16A34A",  "Downloadable audit-quality reports"),
    (fc4, "Network Graph",   "#3B82F6",  "Vendor co-participation visualisation"),
]:
    col.markdown(
        f"""
        <div style="background:white;border:1px solid #CBD5E1;
             border-top:3px solid {color};border-radius:4px;
             padding:0.85rem 1rem;text-align:center">
            <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.07em;color:#64748B">{title}</div>
            <div style="font-size:0.78rem;color:{C_PRIMARY};margin-top:0.3rem">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top:1.5rem'/>", unsafe_allow_html=True)

# Indicator table
st.markdown(
    f"""
    <div style="max-width:800px;margin:0 auto;border:1px solid #CBD5E1;
         border-radius:4px;overflow:hidden">
        <div style="background:{C_PRIMARY};padding:0.5rem 1rem;font-size:0.68rem;
             font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:white;
             text-align:center">
            Risk Indicators Detected
        </div>
        {"".join([
            f'<div style="display:flex;align-items:center;gap:0.75rem;padding:0.55rem 1.1rem;'
            f'border-bottom:1px solid #F1F5F9;font-size:0.82rem">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{color};'
            f'display:inline-block;flex-shrink:0"></span>'
            f'<span style="font-weight:600;color:#1E3A5F;min-width:200px">{name}</span>'
            f'<span style="color:#475569">{desc}</span></div>'
            for name, color, desc in [
                ("Vendor Concentration", "#DC2626",
                 "One vendor winning a disproportionate share in a region/category"),
                ("Bid Clustering",       "#EA580C",
                 "Competing bids unusually close in value — low spread ratio"),
                ("Single Bidder",        "#D97706",
                 "Tender awarded with only one bidder participating"),
                ("Short Tender Window",  "#16A34A",
                 "Unusually short gap between publication and submission deadline"),
                ("Price Inflation",      "#3B82F6",
                 "Awarded value significantly above the estimated contract value"),
            ]
        ])}
    </div>

    <p style="font-size:0.72rem;color:#94A3B8;margin-top:1.25rem;line-height:1.6;
         text-align:center">
        <strong>Notice:</strong> TenderWatch produces Procurement Risk Indicators only.
        It never asserts fraud, corruption, or criminal activity.
        All outputs are statistical triage signals for qualified investigator review.
    </p>
    """,
    unsafe_allow_html=True,
)
