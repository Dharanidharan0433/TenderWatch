"""
pages/vendor_participation_network.py
---------------------------------------
Vendor Network — vendor-to-vendor co-participation investigation aid.
Renamed from "Vendor Participation Network" to "Vendor Network".
Sliders removed per user feedback (they cluttered the header).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from utils.styling import (
    inject_css, sidebar_brand, page_header, section_heading,
    C_PRIMARY, C_ACCENT, C_RISK,
)
from services import tender_service, vendor_service
from visualizations.network_graph import (
    build_vendor_participation_graph,
    render_vendor_participation_figure,
    get_vendor_connection_table,
)

st.set_page_config(
    page_title="Vendor Network — TenderWatch",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
sidebar_brand()
page_header(
    "Vendor Network",
    "Visualize recurring vendor participation patterns across government tenders",
)

# ── FILTERS (region / category / department only — no sliders) ────────
opts = tender_service.get_filter_options()
departments = sorted(opts.get("departments", []))

with st.container():
    c1, c2, c3 = st.columns(3)
    with c1:
        sel_region = st.selectbox("Region", ["All"] + opts["regions"])
    with c2:
        sel_category = st.selectbox("Category", ["All"] + opts["categories"])
    with c3:
        sel_dept = st.selectbox("Department", ["All"] + departments)

# ── VENDOR HIGHLIGHT + BUILD BUTTON ───────────────────────────────────
sh_col, btn_col = st.columns([3, 1])
with sh_col:
    highlight_name = st.text_input(
        "Highlight Vendor (optional)",
        placeholder="Type a vendor name to highlight it in the graph",
        label_visibility="visible",
    )
with btn_col:
    st.markdown("<br>", unsafe_allow_html=True)
    build_btn = st.button("Build Network", use_container_width=True, type="primary")

# ── RESOLVE HIGHLIGHT VENDOR ID ───────────────────────────────────────
highlight_vid: int | None = None
if highlight_name:
    all_vendors = vendor_service.get_all_vendor_options()
    name_lower = highlight_name.strip().lower()
    for v in all_vendors:
        if name_lower in v["vendor_name"].lower():
            highlight_vid = v["vendor_id"]
            break

# ── BUILD / CACHE GRAPH ───────────────────────────────────────────────
cache_key = "vpn_data"
rebuild = (
    build_btn
    or cache_key not in st.session_state
    or st.session_state.get("vpn_filters") != (sel_region, sel_category, sel_dept)
)

if rebuild or (highlight_vid is not None and
               st.session_state.get("vpn_highlight") != highlight_vid):
    with st.spinner("Building vendor participation network…"):
        graph_data = build_vendor_participation_graph(
            region="" if sel_region == "All" else sel_region,
            category="" if sel_category == "All" else sel_category,
            department="" if sel_dept == "All" else sel_dept,
            min_shared_tenders=1,
            max_vendors=30,
            highlight_vendor_id=highlight_vid,
        )
    st.session_state[cache_key] = graph_data
    st.session_state["vpn_filters"] = (sel_region, sel_category, sel_dept)
    st.session_state["vpn_highlight"] = highlight_vid
else:
    graph_data = st.session_state[cache_key]

metrics = graph_data.get("metrics", {})

# ── METRICS ROW ───────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Vendor Nodes",        metrics.get("vendor_count", 0))
m2.metric("Participation Links", metrics.get("edge_count", 0))
m3.metric("Tenders in Scope",    metrics.get("tender_count", 0))
m4.metric("Avg Connections",     metrics.get("avg_connections", 0))
m5.metric("Max Connections",     metrics.get("max_connections", 0))

st.markdown("<div style='margin-top:0.25rem'/>", unsafe_allow_html=True)

# ── GRAPH ─────────────────────────────────────────────────────────────
if graph_data["node_x"]:
    if highlight_vid and highlight_name:
        matched_name = next(
            (v["vendor_name"] for v in vendor_service.get_all_vendor_options()
             if v["vendor_id"] == highlight_vid),
            highlight_name,
        )
        st.markdown(
            f"""
            <div style="padding:0.45rem 0.85rem;background:#FFF7ED;
                 border:1px solid #F59E0B;border-left:3px solid #F59E0B;
                 border-radius:3px;font-size:0.78rem;color:#92400E;margin-bottom:0.5rem">
                Highlighting: <strong>{matched_name}</strong> — shown in
                <span style="color:#DC2626;font-weight:700">red</span>;
                connected vendors in <span style="color:#F59E0B;font-weight:700">amber</span>.
            </div>
            """,
            unsafe_allow_html=True,
        )
    fig = render_vendor_participation_figure(graph_data)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No vendor co-participation data available. Try broadening the filters.")

# ── CONNECTIONS TABLE ─────────────────────────────────────────────────
st.markdown(
    "<hr style='border:none;border-top:1px solid #E2E8F0;margin:0.75rem 0'/>",
    unsafe_allow_html=True,
)
section_heading("Vendor Connections Table")

conn_df = get_vendor_connection_table(graph_data)
if conn_df.empty:
    st.info("No connections to display.")
else:
    tbl_search = st.text_input(
        "Filter table by vendor name",
        placeholder="e.g. Metro Builders",
        key="conn_table_search",
        label_visibility="collapsed",
    )
    if tbl_search:
        mask = (
            conn_df["Vendor"].str.contains(tbl_search, case=False, na=False)
            | conn_df["Connected Vendor"].str.contains(tbl_search, case=False, na=False)
        )
        conn_df = conn_df[mask]

    st.dataframe(conn_df.reset_index(drop=True), use_container_width=True,
                 hide_index=True, height=320)
    st.markdown(
        f"<div style='font-size:0.72rem;color:#94A3B8;margin-top:0.25rem'>"
        f"Showing {len(conn_df):,} connection(s) · sorted by Shared Tenders descending.</div>",
        unsafe_allow_html=True,
    )

# ── INTERPRETATION NOTICE ─────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-top:1rem;padding:0.75rem 1rem;background:#F8FAFC;
         border:1px solid #CBD5E1;border-left:3px solid #64748B;border-radius:3px;
         font-size:0.75rem;color:#475569;line-height:1.6">
    <strong>Interpretation guidance:</strong>
    An edge between two vendors means they have both submitted bids on at least one shared tender.
    High co-participation may reflect normal industry concentration or regional market structure.
    This graph is an investigation aid only — it does not assert or imply irregular procurement.
    Use it to prioritise tenders for manual review, not to reach conclusions.
    </div>
    """,
    unsafe_allow_html=True,
)
