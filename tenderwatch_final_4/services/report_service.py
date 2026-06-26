"""
services/report_service.py
----------------------------
Orchestrates the generation of downloadable PDF investigation reports.

This service sits between the data layer (queries / investigation_service)
and the PDF rendering layer (ReportLab). It:

  1. Gathers all data needed for a report in one place.
  2. Passes that data to the appropriate PDF builder function.
  3. Returns the path of the saved PDF so the UI can offer a download.

Two report types are supported:

  VENDOR INVESTIGATION REPORT
    A profile of one vendor — identity, participation statistics,
    risk summary across all awarded tenders, recommended actions.

  TENDER INVESTIGATION REPORT
    A detail view of one tender — specifications, bid breakdown,
    all 5 risk indicators with explanations, recommended actions.

IMPORTANT — terminology discipline:
    All strings in this file (section headings, boilerplate text, etc.)
    must stay within the approved terminology: "Procurement Risk",
    "Risk Indicator", "Procurement Anomaly", "Investigation Recommended",
    "Audit Recommended". The words "fraud", "corrupt*", or "criminal"
    must never appear in generated reports.
"""

import os
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.platypus import KeepTogether

from database import queries
from services import investigation_service

# ─────────────────────────────────────────────────────────────────────
# COLOUR PALETTE  (matches config.py / styling.py)
# ─────────────────────────────────────────────────────────────────────

COLOR_PRIMARY   = colors.HexColor("#1E3A5F")   # dark navy
COLOR_SECONDARY = colors.HexColor("#64748B")   # slate grey
COLOR_ACCENT    = colors.HexColor("#F59E0B")   # amber
COLOR_SUCCESS   = colors.HexColor("#16A34A")   # green
COLOR_RISK      = colors.HexColor("#DC2626")   # red
COLOR_BG_LIGHT  = colors.HexColor("#F8FAFC")   # near-white
COLOR_BORDER    = colors.HexColor("#CBD5E1")   # light slate

RISK_LEVEL_COLORS = {
    "Low Risk":      colors.HexColor("#16A34A"),
    "Moderate Risk": colors.HexColor("#D97706"),
    "High Risk":     colors.HexColor("#EA580C"),
    "Critical Risk": colors.HexColor("#DC2626"),
}

# ─────────────────────────────────────────────────────────────────────
# OUTPUT DIRECTORY
# ─────────────────────────────────────────────────────────────────────

_EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports",
    "generated",
)
os.makedirs(_EXPORT_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINTS
# ─────────────────────────────────────────────────────────────────────

def generate_vendor_report(vendor_id: int) -> str:
    """
    Generates a Vendor Investigation Report PDF and returns its path.

    Args:
        vendor_id: The vendor to report on.

    Returns:
        Absolute path to the saved PDF file.

    Raises:
        ValueError: if the vendor_id is not found in the database.
    """
    context = investigation_service.get_vendor_investigation_context(vendor_id)
    if not context.get("found"):
        raise ValueError(f"Vendor {vendor_id} not found.")

    vendor = context["vendor"]
    timestamp = _timestamp()
    safe_name = vendor["vendor_name"].replace(" ", "_").replace(".", "")[:30]
    filename = f"Vendor_Report_{safe_name}_{timestamp}.pdf"
    filepath = os.path.join(_EXPORT_DIR, filename)

    doc = _make_doc(filepath, f"Vendor Investigation Report – {vendor['vendor_name']}")
    story = _build_vendor_story(context)
    doc.build(story)

    return filepath


def generate_tender_report(tender_id: int) -> str:
    """
    Generates a Tender Investigation Report PDF and returns its path.

    Args:
        tender_id: The tender to report on.

    Returns:
        Absolute path to the saved PDF file.

    Raises:
        ValueError: if the tender_id is not found in the database.
    """
    summary = investigation_service.get_investigation_summary(tender_id)
    if not summary.get("found"):
        raise ValueError(f"Tender {tender_id} not found.")

    tender = summary["tender"]
    timestamp = _timestamp()
    ref = tender.get("tender_reference", str(tender_id)).replace("/", "-")
    filename = f"Tender_Report_{ref}_{timestamp}.pdf"
    filepath = os.path.join(_EXPORT_DIR, filename)

    bids_df = queries.get_bids_for_tender(tender_id)

    doc = _make_doc(filepath, f"Tender Investigation Report – {ref}")
    story = _build_tender_story(summary, bids_df)
    doc.build(story)

    return filepath


# ─────────────────────────────────────────────────────────────────────
# DOCUMENT SETUP
# ─────────────────────────────────────────────────────────────────────

def _make_doc(filepath: str, title: str) -> SimpleDocTemplate:
    """Creates a SimpleDocTemplate with consistent margins and metadata."""
    return SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="TenderWatch Risk Intelligence Platform",
        subject="Procurement Risk Investigation Report",
    )


