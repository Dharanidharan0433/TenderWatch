"""
visualizations/charts.py
--------------------------
All Plotly chart functions for TenderWatch.
Returns plotly.graph_objects.Figure objects — no Streamlit imports.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.styling import (
    C_PRIMARY, C_SECONDARY, C_ACCENT, C_SUCCESS, C_RISK,
    C_BORDER, C_BG, C_TEXT, C_TEXT_MUTED, RISK_COLORS,
)

_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
_AXIS_COLOR = "#0F172A"   # dark, clearly visible axis labels
_LAYOUT_BASE = dict(
    font=dict(family=_FONT, size=11, color=_AXIS_COLOR),
    paper_bgcolor="white",
    plot_bgcolor="white",
)
_DEFAULT_MARGIN = dict(l=12, r=12, t=36, b=12)


# ── DASHBOARD ─────────────────────────────────────────────────────────

def risk_distribution_bar(dist_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar: tender count by risk level. Fixed for readability."""
    order = ["Low Risk", "Moderate Risk", "High Risk", "Critical Risk"]
    df = dist_df.set_index("risk_level").reindex(order).fillna(0).reset_index()

    fig = go.Figure()
    for _, row in df.iterrows():
        count = int(row["count"])
        fig.add_trace(go.Bar(
            x=[count],
            y=[row["risk_level"]],
            orientation="h",
            marker_color=RISK_COLORS.get(row["risk_level"], C_SECONDARY),
            text=[str(count)] if count > 0 else [""],
            textposition="outside",
            textfont=dict(size=11, color=C_TEXT, family=_FONT),
            showlegend=False,
        ))

    max_val = max(int(df["count"].max()), 1)
    fig.update_layout(
        **_LAYOUT_BASE,
        title=dict(text="Tenders by Risk Level", font=dict(size=12, color=C_PRIMARY)),
        height=220,
        margin=dict(l=110, r=50, t=40, b=20),
        xaxis=dict(
            showgrid=True,
            gridcolor="#F1F5F9",
            range=[0, max_val * 1.25],
            tickfont=dict(size=10, color="#0F172A"),
        ),
        yaxis=dict(
            categoryorder="array",
            categoryarray=order[::-1],
            tickfont=dict(size=11, color="#0F172A"),
            ticklen=0,
        ),
        barmode="overlay",
    )
    return fig


def monthly_trend_line(trend_df: pd.DataFrame) -> go.Figure:
    """Dual-axis: tender count (bars) + avg risk score (line) over time."""
    fig = go.Figure()

    if trend_df.empty:
        fig.update_layout(
            **_LAYOUT_BASE,
            margin=_DEFAULT_MARGIN,
            title=dict(text="Tender Volume & Risk Score Trend",
                       font=dict(size=12, color=C_PRIMARY)),
            height=240,
            annotations=[dict(
                text="No trend data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=13, color=C_SECONDARY),
            )],
        )
        return fig

    fig.add_trace(go.Bar(
        x=trend_df["month"],
        y=trend_df["count"],
        name="Tenders",
        marker_color="#BFDBFE",
        marker_line_color="#93C5FD",
        marker_line_width=0.5,
        yaxis="y1",
    ))

    fig.add_trace(go.Scatter(
        x=trend_df["month"],
        y=trend_df["avg_risk_score"],
        name="Avg Risk Score",
        line=dict(color=C_RISK, width=2),
        mode="lines+markers",
        marker=dict(size=4),
        yaxis="y2",
    ))

    fig.update_layout(
        **_LAYOUT_BASE,
        margin=_DEFAULT_MARGIN,
        title=dict(text="Tender Volume & Risk Score Trend",
                   font=dict(size=12, color=C_PRIMARY)),
        height=240,
        xaxis=dict(showgrid=False, tickangle=-40, tickfont=dict(size=9, color="#0F172A")),
        yaxis=dict(title=dict(text="Tenders", font=dict(color="#0F172A", size=11)), showgrid=True, gridcolor="#F1F5F9",
                   tickfont=dict(size=10, color="#0F172A")),
        yaxis2=dict(title=dict(text="Avg Risk", font=dict(color="#0F172A", size=11)), overlaying="y", side="right",
                    range=[0, 3], tickfont=dict(size=9, color="#0F172A"), showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=10),
                    bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def region_risk_heatmap(region_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar: tender count per region, colored by avg risk."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=region_df["count"],
        y=region_df["region"],
        orientation="h",
        marker=dict(
            color=region_df["avg_risk_score"],
            colorscale=[[0, "#DBEAFE"], [0.5, C_ACCENT], [1, C_RISK]],
            cmin=0, cmax=2,
            colorbar=dict(title="Avg Risk", tickfont=dict(size=9, color="#0F172A"), len=0.7),
        ),
        text=region_df["count"],
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        title=dict(text="Tenders by Region", font=dict(size=12, color=C_PRIMARY)),
        height=270,
        margin=dict(l=110, r=30, t=40, b=20),
        yaxis=dict(categoryorder="total ascending", tickfont=dict(size=10, color="#0F172A")),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
    )
    return fig


def category_risk_bar(cat_df: pd.DataFrame) -> go.Figure:
    """Grouped bar: total vs high-risk per category."""
    cat_df = cat_df.sort_values("count", ascending=False).head(10)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Total Tenders",
        x=cat_df["category"],
        y=cat_df["count"],
        marker_color="#DBEAFE",
        marker_line_color="#93C5FD",
        marker_line_width=0.5,
    ))
    fig.add_trace(go.Bar(
        name="Flagged Risk",
        x=cat_df["category"],
        y=cat_df["high_risk_count"],
        marker_color=C_RISK,
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        margin=_DEFAULT_MARGIN,
        title=dict(text="Categories — Total vs Risk Flagged",
                   font=dict(size=12, color=C_PRIMARY)),
        height=270,
        barmode="group",
        xaxis=dict(tickangle=-35, tickfont=dict(size=9, color="#0F172A"), showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10, color="#0F172A")),
        legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
    )
    return fig


