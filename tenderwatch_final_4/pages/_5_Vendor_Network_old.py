"""
pages/5_Vendor_Network.py
--------------------------
Interactive vendor-tender participation network visualization.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.styling import (
    inject_css, sidebar_brand, page_header, section_heading,
    C_PRIMARY, C_SUCCESS, C_RISK, RISK_COLORS,
)
from services import network_service, tender_service
from visualizations.charts import vendor_network_graph

st.set_page_config(
    page_title="Vendor Network — TenderWatch",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
sidebar_brand()
page_header(
    "Vendor Participation Network",
    "Bipartite graph: vendors (◆) connected to tenders (●) they bid on — node colour = risk level",
)

# ── FILTERS ───────────────────────────────────────────────────────────
opts = tender_service.get_filter_options()

with st.container():
    f1, f2, f3, f4, f5 = st.columns([1, 1, 1, 1, 1])
    with f1:
        region = st.selectbox("Region", ["All"] + opts["regions"])
    with f2:
        category = st.selectbox("Category", ["All"] + opts["categories"])
    with f3:
        risk_filter = st.selectbox(
            "Tender Risk Filter",
            ["All Tenders", "Moderate+ Risk", "High+ Risk"],
        )
    with f4:
        max_vendors = st.slider("Max Vendors", min_value=10, max_value=50, value=25, step=5)
    with f5:
        st.markdown("<br>", unsafe_allow_html=True)
        build_btn = st.button("Build Network", use_container_width=True)

# ── LEGEND ─────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="display:flex;gap:1.5rem;font-size:0.75rem;color:#475569;
         padding:0.5rem 0;border-bottom:1px solid #CBD5E1;margin-bottom:0.75rem">
        <span><b>Node shapes:</b></span>
        <span>◆ Vendor</span>
        <span>● Tender</span>
        <span style="margin-left:1rem"><b>Tender node colour:</b></span>
        <span style="color:{RISK_COLORS['Low Risk']}">● Low Risk</span>
        <span style="color:{RISK_COLORS['Moderate Risk']}">● Moderate</span>
        <span style="color:{RISK_COLORS['High Risk']}">● High</span>
        <span style="color:{RISK_COLORS['Critical Risk']}">● Critical</span>
        <span style="margin-left:1rem">
            <span style="color:{C_PRIMARY}">◆ Vendor</span> (navy, sized by participation count)
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── BUILD ──────────────────────────────────────────────────────────────
if "network_data" not in st.session_state or build_btn:
    risk_map = {
        "All Tenders":    "",
        "Moderate+ Risk": "Moderate+",
        "High+ Risk":     "High+",
    }
    with st.spinner("Building network…"):
        st.session_state.network_data = network_service.build_network_data(
            region="" if region == "All" else region,
            category="" if category == "All" else category,
            risk_filter=risk_map.get(risk_filter, ""),
            max_vendors=max_vendors,
        )

graph_data = st.session_state.network_data
metrics = graph_data.get("metrics", {})

# ── METRICS ────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Vendor Nodes", metrics.get("vendor_count", 0))
m2.metric("Tender Nodes", metrics.get("tender_count", 0))
m3.metric("Connections", metrics.get("edge_count", 0))
m4.metric("Avg Connections / Node", metrics.get("avg_degree", 0))

# ── NETWORK CHART ──────────────────────────────────────────────────────
if graph_data["node_x"]:
    st.plotly_chart(vendor_network_graph(graph_data), use_container_width=True)
else:
    st.info("No network data to display with the current filters. Try broadening the selection.")

# ── INTERPRETATION NOTE ────────────────────────────────────────────────
st.markdown(
    """
    <div style="padding:0.75rem 1rem;background:#F8FAFC;border:1px solid #CBD5E1;
         border-left:3px solid #64748B;border-radius:3px;font-size:0.75rem;color:#475569;
         line-height:1.6;margin-top:0.5rem">
    <strong>Interpretation guidance:</strong>
    Vendors with many connections (large nodes) participate across many tenders.
    High-risk tender nodes (red/orange) adjacent to the same vendor node across multiple
    clusters may warrant further review. This visualisation is a structural overview only —
    connection patterns are not in themselves indicators of irregular procurement.
    </div>
    """,
    unsafe_allow_html=True,
)
