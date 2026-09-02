"""
Language detection service for PatraRekhaAI.

Detects:
- Language (e.g., Hindi, Bengali, Tamil)
- Script (e.g., Devanagari, Latin, Bengali)
- Romanized content (Hinglish, Benglish, Tanglish)
- Code-switching (mixed languages)
- Confidence scores

Uses Unicode range analysis and script-specific heuristics.
No external API calls needed for detection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# Unicode script ranges for Indian scripts
SCRIPT_RANGES = {
    "Devanagari": [
        (0x0900, 0x097F),   # Devanagari
        (0xA8E0, 0xA8FF),   # Devanagari Extended
    ],
    "Bengali": [
        (0x0980, 0x09FF),   # Bengali/Assamese
    ],
    "Tamil": [
        (0x0B80, 0x0BFF),   # Tamil
    ],
    "Telugu": [
        (0x0C00, 0x0C7F),   # Telugu
    ],
    "Gujarati": [
        (0x0A80, 0x0AFF),   # Gujarati
    ],
    "Kannada": [
        (0x0C80, 0x0CFF),   # Kannada
    ],
    "Malayalam": [
        (0x0D00, 0x0D7F),   # Malayalam
    ],
    "Gurmukhi": [
        (0x0A00, 0x0A7F),   # Gurmukhi
    ],
    "Odia": [
        (0x0B00, 0x0B7F),   # Oriya/Odia
    ],
    "Arabic": [
        (0x0600, 0x06FF),   # Arabic
        (0x0750, 0x077F),   # Arabic Supplement
        (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
    ],
    "Latin": [
        (0x0041, 0x005A),   # Basic Latin uppercase
        (0x0061, 0x007A),   # Basic Latin lowercase
    ],
}

# Common Romanized Indian words by language
# Used to detect Hinglish, Benglish, Tanglish, etc.
ROMANIZED_INDIC_MARKERS = {
    "hi": {
        "kya", "kaise", "kab", "kahin", "kyunki", "lekin", "aur", "ya",
        "mein", "mai", "hum", "tum", "aap", "wo", "yeh", "yeh", "is",
        "us", "ki", "ka", "ke", "ko", "se", "par", "tak", "bhi", "hi",
        "tha", "thi", "the", "hoga", "hogi", "tha", "tha", "nahin", "nahi",
        "haan", "ha", "nahin", "abhi", "jab", "tab", "agar", "toh",
        "bhot", "bahut", "kam", "zyada", "acha", "bura", "bada", "chhota",
        "tumhara", "mera", "uska", "inka", "sab", "kuch", "koi", "document",
        "last", "date", "deadline", "application", "kya", "h", "hain",
    },
    "bn": {
        "kobe", "kothay", "ken", "jeta", "eta", "oi", "shei", "ami",
        "tumi", "amader", "tader", "er", "ta", "te", "e", "o", "niye",
        "kore", "achi", "bhalo", "kharap", "boro", "chhoto", "kichu",
        "deadline", "document", "date", "last", "application", "kono",
    },
    "ta": {
        "enna", "eppadi", "enga", "eppo", "endha", "idha", "adha",
        "naan", "nee", "avan", "aval", "avargal", "namak", "avargalukku",
        "la", "le", "thaan", "ah", "matum", "ellaam", "mukkiya",
        "document", "important", "points", "last", "date", "deadline",
        "application", "indha", "andha", "enna", "theriyum",
    },
    "te": {
        "enu", "elago", "ekka", "eppudu", "ee", "aa", "naa", "nee",
        "vaadu", "vaallu", "mana", "mee", "andaru", "konni", "chala",
        "chala", "document", "important", "points", "last", "date",
        "deadline", "application", "ee", "aa", "enti", "enta",
    },
    "mr": {
        "kaa", "kasa", "kauthi", "kauthlya", "aahe", "ahet", "nahi",
        "hoo", "mi", "tu", "aamhi", "te", "tya", "cha", "la", "madhye",
        "document", "deadline", "application", "last", "date", "kadhi",
        "aahe", "kaay", "kiti", "kuthla",
    },
    "gu": {
        "shu", "kem", "kya", "kab", "che", "che", "na", "hu", "tu",
        "ame", "te", "ta", "ni", "ma", "document", "deadline", "application",
        "last", "date", "shu", "ketlu", "kem",
    },
    "kn": {
        "enu", "hege", "ellige", "yaavaga", "ee", "aa", "naanu", "neenu",
        "avaru", "namage", "avara", "alli", "inda", "document", "deadline",
        "application", "last", "date", "estu", "yavudu",
    },
    "ml": {
        "enthu", "epol", "engane", "evide", "ee", "aa", "njaan", "nee",
        "avar", "nammal", "avarude", "il", "document", "deadline",
        "application", "last", "date", "enthaanu", "ethra",
    },
    "pa": {
        "ki", "kiven", "kithhe", "kad", "han", "ne", "nahin", "haan",
        "main", "tu", "asi", "oh", "sanu", "ton", "vich", "document",
        "deadline", "application", "last", "date", "ki", "kiddan",
    },
}

# Language name mapping
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    "ur": "Urdu",
    "mixed": "Mixed",
    "unknown": "Unknown",
}

# Script to most likely language (when only one script is detected)
SCRIPT_TO_LANG = {
    "Devanagari": "hi",  # Default; could be Marathi too (shares script)
    "Bengali": "bn",     # Could be Assamese too
    "Tamil": "ta",
    "Telugu": "te",
    "Gujarati": "gu",
    "Kannada": "kn",
    "Malayalam": "ml",
    "Gurmukhi": "pa",
    "Odia": "or",
    "Arabic": "ur",      # Used for Urdu
    "Latin": "en",
}


@dataclass
class LanguageDetectionResult:
    """Result of language detection."""
    language: str = "en"
    languages: List[str] = field(default_factory=lambda: ["en"])
    script: str = "Latin"
    scripts: List[str] = field(default_factory=lambda: ["Latin"])
    romanized: bool = False
    code_switched: bool = False
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "languages": self.languages,
            "script": self.script,
            "scripts": self.scripts,
            "romanized": self.romanized,
            "code_switched": self.code_switched,
            "language_confidence": round(self.confidence, 2),
        }


def _char_to_script(char: str) -> Optional[str]:
    """Return the script name for a single character, or None."""
    code_point = ord(char)
    for script_name, ranges in SCRIPT_RANGES.items():
        for start, end in ranges:
            if start <= code_point <= end:
                return script_name
    return None


def _detect_scripts(text: str) -> dict:
    """
    Count characters per script in the text.
    Returns {script_name: count}.
    """
    script_counts: dict[str, int] = {}
    for char in text:
        script = _char_to_script(char)
        if script:
            script_counts[script] = script_counts.get(script, 0) + 1
    return script_counts


def _is_latin_indic_romanized(text: str) -> tuple[bool, Optional[str]]:
    """
    Detect if Latin-script text contains Romanized Indian language content.

    Returns (is_romanized, detected_language_code).
    """
    if not text:
        return False, None

    # Normalize to lowercase for matching
    words = set(re.findall(r'[a-z]+', text.lower()))
    if not words:
        return False, None

    # Count matches per language
    lang_scores: dict[str, int] = {}
    for lang_code, markers in ROMANIZED_INDIC_MARKERS.items():
        matches = words & markers
        if matches:
            lang_scores[lang_code] = len(matches)

    if not lang_scores:
        return False, None

    # Get the language with most matches
    best_lang = max(lang_scores, key=lang_scores.get)
    best_score = lang_scores[best_lang]

    # Threshold: at least 2 matches or significant proportion
    total_words = len(words)
    if best_score >= 2 and best_score / max(total_words, 1) >= 0.1:
        return True, best_lang
    if best_score >= 4:
        return True, best_lang

    return False, None


def detect_language(text: str) -> LanguageDetectionResult:
    """
    Detect the language, script, and characteristics of the input text.

    This function handles:
    - Native script Indian languages (Devanagari, Tamil, etc.)
    - Romanized Indian languages (Hinglish, Benglish, Tanglish)
    - Mixed-script queries (code-switching)
    - English
    """
    result = LanguageDetectionResult()

    if not text or not text.strip():
        return result

    text = text.strip()

    # Step 1: Detect scripts present in the text
    script_counts = _detect_scripts(text)

    if not script_counts:
        # Fallback: probably just punctuation/numbers
        return result

    # Sort scripts by frequency
    sorted_scripts = sorted(script_counts.items(), key=lambda x: x[1], reverse=True)
    result.scripts = [s[0] for s in sorted_scripts]
    result.script = sorted_scripts[0][0]

    # Step 2: Determine languages based on scripts
    detected_langs = set()
    has_indic_script = False
    has_latin = "Latin" in script_counts

    for script_name, count in sorted_scripts:
        if script_name == "Latin":
            continue
        has_indic_script = True
        lang = SCRIPT_TO_LANG.get(script_name)
        if lang:
            detected_langs.add(lang)

    # Step 3: Handle Romanized content (Latin script only)
    if has_latin and not has_indic_script:
        # Pure Latin text — check if Romanized Indian language
        is_romanized, romanized_lang = _is_latin_indic_romanized(text)
        if is_romanized and romanized_lang:
            result.romanized = True
            detected_langs.add(romanized_lang)
            # Also add English as secondary since Romanized text contains English words
            detected_langs.add("en")
        else:
            detected_langs.add("en")

    # Step 4: Handle code-switching (Latin + Indic scripts)
    if has_latin and has_indic_script:
        result.code_switched = True
        # Check if the Latin part is Romanized Indic or English
        latin_chars = [c for c in text if _char_to_script(c) == "Latin"]
        latin_text = "".join(latin_chars)
        is_romanized, romanized_lang = _is_latin_indic_romanized(latin_text)
        if is_romanized and romanized_lang:
            result.romanized = True
            detected_langs.add(romanized_lang)

    # Step 5: Set final results
    result.languages = sorted(detected_langs) if detected_langs else ["en"]

    if len(result.languages) > 1:
        result.language = result.languages[0]
    elif result.languages:
        result.language = result.languages[0]
    else:
        result.language = "en"

    # Step 6: Calculate confidence
    total_chars = sum(script_counts.values())
    if total_chars > 0:
        primary_count = sorted_scripts[0][1] if sorted_scripts else 0
        result.confidence = primary_count / total_chars

    return result


def get_language_name(lang_code: str) -> str:
    """Return the human-readable name for a language code."""
    return LANGUAGE_NAMES.get(lang_code, lang_code)
