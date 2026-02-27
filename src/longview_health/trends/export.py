"""PDF trend report export using reportlab platypus.

Generates a professional multi-page PDF with title page, category sections,
per-test tables with deltas, abnormal highlighting, and provenance footnotes.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import KeepTogether

from longview_health.domain.enums import ResultCategory
from longview_health.domain.models import TrendReport, TrendSeries


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

_BLUE = colors.HexColor("#2C5F8A")
_LIGHT_BLUE = colors.HexColor("#E8F0FE")
_LIGHT_RED = colors.HexColor("#FFE0E0")
_LIGHT_GRAY = colors.HexColor("#F5F5F5")
_WHITE = colors.white


def _build_styles() -> dict[str, ParagraphStyle]:
    """Build paragraph styles for the report."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=24,
            spaceAfter=12,
            textColor=_BLUE,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=12,
            spaceAfter=24,
            textColor=colors.gray,
        ),
        "heading": ParagraphStyle(
            "CategoryHeading",
            parent=base["Heading1"],
            fontSize=16,
            spaceBefore=18,
            spaceAfter=10,
            textColor=_BLUE,
        ),
        "subheading": ParagraphStyle(
            "TestSubheading",
            parent=base["Heading2"],
            fontSize=11,
            spaceBefore=12,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["Normal"],
            fontSize=10,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "SmallText",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.gray,
            spaceAfter=4,
        ),
        "stat_label": ParagraphStyle(
            "StatLabel",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.gray,
        ),
        "stat_value": ParagraphStyle(
            "StatValue",
            parent=base["Normal"],
            fontSize=14,
            textColor=_BLUE,
            spaceBefore=2,
            spaceAfter=8,
        ),
    }


# ---------------------------------------------------------------------------
# Title page
# ---------------------------------------------------------------------------

_CATEGORY_LABELS: dict[ResultCategory, str] = {
    ResultCategory.LAB: "Lab Results",
    ResultCategory.IMAGING: "Imaging Findings",
    ResultCategory.PATHOLOGY: "Pathology",
    ResultCategory.DIAGNOSTIC: "Diagnostics",
    ResultCategory.VITALS: "Vitals",
    ResultCategory.OTHER: "Other",
}


def _build_title_page(
    report: TrendReport, styles: dict[str, ParagraphStyle]
) -> list:
    """Build flowables for the title page."""
    elements: list = []

    elements.append(Spacer(1, 1.5 * inch))
    elements.append(Paragraph(f"{report.vault_name}", styles["title"]))
    elements.append(
        Paragraph("Medical Results Trend Report", styles["subtitle"])
    )
    elements.append(Spacer(1, 0.3 * inch))

    # Summary stats
    elements.append(
        Paragraph(f"Generated: {report.generated_at:%Y-%m-%d %H:%M UTC}", styles["body"])
    )

    if report.date_range_start and report.date_range_end:
        elements.append(
            Paragraph(
                f"Date range: {report.date_range_start} to {report.date_range_end}",
                styles["body"],
            )
        )

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(f"Total results: {report.total_results}", styles["body"]))
    elements.append(Paragraph(f"Distinct tests: {report.total_tests}", styles["body"]))

    # Category breakdown
    if report.categories:
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph("Results by category:", styles["body"]))
        for cat, series_list in report.categories.items():
            count = sum(len(s.points) for s in series_list)
            label = _CATEGORY_LABELS.get(cat, cat.value)
            elements.append(
                Paragraph(f"  {label}: {count} results ({len(series_list)} tests)", styles["body"])
            )

    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Per-test table
# ---------------------------------------------------------------------------


