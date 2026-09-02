# -------------------------------
# DATE NORMALISATION
# -------------------------------
MONTH_MAP = {
    "january": "01", "february": "02", "march": "03",
    "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}


def normalise_date(raw):
    raw = raw.strip()

    # Numeric formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    m = re.match(r'^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$', raw)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{d}-{mo}-{y}"

    # Written formats: "12 January 2024" or "12th January 2024"
    m = re.match(
        r'^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{2,4})$', raw
    )
    if m:
        d, mon_str, y = m.group(1).zfill(2), m.group(2).lower(), m.group(3)
        mo = MONTH_MAP.get(mon_str)
        if mo:
            if len(y) == 2:
                y = "20" + y
            return f"{d}-{mo}-{y}"

    return raw
