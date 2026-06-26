"""
pages/6_Reports.py
-------------------
Generate and download PDF investigation reports for vendors or tenders.
"""

import streamlit as st
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.styling import (
    inject_css, sidebar_brand, page_header, section_heading,
    risk_badge, fmt_inr,
)
from services import report_service, vendor_service, investigation_service
from database import queries

st.set_page_config(
    page_title="Reports — TenderWatch",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
sidebar_brand()
page_header(
    "Investigation Reports",
    "Generate downloadable PDF reports for vendor or tender investigations",
)

# ── REPORT TYPE SELECTOR ──────────────────────────────────────────────
report_type = st.radio(
    "Report Type",
    ["Vendor Investigation Report", "Tender Investigation Report"],
    horizontal=True,
)

st.markdown("<hr style='border:none;border-top:1px solid #CBD5E1;margin:0.75rem 0'/>",
            unsafe_allow_html=True)

col_form, col_preview = st.columns([1, 1])

# ── VENDOR REPORT ──────────────────────────────────────────────────────
if report_type == "Vendor Investigation Report":
    with col_form:
        section_heading("Select Vendor")

        vendor_options = vendor_service.get_all_vendor_options()
        if not vendor_options:
            st.error("No vendors found in the database.")
            st.stop()

        vendor_names = {v["vendor_name"]: v["vendor_id"] for v in vendor_options}
        selected_name = st.selectbox("Vendor", list(vendor_names.keys()))
        selected_vid = vendor_names[selected_name]

        st.markdown("<div style='margin-top:0.5rem'/>", unsafe_allow_html=True)
        gen_btn = st.button("Generate Vendor Report", use_container_width=True)

        if gen_btn:
            with st.spinner("Generating PDF…"):
                try:
                    pdf_path = report_service.generate_vendor_report(selected_vid)
                    st.session_state.last_vendor_pdf = pdf_path
                    st.session_state.last_vendor_pdf_name = os.path.basename(pdf_path)
                    st.success("Report generated.")
                except Exception as e:
                    st.error(f"Report generation failed: {e}")

        if "last_vendor_pdf" in st.session_state:
            pdf_path = st.session_state.last_vendor_pdf
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="⬇ Download PDF Report",
                    data=pdf_bytes,
                    file_name=st.session_state.last_vendor_pdf_name,
                    mime="application/pdf",
                    use_container_width=True,
                )

    with col_preview:
        if selected_vid:
            section_heading("Vendor Risk Summary")
            context = investigation_service.get_vendor_investigation_context(selected_vid)
            if context.get("found"):
                vendor = context["vendor"]
                narrative = context.get("narrative", "")
                pattern_summary = context.get("pattern_summary", {})
                recs = context.get("recommendations", [])
                risk_count = context.get("risk_tender_count", 0)

                # Profile card
                st.markdown(
                    f"""
                    <div style="background:white;border:1px solid #CBD5E1;border-radius:3px;
                         padding:0.9rem 1rem;margin-bottom:0.75rem">
                        <div style="font-weight:700;color:#1E3A5F;font-size:0.92rem">
                            {vendor['vendor_name']}</div>
                        <div style="font-size:0.73rem;color:#475569;margin-top:0.15rem">
                            {vendor.get('region','—')} · {vendor.get('category_specialization','—')}
                        </div>
                        <div style="font-size:0.8rem;margin-top:0.4rem">
                            <b style="color:#DC2626">{risk_count}</b> tender(s) with risk indicators
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Pattern summary
                section_heading("Risk Indicator Pattern")
                for detector, count in sorted(
                    pattern_summary.items(), key=lambda x: x[1], reverse=True
                ):
                    color = "#DC2626" if count > 0 else "#16A34A"
                    icon = "⚠" if count > 0 else "✓"
                    st.markdown(
                        f"""
                        <div style="display:flex;justify-content:space-between;
                             padding:0.35rem 0.5rem;border-bottom:1px solid #F1F5F9;
                             font-size:0.8rem">
                            <span>{detector}</span>
                            <span style="color:{color};font-weight:600">{icon} {count}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Narrative
                if narrative:
                    section_heading("Summary")
                    st.markdown(
                        f'<div style="background:#F8FAFC;border:1px solid #CBD5E1;'
                        f'border-radius:3px;padding:0.75rem;font-size:0.78rem;'
                        f'line-height:1.6;white-space:pre-line">{narrative}</div>',
                        unsafe_allow_html=True,
                    )

# ── TENDER REPORT ──────────────────────────────────────────────────────
else:
    with col_form:
        section_heading("Select Tender")

        # Let user search for tender by reference
        search_ref = st.text_input("Tender Reference or Keyword", placeholder="e.g. TW-0042")
        from services import tender_service as ts
        search_results = ts.search_tenders(keyword=search_ref, status="") if search_ref else ts.search_tenders(status="")
        search_results = search_results.head(100)

        if search_results.empty:
            st.info("No tenders found.")
            st.stop()

        tender_options = {
            f"{row['tender_reference']} — {row.get('category','')[:20]} ({row.get('risk_level','')})": int(row["tender_id"])
            for _, row in search_results.iterrows()
        }
        selected_label = st.selectbox("Tender", list(tender_options.keys()))
        selected_tid = tender_options[selected_label]

        st.markdown("<div style='margin-top:0.5rem'/>", unsafe_allow_html=True)
        gen_btn2 = st.button("Generate Tender Report", use_container_width=True)

        if gen_btn2:
            with st.spinner("Generating PDF…"):
                try:
                    pdf_path = report_service.generate_tender_report(selected_tid)
                    st.session_state.last_tender_pdf = pdf_path
                    st.session_state.last_tender_pdf_name = os.path.basename(pdf_path)
                    st.success("Report generated.")
                except Exception as e:
                    st.error(f"Report generation failed: {e}")

        if "last_tender_pdf" in st.session_state:
            pdf_path = st.session_state.last_tender_pdf
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="⬇ Download PDF Report",
                    data=pdf_bytes,
                    file_name=st.session_state.last_tender_pdf_name,
                    mime="application/pdf",
                    use_container_width=True,
                )

    with col_preview:
        if selected_tid:
            section_heading("Tender Risk Summary")
            summary = investigation_service.get_investigation_summary(selected_tid)
            if summary.get("found"):
                tender = summary["tender"]
                triggered = summary["triggered_indicators"]
                risk_score = summary["risk_score"]
                risk_level = summary["risk_level"]
                recs = summary["recommendations"]

                rl_color = {"Low Risk": "#16A34A", "Moderate Risk": "#D97706",
                            "High Risk": "#EA580C", "Critical Risk": "#DC2626"}.get(risk_level, "#64748B")

                st.markdown(
                    f"""
                    <div style="background:white;border:1px solid #CBD5E1;
                         border-top:3px solid {rl_color};border-radius:3px;
                         padding:0.9rem 1rem;margin-bottom:0.75rem">
                        <div style="font-weight:700;color:#1E3A5F;font-size:0.88rem">
                            {tender.get('tender_reference','—')}</div>
                        <div style="font-size:0.73rem;color:#475569;margin:0.15rem 0">
                            {tender.get('title','—')}</div>
                        <div style="font-size:0.73rem;color:#475569">
                            {tender.get('region','—')} · {tender.get('category','—')}
                            · {fmt_inr(tender.get('awarded_value'))}
                        </div>
                        <div style="font-size:1rem;font-weight:700;color:{rl_color};margin-top:0.5rem">
                            Risk Score {risk_score}/5 — {risk_level}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if triggered:
                    section_heading(f"Triggered Indicators ({len(triggered)})")
                    for item in triggered:
                        from utils.styling import render_indicator_row
                        render_indicator_row(item)
                else:
                    st.success("No risk indicators triggered for this tender.")

                if recs:
                    section_heading("Top Recommendations")
                    for i, rec in enumerate(recs[:4], 1):
                        st.markdown(
                            f"""
                            <div style="display:flex;gap:0.5rem;padding:0.35rem 0;
                                 border-bottom:1px solid #F1F5F9;font-size:0.78rem;line-height:1.4">
                                <span style="font-weight:700;color:#F59E0B">{i}.</span>
                                <span>{rec}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )


