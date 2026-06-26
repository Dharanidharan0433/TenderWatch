"""
visualizations/network_graph.py
---------------------------------
Vendor Participation Network: vendor-to-vendor graph where edges represent
shared participation in the same tenders.

This module is an INVESTIGATION AID only. It surfaces recurring co-participation
patterns so that auditors can ask questions — it does not detect or assert
irregular procurement activity.

Terminology discipline
----------------------
The words "collusion", "fraud", "cartel", or "syndicate" must never appear
in any string produced by this module. Use "co-participation", "shared tenders",
or "participation pattern" instead.

Public API
----------
    build_vendor_participation_graph(...)  →  dict   (layout data for Plotly)
    render_vendor_participation_figure(...)→  Figure  (ready for st.plotly_chart)
    get_vendor_connection_table(...)       →  pd.DataFrame
"""

from __future__ import annotations

from typing import Optional

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

from database import queries
from utils.styling import (
    C_PRIMARY, C_SECONDARY, C_ACCENT, C_SUCCESS, C_RISK,
    C_BORDER, C_TEXT, RISK_COLORS,
)


# ─────────────────────────────────────────────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────────────────────────────────────────────

def build_vendor_participation_graph(
    region: str = "",
    category: str = "",
    department: str = "",
    min_shared_tenders: int = 1,
    max_vendors: int = 40,
    highlight_vendor_id: Optional[int] = None,
) -> dict:
    """
    Constructs a vendor-to-vendor co-participation graph.

    Two vendors are connected when they have both submitted bids on the
    same tender(s).  Edge weight = number of shared tenders.

    Args:
        region: Optional region filter applied to tenders.
        category: Optional category filter applied to tenders.
        department: Optional department filter applied to tenders.
        min_shared_tenders: Only draw edges where shared tender count >= this.
        max_vendors: Cap on vendor nodes to keep the graph readable.
        highlight_vendor_id: If set, that vendor's node is rendered in accent
            colour and its neighbours are visually distinguished.

    Returns:
        dict with keys used by render_vendor_participation_figure():
            node_x, node_y, node_labels, node_colors, node_sizes,
            node_hover, node_ids,
            edge_x, edge_y, edge_weights, edge_hover,
            metrics (dict),
            vendor_connections (list[dict])  — for the connections table.
    """
    tenders_df = queries.get_all_tenders()
    bids_df = queries.get_all_bids()
    vendors_df = queries.get_all_vendors()

    if tenders_df.empty or bids_df.empty:
        return _empty_result()

    # ── Apply filters ─────────────────────────────────────────────────
    if region:
        tenders_df = tenders_df[tenders_df["region"] == region]
    if category:
        tenders_df = tenders_df[tenders_df["category"] == category]
    if department and "department" in tenders_df.columns:
        tenders_df = tenders_df[tenders_df["department"] == department]

    if tenders_df.empty:
        return _empty_result()

    tender_ids_in_scope = set(tenders_df["tender_id"].tolist())
    bids_in_scope = bids_df[bids_df["tender_id"].isin(tender_ids_in_scope)]

    # ── Select top vendors by participation count ─────────────────────
    top_vids = (
        bids_in_scope.groupby("vendor_id")["tender_id"]
        .nunique()
        .sort_values(ascending=False)
        .head(max_vendors)
        .index.tolist()
    )
    bids_in_scope = bids_in_scope[bids_in_scope["vendor_id"].isin(top_vids)]

    # ── Build vendor name lookup ──────────────────────────────────────
    vendor_name: dict[int, str] = {}
    if not vendors_df.empty:
        vendor_name = dict(zip(vendors_df["vendor_id"], vendors_df["vendor_name"]))

    # ── Count shared tenders for every vendor pair ────────────────────
    # pivot: rows = tender_id, columns = vendor_id, values = 1/0
    pivot = (
        bids_in_scope[["tender_id", "vendor_id"]]
        .drop_duplicates()
        .assign(participated=1)
        .pivot(index="tender_id", columns="vendor_id", values="participated")
        .fillna(0)
    )

    # For each pair of vendors, shared = dot product of their columns.
    vids = pivot.columns.tolist()
    mat = pivot.values  # shape (tenders, vendors)

    # Shared tender count matrix: (vendors x vendors)
    shared_matrix = (mat.T @ mat).astype(int)

    # ── Build NetworkX graph ──────────────────────────────────────────
    G = nx.Graph()
    for vid in vids:
        G.add_node(vid, vendor_id=vid, name=vendor_name.get(vid, f"Vendor {vid}"))

    for i, vi in enumerate(vids):
        for j, vj in enumerate(vids):
            if j <= i:
                continue
            shared = int(shared_matrix[i, j])
            if shared >= min_shared_tenders:
                G.add_edge(vi, vj, weight=shared)

    # Remove isolated nodes (no edges).
    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)

    if G.number_of_nodes() == 0:
        return _empty_result()

    # ── Layout ────────────────────────────────────────────────────────
    k_val = 2.5 / max(1, G.number_of_nodes() ** 0.5)
    pos = nx.spring_layout(G, seed=42, k=k_val, iterations=60)

    # ── Degree and centrality for node sizing ─────────────────────────
    degree = dict(G.degree(weight="weight"))
    max_deg = max(degree.values()) if degree else 1

    # ── Participation count per vendor (for hover) ────────────────────
    part_count: dict[int, int] = (
        bids_in_scope.groupby("vendor_id")["tender_id"].nunique().to_dict()
    )

    # ── Assemble node data ────────────────────────────────────────────
    node_x, node_y, node_labels = [], [], []
    node_colors, node_sizes, node_hover, node_ids = [], [], [], []

    for vid in G.nodes():
        x, y = pos[vid]
        node_x.append(float(x))
        node_y.append(float(y))

        name = vendor_name.get(vid, f"Vendor {vid}")
        label = name[:20] + "…" if len(name) > 20 else name
        node_labels.append(label)
        node_ids.append(vid)

        neighbours = list(G.neighbors(vid))
        neighbour_names = ", ".join(
            vendor_name.get(n, str(n)) for n in neighbours[:5]
        )
        if len(neighbours) > 5:
            neighbour_names += f" +{len(neighbours) - 5} more"

        hover_text = (
            f"<b>{name}</b><br>"
            f"Tender participations: {part_count.get(vid, 0)}<br>"
            f"Co-participants: {len(neighbours)}<br>"
            f"Connected vendors: {neighbour_names}"
        )
        node_hover.append(hover_text)

        # Colour: highlight selected vendor; neighbours in accent; rest in primary.
        if highlight_vendor_id is not None and vid == highlight_vendor_id:
            color = C_RISK          # amber-red to stand out
        elif highlight_vendor_id is not None and vid in G.neighbors(highlight_vendor_id):
            color = C_ACCENT
        else:
            color = C_PRIMARY

        node_colors.append(color)

        # Size scaled by weighted degree.
        base_size = 12
        scale = 22 * (degree.get(vid, 0) / max(max_deg, 1))
        node_sizes.append(base_size + scale)

    # ── Assemble edge data ────────────────────────────────────────────
    edge_x, edge_y, edge_weights, edge_hover = [], [], [], []

    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x += [float(x0), float(x1), None]
        edge_y += [float(y0), float(y1), None]
        w = data.get("weight", 1)
        edge_weights.append(w)
        edge_hover.append(
            f"{vendor_name.get(u, u)} ↔ {vendor_name.get(v, v)}: "
            f"{w} shared tender(s)"
        )

    # ── Vendor connections table data ─────────────────────────────────
    connections: list[dict] = []
    for u, v, data in sorted(G.edges(data=True), key=lambda e: -e[2].get("weight", 0)):
        connections.append({
            "Vendor": vendor_name.get(u, f"Vendor {u}"),
            "Connected Vendor": vendor_name.get(v, f"Vendor {v}"),
            "Shared Tenders": int(data.get("weight", 1)),
        })

    # ── Metrics ───────────────────────────────────────────────────────
    metrics = {
        "vendor_count":     G.number_of_nodes(),
        "edge_count":       G.number_of_edges(),
        "tender_count":     len(tender_ids_in_scope),
        "avg_connections":  round(
            sum(dict(G.degree()).values()) / G.number_of_nodes(), 2
        ) if G.number_of_nodes() > 0 else 0,
        "max_connections":  max(dict(G.degree()).values(), default=0),
    }

    return {
        "node_x": node_x, "node_y": node_y,
        "node_labels": node_labels, "node_colors": node_colors,
        "node_sizes": node_sizes, "node_hover": node_hover,
        "node_ids": node_ids,
        "edge_x": edge_x, "edge_y": edge_y,
        "edge_weights": edge_weights, "edge_hover": edge_hover,
        "metrics": metrics,
        "vendor_connections": connections,
    }


