"""Deterministic PDF rendering of canonical workflow results."""

from __future__ import annotations

import io
import os

from fpdf import FPDF

from ..config import PDF_UNICODE_FONT
from ..models import ComparisonResult, ReportDocument

LEFT = 12
PAGE_WIDTH = 210
PAGE_RIGHT = 198
CONTENT_WIDTH = PAGE_RIGHT - LEFT


def _register_font(pdf: FPDF) -> None:
    if PDF_UNICODE_FONT and os.path.exists(PDF_UNICODE_FONT):
        try:
            pdf.add_font(
                "Noto",
                "",
                PDF_UNICODE_FONT,
            )

            bold_path = (
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            )
            if os.path.exists(bold_path):
                pdf.add_font("Noto", "B", bold_path)

            pdf.set_font("Noto", "", 9)
            return
        except Exception:
            pass

    pdf.set_font("Helvetica", "", 9)


def _guard_pdf_space(pdf: FPDF, needed: float = 18.0) -> None:
    if pdf.get_y() + needed > pdf.h - 20:
        pdf.add_page()


def _write_section_header(pdf: FPDF, text: str) -> None:
    _guard_pdf_space(pdf)
    pdf.set_font("Noto", "B", 10)
    pdf.set_text_color(31, 78, 121)
    pdf.set_fill_color(214, 228, 240)
    pdf.multi_cell(
        CONTENT_WIDTH,
        6,
        text,
        new_x="LMARGIN",
        new_y="NEXT",
        fill=True,
    )
    pdf.ln(2)
    pdf.set_font("Noto", "", 9)
    pdf.set_text_color(0, 0, 0)


def _write_table_header(pdf: FPDF, headers: list, col_widths: list) -> None:
    pdf.set_fill_color(31, 78, 121)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Noto", "B", 8)

    for col, header in enumerate(headers):
        pdf.cell(col_widths[col], 6.5, str(header)[:40], 1, fill=True)

    pdf.ln(6.5)
    pdf.set_font("Noto", "", 8)
    pdf.set_text_color(0, 0, 0)


def _write_table(
    pdf: FPDF,
    headers: list,
    rows: list,
    col_widths: list,
) -> None:
    row_height = 6.5

    if pdf.get_y() + 20 > pdf.h - 20:
        pdf.add_page()
    else:
        _guard_pdf_space(pdf, 30)

    _write_table_header(pdf, headers, col_widths)

    fill = False

    for row in rows:
        line_counts = [
            len(
                pdf.multi_cell(
                    col_widths[col],
                    row_height,
                    str(value or "—"),
                    dry_run=True,
                    output="LINES",
                )
            )
            for col, value in enumerate(row)
        ]

        lines = max(line_counts) if line_counts else 1
        row_px = row_height * lines

        if pdf.get_y() + row_px > pdf.h - 20:
            pdf.add_page()
            _write_table_header(pdf, headers, col_widths)

        fill = not fill
        start_y = pdf.get_y()
        offset_x = 0

        for col, value in enumerate(row):
            pdf.set_xy(LEFT + offset_x, start_y)
            pdf.set_fill_color(
                245 if fill else 255,
                245 if fill else 255,
                245 if fill else 255,
            )
            pdf.multi_cell(
                col_widths[col],
                row_height,
                str(value or "—"),
                border=1,
                fill=True,
                new_x="LMARGIN",
                new_y="TOP",
            )
            offset_x += col_widths[col]

        pdf.set_y(start_y + row_px)

    pdf.ln(3)


def _write_body(pdf: FPDF, content: str) -> None:
    _guard_pdf_space(pdf)
    pdf.set_font("Noto", "", 9)
    pdf.multi_cell(
        CONTENT_WIDTH,
        5,
        content or "—",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(3)


def comparison_to_pdf(
    result: ComparisonResult,
    doc_a: str,
    doc_b: str,
) -> bytes:
    """Render a ComparisonResult into a professional PDF report."""

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    _register_font(pdf)
    pdf.set_left_margin(LEFT)
    pdf.set_right_margin(PAGE_WIDTH - PAGE_RIGHT)

    pdf.set_font("Noto", "B", 16)
    pdf.set_text_color(31, 78, 121)
    pdf.cell(CONTENT_WIDTH, 9, f"{doc_a} vs {doc_b}")
    pdf.ln(9)

    pdf.set_font("Noto", "", 8)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(
        CONTENT_WIDTH,
        5,
        (
            f"Automated document comparison · "
            f"{result.total_rows()} items · "
            f"{len(result.differences())} differences · "
            f"{len(result.high_impact_differences())} high-impact"
        ),
    )
    pdf.ln(6)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Noto", "", 9)

    for section in result.sections:
        if not section.rows:
            continue

        _write_section_header(pdf, section.name)

        headers = ["Topic", doc_a, doc_b, "Diff", "Impact"]
        col_widths = [34, 48, 48, 14, 14]

        rows = []

        for row in section.rows:
            impact = row.impact.capitalize()
            if row.unverified:
                impact += " *"

            rows.append(
                [
                    row.topic,
                    row.document_a,
                    row.document_b,
                    "Yes" if row.difference else "No",
                    impact,
                ]
            )

        _write_table(pdf, headers, rows, col_widths)

    if result.unverified_rows():
        pdf.set_font("Noto", "I", 8)
        pdf.multi_cell(
            CONTENT_WIDTH,
            5,
            (
                "* Items marked with an asterisk could not be fully "
                "confirmed from the retrieved text."
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

    buffer = io.BytesIO()
    pdf.output(buffer)

    return buffer.getvalue()


def report_to_pdf(report: ReportDocument) -> bytes:
    """Render a ReportDocument into a PDF report."""

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    _register_font(pdf)
    pdf.set_left_margin(LEFT)
    pdf.set_right_margin(PAGE_WIDTH - PAGE_RIGHT)

    pdf.set_font("Noto", "B", 16)
    pdf.set_text_color(31, 78, 121)
    pdf.multi_cell(
        CONTENT_WIDTH,
        9,
        report.title,
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Noto", "", 9)

    for section in report.sections:
        _write_section_header(pdf, section.heading)

        if section.table and section.table.headers:
            _write_table(
                pdf,
                section.table.headers,
                section.table.rows,
                [CONTENT_WIDTH / len(section.table.headers)]
                * len(section.table.headers),
            )
        else:
            _write_body(pdf, section.content)

    buffer = io.BytesIO()
    pdf.output(buffer)

    return buffer.getvalue()