# ── HIGH RISK TENDER CSV EXPORT ───────────────────────────────────────
st.markdown(
    "<hr style='border:none;border-top:1px solid #E2E8F0;margin:1.25rem 0'/>",
    unsafe_allow_html=True,
)
section_heading("High Risk Tender Export (CSV)")
st.markdown(
    """
    <div style="font-size:0.8rem;color:#475569;line-height:1.6;margin-bottom:0.75rem">
    Export all tenders above a selected risk threshold as a structured CSV file.
    Suitable for bulk review by audit teams, compliance officers, or external reviewers.
    </div>
    """,
    unsafe_allow_html=True,
)

csv_col1, csv_col2 = st.columns([1, 2])
with csv_col1:
    min_score = st.selectbox(
        "Minimum Risk Score",
        options=[1, 2, 3, 4, 5],
        index=0,
        format_func=lambda s: {
            1: "1 — Moderate Risk and above",
            2: "2 — Elevated Risk and above",
            3: "3 — High Risk and above",
            4: "4 — Very High Risk and above",
            5: "5 — Critical Risk only",
        }.get(s, str(s)),
    )

    csv_btn = st.button("Generate CSV Export", use_container_width=True)

    if csv_btn:
        with st.spinner("Generating CSV…"):
            try:
                csv_path = report_service.generate_high_risk_csv(min_risk_score=min_score)
                st.session_state.last_csv_path = csv_path
                st.success("CSV ready.")
            except ValueError as e:
                st.warning(str(e))
            except Exception as e:
                st.error(f"CSV generation failed: {e}")

    if "last_csv_path" in st.session_state:
        csv_path = st.session_state.last_csv_path
        if os.path.exists(csv_path):
            with open(csv_path, "rb") as f:
                csv_bytes = f.read()
            st.download_button(
                label="⬇ Download High Risk CSV",
                data=csv_bytes,
                file_name=os.path.basename(csv_path),
                mime="text/csv",
                use_container_width=True,
            )