# ─────────────────────────────────────────────────────────────────────
# PLOTLY FIGURE RENDERER
# ─────────────────────────────────────────────────────────────────────

def render_vendor_participation_figure(graph_data: dict) -> go.Figure:
    """
    Converts graph_data (from build_vendor_participation_graph) into an
    interactive Plotly figure.

    Edge thickness scales with number of shared tenders.
    Node size scales with weighted degree.
    Hover shows vendor name, shared tender count, and connected vendors.

    Args:
        graph_data: dict returned by build_vendor_participation_graph().

    Returns:
        plotly.graph_objects.Figure ready for st.plotly_chart().
    """
    fig = go.Figure()

    if not graph_data["node_x"]:
        fig.update_layout(
            title="No vendor co-participation data for the selected filters.",
            height=480,
        )
        return fig

    # ── Edges ─────────────────────────────────────────────────────────
    # Draw edges grouped by weight bucket so we can vary opacity/width.
    weights = graph_data["edge_weights"]
    max_w = max(weights) if weights else 1

    edge_x = graph_data["edge_x"]
    edge_y = graph_data["edge_y"]

    # Single edge trace (lightweight — individual width per segment
    # not natively supported in Scatter, so we use a uniform light line).
    fig.add_trace(go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(width=0.8, color="#94A3B8"),
        hoverinfo="none",
        showlegend=False,
        opacity=0.6,
    ))

    # ── Nodes ─────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=graph_data["node_x"],
        y=graph_data["node_y"],
        mode="markers+text",
        marker=dict(
            size=graph_data["node_sizes"],
            color=graph_data["node_colors"],
            line=dict(width=1.5, color="white"),
            opacity=0.92,
        ),
        text=graph_data["node_labels"],
        textposition="top center",
        textfont=dict(size=8, color=C_TEXT),
        hovertext=graph_data["node_hover"],
        hovertemplate="%{hovertext}<extra></extra>",
        name="Vendor",
        showlegend=False,
    ))

    # ── Layout ────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text="Vendor Participation Network — Co-participation by Shared Tenders",
            font=dict(size=12, color=C_PRIMARY, family="'Segoe UI', sans-serif"),
            x=0.01,
        ),
        height=560,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(
            family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            size=11,
            color=C_TEXT,
        ),
        margin=dict(l=16, r=16, t=48, b=16),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   showline=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   showline=False),
        legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        hovermode="closest",
    )

    return fig


