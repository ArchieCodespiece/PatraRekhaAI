# -------------------------------
# DATE NORMALISATION
# -------------------------------
import re

# Gregorian month map covering English + Indic languages/scripts.
# Values are zero-padded month numbers so normalised output stays uniform.
MONTH_MAP = {
    # English / romanised
    "january": "01", "jan": "01", "janv": "01",
    "february": "02", "feb": "02", "febru": "02",
    "march": "03", "mar": "03", "marchi": "03", "marci": "03",
    "april": "04", "apr": "04", "aprail": "04", "april": "04", "aepril": "04",
    "may": "05", "mai": "05", "mey": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07", "julai": "07", "juloi": "07",
    "august": "08", "aug": "08", "agast": "08", "agost": "08", "agosto": "08", "ogos": "08",
    "september": "09", "sept": "09", "septembar": "09", "sitambar": "09", "siptambar": "09",
    "october": "10", "oct": "10", "octobar": "10", "aktubar": "10", "auktubar": "10",
    "november": "11", "nov": "11", "novembar": "11", "navambar": "11",
    "december": "12", "dec": "12", "disambar": "12", "desambar": "12",

    # Hindi (Devanagari)
    "जनवरी": "01", "फरवरी": "02", "मार्च": "03", "अप्रैल": "04",
    "मई": "05", "जून": "06", "जुलाई": "07", "अगस्त": "08",
    "सितंबर": "09", "सितम्बर": "09", "अक्टूबर": "10", "नवंबर": "11", "दिसंबर": "12",

    # Marathi (Devanagari)
    "जानेवारी": "01", "फेब्रुवारी": "02", "मार्च": "03", "एप्रिल": "04",
    "मे": "05", "जून": "06", "जुलै": "07", "ऑगस्ट": "08",
    "सप्टेंबर": "09", "ऑक्टोबर": "10", "नोव्हेंबर": "11", "डिसेंबर": "12",

    # Bengali (bn)
    "জানুয়ারি": "01", "জানু": "01", "ফেব্রুয়ারি": "02", "ফেব্রু": "02",
    "মার্চ": "03", "এপ্রিল": "04", "এপ্রি": "04", "মে": "05",
    "জুন": "06", "জুলাই": "07", "জুলাই": "07", "আগস্ট": "08", "আগ": "08",
    "সেপ্টেম্বর": "09", "সেপ্টে": "09", "অক্টোবর": "10", "অক্টো": "10",
    "নভেম্বর": "11", "নভে": "11", "ডিসেম্বর": "12", "ডিসে": "12",

    # Assamese (as) - Bengali script
    "জানুৱাৰী": "01", "ফেব্ৰুৱাৰী": "02", "মাৰ্চ": "03", "এপ্ৰিল": "04",
    "মে": "05", "জুন": "06", "জুলাই": "07", "আগষ্ট": "08",
    "ছেপ্টেম্বৰ": "09", "অক্টোবৰ": "10", "নৱেম্বৰ": "11", "ডিচেম্বৰ": "12",

    # Tamil (ta)
    "ஜனவரி": "01", "பிப்ரவரி": "02", "மார்ச்": "03", "ஏப்ரல்": "04",
    "மே": "05", "ஜூன்": "06", "ஜூலை": "07", "ஆகஸ்ட்": "08",
    "செப்டம்பர்": "09", "அக்டோபர்": "10", "நவம்பர்": "11", "டிசம்பர்": "12",

    # Telugu (te)
    "జనవరి": "01", "ఫిబ్రవరి": "02", "మార్చి": "03", "ఏప్రిల్": "04",
    "మే": "05", "జూన్": "06", "జూలై": "07", "ఆగస్టు": "08",
    "సెప్టెంబర్": "09", "అక్టోబర్": "10", "నవంబర్": "11", "డిసెంబర్": "12",

    # Gujarati (gu)
    "જાન્યુઆરી": "01", "ફેબ્રુઆરી": "02", "માર્ચ": "03", "એપ્રિલ": "04",
    "મે": "05", "જૂન": "06", "જુલાઈ": "07", "ઓગસ્ટ": "08",
    "સપ્ટેમ્બર": "09", "ઓક્ટોબર": "10", "નવેમ્બર": "11", "ડિસેમ્બર": "12",

    # Kannada (kn)
    "ಜನವರಿ": "01", "ಫೆಬ್ರವರಿ": "02", "ಮಾರ್ಚ್": "03", "ಏಪ್ರಿಲ್": "04",
    "ಮೇ": "05", "ಜೂನ್": "06", "ಜುಲೈ": "07", "ಆಗಸ್ಟ್": "08",
    "ಸೆಪ್ಟೆಂಬರ್": "09", "ಅಕ್ಟೋಬರ್": "10", "ನವೆಂಬರ್": "11", "ಡಿಸೆಂಬರ್": "12",

    # Malayalam (ml)
    "ജനുവരി": "01", "ഫെബ്രുവരി": "02", "മാർച്ച്": "03", "ഏപ്രിൽ": "04",
    "മേയ്": "05", "ജൂൺ": "06", "ജൂലൈ": "07", "ഓഗസ്റ്റ്": "08",
    "സെപ്റ്റംബർ": "09", "ഒക്ടോബർ": "10", "നവംബർ": "11", "ഡിസംബർ": "12",

    # Punjabi / Gurmukhi (pa)
    "ਜਨਵਰੀ": "01", "ਫਰਵਰੀ": "02", "ਮਾਰਚ": "03", "ਅਪ੍ਰੈਲ": "04",
    "ਮਈ": "05", "ਜੂਨ": "06", "ਜੁਲਾਈ": "07", "ਅਗਸਤ": "08",
    "ਸਤੰਬਰ": "09", "ਅਕਤੂਬਰ": "10", "ਨਵੰਬਰ": "11", "ਦਸੰਬਰ": "12",

    # Odia (or)
    "ଜାନୁଆରୀ": "01", "ଫେବୃଆରୀ": "02", "ମାର୍ଚ୍ଚ": "03", "ଅପ୍ରେଲ": "04",
    "ମେ": "05", "ଜୁନ": "06", "ଜୁଲାଇ": "07", "ଅଗଷ୍ଟ": "08",
    "ସେପ୍ଟେମ୍ବର": "09", "ଅକ୍ଟୋବର": "10", "ନଭେମ୍ବର": "11", "ଡିସେମ୍ବର": "12",

    # Urdu (Arabic script)
    "جنوری": "01", "فروری": "02", "مارچ": "03", "اپریل": "04",
    "مئی": "05", "جون": "06", "جولائی": "07", "اگست": "08",
    "ستمبر": "09", "اکتوبر": "10", "نومبر": "11", "دسمبر": "12",
}

