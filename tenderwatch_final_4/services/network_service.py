"""
services/network_service.py
-----------------------------
Builds vendor-tender bipartite graph data for the Vendor Network page.
Uses NetworkX for graph construction and centrality metrics, returns
plain dicts of coordinates/colors for Plotly rendering.
"""

import networkx as nx
import numpy as np
import pandas as pd

from database import queries
from utils.styling import C_PRIMARY, C_RISK, C_SUCCESS, RISK_COLORS, C_ACCENT


def build_network_data(
    region: str = "",
    category: str = "",
    risk_filter: str = "",
    max_vendors: int = 30,
) -> dict:
    """
    Builds a vendor-tender bipartite graph and returns layout data
    suitable for Plotly rendering.

    Args:
        region: Optional region filter.
        category: Optional category filter.
        risk_filter: If set, only include tenders at this risk level or above.
        max_vendors: Caps vendor nodes to keep the graph readable.

    Returns:
        dict with keys: node_x, node_y, node_text, node_color, node_size,
        node_type, edge_x, edge_y, vendor_count, tender_count, metrics.
    """
    tenders_df = queries.get_all_tenders()
    bids_df = queries.get_all_bids()

    if tenders_df.empty or bids_df.empty:
        return _empty_graph()

    # Apply filters.
    if region:
        tenders_df = tenders_df[tenders_df["region"] == region]
    if category:
        tenders_df = tenders_df[tenders_df["category"] == category]
    if risk_filter == "High+":
        tenders_df = tenders_df[tenders_df["total_risk_score"] >= 3]
    elif risk_filter == "Moderate+":
        tenders_df = tenders_df[tenders_df["total_risk_score"] >= 1]

    if tenders_df.empty:
        return _empty_graph()

    # Limit scope to keep the graph readable.
    tender_ids = set(tenders_df["tender_id"].tolist())
    bids_subset = bids_df[bids_df["tender_id"].isin(tender_ids)]

    # Top vendors by participation count.
    top_vendors = (
        bids_subset.groupby("vendor_id")["tender_id"]
        .nunique()
        .sort_values(ascending=False)
        .head(max_vendors)
        .index.tolist()
    )
    bids_subset = bids_subset[bids_subset["vendor_id"].isin(top_vendors)]
    tender_ids_in_scope = set(bids_subset["tender_id"].tolist())
    tenders_in_scope = tenders_df[tenders_df["tender_id"].isin(tender_ids_in_scope)]

    # Build bipartite graph.
    G = nx.Graph()

    for vid in top_vendors:
        G.add_node(f"v_{vid}", node_type="vendor", vendor_id=vid)

    for _, row in tenders_in_scope.iterrows():
        G.add_node(
            f"t_{row['tender_id']}",
            node_type="tender",
            tender_id=row["tender_id"],
            risk_score=row["total_risk_score"],
            risk_level=row.get("risk_level", "Low Risk"),
        )

    for _, row in bids_subset.iterrows():
        v_node = f"v_{row['vendor_id']}"
        t_node = f"t_{row['tender_id']}"
        if G.has_node(v_node) and G.has_node(t_node):
            G.add_edge(v_node, t_node, weight=float(row.get("bid_amount", 1)))

    if G.number_of_nodes() == 0:
        return _empty_graph()

    # Layout.
    pos = nx.spring_layout(G, seed=42, k=1.8 / (G.number_of_nodes() ** 0.5))

    # Build vendors name lookup.
    all_vendors = queries.get_all_vendors()
    vendor_names = dict(zip(all_vendors["vendor_id"], all_vendors["vendor_name"])) \
        if not all_vendors.empty else {}

    # Degree centrality for node sizing.
    degree = nx.degree_centrality(G)

    node_x, node_y, node_text, node_color, node_size, node_type = [], [], [], [], [], []

    for node, data in G.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)

        if data["node_type"] == "vendor":
            vid = data["vendor_id"]
            name = vendor_names.get(vid, f"Vendor {vid}")
            # Shorten long names
            label = name[:18] + "…" if len(name) > 18 else name
            node_text.append(label)
            node_color.append(C_PRIMARY)
            node_size.append(14 + degree.get(node, 0) * 60)
            node_type.append("vendor")
        else:
            risk_level = data.get("risk_level", "Low Risk")
            score = data.get("risk_score", 0)
            node_text.append(f"Score:{score}")
            node_color.append(RISK_COLORS.get(risk_level, C_SUCCESS))
            node_size.append(8 + degree.get(node, 0) * 30)
            node_type.append("tender")

    # Edges.
    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    # Metrics.
    metrics = {
        "vendor_count": len([n for n in G.nodes() if G.nodes[n]["node_type"] == "vendor"]),
        "tender_count": len([n for n in G.nodes() if G.nodes[n]["node_type"] == "tender"]),
        "edge_count": G.number_of_edges(),
        "avg_degree": round(sum(dict(G.degree()).values()) / G.number_of_nodes(), 2)
        if G.number_of_nodes() > 0 else 0,
    }

    return {
        "node_x": node_x, "node_y": node_y, "node_text": node_text,
        "node_color": node_color, "node_size": node_size, "node_type": node_type,
        "edge_x": edge_x, "edge_y": edge_y,
        "metrics": metrics,
    }


def _empty_graph() -> dict:
    return {
        "node_x": [], "node_y": [], "node_text": [], "node_color": [],
        "node_size": [], "node_type": [], "edge_x": [], "edge_y": [],
        "metrics": {"vendor_count": 0, "tender_count": 0,
                    "edge_count": 0, "avg_degree": 0},
    }
