"""
pages/2_Vendor_Search.py
--------------------------
Search vendors, view profile, participation history, risk summary.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.styling import (
    inject_css, sidebar_brand, page_header, risk_badge,
    section_heading, fmt_inr, fmt_pct, render_indicator_row, C_PRIMARY,
)
from services import vendor_service
from visualizations.charts import (
    vendor_win_rate_trend, vendor_risk_trend, vendor_risk_distribution_donut,
)

st.set_page_config(
    page_title="Vendor Search — TenderWatch",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
sidebar_brand()
page_header("Vendor Search", "Search and investigate vendor participation records")

# ── FILTERS ──────────────────────────────────────────────────────────
opts = vendor_service.get_filter_options()

with st.container():
    fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
    with fc1:
        search_name = st.text_input("Vendor Name", placeholder="Search by name…")
    with fc2:
        search_region = st.selectbox("Region", ["All"] + opts["regions"])
    with fc3:
        search_category = st.selectbox("Category", ["All"] + opts["categories"])
    with fc4:
        st.markdown("<br>", unsafe_allow_html=True)
        do_search = st.button("Search Vendors", use_container_width=True)

# ── STATE ─────────────────────────────────────────────────────────────
if "vendor_results" not in st.session_state:
    st.session_state.vendor_results = vendor_service.search_vendors()
if "selected_vendor_id" not in st.session_state:
    st.session_state.selected_vendor_id = None

if do_search:
    st.session_state.vendor_results = vendor_service.search_vendors(
        name=search_name,
        region="" if search_region == "All" else search_region,
        category="" if search_category == "All" else search_category,
    )
    st.session_state.selected_vendor_id = None

results_df = st.session_state.vendor_results
col_left, col_right = st.columns([1, 1])

# ── RESULTS LIST ──────────────────────────────────────────────────────
with col_left:
    section_heading(f"Vendors ({len(results_df)} results)")
    if results_df.empty:
        st.info("No vendors match the search criteria.")
    else:
        for _, row in results_df.iterrows():
            won          = int(row.get("tenders_won", 0))
            participated = int(row.get("tenders_participated", 0))
            avg_risk     = float(row.get("avg_risk_score", 0))
            high_risk    = int(row.get("high_risk_count", 0))

            risk_color = ""
            risk_label = ""
            if avg_risk >= 2:
                risk_color = "#DC2626"
                risk_label = f"⚠ Avg Risk {avg_risk:.1f}"
            elif avg_risk >= 0.5:
                risk_color = "#D97706"
                risk_label = f"Avg Risk {avg_risk:.1f}"

            is_selected = st.session_state.selected_vendor_id == row["vendor_id"]
            border = "border-left:3px solid #1E3A5F" if is_selected else "border-left:3px solid transparent"

            risk_html = (
                f'&nbsp;·&nbsp;<span style="color:{risk_color};font-weight:600">{risk_label}</span>'
                if risk_label else ""
            )

            st.markdown(
                f'<div style="background:white;border:1px solid #CBD5E1;{border};'
                f'border-radius:3px;padding:0.65rem 0.9rem;margin-bottom:0.4rem">'
                f'<div style="font-weight:700;font-size:0.88rem;color:#0F172A">{row["vendor_name"]}</div>'
                f'<div style="font-size:0.72rem;color:#475569;margin-top:0.15rem">'
                f'{row["region"]} &nbsp;·&nbsp; {row["category_specialization"]}'
                f'&nbsp;·&nbsp; Won {won} / {participated} tenders{risk_html}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            if st.button("View Profile", key=f"vbtn_{row['vendor_id']}"):
                st.session_state.selected_vendor_id = int(row["vendor_id"])
                st.rerun()

# ── VENDOR DETAIL ─────────────────────────────────────────────────────
with col_right:
    vid = st.session_state.selected_vendor_id
    if vid is None:
        st.markdown(
            """<div style="background:white;border:1px solid #CBD5E1;border-radius:4px;
                padding:2rem;text-align:center;color:#64748B;font-size:0.85rem">
                Select a vendor from the list to view their profile.</div>""",
            unsafe_allow_html=True,
        )
    else:
        profile = vendor_service.get_vendor_profile(vid)
        if not profile.get("found"):
            st.error("Vendor not found.")
        else:
            vendor      = profile["identity"]
            stats       = profile["stats"]
            risk_summary = profile["risk_summary"]

            section_heading("Vendor Profile")

            # Identity card
            st.markdown(
                f'<div class="tw-detail-panel" style="margin-bottom:0.75rem">'
                f'<div style="font-size:1rem;font-weight:700;color:#1E3A5F;margin-bottom:0.5rem">{vendor["vendor_name"]}</div>'
                f'<div class="tw-kv-row"><span class="tw-kv-label">Registration</span>'
                f'<span class="tw-kv-value">{vendor.get("registration_number","—")}</span></div>'
                f'<div class="tw-kv-row"><span class="tw-kv-label">Region</span>'
                f'<span class="tw-kv-value">{vendor.get("region","—")}</span></div>'
                f'<div class="tw-kv-row"><span class="tw-kv-label">Specialization</span>'
                f'<span class="tw-kv-value">{vendor.get("category_specialization","—")}</span></div>'
                f'<div class="tw-kv-row"><span class="tw-kv-label">Registered Since</span>'
                f'<span class="tw-kv-value">{str(vendor.get("date_registered","—"))[:10]}</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Stats row — fixed: show moderate + high separately, rename avg_risk_score
            moderate_count = int(risk_summary.get("Moderate Risk", 0))
            high_count     = int(risk_summary.get("High Risk", 0))
            critical_count = int(risk_summary.get("Critical Risk", 0))

            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Won / Participated",
                      f"{stats['tenders_won']} / {stats['tenders_participated']}")
            s2.metric("Win Rate", f"{stats['win_rate']:.1f}%")
            s3.metric("Moderate Risk Tenders", moderate_count)
            s4.metric("High / Critical Risk", high_count + critical_count)

            # Risk score row
            st.markdown(
                f'<div style="background:#F8FAFC;border:1px solid #CBD5E1;border-radius:3px;'
                f'padding:0.55rem 0.9rem;margin:0.4rem 0 0.75rem;'
                f'display:flex;align-items:center;gap:1.5rem;font-size:0.8rem">'
                f'<span style="color:#475569">Risk Score (avg across awarded tenders):</span>'
                f'<span style="font-weight:700;font-size:1.05rem;color:#1E3A5F">'
                f'{stats["avg_risk_score"]:.2f} / 5.00</span></div>',
                unsafe_allow_html=True,
            )

            # Charts tabs
            tab1, tab2, tab3 = st.tabs(["Risk History", "Win Rate Trend", "Risk Distribution"])

            with tab1:
                risk_trend = vendor_service.get_vendor_risk_trend(vid)
                if not risk_trend.empty:
                    st.plotly_chart(vendor_risk_trend(risk_trend), use_container_width=True)
                else:
                    st.caption("No awarded tender history available.")

            with tab2:
                win_rate_df = vendor_service.get_vendor_win_rate_over_time(vid)
                if not win_rate_df.empty:
                    st.plotly_chart(vendor_win_rate_trend(win_rate_df), use_container_width=True)
                else:
                    st.caption("No bid history available.")

            with tab3:
                st.plotly_chart(vendor_risk_distribution_donut(risk_summary), use_container_width=True)

            # Tender history
            section_heading("Awarded Tender History")
            history_df = vendor_service.get_vendor_tender_history(vid)
            if history_df.empty:
                st.caption("No awarded tenders on record.")
            else:
                for _, row in history_df.head(10).iterrows():
                    badge = risk_badge(row.get("risk_level", "Low Risk"))
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;align-items:center;'
                        f'padding:0.45rem 0.7rem;border-bottom:1px solid #F1F5F9;font-size:0.8rem">'
                        f'<div>'
                        f'<span style="font-weight:600;color:#1E3A5F">{row.get("tender_reference","—")}</span>'
                        f'<span style="color:#475569;margin-left:0.5rem">{row.get("category","—")}</span>'
                        f'</div>'
                        f'<div style="display:flex;gap:0.75rem;align-items:center">'
                        f'<span>{fmt_inr(row.get("awarded_value"))}</span>{badge}'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )