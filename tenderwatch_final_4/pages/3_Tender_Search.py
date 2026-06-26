"""
pages/3_Tender_Search.py
--------------------------
Search tenders; view detail, bid breakdown, and risk indicators.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.styling import (
    inject_css, sidebar_brand, page_header, risk_badge,
    section_heading, fmt_inr, fmt_pct, render_indicator_row,
)
from services import tender_service
from visualizations.charts import bid_comparison_bar, risk_score_gauge

st.set_page_config(
    page_title="Tender Search — TenderWatch",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
sidebar_brand()
page_header("Tender Search", "Search and review individual tender records and risk indicators")

# ── FILTERS ──────────────────────────────────────────────────────────
opts = tender_service.get_filter_options()

with st.expander("Search Filters", expanded=True):
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        kw     = st.text_input("Keyword (title / reference)", placeholder="e.g. infrastructure")
        region = st.selectbox("Region", ["All"] + opts["regions"])
    with fc2:
        category   = st.selectbox("Category", ["All"] + opts["categories"])
        risk_level = st.selectbox("Risk Level", ["All"] + opts["risk_levels"])
    with fc3:
        department = st.selectbox("Department", ["All"] + opts["departments"])
        col_a, col_b = st.columns(2)
        with col_a:
            min_val = st.number_input("Min Value (₹)", value=0, step=100000)
        with col_b:
            max_val = st.number_input("Max Value (₹)", value=0, step=100000,
                                      help="0 = no upper limit")
    sc1, sc2 = st.columns(2)
    with sc1:
        date_from = st.text_input("Publish Date From (YYYY-MM-DD)", "")
    with sc2:
        date_to = st.text_input("Publish Date To (YYYY-MM-DD)", "")

    do_search = st.button("Search Tenders", use_container_width=False)

# ── STATE ─────────────────────────────────────────────────────────────
if "tender_results" not in st.session_state:
    st.session_state.tender_results = tender_service.search_tenders(status="")
if "selected_tender_id" not in st.session_state:
    st.session_state.selected_tender_id = None

if do_search:
    st.session_state.tender_results = tender_service.search_tenders(
        keyword=kw,
        region="" if region == "All" else region,
        category="" if category == "All" else category,
        department="" if department == "All" else department,
        risk_level="" if risk_level == "All" else risk_level,
        status="",
        min_value=float(min_val),
        max_value=float(max_val),
        date_from=date_from,
        date_to=date_to,
    )
    st.session_state.selected_tender_id = None

results = st.session_state.tender_results
col_list, col_detail = st.columns([1, 1])

# ── RESULTS LIST ──────────────────────────────────────────────────────
with col_list:
    section_heading(f"Results ({len(results)} tenders)")
    if results.empty:
        st.info("No tenders match the search criteria.")
    else:
        for _, row in results.iterrows():
            score = int(row.get("total_risk_score", 0))
            rl    = row.get("risk_level", "Low Risk")
            badge_html  = risk_badge(rl)
            score_color = {
                "Low Risk":      "#16A34A",
                "Moderate Risk": "#D97706",
                "High Risk":     "#EA580C",
                "Critical Risk": "#DC2626",
            }.get(rl, "#64748B")
            is_sel = st.session_state.selected_tender_id == row["tender_id"]
            border = "border-left:3px solid #1E3A5F" if is_sel else "border-left:3px solid transparent"

            st.markdown(
                f"""
                <div style="background:white;border:1px solid #CBD5E1;{border};
                     border-radius:3px;padding:0.65rem 0.9rem;margin-bottom:0.4rem">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start">
                        <div>
                            <span style="font-weight:600;font-size:0.85rem;color:#1E3A5F">
                                {row.get('tender_reference','—')}</span>
                            <span style="font-size:0.72rem;color:#475569;margin-left:0.5rem">
                                {row.get('category','—')}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:0.5rem">
                            <span style="font-size:0.78rem;font-weight:700;color:{score_color}">{score}/5</span>
                            {badge_html}
                        </div>
                    </div>
                    <div style="font-size:0.75rem;color:#475569;margin-top:0.2rem">
                        {row.get('region','—')} &nbsp;·&nbsp; {row.get('department','—')}
                        &nbsp;·&nbsp; {fmt_inr(row.get('awarded_value'))}
                        &nbsp;·&nbsp; {str(row.get('publish_date',''))[:10]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("View Details", key=f"tbtn_{row['tender_id']}"):
                st.session_state.selected_tender_id = int(row["tender_id"])
                st.rerun()

# ── TENDER DETAIL ─────────────────────────────────────────────────────
with col_detail:
    tid = st.session_state.selected_tender_id
    if tid is None:
        st.markdown(
            """<div style="background:white;border:1px solid #CBD5E1;border-radius:4px;
                padding:2rem;text-align:center;color:#64748B;font-size:0.85rem">
                Select a tender to view its detail and risk indicators.</div>""",
            unsafe_allow_html=True,
        )
    else:
        detail = tender_service.get_tender_detail(tid)
        if not detail.get("found"):
            st.error("Tender not found.")
        else:
            tender      = detail["tender"]
            bids        = detail["bids"]
            bid_stats   = detail["bid_stats"]
            indicators_df = detail["indicators"]

            score      = int(tender.get("total_risk_score", 0))
            risk_level = tender.get("risk_level", "Low Risk")

            section_heading("Tender Detail")

            # ── Gauge + key facts side by side ──────────────────────
            g_col, info_col = st.columns([1, 1])

            with g_col:
                st.plotly_chart(risk_score_gauge(score, risk_level),
                                use_container_width=True)

                # Awarded value big number
                rl_color = {
                    "Low Risk": "#16A34A", "Moderate Risk": "#D97706",
                    "High Risk": "#EA580C", "Critical Risk": "#DC2626",
                }.get(risk_level, "#64748B")
                st.markdown(
                    f"""
                    <div style="text-align:center;margin-top:-0.5rem">
                        <div style="font-size:0.67rem;text-transform:uppercase;
                             letter-spacing:0.08em;color:#64748B">Awarded Value</div>
                        <div style="font-size:1.25rem;font-weight:800;color:#1E3A5F">
                            {fmt_inr(tender.get('awarded_value'))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with info_col:
                st.markdown(
                    f"""
                    <div class="tw-detail-panel">
                        <div style="font-size:0.88rem;font-weight:700;color:#1E3A5F;margin-bottom:0.5rem">
                            {tender.get('tender_reference','—')}</div>
                        <div class="tw-kv-row">
                            <span class="tw-kv-label">Title</span>
                            <span class="tw-kv-value" style="font-size:0.77rem">
                                {tender.get('title','—')}</span></div>
                        <div class="tw-kv-row">
                            <span class="tw-kv-label">Category</span>
                            <span class="tw-kv-value">{tender.get('category','—')}</span></div>
                        <div class="tw-kv-row">
                            <span class="tw-kv-label">Region</span>
                            <span class="tw-kv-value">{tender.get('region','—')}</span></div>
                        <div class="tw-kv-row">
                            <span class="tw-kv-label">Department</span>
                            <span class="tw-kv-value" style="font-size:0.75rem">
                                {tender.get('department','—')}</span></div>
                        <div class="tw-kv-row">
                            <span class="tw-kv-label">Tender Window</span>
                            <span class="tw-kv-value">{tender.get('tender_window_days','—')} days</span></div>
                        <div class="tw-kv-row">
                            <span class="tw-kv-label">Est. Value</span>
                            <span class="tw-kv-value">{fmt_inr(tender.get('estimated_value'))}</span></div>
                        <div class="tw-kv-row">
                            <span class="tw-kv-label">Awarded To</span>
                            <span class="tw-kv-value" style="font-size:0.77rem">
                                {tender.get('awarded_vendor_name','—')}</span></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # ── Bid Analysis ─────────────────────────────────────────
            section_heading(f"Bid Analysis — {bid_stats.get('bidder_count', 0)} Bidder(s)")
            bs1, bs2, bs3, bs4 = st.columns(4)
            bs1.metric("Bidders",     bid_stats.get("bidder_count", 0))
            bs2.metric("Lowest Bid",  fmt_inr(bid_stats.get("lowest_bid")))
            bs3.metric("Highest Bid", fmt_inr(bid_stats.get("highest_bid")))
            bs4.metric("Bid Spread",  fmt_pct(bid_stats.get("bid_spread_pct")))

            if not bids.empty:
                st.plotly_chart(
                    bid_comparison_bar(bids, tender.get("awarded_value")),
                    use_container_width=True,
                )

            # ── Risk Indicators ───────────────────────────────────────
            section_heading("Risk Indicators")
            if not indicators_df.empty:
                triggered = indicators_df[indicators_df["triggered"] == 1]
                clear     = indicators_df[indicators_df["triggered"] == 0]

                if not triggered.empty:
                    st.markdown(
                        f'<div style="font-size:0.78rem;font-weight:600;color:#DC2626;margin-bottom:0.4rem">'
                        f'⚠ {len(triggered)} indicator(s) triggered</div>',
                        unsafe_allow_html=True,
                    )
                    for _, ind in triggered.iterrows():
                        render_indicator_row(ind.to_dict())

                if not clear.empty:
                    with st.expander(f"✓ {len(clear)} indicator(s) clear — no anomaly detected"):
                        for _, ind in clear.iterrows():
                            render_indicator_row(ind.to_dict())
            else:
                st.caption("No risk assessment data available.")
