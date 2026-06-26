"""
pages/1_Dashboard.py
---------------------
System-wide overview: KPI cards, risk distribution, trend, region & category charts.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.styling import inject_css, sidebar_brand, page_header, fmt_inr, section_heading
from services import tender_service, scoring_service
from visualizations.charts import (
    risk_distribution_bar, monthly_trend_line,
    region_risk_heatmap, category_risk_bar,
)

st.set_page_config(
    page_title="Dashboard — TenderWatch",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
sidebar_brand()

# Ensure scoring has been run.
scoring_service.ensure_scored()

page_header(
    "Dashboard",
    "Government Procurement Risk Overview — Statistical Patterns Only",
)

# ── KPI CARDS ─────────────────────────────────────────────────────────
summary = tender_service.get_dashboard_summary()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Tenders",    f"{summary['total_tenders']:,}")
c2.metric("Total Vendors",    f"{summary['total_vendors']}")
c3.metric("Moderate Risk",    f"{summary['moderate_count']}")
c4.metric("High / Critical",  f"{summary['high_risk_count']}")
c5.metric("Total Contract Value", fmt_inr(summary["total_value"]))

st.markdown("<div style='margin-top:1rem'/>", unsafe_allow_html=True)

# ── ROW 1: Risk distribution + Monthly trend ────────────────────────
col_l, col_r = st.columns([1, 2])

with col_l:
    section_heading("Risk Level Distribution")
    dist_df = tender_service.get_risk_distribution()
    st.plotly_chart(risk_distribution_bar(dist_df), use_container_width=True)

with col_r:
    section_heading("Monthly Volume & Risk Trend")
    trend_df = tender_service.get_monthly_trend()
    st.plotly_chart(monthly_trend_line(trend_df), use_container_width=True)

# ── ROW 2: Region + Category ────────────────────────────────────────
col_l2, col_r2 = st.columns(2)

with col_l2:
    section_heading("Tenders by Region")
    region_df = tender_service.get_tenders_by_region()
    st.plotly_chart(region_risk_heatmap(region_df), use_container_width=True)

with col_r2:
    section_heading("Categories — Total vs High-Risk")
    cat_df = tender_service.get_tenders_by_category()
    st.plotly_chart(category_risk_bar(cat_df), use_container_width=True)

# ── NOTICE ────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-top:1.5rem;padding:0.75rem 1rem;background:#F8FAFC;
         border:1px solid #CBD5E1;border-left:3px solid #64748B;border-radius:3px;
         font-size:0.75rem;color:#475569;line-height:1.6">
    <strong>Statistical Analysis Notice:</strong>
    All risk indicators on this platform are derived from statistical patterns in procurement
    data. They represent anomalies that <em>may warrant</em> further review — not findings of
    irregularity, misconduct, or legal violation. Every indicator should be reviewed by a
    qualified procurement officer before any action is taken.
    </div>
    """,
    unsafe_allow_html=True,
)