# ─────────────────────────────────────────────────────────────────────
# SHARED STYLES
# ─────────────────────────────────────────────────────────────────────

def _get_styles() -> dict:
    """Returns a dict of named ParagraphStyles for consistent typography."""
    base = getSampleStyleSheet()

    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=COLOR_PRIMARY,
            spaceAfter=6,
            alignment=TA_LEFT,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            fontName="Helvetica",
            fontSize=11,
            textColor=COLOR_SECONDARY,
            spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "section_heading": ParagraphStyle(
            "section_heading",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=COLOR_PRIMARY,
            spaceBefore=12,
            spaceAfter=6,
            borderPad=(0, 0, 2, 0),
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.black,
            leading=14,
            spaceAfter=4,
        ),
        "body_bold": ParagraphStyle(
            "body_bold",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.black,
            leading=14,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="Helvetica",
            fontSize=8,
            textColor=COLOR_SECONDARY,
            leading=12,
            spaceAfter=3,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer",
            fontName="Helvetica-Oblique",
            fontSize=8,
            textColor=COLOR_SECONDARY,
            leading=12,
            spaceAfter=4,
        ),
        "risk_triggered": ParagraphStyle(
            "risk_triggered",
            fontName="Helvetica",
            fontSize=9,
            textColor=COLOR_RISK,
            leading=13,
            spaceAfter=3,
        ),
        "risk_clear": ParagraphStyle(
            "risk_clear",
            fontName="Helvetica",
            fontSize=9,
            textColor=COLOR_SUCCESS,
            leading=13,
            spaceAfter=3,
        ),
        "recommendation": ParagraphStyle(
            "recommendation",
            fontName="Helvetica",
            fontSize=9,
            textColor=COLOR_PRIMARY,
            leading=13,
            leftIndent=10,
            spaceAfter=4,
        ),
    }


# ─────────────────────────────────────────────────────────────────────
# SHARED FLOWABLE HELPERS
# ─────────────────────────────────────────────────────────────────────

def _section_rule():
    return HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceAfter=4)


def _section_header(title: str, styles: dict):
    return [
        Paragraph(title.upper(), styles["section_heading"]),
        _section_rule(),
    ]


def _kv_table(pairs: list[tuple[str, str]], styles: dict) -> Table:
    """
    Renders a two-column key/value table for metadata fields.
    pairs: list of (label, value) tuples.
    """
    data = [
        [
            Paragraph(label, styles["body_bold"]),
            Paragraph(str(value) if value is not None else "—", styles["body"]),
        ]
        for label, value in pairs
    ]
    col_widths = [55 * mm, 110 * mm]
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
        ("LINEBELOW",   (0, 0), (-1, -1), 0.3, COLOR_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def _risk_badge_paragraph(risk_level: str, score: int, styles: dict) -> Paragraph:
    """Renders a risk level badge as a styled paragraph."""
    badge_color = RISK_LEVEL_COLORS.get(risk_level, COLOR_SECONDARY)
    hex_color = badge_color.hexval() if hasattr(badge_color, 'hexval') else "#64748B"
    text = (
        f'<font color="{hex_color}"><b>[RISK SCORE: {score}/5 — {risk_level.upper()}]</b></font>'
    )
    return Paragraph(text, styles["section_heading"])


def _cover_block(report_type: str, subject_name: str, generated_at: str, styles: dict) -> list:
    """Renders the report cover header block."""
    flowables = [
        Paragraph("TENDERWATCH", ParagraphStyle(
            "brand",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=COLOR_SECONDARY,
            spaceAfter=2,
        )),
        Paragraph("Government Procurement Risk Intelligence Platform", ParagraphStyle(
            "brand_sub",
            fontName="Helvetica",
            fontSize=9,
            textColor=COLOR_SECONDARY,
            spaceAfter=8,
        )),
        HRFlowable(width="100%", thickness=2, color=COLOR_PRIMARY, spaceAfter=8),
        Paragraph(report_type, styles["cover_title"]),
        Paragraph(subject_name, styles["cover_subtitle"]),
        Paragraph(
            f"Generated: {generated_at}  |  CONFIDENTIAL – FOR OFFICIAL USE ONLY",
            styles["small"],
        ),
        HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceBefore=8, spaceAfter=12),
    ]
    return flowables


