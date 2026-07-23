import json
def contiguous_ranges(page_nums):
    """
    Convert a sorted list of page numbers into contiguous (first, last) ranges.
    E.g. [3,4,5,10,11] → [(3,5), (10,11)]
    This minimises the number of poppler convert_from_path calls.
    """
    if not page_nums:
        return []
    ranges = []
    start = prev = page_nums[0]
    for n in page_nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append((start, prev))
            start = prev = n
    ranges.append((start, prev))
    return ranges


def write_output(results, output_json, total_pages):
    """Sort and write the final JSON output."""
    entries = [results[pn] for pn in sorted(results.keys())]
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Done. {len(entries)}/{total_pages} pages written to '{output_json}'.")


# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    pdf_path = r"E:\proj\tender_eval\bidder_eval\ilovepdf_merged.pdf"
    process_pdf(
        pdf_path,
        output_json="paddle_output.json",
        batch_size=BATCH_SIZE,
        dpi=DPI,
        resume=True,          # set False to start fresh
    )