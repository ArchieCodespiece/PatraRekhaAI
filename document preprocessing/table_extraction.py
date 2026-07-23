# -------------------------------
# TABLE HELPERS
# -------------------------------
import re
def reconstruct_tables_from_boxes(boxes, min_cols=2, min_rows=2):
    """
    Detect and reconstruct tables from word bounding-boxes.
    boxes : list of (text, left, top, right, bottom)  -- pixel coords
    Returns list of {"rows": [[cell, ...], ...]} dicts.
    """
    if not boxes:
        return []

    boxes = sorted(boxes, key=lambda b: (b[2], b[1]))  # top→bottom, left→right

    # ── Group words into visual lines ─────────────────────────────────────────
    lines, cur_line, line_bottom = [], [], None
    for b in boxes:
        _, _, top, _, bottom = b
        mid_y = (top + bottom) / 2
        if line_bottom is None or mid_y <= line_bottom + (bottom - top) * 0.5:
            cur_line.append(b)
            line_bottom = max(line_bottom or bottom, bottom)
        else:
            lines.append(sorted(cur_line, key=lambda x: x[1]))
            cur_line, line_bottom = [b], bottom
    if cur_line:
        lines.append(sorted(cur_line, key=lambda x: x[1]))

    # ── Compute adaptive column-gap threshold (3× median inter-word gap) ──────
    all_gaps = sorted(
        line[i][1] - line[i-1][3]          # left_i − right_{i−1}
        for line in lines
        for i in range(1, len(line))
        if line[i][1] - line[i-1][3] > 0
    )
    if not all_gaps:
        return []
    col_gap = max(all_gaps[len(all_gaps) // 2] * 3, 20)

    # ── Split each line into columns ───────────────────────────────────────────
    def line_to_cols(line):
        if len(line) < min_cols:
            return None
        cols = [[line[0]]]
        for w in line[1:]:
            if w[1] - cols[-1][-1][3] >= col_gap:
                cols.append([w])
            else:
                cols[-1].append(w)
        return [' '.join(x[0] for x in c) for c in cols] if len(cols) >= min_cols else None

    row_cols = [line_to_cols(l) for l in lines]

    # ── Collect contiguous spans of table rows ─────────────────────────────────
    tables, i = [], 0
    while i < len(row_cols):
        if row_cols[i] is not None:
            j = i
            while j < len(row_cols) and row_cols[j] is not None:
                j += 1
            if j - i >= min_rows:
                block = row_cols[i:j]
                w = max(len(r) for r in block)
                tables.append({"rows": [r + [''] * (w - len(r)) for r in block]})
            i = j
        else:
            i += 1
    return tables


def extract_tables_from_page(page):
    """
    Extract structured tables from a pdfplumber page object.
    Returns list of {"rows": [[cell, ...], ...]} dicts.
    """
    tables = []
    for raw in (page.extract_tables() or []):
        cleaned = [
            [re.sub(r'\s+', ' ', cell or '').strip() for cell in row]
            for row in raw
            if any(cell and cell.strip() for cell in row)
        ]
        if len(cleaned) >= 2:  # at least a header + one data row
            tables.append({"rows": cleaned})
    return tables