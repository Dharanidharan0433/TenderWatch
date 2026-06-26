"""
utils/styling.py
-----------------
Shared CSS and UI helpers for TenderWatch.
Government-grade procurement investigation aesthetic — no gradients, no gimmicks.
"""

import streamlit as st

# ── Colour constants ──────────────────────────────────────────────────
C_PRIMARY    = "#1E3A5F"
C_SECONDARY  = "#64748B"
C_ACCENT     = "#F59E0B"
C_SUCCESS    = "#16A34A"
C_RISK       = "#DC2626"
C_BG         = "#F8FAFC"
C_BORDER     = "#CBD5E1"
C_TEXT       = "#0F172A"
C_TEXT_MUTED = "#475569"

RISK_COLORS = {
    "Low Risk":      C_SUCCESS,
    "Moderate Risk": "#D97706",
    "High Risk":     "#EA580C",
    "Critical Risk": C_RISK,
}

RISK_BG = {
    "Low Risk":      "#F0FDF4",
    "Moderate Risk": "#FFFBEB",
    "High Risk":     "#FFF7ED",
    "Critical Risk": "#FEF2F2",
}

CSS = f"""
<style>
/* ── BASE ─────────────────────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
                 Helvetica, Arial, sans-serif;
    color: {C_TEXT};
}}

[data-testid="stAppViewContainer"] {{
    background-color: #F5F6FA !important;
}}

/* ── SIDEBAR ──────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {C_PRIMARY} !important;
    border-right: none !important;
}}

[data-testid="stSidebar"] > div * {{
    color: #E2E8F0 !important;
}}

/* Hide Streamlit's auto-generated nav entirely */
[data-testid="stSidebarNav"] {{
    display: none !important;
}}

/* ── SIDEBAR NAV ITEMS ────────────────────────────────────────── */
/* Style the st.page_link items to look like Image 2 */
[data-testid="stSidebar"] [data-testid="stPageLink"] {{
    margin: 0 !important;
    padding: 0 !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
    color: #94A3B8 !important;
    text-decoration: none !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.10em !important;
    text-transform: uppercase !important;
    display: flex !important;
    align-items: center !important;
    gap: 0.75rem !important;
    padding: 0.85rem 1.2rem !important;
    border-left: 3px solid transparent !important;
    border-radius: 0 !important;
    transition: all 0.15s ease !important;
    background: transparent !important;
    width: 100% !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{
    color: #F1F5F9 !important;
    border-left-color: #FF9933 !important;
    background: rgba(255,255,255,0.07) !important;
    text-decoration: none !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink-active"] a {{
    color: #FFFFFF !important;
    border-left-color: #FF9933 !important;
    background: rgba(255,153,51,0.12) !important;
    font-weight: 700 !important;
}}

/* Nav icon sizing */
[data-testid="stSidebar"] [data-testid="stPageLink"] a svg,
[data-testid="stSidebar"] [data-testid="stPageLink"] a img {{
    width: 16px !important;
    height: 16px !important;
    flex-shrink: 0 !important;
    opacity: 0.75 !important;
}}

[data-testid="stSidebar"] [data-testid="stPageLink-active"] a svg,
[data-testid="stSidebar"] [data-testid="stPageLink-active"] a img {{
    opacity: 1 !important;
}}

/* Nav divider line between brand and links */
.tw-nav-divider {{
    height: 1px;
    background: rgba(255,255,255,0.10);
    margin: 0.2rem 0 0.4rem;
}}

/* ── INPUT FIELDS ─────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div > div,
[data-testid="stNumberInput"] input {{
    background-color: #F1F5F9 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 4px !important;
    color: {C_TEXT} !important;
    font-size: 0.85rem !important;
}}

[data-testid="stTextInput"] input:focus,
[data-testid="stSelectbox"] > div > div:focus-within,
[data-testid="stNumberInput"] input:focus {{
    border-color: {C_PRIMARY} !important;
    outline: none !important;
    box-shadow: 0 0 0 2px rgba(30,58,95,0.12) !important;
}}

[data-testid="stSelectbox"] svg {{
    color: {C_SECONDARY} !important;
}}

/* ── METRIC CARDS ─────────────────────────────────────────────── */
div[data-testid="stMetric"] {{
    background: white;
    border: 1px solid {C_BORDER};
    border-top: 3px solid #FF9933;
    border-radius: 4px;
    padding: 0.8rem 1rem;
}}

div[data-testid="stMetric"] label {{
    font-size: 0.66rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {C_TEXT_MUTED} !important;
}}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-size: 1.45rem !important;
    font-weight: 800 !important;
    color: {C_PRIMARY} !important;
}}

/* ── SECTION HEADINGS ─────────────────────────────────────────── */
.tw-section-heading {{
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {C_PRIMARY} !important;
    border-bottom: 1px solid #FF9933 !important;
    padding-bottom: 0.35rem;
    margin-bottom: 0.65rem;
    margin-top: 1rem;
}}

/* ── RISK BADGES ──────────────────────────────────────────────── */
.tw-badge {{
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 2px 7px;
    border-radius: 2px;
    border: 1px solid currentColor;
}}

.tw-badge-low      {{ color: {C_SUCCESS};  background: #F0FDF4; border-color: #BBF7D0; }}
.tw-badge-moderate {{ color: #D97706;      background: #FFFBEB; border-color: #FDE68A; }}
.tw-badge-high     {{ color: #EA580C;      background: #FFF7ED; border-color: #FED7AA; }}
.tw-badge-critical {{ color: {C_RISK};     background: #FEF2F2; border-color: #FECACA; }}

/* ── TABLES ───────────────────────────────────────────────────── */
.tw-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
}}

.tw-table th {{
    background: {C_PRIMARY} !important;
    color: white;
    font-weight: 600;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 2px solid #FF9933 !important;
}}

.tw-table td {{
    padding: 0.42rem 0.75rem;
    border-bottom: 1px solid {C_BORDER};
    color: {C_TEXT};
    vertical-align: middle;
}}

.tw-table tr:nth-child(even) td {{
    background: #F8FAFC;
}}

/* ── DETAIL PANELS ────────────────────────────────────────────── */
.tw-detail-panel {{
    background: white;
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 1.1rem;
}}

.tw-kv-row {{
    display: flex;
    gap: 0.75rem;
    padding: 0.38rem 0;
    border-bottom: 1px solid #F1F5F9;
    font-size: 0.81rem;
}}

.tw-kv-label {{
    font-weight: 600;
    color: {C_TEXT_MUTED};
    min-width: 155px;
    font-size: 0.77rem;
}}

.tw-kv-value {{
    color: {C_TEXT};
}}

/* ── RISK INDICATORS ──────────────────────────────────────────── */
.tw-indicator-triggered {{
    background: #FEF2F2;
    border-left: 3px solid {C_RISK};
    border-radius: 2px;
    padding: 0.6rem 0.9rem;
    margin-bottom: 0.5rem;
}}

.tw-indicator-clear {{
    background: #F0FDF4;
    border-left: 3px solid {C_SUCCESS};
    border-radius: 2px;
    padding: 0.6rem 0.9rem;
    margin-bottom: 0.5rem;
}}

.tw-indicator-name {{
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.2rem;
}}

.tw-indicator-explanation {{
    font-size: 0.8rem;
    line-height: 1.5;
    color: {C_TEXT};
}}

.tw-indicator-metric {{
    font-size: 0.7rem;
    color: {C_TEXT_MUTED};
    margin-top: 0.25rem;
    font-family: "SFMono-Regular", "Consolas", monospace;
    word-break: break-all;
}}

/* ── RECOMMENDATIONS ──────────────────────────────────────────── */
.tw-rec-item {{
    display: flex;
    gap: 0.6rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid #F1F5F9;
    font-size: 0.82rem;
    line-height: 1.5;
}}

.tw-rec-num {{
    font-weight: 700;
    color: {C_ACCENT};
    min-width: 20px;
}}

/* ── SIDEBAR BRANDING ─────────────────────────────────────────── */
.tw-sidebar-brand {{
    padding: 1.4rem 1.2rem 1.1rem;
    border-bottom: 1px solid rgba(255,153,51,0.35);
    margin-bottom: 0.5rem;
}}

.tw-sidebar-brand-icon {{
    font-size: 1.4rem;
    margin-bottom: 0.3rem;
    line-height: 1;
}}

.tw-sidebar-brand-name {{
    font-size: 1.15rem;
    font-weight: 800;
    color: white !important;
    letter-spacing: 0.01em;
    line-height: 1.1;
}}

.tw-sidebar-brand-tagline {{
    font-size: 0.6rem;
    color: #64748B !important;
    margin-top: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    font-weight: 500;
}}

/* ── FILTER BAR ───────────────────────────────────────────────── */
.tw-filter-bar {{
    background: white;
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 0.85rem 1rem;
    margin-bottom: 1rem;
}}

/* ── BUTTONS ──────────────────────────────────────────────────── */
.stButton > button {{
    background: #FF9933 !important;
    color: #1E3A5F !important;
    border: none !important;
    border-radius: 4px !important;
    font-size: 0.8rem !important;
    font-weight: 700 !important;
    padding: 0.45rem 1.1rem !important;
    letter-spacing: 0.02em !important;
}}

.stButton > button:hover {{
    background: #e6871e !important;
    color: #1E3A5F !important;
    border: none !important;
}}

/* ── SELECTBOX LABELS ─────────────────────────────────────────── */
div[data-testid="stSelectbox"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stSlider"] label {{
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: {C_TEXT_MUTED} !important;
}}

/* ── EXPANDER ─────────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    background: white;
}}

/* ── SCROLLBAR ────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {C_BG}; }}
::-webkit-scrollbar-thumb {{ background: {C_BORDER}; border-radius: 3px; }}

/* ── SIDEBAR FOOTER ───────────────────────────────────────────── */
.tw-sidebar-footer {{
    position: fixed;
    bottom: 0;
    padding: 0.75rem 1.2rem;
    border-top: 1px solid rgba(255,255,255,0.08);
    font-size: 0.59rem;
    color: #64748B !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    line-height: 1.7;
    background: {C_PRIMARY};
    width: inherit;
}}

/* ── HEADER BAR ───────────────────────────────────────────────── */
[data-testid="stHeader"] {{
    background: {C_PRIMARY} !important;
    border-bottom: 4px solid #FF9933 !important;
}}

/* ── HERO SECTION ─────────────────────────────────────────────── */
.tw-hero {{
    text-align: center;
    padding: 2.5rem 1rem 1.5rem;
}}

.tw-hero-subtitle {{
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: {C_TEXT_MUTED};
    margin-bottom: 0.6rem;
}}

.tw-hero-title {{
    font-size: 2.8rem;
    font-weight: 900;
    color: {C_PRIMARY};
    letter-spacing: -0.03em;
    margin-bottom: 0.75rem;
    line-height: 1;
}}

.tw-hero-desc {{
    font-size: 0.92rem;
    color: {C_TEXT_MUTED};
    max-width: 680px;
    margin: 0 auto;
    line-height: 1.7;
}}

/* ── FEATURE CARDS GRID ───────────────────────────────────────── */
.tw-feature-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin: 1.5rem 0 1.5rem;
}}

.tw-feature-card {{
    background: white;
    border-radius: 6px;
    padding: 1.2rem 1.1rem 1.0rem;
    border-top: 4px solid transparent;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
}}

.tw-feature-card.fc-blue  {{ border-top-color: #2563EB; }}
.tw-feature-card.fc-orange{{ border-top-color: #F59E0B; }}
.tw-feature-card.fc-green {{ border-top-color: #16A34A; }}
.tw-feature-card.fc-sky   {{ border-top-color: #0EA5E9; }}

.tw-feature-icon {{
    font-size: 1.6rem;
    margin-bottom: 0.5rem;
    line-height: 1;
}}

.tw-feature-title {{
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: {C_PRIMARY};
    margin-bottom: 0.1rem;
}}

.tw-feature-big {{
    font-size: 2rem;
    font-weight: 900;
    color: {C_PRIMARY};
    line-height: 1.1;
}}

.tw-feature-sub {{
    font-size: 0.72rem;
    color: {C_TEXT_MUTED};
    margin-bottom: 0.5rem;
}}

.tw-feature-divider {{
    height: 1px;
    background: {C_BORDER};
    margin: 0.6rem 0;
}}

.tw-feature-desc {{
    font-size: 0.78rem;
    color: {C_TEXT_MUTED};
    line-height: 1.4;
}}

/* ── RISK TABLE ───────────────────────────────────────────────── */
.tw-risk-table {{
    background: white;
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}}

.tw-risk-table-header {{
    background: {C_PRIMARY};
    color: white;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 0.75rem 1.1rem;
}}

.tw-risk-row {{
    display: flex;
    align-items: flex-start;
    gap: 0.85rem;
    padding: 0.7rem 1.1rem;
    border-bottom: 1px solid #F1F5F9;
}}

.tw-risk-row:last-child {{
    border-bottom: none;
}}

.tw-risk-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 3px;
}}

.tw-risk-name {{
    font-size: 0.82rem;
    font-weight: 700;
    color: {C_PRIMARY};
    min-width: 160px;
    flex-shrink: 0;
}}

.tw-risk-desc {{
    font-size: 0.8rem;
    color: {C_TEXT_MUTED};
    line-height: 1.4;
}}

/* ── ABOUT PANEL ──────────────────────────────────────────────── */
.tw-about-panel {{
    background: {C_PRIMARY};
    border-radius: 6px;
    overflow: hidden;
    height: 100%;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}}

.tw-about-header {{
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: white;
    padding: 0.75rem 1.1rem;
    border-bottom: 1px solid rgba(255,255,255,0.12);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}

.tw-about-body {{
    font-size: 0.82rem;
    color: #CBD5E1;
    line-height: 1.7;
    padding: 1rem 1.1rem 1.2rem;
}}

/* ── NOTICE BOX ───────────────────────────────────────────────── */
.tw-notice {{
    display: flex;
    align-items: flex-start;
    gap: 0.9rem;
    background: white;
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 1rem 1.2rem;
    margin-top: 1.5rem;
    font-size: 0.83rem;
    color: {C_TEXT_MUTED};
    line-height: 1.6;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}}

.tw-notice-icon {{
    font-size: 1.4rem;
    flex-shrink: 0;
    margin-top: 0.05rem;
}}

.tw-notice strong {{
    color: {C_TEXT};
}}

/* ── PAGE HEADER ──────────────────────────────────────────────── */
.tw-page-header {{
    background: white;
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 0;
    margin-bottom: 1.5rem;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}}

.tw-page-header::before {{
    content: '';
    display: block;
    height: 5px;
    background: linear-gradient(to right,
        #FF9933 33.33%,
        #FFFFFF 33.33%, #FFFFFF 66.66%,
        #138808 66.66%
    );
}}

.tw-page-header-inner {{
    padding: 0.85rem 1.25rem 0.75rem;
    border-left: 4px solid {C_PRIMARY};
    text-align: left;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: white;
}}

.tw-page-title {{
    font-size: 2rem;
    font-weight: 800;
    color: {C_PRIMARY} !important;
    letter-spacing: -0.02em;
    margin: 0 0 0.2rem;
    opacity: 1 !important;
}}

.tw-page-subtitle {{
    font-size: 0.78rem;
    color: {C_TEXT_MUTED} !important;
    margin: 0;
    letter-spacing: 0.01em;
    opacity: 1 !important;
}}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="tw-sidebar-brand">
            <div class="tw-sidebar-brand-icon">🏛️</div>
            <div class="tw-sidebar-brand-name">TenderWatch</div>
            <div class="tw-sidebar-brand-tagline">Procurement Risk Intelligence</div>
        </div>
        
        """,
        unsafe_allow_html=True,
    )

    # Nav links with icons via page_link
    st.sidebar.page_link("app.py",                                    label="Dashboard",          )
    st.sidebar.page_link("pages/2_Vendor_Search.py",                  label="Vendor Search",     )
    st.sidebar.page_link("pages/3_Tender_Search.py",                  label="Tender Search",     )
    st.sidebar.page_link("pages/4_Investigation_Center.py",           label="Investigation Center", )
    st.sidebar.page_link("pages/vendor_participation_network.py",     label="Vendor Network",    )
    st.sidebar.page_link("pages/6_Reports.py",                        label="Reports",     )

    st.sidebar.markdown(
        """
        <div class="tw-sidebar-footer">
            TenderWatch · Open-Source<br>
            Govt. Procurement Risk Intelligence
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "") -> None:
    sub_html = f'<p class="tw-page-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div class="tw-page-header">
            <div class="tw-page-header-inner">
                <div>
                    <h1 class="tw-page-title">{title}</h1>
                    {sub_html}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def risk_badge(risk_level: str) -> str:
    cls_map = {
        "Low Risk":      "tw-badge-low",
        "Moderate Risk": "tw-badge-moderate",
        "High Risk":     "tw-badge-high",
        "Critical Risk": "tw-badge-critical",
    }
    cls = cls_map.get(risk_level, "tw-badge-low")
    return f'<span class="tw-badge {cls}">{risk_level}</span>'


def score_display(score: int, risk_level: str) -> str:
    color = RISK_COLORS.get(risk_level, C_SECONDARY)
    return (
        f'<span style="font-size:1.1rem;font-weight:700;color:{color}">{score}/5</span> '
        f'{risk_badge(risk_level)}'
    )


def fmt_inr(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
        if v >= 1_00_00_000:
            return f"₹{v / 1_00_00_000:.1f} Cr"
        if v >= 1_00_000:
            return f"₹{v / 1_00_000:.1f} L"
        return f"₹{v:,.0f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_pct(value, prefix_sign: bool = False) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
        sign = "+" if prefix_sign and v > 0 else ""
        return f"{sign}{v:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def section_heading(text: str) -> None:
    st.markdown(f'<div class="tw-section-heading">{text}</div>', unsafe_allow_html=True)


def render_indicator_row(item: dict) -> None:
    triggered = bool(item.get("triggered"))
    css_class = "tw-indicator-triggered" if triggered else "tw-indicator-clear"
    icon = "▶" if triggered else "✓"
    name_color = C_RISK if triggered else C_SUCCESS
    explanation = item.get("explanation", "")
    metric_html = ""
    if item.get("supporting_metric"):
        metric_raw = item["supporting_metric"]
        metric_html = f'<div class="tw-indicator-metric">{metric_raw}</div>'

    st.markdown(
        f"""
        <div class="{css_class}">
            <div class="tw-indicator-name" style="color:{name_color}">{icon} {item.get("detector_name","")}</div>
            <div class="tw-indicator-explanation">{explanation}</div>
            {metric_html}
        </div>
        """,
        unsafe_allow_html=True,
    )