# Longest-first for regex alternation so multi-script prefixes don't shadow
# longer names (e.g. "জানু" must not partially match "জানুয়ারি").
MONTH_KEYS_SORTED = sorted(
    MONTH_MAP.keys(),
    key=len,
    reverse=True,
)


def lookup_month(token: str) -> str | None:
    """Return the zero-padded month number for a month token, or None."""
    if not token:
        return None
    return MONTH_MAP.get(token.strip(" '\"").lower())


def _expand_century(two_digit_year: str) -> str:
    return "20" + two_digit_year


def normalise_date_iso(raw) -> str | None:
    """
    Normalise a date string to canonical ISO format: YYYY-MM-DD.

    Supports:
      - ISO YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
      - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
      - Written day-first: "12 January 2024", "15th March 2026"
      - Written month-first: "January 12, 2024", "March 15 2026"
      - Indic script months (see MONTH_MAP)

    Returns None when the raw value is not a valid date.
    """
    if not raw:
        return None
    raw = str(raw).strip()

    # 1. ISO formats: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    m_iso = re.match(r"^(\d{4})[./-](\d{1,2})[./-](\d{1,2})$", raw)
    if m_iso:
        y, mo, d = m_iso.group(1), m_iso.group(2), m_iso.group(3)
        return _format_date_iso(d, mo, y)

    # 2. Numeric DD/MM/YYYY formats
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$", raw)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        if len(y) == 2:
            y = _expand_century(y)
        return _format_date_iso(d, mo, y)

    # 3. Written: "12 January 2024", "12th January 2024"
    m = re.match(
        r"^(\d{1,2})(?:st|nd|rd|th)?[\s.-]+\s*([A-Za-z\u00C0-\u024F\u0900-\u0D7F][^-0-9]*?)\s+(\d{2,4})$",
        raw,
    )
    if m:
        d, month_token, y = m.group(1), m.group(2), m.group(3)
        mo = lookup_month(month_token)
        if mo:
            if len(y) == 2:
                y = _expand_century(y)
            return _format_date_iso(d, mo, y)

    # 4. Written: "January 12, 2024" / "March 15 2026"
    m = re.match(
        r"^([A-Za-z\u00C0-\u024F\u0900-\u0D7F][^-0-9]*?)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(\d{2,4})$",
        raw,
    )
    if m:
        month_token, d, y = m.group(1), m.group(2), m.group(3)
        mo = lookup_month(month_token)
        if mo:
            if len(y) == 2:
                y = _expand_century(y)
            return _format_date_iso(d, mo, y)

    return None


def normalise_date_dd_mm_yyyy(raw) -> str | None:
    """
    Normalise a date string to display format: DD/MM/YYYY.

    Supports ISO YYYY-MM-DD as well as DD/MM/YYYY, written dates, and Indic months.
    """
    iso = normalise_date_iso(raw)
    if not iso:
        return None
    y, mo, d = iso.split("-")
    return f"{d}/{mo}/{y}"


def iso_to_dd_mm_yyyy(iso_str: str | None) -> str | None:
    """Convert YYYY-MM-DD to DD/MM/YYYY."""
    if not iso_str:
        return None
    iso = normalise_date_iso(iso_str)
    if not iso:
        return None
    y, mo, d = iso.split("-")
    return f"{d}/{mo}/{y}"


def dd_mm_yyyy_to_iso(dmy_str: str | None) -> str | None:
    """Convert DD/MM/YYYY (or any supported date) to canonical YYYY-MM-DD."""
    return normalise_date_iso(dmy_str)


def _format_date_iso(day: str, month: str, year: str) -> str | None:
    """Build a validated YYYY-MM-DD string, or None if invalid."""
    try:
        d, mo, y = int(day), int(month), int(year)
    except (TypeError, ValueError):
        return None
    if not (1 <= d <= 31 and 1 <= mo <= 12 and 1000 <= y <= 9999):
        return None
    import datetime

    try:
        dt = datetime.date(y, mo, d)
        return dt.isoformat()
    except ValueError:
        return None


def _format_date(day: str, month: str, year: str) -> str | None:
    """Build a validated dd/mm/yyyy string, or None if invalid."""
    iso = _format_date_iso(day, month, year)
    if not iso:
        return None
    y, mo, d = iso.split("-")
    return f"{d}/{mo}/{y}"


# -------------------------------
# Backward-compatible normalisation
# -------------------------------

def normalise_date(raw):
    """
    Legacy normaliser (returns DD-MM-YYYY).

    Prefer normalise_date_dd_mm_yyyy() for new code — the internal canonical
    format across the product is dd/mm/yyyy (LLM prompt + calendar parser).
    """
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