with csv_col2:
    # Preview: show what the CSV will contain.
    section_heading("Preview")
    try:
        from database import queries as _q
        tenders_df = _q.get_all_tenders()
        if not tenders_df.empty:
            preview = tenders_df[tenders_df["total_risk_score"] >= min_score][
                ["tender_reference", "category", "region", "department",
                 "awarded_value", "total_risk_score", "risk_level"]
            ].sort_values("total_risk_score", ascending=False).head(8)

            if preview.empty:
                st.info(f"No tenders found with risk score ≥ {min_score}.")
            else:
                preview_display = preview.rename(columns={
                    "tender_reference": "Reference",
                    "category": "Category",
                    "region": "Region",
                    "department": "Department",
                    "awarded_value": "Awarded (INR)",
                    "total_risk_score": "Score",
                    "risk_level": "Risk Level",
                }).reset_index(drop=True)
                st.dataframe(preview_display, use_container_width=True, hide_index=True)
                st.markdown(
                    f"<div style='font-size:0.72rem;color:#94A3B8'>"
                    f"Showing top 8 of {len(tenders_df[tenders_df['total_risk_score'] >= min_score])} "
                    f"tender(s) with score ≥ {min_score}.</div>",
                    unsafe_allow_html=True,
                )
    except Exception:
        st.info("Preview unavailable.")

# ── DISCLAIMER ────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-top:1.5rem;padding:0.75rem 1rem;background:#F8FAFC;
         border:1px solid #CBD5E1;border-left:3px solid #64748B;border-radius:3px;
         font-size:0.73rem;color:#475569;line-height:1.6">
    <strong>Report Disclaimer:</strong>
    All generated reports are based on automated statistical pattern analysis.
    They contain Procurement Risk Indicators only — not findings of irregularity
    or legal violation. Reports are for official internal use only and must not
    be shared with vendors or external parties pending independent review.
    </div>
    """,
    unsafe_allow_html=True,
)