def _build_test_table(
    series: TrendSeries,
    doc_names: dict[str, str] | None,
    styles: dict[str, ParagraphStyle],
) -> list:
    """Build flowables for a single test's trend table."""
    elements: list = []

    unit_str = f" ({series.unit})" if series.unit else ""
    elements.append(
        Paragraph(f"{series.test_name}{unit_str}", styles["subheading"])
    )

    # Table header
    header = ["Date", "Value", "Unit", "Ref Range", "Flag", "Delta", "Source"]
    data = [header]
    abnormal_rows: list[int] = []

    for i, point in enumerate(series.points):
        r = point.result
        rv = r.result_value

        # Reference range
        ref = ""
        if rv.reference_low and rv.reference_high:
            ref = f"{rv.reference_low}-{rv.reference_high}"
        elif rv.reference_low:
            ref = f">={rv.reference_low}"
        elif rv.reference_high:
            ref = f"<={rv.reference_high}"

        # Flag
        flag = ""
        if rv.is_abnormal is True:
            flag = "ABNORMAL"
        elif rv.is_abnormal is False:
            flag = "normal"

        # Delta
        delta_str = ""
        if point.delta is not None:
            sign = "+" if point.delta > 0 else ""
            delta_str = f"{sign}{point.delta}"
            if point.delta_percent is not None:
                delta_str += f" ({sign}{point.delta_percent}%)"

        # Source
        source = ""
        if doc_names and r.document_id in doc_names:
            source = doc_names[r.document_id]
        else:
            source = r.document_id[:12]

        row = [
            str(r.result_date),
            rv.value,
            rv.unit or "",
            ref,
            flag,
            delta_str,
            source,
        ]
        data.append(row)

        if rv.is_abnormal is True:
            abnormal_rows.append(i + 1)  # +1 for header row

    col_widths = [0.85 * inch, 0.75 * inch, 0.55 * inch, 0.85 * inch, 0.7 * inch, 1.0 * inch, 1.3 * inch]
    table = Table(data, colWidths=col_widths, repeatRows=1)

    # Table styling
    style_commands = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]

    # Alternating row backgrounds
    for row_idx in range(1, len(data)):
        if row_idx % 2 == 0:
            style_commands.append(
                ("BACKGROUND", (0, row_idx), (-1, row_idx), _LIGHT_GRAY)
            )

    # Abnormal row highlighting (overrides alternating)
    for row_idx in abnormal_rows:
        style_commands.append(
            ("BACKGROUND", (0, row_idx), (-1, row_idx), _LIGHT_RED)
        )

    table.setStyle(TableStyle(style_commands))
    elements.append(table)

    # Provenance footnote
    if series.points:
        last = series.points[-1].result
        elements.append(
            Paragraph(
                f"Extractor: {last.extractor_version} | Parser: {last.parser_used}",
                styles["small"],
            )
        )

    elements.append(Spacer(1, 0.15 * inch))
    return elements


# ---------------------------------------------------------------------------
# Category section
# ---------------------------------------------------------------------------


def _build_category_section(
    category: ResultCategory,
    series_list: list[TrendSeries],
    doc_names: dict[str, str] | None,
    styles: dict[str, ParagraphStyle],
) -> list:
    """Build flowables for one category section."""
    elements: list = []
    label = _CATEGORY_LABELS.get(category, category.value)
    elements.append(Paragraph(label, styles["heading"]))

    count = sum(len(s.points) for s in series_list)
    elements.append(
        Paragraph(
            f"{len(series_list)} tests, {count} results",
            styles["small"],
        )
    )
    elements.append(Spacer(1, 0.1 * inch))

    for series in series_list:
        table_elements = _build_test_table(series, doc_names, styles)
        elements.append(KeepTogether(table_elements))

    return elements


# ---------------------------------------------------------------------------
# Header / footer
# ---------------------------------------------------------------------------


def _make_header_footer(vault_name: str):
    """Return an onPage callback that draws header and footer."""

    def _header_footer(canvas, doc):
        canvas.saveState()
        # Header
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.gray)
        canvas.drawString(
            doc.leftMargin, doc.height + doc.topMargin + 10, vault_name
        )
        # Footer -- page number
        canvas.drawRightString(
            doc.width + doc.leftMargin,
            doc.bottomMargin - 10,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    return _header_footer


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def export_pdf(
    report: TrendReport,
    output_path: str | Path,
    doc_names: dict[str, str] | None = None,
) -> Path:
    """Generate a PDF trend report and write it to output_path.

    Returns the resolved output Path.
    """
    output_path = Path(output_path)
    styles = _build_styles()

    frame = Frame(
        0.75 * inch,
        0.75 * inch,
        letter[0] - 1.5 * inch,
        letter[1] - 1.5 * inch,
        id="main",
    )

    on_page = _make_header_footer(report.vault_name)

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    doc.addPageTemplates(
        [PageTemplate(id="all", frames=[frame], onPage=on_page)]
    )

    # Build all flowables
    elements: list = []
    elements.extend(_build_title_page(report, styles))

    for cat, series_list in report.categories.items():
        elements.extend(
            _build_category_section(cat, series_list, doc_names, styles)
        )
        elements.append(PageBreak())

    # Need at least one flowable for platypus
    if not elements:
        elements.append(Paragraph("No results to report.", styles["body"]))

    doc.build(elements)
    return output_path
