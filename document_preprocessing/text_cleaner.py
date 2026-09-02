import re
import unicodedata


# Indic Unicode ranges that must NOT be stripped or altered
INDIC_RANGES = [
    (0x0900, 0x097F),   # Devanagari
    (0x0980, 0x09FF),   # Bengali
    (0x0A00, 0x0A7F),   # Gurmukhi
    (0x0A80, 0x0AFF),   # Gujarati
    (0x0B00, 0x0B7F),   # Oriya/Odia
    (0x0B80, 0x0BFF),   # Tamil
    (0x0C00, 0x0C7F),   # Telugu
    (0x0C80, 0x0CFF),   # Kannada
    (0x0D00, 0x0D7F),   # Malayalam
    (0x0D80, 0x0DFF),   # Sinhala
    (0x0E00, 0x0E7F),   # Thai
    (0xA8E0, 0xA8FF),   # Devanagari Extended
    (0x11B00, 0x11B5F), # Devanagari Extended-A
]

# Arabic ranges (for Urdu)
ARABIC_RANGES = [
    (0x0600, 0x06FF),   # Arabic
    (0x0750, 0x077F),   # Arabic Supplement
    (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
]

ALL_PRESERVED_RANGES = INDIC_RANGES + ARABIC_RANGES


def _is_indic_or_arabic(char: str) -> bool:
    """Check if a character belongs to an Indic or Arabic script."""
    code_point = ord(char)
    for start, end in ALL_PRESERVED_RANGES:
        if start <= code_point <= end:
            return True
    return False


def _is_meaningful_indic_char(char: str) -> bool:
    """
    Check if an Indic character is meaningful (not just a combining mark
    that could be removed).
    """
    code_point = ord(char)
    category = unicodedata.category(char)

    # Preserve letters, digits, and punctuation
    if category.startswith('L') or category.startswith('N') or category.startswith('P'):
        return True

    # Preserve dependent vowels (matras) - they change meaning
    if 0x093E <= code_point <= 0x094C:  # Devanagari matras
        return True
    if 0x09BE <= code_point <= 0x09CC:  # Bengali matras
        return True
    if 0x0BBE <= code_point <= 0x0BCC:  # Tamil matras
        return True
    if 0x0C3E <= code_point <= 0x0C4C:  # Telugu matras
        return True
    if 0x0ABE <= code_point <= 0x0ACC:  # Gujarati matras
        return True
    if 0x0CBE <= code_point <= 0x0CCC:  # Kannada matras
        return True
    if 0x0D3E <= code_point <= 0x0D4C:  # Malayalam matras
        return True

    # Virama (halant) - used for conjuncts, preserve
    if category == 'Mn':  # Nonspacing mark
        return True

    return False

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
    # Unicode normalization (NFC)
    # This standardizes combining characters without removing them
    # IMPORTANT: NFC is safe for all scripts including Indic
    # -----------------------------
    text = unicodedata.normalize('NFC', text)

    # -----------------------------
    # Replace smart quotes
    # -----------------------------
    text = (
        text.replace('→', '"')
            .replace('”', '"')
            .replace('‘', "'")
            .replace('’', "'")
            .replace('„', '"')
            .replace('‟', '"')
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

        # Remove decorative separator lines (ASCII only — don't match Indic chars)
        stripped = line.strip()
        if _is_ascii_separator(stripped):
            continue

        # Remove page numbers (but NOT Indic numbers which are meaningful)
        if re.fullmatch(r'\d+', line.strip()):
            # Only remove if it's a single ASCII number (likely a page number)
            # Keep lines with Indic numbers as they may be meaningful content
            if not any(_is_indic_or_arabic(c) for c in line.strip()):
                continue

        # Remove empty brackets (ASCII only)
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


def _is_ascii_separator(line: str) -> bool:
    """
    Check if a line is a decorative separator made of ASCII characters only.
    This avoids matching Indic script characters that could look similar.
    """
    if not line:
        return False
    # Only ASCII separator characters
    separator_chars = set('-_=*#+.|\\/ ')
    return all(c in separator_chars for c in line) and len(line) >= 3