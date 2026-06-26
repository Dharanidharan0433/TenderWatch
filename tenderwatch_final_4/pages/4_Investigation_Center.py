"""
pages/4_Investigation_Center.py
--------------------------------
Prioritized case queue for vigilance officers and auditors.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.styling import (
    inject_css, sidebar_brand, page_header, risk_badge,
    section_heading, fmt_inr, render_indicator_row, C_RISK, C_PRIMARY,
)
from services import investigation_service, tender_service
from database import queries

st.set_page_config(
    page_title="Investigation Center — TenderWatch",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
sidebar_brand()
page_header(
    "Investigation Center",
    "Prioritized procurement risk cases — for review by authorised vigilance personnel only",
)

# ── HEADER COUNTS ─────────────────────────────────────────────────────
all_tenders = queries.get_all_tenders()
total_tenders = len(all_tenders)
total_flagged = int((all_tenders["total_risk_score"] >= 1).sum()) if not all_tenders.empty else 0
moderate_count = int((all_tenders["risk_level"] == "Moderate Risk").sum()) if not all_tenders.empty else 0
high_count = int((all_tenders["risk_level"] == "High Risk").sum()) if not all_tenders.empty else 0
critical_count = int((all_tenders["risk_level"] == "Critical Risk").sum()) if not all_tenders.empty else 0

hc1, hc2, hc3, hc4, hc5 = st.columns(5)
hc1.metric("Total Tenders",      f"{total_tenders:,}")
hc2.metric("Total Flagged",      total_flagged)
hc3.metric("Moderate Risk",      moderate_count)
hc4.metric("High Risk",          high_count)
hc5.metric("Critical Risk",      critical_count)

st.markdown("<div style='margin-top:0.75rem'/>", unsafe_allow_html=True)

# ── FILTERS ───────────────────────────────────────────────────────────
opts = tender_service.get_filter_options()

with st.container():
    f1, f2, f3, f4, f5 = st.columns([1, 1, 1, 1, 1])
    with f1:
        risk_filter = st.selectbox(
            "Minimum Risk Level",
            ["All Risk", "Moderate Risk", "High Risk", "Critical Risk"],
        )
    with f2:
        region = st.selectbox("Region", ["All"] + opts["regions"])
    with f3:
        category = st.selectbox("Category", ["All"] + opts["categories"])
    with f4:
        sort_by = st.selectbox("Sort By", ["Risk Score", "Contract Value", "Date"])
    with f5:
        st.markdown("<br>", unsafe_allow_html=True)
        do_filter = st.button("Apply Filters", use_container_width=True)

# ── QUEUE ─────────────────────────────────────────────────────────────
if "inv_results" not in st.session_state or do_filter:
    risk_map = {
        "All Risk": "",
        "Moderate Risk": "Moderate Risk",
        "High Risk": "High Risk",
        "Critical Risk": "Critical Risk",
    }
    sort_map = {"Risk Score": "risk_score", "Contract Value": "value", "Date": "date"}
    st.session_state.inv_results = investigation_service.get_investigation_queue(
        risk_level_filter=risk_map.get(risk_filter, ""),
        region="" if region == "All" else region,
        category="" if category == "All" else category,
        sort_by=sort_map.get(sort_by, "risk_score"),
    )

if "selected_inv_id" not in st.session_state:
    st.session_state.selected_inv_id = None

queue_df = st.session_state.inv_results
col_queue, col_summary = st.columns([1, 1])

# ── CASE LIST ─────────────────────────────────────────────────────────
with col_queue:
    section_heading(f"Case Queue ({len(queue_df)} cases)")

    if queue_df.empty:
        st.info("No cases match the current filters.")
    else:
        for _, row in queue_df.iterrows():
            score    = int(row.get("total_risk_score", 0))
            rl       = row.get("risk_level", "Low Risk")
            priority = row.get("investigation_priority", "")
            badge_html = risk_badge(rl)

            p_color = {
                "Priority 1": C_RISK,
                "Priority 2": "#EA580C",
                "Priority 3": "#D97706",
            }.get(priority[:10], "#64748B")

            is_sel = st.session_state.selected_inv_id == row["tender_id"]
            border = "border-left:3px solid #DC2626" if is_sel else "border-left:3px solid #CBD5E1"

            st.markdown(
                f"""
                <div style="background:white;border:1px solid #CBD5E1;{border};
                     border-radius:3px;padding:0.65rem 0.9rem;margin-bottom:0.4rem">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start">
                        <div>
                            <span style="font-weight:700;font-size:0.83rem;color:#1E3A5F">
                                {row.get('tender_reference','—')}</span>
                            <span style="font-size:0.72rem;color:#475569;margin-left:0.5rem">
                                Score: {score}/5</span>
                        </div>
                        {badge_html}
                    </div>
                    <div style="font-size:0.72rem;color:{p_color};font-weight:600;margin-top:0.15rem">
                        {priority}</div>
                    <div style="font-size:0.72rem;color:#475569;margin-top:0.1rem">
                        {row.get('category','—')} &nbsp;·&nbsp; {row.get('region','—')}
                        &nbsp;·&nbsp; {fmt_inr(row.get('awarded_value'))}
                        &nbsp;·&nbsp; {row.get('awarded_vendor_name','—')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Case", key=f"inv_{row['tender_id']}"):
                st.session_state.selected_inv_id = int(row["tender_id"])
                st.rerun()

# ── CASE SUMMARY PANEL ────────────────────────────────────────────────
with col_summary:
    sel_id = st.session_state.selected_inv_id
    if sel_id is None:
        st.markdown(
            """<div style="background:white;border:1px solid #CBD5E1;border-radius:4px;
                padding:2rem;text-align:center;color:#64748B;font-size:0.85rem">
                Open a case from the queue to view the investigation summary.</div>""",
            unsafe_allow_html=True,
        )
    else:
        summary = investigation_service.get_investigation_summary(sel_id)
        if not summary.get("found"):
            st.error("Case not found.")
        else:
            tender          = summary["tender"]
            risk_score      = summary["risk_score"]
            risk_level      = summary["risk_level"]
            triggered       = summary["triggered_indicators"]
            narrative       = summary["narrative"]
            recommendations = summary["recommendations"]

            section_heading("Investigation Summary")

            rl_color = {
                "Low Risk":      "#16A34A",
                "Moderate Risk": "#D97706",
                "High Risk":     "#EA580C",
                "Critical Risk": "#DC2626",
            }.get(risk_level, "#64748B")

            # Header card
            st.markdown(
                f"""
                <div style="background:white;border:1px solid #CBD5E1;
                     border-top:3px solid {rl_color};border-radius:3px;
                     padding:0.9rem 1rem;margin-bottom:0.75rem">
                    <div style="font-weight:700;color:#1E3A5F;font-size:0.9rem">
                        {tender.get('tender_reference','—')}</div>
                    <div style="font-size:0.75rem;color:#475569;margin:0.2rem 0">
                        {tender.get('title','—')}</div>
                    <div style="font-size:0.72rem;color:#475569">
                        {tender.get('region','—')} · {tender.get('category','—')}
                        · {fmt_inr(tender.get('awarded_value'))}
                        · Awarded to: {tender.get('awarded_vendor_name','—')}
                    </div>
                    <div style="margin-top:0.5rem;font-size:1.15rem;font-weight:800;color:{rl_color}">
                        Risk Score {risk_score}/5 — {risk_level}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Triggered indicators
            if triggered:
                section_heading(f"Triggered Indicators ({len(triggered)})")
                for item in triggered:
                    render_indicator_row(item)
            else:
                st.info("No indicators were triggered for this tender.")

            # Narrative — always show (never empty for scored tenders)
            section_heading("Narrative")
            if narrative:
                # Split by \n and render each paragraph properly
                paras = [p.strip() for p in narrative.split("\n") if p.strip()]
                narrative_html = "".join(
                    f'<p style="margin:0 0 0.5rem;font-size:0.8rem;line-height:1.6;color:#0F172A">'
                    f'{p}</p>'
                    for p in paras
                )
                st.markdown(
                    f'<div style="background:#F8FAFC;border:1px solid #CBD5E1;border-radius:3px;'
                    f'padding:0.75rem 1rem">{narrative_html}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Narrative unavailable for this case.")

            # Recommendations — always show
            section_heading("Recommended Actions")
            if recommendations:
                for i, rec in enumerate(recommendations, 1):
                    st.markdown(
                        f"""
                        <div style="display:flex;gap:0.6rem;padding:0.45rem 0;
                             border-bottom:1px solid #F1F5F9;font-size:0.8rem;line-height:1.5">
                            <span style="font-weight:700;color:#F59E0B;min-width:20px">{i}.</span>
                            <span>{rec}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No specific recommendations for this case.")