# ── VENDOR CHARTS ──────────────────────────────────────────────────────

def vendor_win_rate_trend(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["month"],
        y=df["win_rate"],
        mode="lines+markers",
        line=dict(color=C_PRIMARY, width=2),
        marker=dict(size=5),
        fill="tozeroy",
        fillcolor="rgba(30,58,95,0.07)",
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        margin=_DEFAULT_MARGIN,
        title=dict(text="Monthly Win Rate (%)", font=dict(size=12, color=C_PRIMARY)),
        height=220,
        xaxis=dict(tickangle=-30, tickfont=dict(size=9, color="#0F172A"), showgrid=False),
        yaxis=dict(range=[0, 100], ticksuffix="%", showgrid=True,
                   gridcolor="#F1F5F9", tickfont=dict(size=10, color="#0F172A")),
    )
    return fig


def vendor_risk_trend(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["award_date"],
        y=df["total_risk_score"],
        mode="markers+lines",
        line=dict(color=C_ACCENT, width=1.5, dash="dot"),
        marker=dict(size=7, color=df["total_risk_score"],
                    colorscale=[[0, C_SUCCESS], [0.4, C_ACCENT], [1, C_RISK]],
                    cmin=0, cmax=5),
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        margin=_DEFAULT_MARGIN,
        title=dict(text="Risk Score — Awarded Tenders", font=dict(size=12, color=C_PRIMARY)),
        height=220,
        xaxis=dict(tickangle=-30, tickfont=dict(size=9, color="#0F172A"), showgrid=False),
        yaxis=dict(range=[-0.2, 5.2], showgrid=True, gridcolor="#F1F5F9",
                   tickfont=dict(size=10, color="#0F172A"), dtick=1),
    )
    return fig


def vendor_risk_distribution_donut(risk_summary: dict) -> go.Figure:
    labels = list(risk_summary.keys())
    values = list(risk_summary.values())
    colors = [RISK_COLORS.get(l, C_SECONDARY) for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textfont=dict(size=10),
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        margin=_DEFAULT_MARGIN,
        title=dict(text="Risk Level Distribution", font=dict(size=12, color=C_PRIMARY)),
        height=220,
        showlegend=True,
        legend=dict(font=dict(size=9), bgcolor="rgba(0,0,0,0)"),
    )
    return fig


# ── TENDER CHARTS ──────────────────────────────────────────────────────