def _disclaimer_block(styles: dict) -> list:
    """Renders the mandatory disclaimer footer block."""
    return [
        Spacer(1, 8 * mm),
        _section_rule(),
        Paragraph(
            "DISCLAIMER: This report contains automated procurement risk indicators generated "
            "by the TenderWatch statistical analysis platform. Risk indicators represent "
            "statistical patterns in procurement data that may warrant further investigation. "
            "They do not constitute a finding of irregularity, misconduct, or legal violation, "
            "and should not be acted upon without independent verification by a qualified "
            "procurement officer or auditor. This document is intended for official internal "
            "use only and should not be disclosed to vendors or external parties.",
            styles["disclaimer"],
        ),
    ]


def _fmt_currency(value) -> str:
    """Formats a numeric value as Indian Rupee currency string."""
    if value is None:
        return "—"
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_date(value) -> str:
    """Formats a date string or None for display."""
    if value is None:
        return "—"
    return str(value)[:10]  # ISO YYYY-MM-DD


def _fmt_pct(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):+.1f}%"


# ─────────────────────────────────────────────────────────────────────
# VENDOR REPORT BUILDER
# ─────────────────────────────────────────────────────────────────────

def _build_vendor_story(context: dict) -> list:
    """Assembles the full ReportLab story (list of Flowables) for a vendor report."""
    styles = _get_styles()
    story = []
    generated_at = datetime.datetime.now().strftime("%d %B %Y, %H:%M")

    vendor = context["vendor"]
    stats = context.get("stats", {})
    pattern_summary = context.get("pattern_summary", {})
    narrative = context.get("narrative", "")
    recommendations = context.get("recommendations", [])

    # ── Cover ────────────────────────────────────────────────────────
    story += _cover_block(
        "VENDOR INVESTIGATION REPORT",
        vendor.get("vendor_name", "Unknown Vendor"),
        generated_at,
        styles,
    )

    # ── Vendor Identity ──────────────────────────────────────────────
    story += _section_header("Vendor Identity", styles)
    identity_pairs = [
        ("Vendor Name",           vendor.get("vendor_name", "—")),
        ("Registration Number",   vendor.get("registration_number", "—")),
        ("Region",                vendor.get("region", "—")),
        ("Category Specialization", vendor.get("category_specialization", "—")),
        ("Date Registered",       _fmt_date(vendor.get("date_registered"))),
    ]
    story.append(_kv_table(identity_pairs, styles))
    story.append(Spacer(1, 4 * mm))

    # ── Participation Statistics ─────────────────────────────────────
    story += _section_header("Participation Statistics", styles)
    stat_pairs = [
        ("Tenders Participated",    stats.get("tenders_participated", 0)),
        ("Tenders Won (Awarded)",   stats.get("tenders_won", 0)),
        ("Win Rate",                f"{stats.get('win_rate', 0):.1f}%"),
        ("Total Contract Value",    _fmt_currency(stats.get("total_contract_value", 0))),
        ("Average Risk Score",      f"{stats.get('avg_risk_score', 0):.2f} / 5.00"),
        ("High/Critical Risk Tenders", stats.get("high_risk_count", 0)),
    ]
    story.append(_kv_table(stat_pairs, styles))
    story.append(Spacer(1, 4 * mm))

    # ── Risk Pattern Summary ─────────────────────────────────────────
    if pattern_summary:
        story += _section_header("Risk Indicator Pattern Summary", styles)
        story.append(
            Paragraph(
                "Number of awarded tenders where each risk indicator was triggered:",
                styles["body"],
            )
        )
        pattern_data = [["Risk Indicator", "Tender Count Triggered"]]
        for detector, count in sorted(
            pattern_summary.items(), key=lambda x: x[1], reverse=True
        ):
            triggered_text = str(count) if count == 0 else f"⚠ {count}"
            pattern_data.append([detector, triggered_text])

        pattern_tbl = Table(pattern_data, colWidths=[100 * mm, 65 * mm])
        pattern_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), COLOR_PRIMARY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.3, COLOR_BORDER),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(pattern_tbl)
        story.append(Spacer(1, 4 * mm))

    # ── Investigation Narrative ──────────────────────────────────────
    if narrative:
        story += _section_header("Investigation Summary", styles)
        for line in narrative.split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), styles["body"]))
        story.append(Spacer(1, 4 * mm))

    # ── Recommendations ──────────────────────────────────────────────
    if recommendations:
        story += _section_header("Recommended Actions", styles)
        for i, rec in enumerate(recommendations, 1):
            story.append(
                Paragraph(f"{i}. {rec}", styles["recommendation"])
            )
        story.append(Spacer(1, 4 * mm))

    # ── Flagged Tenders ──────────────────────────────────────────────
    flagged_df = context.get("flagged_tenders")
    if flagged_df is not None and not flagged_df.empty:
        story += _section_header(
            f"Awarded Tenders with Risk Indicators ({len(flagged_df)} Tenders)",
            styles,
        )
        flagged_data = [[
            "Reference", "Category", "Region",
            "Awarded Value", "Risk Score", "Risk Level",
        ]]
        for _, row in flagged_df.iterrows():
            risk_level = row.get("risk_level", "Low Risk")
            flagged_data.append([
                row.get("tender_reference", "—"),
                row.get("category", "—"),
                row.get("region", "—"),
                _fmt_currency(row.get("awarded_value")),
                str(int(row.get("total_risk_score", 0))),
                risk_level,
            ])

        flagged_tbl = Table(
            flagged_data,
            colWidths=[32 * mm, 30 * mm, 26 * mm, 30 * mm, 20 * mm, 28 * mm],
        )
        flagged_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), COLOR_PRIMARY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.3, COLOR_BORDER),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("WORDWRAP",      (0, 0), (-1, -1), True),
        ]))
        story.append(flagged_tbl)

    # ── Disclaimer ───────────────────────────────────────────────────
    story += _disclaimer_block(styles)
    return story