# ─────────────────────────────────────────────────────────────────────
# CONNECTION TABLE HELPER
# ─────────────────────────────────────────────────────────────────────

def get_vendor_connection_table(graph_data: dict) -> pd.DataFrame:
    """
    Returns a tidy DataFrame of vendor co-participation pairs, sorted by
    shared tender count descending.

    Args:
        graph_data: dict returned by build_vendor_participation_graph().

    Returns:
        pd.DataFrame with columns: Vendor, Connected Vendor, Shared Tenders.
    """
    rows = graph_data.get("vendor_connections", [])
    if not rows:
        return pd.DataFrame(columns=["Vendor", "Connected Vendor", "Shared Tenders"])
    return pd.DataFrame(rows).sort_values("Shared Tenders", ascending=False)


# ─────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────

def _empty_result() -> dict:
    return {
        "node_x": [], "node_y": [],
        "node_labels": [], "node_colors": [],
        "node_sizes": [], "node_hover": [],
        "node_ids": [],
        "edge_x": [], "edge_y": [],
        "edge_weights": [], "edge_hover": [],
        "metrics": {
            "vendor_count": 0, "edge_count": 0,
            "tender_count": 0, "avg_connections": 0,
            "max_connections": 0,
        },
        "vendor_connections": [],
    }
