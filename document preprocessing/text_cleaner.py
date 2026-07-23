import re

def parse_and_format_headings(line):
    """
    Checks if a line contains a heading.
    If the line starts with a heading pattern followed by body text,
    splits it and formats the heading part with '# ' or '## ' and returns
    the heading line and the body line.
    Otherwise, if the entire line is a heading, formats and returns it.
    Otherwise, returns the line unchanged.
    """
    line_stripped = line.strip()
    if not line_stripped:
        return line

    # 1. Numbering/list patterns at the start
    # e.g., "1. Job description", "2. Eligibility", "3. Submission of application:", "(I) Age", "A. Applicant"
    numbered_regex = r'^((?:\d+(?:\.\d+)*|[A-Z]|\([a-zA-Z0-9]+\))\s*[\.\)]\s+)(.*)$'
    
    match = re.match(numbered_regex, line_stripped)
    if match:
        prefix = match.group(1).strip()
        rest = match.group(2).strip()
        
        # Check if the rest of the line contains a body text separator like ":" followed by space
        # e.g. "3. Submission of application: Applicants should send..."
        colon_match = re.match(r'^([^:]+?)\s*:\s+(.+)$', rest)
        if colon_match:
            heading_title = colon_match.group(1).strip()
            body_text = colon_match.group(2).strip()
            
            # Check if this heading title itself isn't too long
            if len(heading_title) < 80:
                level = "## " if ('.' in prefix or len(prefix) > 2) else "# "
                return f"{level}{prefix} {heading_title}\n{body_text}"
        
        # If no colon separating body, let's check if the rest is too long (likely body text)
        if len(rest) > 80:
            return line
            
        level = "## " if ('.' in prefix or len(prefix) > 2) else "# "
        return f"{level}{line_stripped}"

    # 2. Known section titles in ALL CAPS (must be at least 2 words or starts with ANNEXURE/APPENDIX)
    all_caps_pattern = r'^[A-Z0-9\s,\(\)\-\/\&\.\:\'\"]+$'
    if re.match(all_caps_pattern, line_stripped) and len(line_stripped) > 3:
        # Ignore lines that are just numbers/dots/separators/short tokens
        if not re.match(r'^[\d\s\.\-\_]+$', line_stripped):
            words = line_stripped.split()
            if len(words) >= 2 or line_stripped.startswith("ANNEXURE") or line_stripped.startswith("APPENDIX"):
                # Exclude key-value lines like "DATE: 09/07/2024" or "REF : ..."
                if not re.search(r'\b(?:REF|DATE|EMAIL|TEL|FAX|PHONE|URL|WEBSITE)\b\s*:', line_stripped, re.IGNORECASE):
                    return f"# {line_stripped}"

    return line


def clean_text(text):
    if not text:
        return ""

    # -----------------------------
    # Normalize line endings
    # -----------------------------
    text = re.sub(r'\r\n|\r', '\n', text)

    # -----------------------------
    # Replace smart quotes
    # -----------------------------
    text = (
        text.replace('\u201c', '"')
            .replace('\u201d', '"')
            .replace('\u2018', "'")
            .replace('\u2019', "'")
            .replace('\u201e', '"')
            .replace('\u201f', '"')
    )

    # -----------------------------
    # Remove decorative dots
    # -----------------------------
    text = re.sub(r'[.\u2026]{4,}', '', text)

    # -----------------------------
    # Remove repeating headers
    # -----------------------------
    text = re.sub(
        r'Contract Cell,?\s+SZ\s+Page\s+\d+\s+of\s+\d+',
        '',
        text,
        flags=re.IGNORECASE
    )

    # -----------------------------
    # Clean line-by-line
    # -----------------------------
    cleaned_lines = []

    for line in text.splitlines():

        # Remove trailing spaces only
        line = line.rstrip()

        if not line.strip():
            cleaned_lines.append("")
            continue

        # Remove decorative separator lines
        if re.fullmatch(r'[-_=*#+.|\\/ ]+', line.strip()):
            continue

        # Remove page numbers
        if re.fullmatch(r'\d+', line.strip()):
            continue

        # Remove empty brackets
        if re.fullmatch(r'[\[\](). ]+', line.strip()):
            continue

        # Convert long spaces to tabs
        line = re.sub(r' {4,}', '\t', line)

        # Compress only double+ spaces
        line = re.sub(r' {2,}', ' ', line)

        # Parse and format headings/body splits
        line = parse_and_format_headings(line)

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()