# ─────────────────────────────────────────────────────────────────────
# TENDER REPORT BUILDER
# ─────────────────────────────────────────────────────────────────────

def _build_tender_story(summary: dict, bids_df) -> list:
    """Assembles the full ReportLab story for a tender investigation report."""
    styles = _get_styles()
    story = []
    generated_at = datetime.datetime.now().strftime("%d %B %Y, %H:%M")

    tender = summary["tender"]
    risk_score = summary.get("risk_score", 0)
    risk_level = summary.get("risk_level", "Low Risk")
    triggered = summary.get("triggered_indicators", [])
    clear = summary.get("clear_indicators", [])
    narrative = summary.get("narrative", "")
    recommendations = summary.get("recommendations", [])

    # ── Cover ────────────────────────────────────────────────────────
    story += _cover_block(
        "TENDER INVESTIGATION REPORT",
        f"{tender.get('tender_reference', '—')} — {tender.get('title', '—')}",
        generated_at,
        styles,
    )

    # ── Risk Score Badge ─────────────────────────────────────────────
    story.append(_risk_badge_paragraph(risk_level, risk_score, styles))
    story.append(Spacer(1, 4 * mm))

    # ── Tender Specifications ────────────────────────────────────────
    story += _section_header("Tender Specifications", styles)
    spec_pairs = [
        ("Tender Reference",  tender.get("tender_reference", "—")),
        ("Title",             tender.get("title", "—")),
        ("Category",          tender.get("category", "—")),
        ("Region",            tender.get("region", "—")),
        ("Department",        tender.get("department", "—")),
        ("Publish Date",      _fmt_date(tender.get("publish_date"))),
        ("Submission Deadline", _fmt_date(tender.get("submission_deadline"))),
        ("Tender Window",     f"{tender.get('tender_window_days', '—')} days"),
        ("Status",            tender.get("status", "—")),
        ("Estimated Value",   _fmt_currency(tender.get("estimated_value"))),
        ("Awarded Value",     _fmt_currency(tender.get("awarded_value"))),
        ("Overage vs Estimate", _fmt_pct(
            ((tender.get("awarded_value", 0) or 0) - (tender.get("estimated_value", 0) or 0))
            / (tender.get("estimated_value", 1) or 1) * 100
            if tender.get("estimated_value") else None
        )),
        ("Awarded To",        tender.get("awarded_vendor_name", "—")),
        ("Vendor Registration", tender.get("awarded_vendor_reg", "—")),
    ]
    story.append(_kv_table(spec_pairs, styles))
    story.append(Spacer(1, 4 * mm))

    # ── Risk Indicators ──────────────────────────────────────────────
    story += _section_header("Risk Indicator Assessment", styles)

    if triggered:
        story.append(
            Paragraph(
                f"<b>{len(triggered)} indicator(s) triggered:</b>",
                styles["body_bold"],
            )
        )
        for item in triggered:
            story.append(KeepTogether([
                Paragraph(
                    f"▶ {item['detector_name'].upper()}",
                    styles["risk_triggered"],
                ),
                Paragraph(item["explanation"], styles["body"]),
                Paragraph(
                    f"Supporting metric: {item.get('supporting_metric', '—')}",
                    styles["small"],
                ),
                Spacer(1, 3 * mm),
            ]))
    else:
        story.append(
            Paragraph(
                "No risk indicators were triggered for this tender.",
                styles["risk_clear"],
            )
        )

    if clear:
        story.append(Spacer(1, 2 * mm))
        story.append(
            Paragraph(
                f"<b>{len(clear)} indicator(s) clear:</b>",
                styles["body_bold"],
            )
        )
        for item in clear:
            story.append(
                Paragraph(
                    f"✓ {item['detector_name']}: {item['explanation']}",
                    styles["risk_clear"],
                )
            )
    story.append(Spacer(1, 4 * mm))

    # ── Bid Analysis ─────────────────────────────────────────────────
    if bids_df is not None and not bids_df.empty:
        story += _section_header(
            f"Bid Analysis ({len(bids_df)} Bid(s) Received)",
            styles,
        )

        # Summary stats above the table.
        amounts = bids_df["bid_amount"]
        avg_bid = float(amounts.mean())
        spread_pct = (
            round((float(amounts.max()) - float(amounts.min())) / avg_bid * 100, 2)
            if avg_bid > 0 else 0.0
        )
        bid_stat_pairs = [
            ("Number of Bidders",    bids_df["vendor_id"].nunique()),
            ("Lowest Bid",           _fmt_currency(amounts.min())),
            ("Highest Bid",          _fmt_currency(amounts.max())),
            ("Average Bid",          _fmt_currency(avg_bid)),
            ("Bid Value Spread",     f"{spread_pct}% of average bid"),
        ]
        story.append(_kv_table(bid_stat_pairs, styles))
        story.append(Spacer(1, 3 * mm))

        # Full bid table.
        bid_data = [["Vendor Name", "Bid Amount", "Bid Date", "Winning Bid"]]
        for _, row in bids_df.sort_values("bid_amount").iterrows():
            bid_data.append([
                row.get("vendor_name", "—"),
                _fmt_currency(row.get("bid_amount")),
                _fmt_date(row.get("bid_date")),
                "YES" if row.get("is_winning_bid") else "No",
            ])

        bid_tbl = Table(bid_data, colWidths=[70 * mm, 38 * mm, 28 * mm, 24 * mm])
        bid_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), COLOR_PRIMARY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.3, COLOR_BORDER),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            # Highlight winning bid row in green text.
            *[
                ("TEXTCOLOR", (3, i + 1), (3, i + 1),
                 COLOR_SUCCESS if row.get("is_winning_bid") else colors.black)
                for i, (_, row) in enumerate(bids_df.sort_values("bid_amount").iterrows())
            ],
        ]))
        story.append(bid_tbl)
        story.append(Spacer(1, 4 * mm))

    # ── Investigation Narrative ──────────────────────────────────────
    if narrative:
        story += _section_header("Investigation Summary", styles)
        for line in narrative.split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), styles["body"]))
        story.append(Spacer(1, 4 * mm))

    # ── Recommendations ──────────────────────────────────────────────
    if recommendations:
        story += _section_header("Recommended Actions", styles)
        for i, rec in enumerate(recommendations, 1):
            story.append(
                Paragraph(f"{i}. {rec}", styles["recommendation"])
            )

    # ── Disclaimer ───────────────────────────────────────────────────
    story += _disclaimer_block(styles)
    return story


