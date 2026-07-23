

from paddleocr import PaddleOCR

from config import OCR_LANGUAGE, MIN_OCR_CONFIDENCE
from table_extraction import reconstruct_tables_from_boxes

# ----------------------------------------------------
# Lazy Singleton OCR Instance
# ----------------------------------------------------

_ocr = None


def get_ocr():
    """
    Returns a singleton PaddleOCR instance.
    """
    global _ocr

    if _ocr is None:
        _ocr = PaddleOCR(
            use_textline_orientation=True,
            lang=OCR_LANGUAGE
        )

    return _ocr


# ----------------------------------------------------
# OCR
# ----------------------------------------------------

def run_paddle_ocr(img):
    """
    Runs PaddleOCR on a preprocessed image.

    Parameters
    ----------
    img : numpy.ndarray
        Preprocessed grayscale image.

    Returns
    -------
    tuple
        (
            extracted_text,
            reconstructed_tables
        )
    """

    result = get_ocr().ocr(img)

    words = []
    boxes = []

    for page_result in (result or []):

        if page_result is None:
            continue

        for word_info in page_result:

            bbox = word_info[0]

            text = word_info[1][0]

            confidence = word_info[1][1]

            if confidence >= MIN_OCR_CONFIDENCE and text.strip():

                words.append(text)

                left = int(min(point[0] for point in bbox))
                top = int(min(point[1] for point in bbox))
                right = int(max(point[0] for point in bbox))
                bottom = int(max(point[1] for point in bbox))

                boxes.append(
                    (
                        text.strip(),
                        left,
                        top,
                        right,
                        bottom
                    )
                )

    # Reconstruct text layout with newlines and tabs
    if boxes:
        # Sort boxes: primary key top (vertical), secondary key left (horizontal)
        sorted_boxes = sorted(boxes, key=lambda b: (b[2], b[1]))

        # Group boxes into visual lines
        lines = []
        cur_line = []
        line_bottom = None

        for b in sorted_boxes:
            text_val, left, top, right, bottom = b
            mid_y = (top + bottom) / 2
            if line_bottom is None or mid_y <= line_bottom + (bottom - top) * 0.5:
                cur_line.append(b)
                line_bottom = max(line_bottom or bottom, bottom)
            else:
                lines.append(sorted(cur_line, key=lambda x: x[1]))
                cur_line, line_bottom = [b], bottom
        if cur_line:
            lines.append(sorted(cur_line, key=lambda x: x[1]))

        # Compute horizontal gap threshold for tabs
        all_gaps = []
        for line in lines:
            for i in range(1, len(line)):
                gap = line[i][1] - line[i-1][3]
                if gap > 0:
                    all_gaps.append(gap)

        if all_gaps:
            all_gaps.sort()
            median_gap = all_gaps[len(all_gaps) // 2]
            tab_threshold = max(median_gap * 3, 20)
        else:
            tab_threshold = 20

        # Build lines with spaces or tabs
        reconstructed_lines = []
        for line in lines:
            line_text_parts = []
            for i, b in enumerate(line):
                text_val = b[0]
                if i > 0:
                    gap = b[1] - line[i-1][3]
                    if gap >= tab_threshold:
                        line_text_parts.append("\t" + text_val)
                    else:
                        line_text_parts.append(" " + text_val)
                else:
                    line_text_parts.append(text_val)
            reconstructed_lines.append("".join(line_text_parts))

        flat_text = "\n".join(reconstructed_lines)
    else:
        flat_text = ""

    tables = reconstruct_tables_from_boxes(boxes)

    return flat_text, tables