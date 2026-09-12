"""Deterministic XLSX rendering of canonical workflow results."""

from __future__ import annotations

import io
import re
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..models import ComparisonResult, ReportDocument

HEADER_FILL = PatternFill(
    start_color="1F4E79",
    end_color="1F4E79",
    fill_type="solid",
)
HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
SECTION_FILL = PatternFill(
    start_color="D6E4F0",
    end_color="D6E4F0",
    fill_type="solid",
)
SECTION_FONT = Font(bold=True, size=10)
BODY_FONT = Font(size=10)
THIN = Side(style="thin", color="B0B0B0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")


def _sanitize_sheet_name(name: str) -> str:
    cleaned = re.sub(r"[\[\]:*?/\\]", " ", str(name))
    return cleaned.replace("\t", " ")[:31] or "Section"


def _style_header(ws, columns: int) -> None:
    for col in range(1, columns + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = WRAP
        cell.border = BORDER

    ws.freeze_panes = "A2"


def _autosize(ws, widths: List[int]) -> None:
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width


def _write_rows(ws, rows: List[List[str]], start_row: int = 1) -> int:
    for row_index, row in enumerate(rows, start=start_row):
        for col_index, value in enumerate(row, start=1):
            cell = ws.cell(row=row_index, column=col_index)
            cell.value = value
            cell.font = BODY_FONT
            cell.alignment = WRAP
            cell.border = BORDER

    return start_row + len(rows)


def comparison_to_xlsx(
    result: ComparisonResult,
    doc_a: str,
    doc_b: str,
) -> bytes:
    """Render a ComparisonResult into a multi-sheet XLSX workbook."""

    wb = Workbook()

    differences = result.differences()
    high_impact = result.high_impact_differences()

    summary_ws = wb.active
    summary_ws.title = "Summary"

    summary_ws.append(
        [
            "Documents",
            "Sections",
            "Items",
            "Differences",
            "High-impact",
        ]
    )
    _style_header(summary_ws, 5)

    _write_rows(
        summary_ws,
        [
            [
                f"{doc_a} vs {doc_b}",
                len(result.sections),
                result.total_rows(),
                len(differences),
                len(high_impact),
            ]
        ],
        start_row=2,
    )

    _autosize(
        summary_ws,
        [40, 10, 10, 12, 12],
    )

    section_rows_built = 0

    for section in result.sections:
        if not section.rows:
            continue

        ws = wb.create_sheet(_sanitize_sheet_name(section.name))
        ws.append(["Topic", doc_a, doc_b, "Difference", "Impact", "Evidence"])

        _style_header(ws, 6)

        rows: List[List[str]] = []

        for row in section.rows:
            evidence_txt = " | ".join(
                (
                    f"{item.document} p.{item.page_start or '-'}"
                    + (f"-{item.page_end}" if item.page_end else "")
                )
                for item in row.evidence[:2]
            ) or "—"

            unverified = " [unverified]" if row.unverified else ""

            rows.append(
                [
                    row.topic,
                    row.document_a,
                    row.document_b,
                    "Yes" if row.difference else "No",
                    row.impact.capitalize() + unverified,
                    evidence_txt,
                ]
            )

        _write_rows(ws, rows, start_row=2)
        _autosize(ws, [30, 35, 35, 10, 12, 45])
        section_rows_built += 1

    if section_rows_built == 0:
        empty = wb.create_sheet("Rows")
        empty.append(["A comparison could not be produced."])
        _style_header(empty, 1)
        _autosize(empty, [60])

    buffer = io.BytesIO()
    wb.save(buffer)

    return buffer.getvalue()


def report_to_xlsx(report: ReportDocument) -> bytes:
    """Render a ReportDocument into a workbook (one sheet per section)."""

    wb = Workbook()

    overview_ws = wb.active
    overview_ws.title = "Overview"
    overview_ws.append(["Report", len(report.sections)])

    _style_header(overview_ws, 2)
    _write_rows(
        overview_ws,
        [[report.title, f"{len(report.sections)} sections"]],
        start_row=2,
    )
    _autosize(overview_ws, [50, 15])

    for section in report.sections:
        ws = wb.create_sheet(_sanitize_sheet_name(section.heading))

        if section.table and section.table.headers:
            ws.append(section.table.headers)
            _style_header(ws, len(section.table.headers))
            _write_rows(ws, section.table.rows, start_row=2)
            _autosize(ws, [28] * len(section.table.headers))
        else:
            ws.append(["Content"])
            _style_header(ws, 1)
            _write_rows(ws, [[section.content]], start_row=2)
            _autosize(ws, [80])

    buffer = io.BytesIO()
    wb.save(buffer)

    return buffer.getvalue()