def generate_high_risk_csv(min_risk_score: int = 3) -> str:
    """
    Generates a CSV file listing all high-risk tenders and returns its path.

    The CSV is suitable for bulk review by audit teams.  It includes tender
    identifiers, department, category, winning vendor, risk score, and the
    names of all triggered indicators.

    Args:
        min_risk_score: Minimum total_risk_score to include (default 3 = High+).

    Returns:
        Absolute path to the saved CSV file.
    """
    import csv

    tenders_df = queries.get_all_tenders()
    if tenders_df.empty:
        raise ValueError("No tender data found in the database.")

    high_risk = tenders_df[tenders_df["total_risk_score"] >= min_risk_score].copy()

    if high_risk.empty:
        raise ValueError(
            f"No tenders found with risk score ≥ {min_risk_score}."
        )

    # Resolve awarded vendor names.
    vendors_df = queries.get_all_vendors()
    vendor_map: dict[int, str] = {}
    if not vendors_df.empty:
        vendor_map = dict(zip(vendors_df["vendor_id"], vendors_df["vendor_name"]))

    filename = f"HighRisk_Tenders_{_timestamp()}.csv"
    filepath = os.path.join(_EXPORT_DIR, filename)

    fieldnames = [
        "Tender ID",
        "Tender Reference",
        "Title",
        "Department",
        "Category",
        "Region",
        "Awarded Value (INR)",
        "Winning Vendor",
        "Risk Score",
        "Risk Level",
        "Triggered Indicators",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        for _, row in high_risk.sort_values("total_risk_score", ascending=False).iterrows():
            # Collect triggered indicator names via investigation_service.
            try:
                summary = investigation_service.get_investigation_summary(
                    int(row["tender_id"])
                )
                indicators: list[str] = [
                    item["detector_name"]
                    for item in summary.get("triggered_indicators", [])
                    if item.get("triggered")
                ]
            except Exception:
                indicators = []

            risk_score = int(row.get("total_risk_score", 0))
            awarded_vid = row.get("awarded_vendor_id")
            winning_vendor = vendor_map.get(int(awarded_vid), "—") \
                if awarded_vid is not None else "—"

            # Derive risk level label.
            if risk_score >= 5:
                risk_label = "Critical Risk"
            elif risk_score >= 3:
                risk_label = "High Risk"
            elif risk_score >= 1:
                risk_label = "Moderate Risk"
            else:
                risk_label = "Low Risk"

            writer.writerow({
                "Tender ID":           int(row.get("tender_id", 0)),
                "Tender Reference":    row.get("tender_reference", "—"),
                "Title":               row.get("title", "—"),
                "Department":          row.get("department", "—"),
                "Category":            row.get("category", "—"),
                "Region":              row.get("region", "—"),
                "Awarded Value (INR)": row.get("awarded_value", ""),
                "Winning Vendor":      winning_vendor,
                "Risk Score":          risk_score,
                "Risk Level":          risk_label,
                "Triggered Indicators": "; ".join(indicators) if indicators else "None",
            })

    return filepath


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def _timestamp() -> str:
    """Returns a compact timestamp string for use in filenames."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
