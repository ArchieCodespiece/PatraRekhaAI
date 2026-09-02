"""
Romanized Indian language query normalizer for PatraRekhaAI.

Converts Romanized Indian language queries (Hinglish, Benglish, Tanglish, etc.)
into normalized forms for better semantic retrieval.

This does NOT transliterate to native scripts — it normalizes common
Romanized variations to a canonical form so the embedding model
can better match against document content.

Examples:
    "kya hai" -> "kya hai" (already canonical)
    "document mein" -> "document mein" (canonical)
    "last date kab hai" -> "last date kab hai" (mixed English/Hindi preserved)
    "kya h" -> "kya hai" (expanded)
    "doc me" -> "document mein" (expanded)
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


# Common Romanized Indic word variations mapped to canonical forms
# These help normalize queries for better embedding similarity
ROMANIZATION_NORMALIZATIONS: Dict[str, str] = {
    # Hindi/Hinglish common variations
    "h": "hai",
    "hn": "hain",
    "nhi": "nahi",
    "nhn": "nahi",
    "ha": "hai",
    "hi": "hai",  # careful: "hi" can also be emphasis
    "k": "ka",
    "ki": "ki",
    "kisi": "kisi",
    "kiska": "kiska",
    "kisko": "kisko",
    "kismein": "kisamein",
    "kaun": "kaun",
    "kaunsa": "kaunsa",
    "kaunsi": "kaunsi",
    "kyu": "kyun",
    "kyun": "kyun",
    "kaise": "kaise",
    "kaisey": "kaise",
    "kab": "kab",
    "kabhi": "kabhi",
    "kahan": "kahan",
    "kahan": "kahan",
    "kahin": "kahin",
    "kitna": "kitna",
    "kitni": "kitni",
    "kitne": "kitmein",
    "kyunki": "kyunki",
    "lekin": "lekin",
    "agar": "agar",
    "agar": "agar",
    "toh": "toh",
    "to": "toh",
    "bhi": "bhi",
    "bahut": "bahut",
    "bohot": "bahut",
    "zyada": "zyada",
    "jyada": "zyada",
    "kam": "kam",
    "acha": "acha",
    "accha": "acha",
    "bura": "bura",
    "theek": "theek",
    "thik": "theek",
    "haan": "haan",
    "haanji": "haan",

    # Common English abbreviation expansions in Indian context
    "doc": "document",
    "docs": "documents",
    "appln": "application",
    "appl": "application",
    "dt": "date",
    "dt.": "date",
    "no.": "number",
    "no": "number",
    "qty": "quantity",
    "amt": "amount",
    "approx": "approximately",
    "info": "information",
    "dept": "department",
    "govt": "government",
    "govt.": "government",
    "pvt": "private",
    "ltd": "limited",
    "corp": "corporation",

    # Common mixed query patterns (kept as-is but recognized)
    "mein": "mein",
    "me": "mein",
    "madhye": "madhye",
    "madhya": "madhye",
    "modhye": "madhye",
    "andher": "andar",
    "andar": "andar",
    "upar": "upar",
    "uper": "upar",
    "niche": "niche",
    "aage": "aage",
    "peeche": "peeche",
    "baad": "baad",
    "pehle": "pehle",
    "pahle": "pehle",
    "samay": "samay",
    "waqt": "waqt",
    "time": "time",
}

# Multi-word patterns for normalization (applied before single-word)
PHRASE_NORMALIZATIONS: List[Tuple[str, str]] = [
    # Common Hinglish patterns
    (r"\bki last date\b", "ki last date"),
    (r"\bki final date\b", "ki last date"),
    (r"\bki antim date\b", "ki last date"),
    (r"\bki deadline\b", "ki last date"),
    (r"\bka deadline\b", "ka deadline"),
    (r"\bka last date\b", "ka last date"),
    (r"\bka final date\b", "ka last date"),
    (r"\bka antim date\b", "ka last date"),
    (r"\bka antim tareekh\b", "ka last date"),
    (r"\bki antim tareekh\b", "ki last date"),
    (r"\bki aakhri date\b", "ki last date"),
    (r"\bka aakhri date\b", "ka last date"),
    (r"\bki aakhri tareekh\b", "ki last date"),
    (r"\bka aakhri tareekh\b", "ka last date"),
    (r"\bkal last date\b", "ka last date"),
    (r"\bkal deadline\b", "ka deadline"),
    (r"\baaj ki date\b", "aaj ki date"),
    (r"\baaj ka deadline\b", "aaj ka deadline"),
    (r"\bkal ki deadline\b", "kal ki deadline"),
    (r"\bkal ka deadline\b", "kal ka deadline"),
    (r"\bapplication ki last date\b", "application ki last date"),
    (r"\bapplication ka last date\b", "application ka last date"),
    (r"\bapplication ki deadline\b", "application ki deadline"),
    (r"\bapplication ka deadline\b", "application ka deadline"),
    (r"\bdeadline kya hai\b", "deadline kya hai"),
    (r"\bdeadline kab hai\b", "deadline kab hai"),
    (r"\bdeadline kab hai\b", "deadline kab hai"),
    (r"\blast date kya hai\b", "last date kya hai"),
    (r"\blast date kab hai\b", "last date kab hai"),
    (r"\bfinal date kya hai\b", "last date kya hai"),
    (r"\bantim date kya hai\b", "last date kya hai"),
    (r"\baakhri date kya hai\b", "last date kya hai"),
    (r"\bimportant points kya hain\b", "important points kya hain"),
    (r"\bimportant point kya hai\b", "important point kya hai"),
    (r"\bmukkiya points kya hain\b", "important points kya hain"),
    (r"\bmukkiya point kya hai\b", "important point kya hai"),
    (r"\bkya hai ye\b", "kya hai yeh"),
    (r"\bkya hai yeh\b", "kya hai yeh"),
    (r"\bkya hai isme\b", "kya hai ismein"),
    (r"\bkya hai ismein\b", "kya hai ismein"),
    (r"\bkya hai usme\b", "kya hai usmein"),
    (r"\bkya hai usmein\b", "kya hai usmein"),
    (r"\bkaise kare\b", "kaise karein"),
    (r"\bkaise karein\b", "kaise karein"),
    (r"\bkaise karu\b", "kaise karein"),
    (r"\bkaise kiya\b", "kiya kaise"),
    (r"\bkaise kiya hai\b", "kaise kiya hai"),
    (r"\bkaise kiya gaya\b", "kaise kiya gaya"),
    (r"\bkaise kiya gaya hai\b", "kaise kiya gaya hai"),
    (r"\bkya karna hai\b", "kya karna hai"),
    (r"\bkya karna hoga\b", "kya karna hoga"),
    (r"\bkya karna padega\b", "kya karna padega"),
    (r"\bkya karna padta hai\b", "kya karna padta hai"),
    (r"\bkya kiya ja sakta hai\b", "kya kiya ja sakta hai"),
    (r"\bkya kiya sakta hai\b", "kya kiya sakta hai"),
    (r"\bkya kiya sakte hain\b", "kya kiya sakte hain"),
    (r"\bkya kiya sakte ho\b", "kya kiya sakte hain"),
    (r"\bkya karna chahiye\b", "kya karna chahiye"),
    (r"\bkya karna chahiye tha\b", "kya karna chahiye tha"),
    (r"\bkya karna tha\b", "kya karna tha"),
    (r"\bkya karna padega ab\b", "kya karna padega ab"),
    (r"\bkya karna hai ab\b", "kya karna hai ab"),
    (r"\bkya karna hai mujhe\b", "kya karna hai"),
    (r"\bkya karna hai hume\b", "kya karna hai"),
    (r"\bkya karna hai hamein\b", "kya karna hai"),
    (r"\bkya karna hai hame\b", "kya karna hai"),
    (r"\bkya karna hai hamare liye\b", "kya karna hai"),
    (r"\bkya karna hai hamre liye\b", "kya karna hai"),
    (r"\bkya karna hai mere liye\b", "kya karna hai"),
    (r"\bkya karna hai mere\b", "kya karna hai"),
    (r"\bkya karna hai mujhse\b", "kya karna hai"),
    (r"\bkya karna hai ismein\b", "kya karna hai"),
    (r"\bkya karna hai document mein\b", "kya karna hai"),
    (r"\bkya karna hai doc mein\b", "kya karna hai"),
    (r"\bkya karna hai doc me\b", "kya karna hai"),
    (r"\bkya karna hai is document mein\b", "kya karna hai"),
    (r"\bkya karna hai is doc mein\b", "kya karna hai"),
    (r"\bkya karna hai is doc me\b", "kya karna hai"),
    (r"\bkya karna hai iss document mein\b", "kya karna hai"),
    (r"\bkya karna hai iss doc mein\b", "kya karna hai"),
    (r"\bkya karna hai iss doc me\b", "kya karna hai"),
]


def normalize_romanized_query(query: str) -> str:
    """
    Normalize a Romanized Indian language query for better retrieval.

    Steps:
    1. Apply phrase-level normalizations (multi-word patterns).
    2. Apply single-word normalizations (common abbreviations/variants).
    3. Preserve the original query structure — only fix obvious variations.

    The original query is always preserved in the UI — this normalized form
    is used internally for embedding/retrieval only.
    """
    if not query:
        return query

    query = query.strip()

    # Step 1: Phrase-level normalizations
    for pattern, replacement in PHRASE_NORMALIZATIONS:
        query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

    # Step 2: Single-word normalizations
    words = query.split()
    normalized_words = []
    for word in words:
        lower = word.lower()
        if lower in ROMANIZATION_NORMALIZATIONS:
            normalized_words.append(ROMANIZATION_NORMALIZATIONS[lower])
        else:
            normalized_words.append(word)

    return " ".join(normalized_words)


def get_retrieval_query(original_query: str) -> str:
    """
    Get the internal retrieval representation for a query.

    This is the query that should be used for embedding/vector search.
    The original user query is preserved for display.

    For Romanized Indic queries, this returns a normalized form.
    For native-script queries, this returns the original.
    """
    if not original_query:
        return original_query

    # Check if the query contains Latin script (potential Romanized Indic)
    has_latin = any(
        'a' <= c.lower() <= 'z' for c in original_query if c.isalpha()
    )

    if has_latin:
        return normalize_romanized_query(original_query)

    return original_query