def bid_comparison_bar(bids_df: pd.DataFrame, awarded_value=None) -> go.Figure:
    """Bar chart comparing all bids, highlight the winning bid."""
    bids_sorted = bids_df.sort_values("bid_amount").copy()
    colors = [
        C_SUCCESS if bool(row.get("is_winning_bid")) else "#BFDBFE"
        for _, row in bids_sorted.iterrows()
    ]
    labels = [
        row.get("vendor_name", f"Vendor {row.get('vendor_id','?')}")[:22]
        for _, row in bids_sorted.iterrows()
    ]
    fig = go.Figure(go.Bar(
        x=labels,
        y=bids_sorted["bid_amount"],
        marker_color=colors,
        marker_line_color="white",
        marker_line_width=1,
        text=[f"₹{v/1e7:.1f}Cr" for v in bids_sorted["bid_amount"]],
        textposition="outside",
        textfont=dict(size=9),
    ))
    if awarded_value:
        fig.add_hline(y=awarded_value, line_dash="dash",
                      line_color=C_ACCENT, line_width=1.5,
                      annotation_text="Awarded", annotation_font_size=10)
    fig.update_layout(
        **_LAYOUT_BASE,
        margin=_DEFAULT_MARGIN,
        title=dict(text="Bid Comparison", font=dict(size=12, color=C_PRIMARY)),
        height=230,
        xaxis=dict(tickangle=-30, tickfont=dict(size=9, color="#0F172A"), showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickfont=dict(size=10, color="#0F172A")),
    )
    return fig


def risk_score_gauge(score: int, risk_level: str) -> go.Figure:
    """Gauge chart for risk score 0-5."""
    color = RISK_COLORS.get(risk_level, C_SECONDARY)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(font=dict(size=36, color=color, family=_FONT)),
        gauge=dict(
            axis=dict(range=[0, 5], tickwidth=1, tickcolor=C_BORDER,
                      tickfont=dict(size=11, color="#0F172A"), nticks=6),
            bar=dict(color=color, thickness=0.28),
            bgcolor="white",
            borderwidth=1,
            bordercolor=C_BORDER,
            steps=[
                dict(range=[0, 1], color="#F0FDF4"),
                dict(range=[1, 2], color="#FFFBEB"),
                dict(range=[2, 3], color="#FFF7ED"),
                dict(range=[3, 5], color="#FEF2F2"),
            ],
        ),
        title=dict(text=risk_level, font=dict(size=13, color=color, family=_FONT)),
    ))
    fig.update_layout(
        paper_bgcolor="white",
        font=dict(family=_FONT),
        height=200,
        margin=dict(l=20, r=20, t=30, b=10),
    )
    return fig


# ── NETWORK GRAPH ──────────────────────────────────────────────────────

def vendor_network_graph(graph_data: dict) -> go.Figure:
    """Bipartite vendor-tender participation network (Plotly)."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=graph_data["edge_x"],
        y=graph_data["edge_y"],
        mode="lines",
        line=dict(width=0.6, color="#CBD5E1"),
        hoverinfo="none",
        showlegend=False,
    ))

    vendor_mask = [t == "vendor" for t in graph_data["node_type"]]
    tender_mask = [t == "tender" for t in graph_data["node_type"]]

    for mask, name, symbol in [
        (vendor_mask, "Vendor", "diamond"),
        (tender_mask, "Tender", "circle"),
    ]:
        if not any(mask):
            continue
        x = [v for v, m in zip(graph_data["node_x"], mask) if m]
        y = [v for v, m in zip(graph_data["node_y"], mask) if m]
        text = [v for v, m in zip(graph_data["node_text"], mask) if m]
        color = [v for v, m in zip(graph_data["node_color"], mask) if m]
        size = [v for v, m in zip(graph_data["node_size"], mask) if m]

        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode="markers+text",
            marker=dict(symbol=symbol, size=size, color=color,
                        line=dict(width=1, color="white")),
            text=text,
            textposition="top center",
            textfont=dict(size=8),
            hovertemplate="%{text}<extra></extra>",
            name=name,
        ))

    layout = dict(**_LAYOUT_BASE)
    layout["legend"] = dict(itemsizing="constant", font=dict(size=10),
                            bgcolor="rgba(0,0,0,0)")
    fig.update_layout(
        **layout,
        title=dict(text="Vendor–Tender Participation Network",
                   font=dict(size=12, color=C_PRIMARY)),
        height=560,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig
