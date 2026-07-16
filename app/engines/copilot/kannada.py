"""GARUDA copilot — Kannada → English query normalization (plan §4.13).

The voice showpiece: the browser's speech recognition produces a *Kannada*
transcript (Catalyst Zia has OCR/NER but no speech-to-text or translation —
verified against the SDK), and this module turns it into the English tokens
nl2query.parse_query and the TF-IDF retriever actually key on:

  1. domain lexicon — crime types, the 31 district names (exact census
     spellings, since the parser matches them as substrings), question/time
     words;
  2. anything still in Kannada script (person names, places) is
     transliterated to Latin via indic-transliteration, so it can still hit
     the semantic/entity arms loosely.

Pure-Python, $0, deterministic — same contract as the rest of the copilot.
"""
from __future__ import annotations

import re

# --- crime types → the synonyms/canonical labels nl2query already resolves ---
_CRIME = {
    "ಸರಗಳ್ಳತನ": "chain snatching",
    "ಸರ ಕಳ್ಳತನ": "chain snatching",
    "ಚೈನ್ ಕಳ್ಳತನ": "chain snatching",
    "ದ್ವಿಚಕ್ರ ವಾಹನ ಕಳ್ಳತನ": "two-wheeler theft",
    "ಬೈಕ್ ಕಳ್ಳತನ": "bike theft",
    "ಸ್ಕೂಟರ್ ಕಳ್ಳತನ": "scooter theft",
    "ಕಾರು ಕಳ್ಳತನ": "car theft",
    "ವಾಹನ ಕಳ್ಳತನ": "vehicle theft",
    "ಮನೆಗಳ್ಳತನ": "burglary",
    "ಮನೆ ಕಳ್ಳತನ": "burglary",
    "ಕನ್ನ ಹಾಕುವುದು": "housebreaking",
    "ಕಳ್ಳತನ": "theft",
    "ದರೋಡೆ": "robbery",
    "ಡಕಾಯಿತಿ": "dacoity",
    "ಕೊಲೆ": "murder",
    "ಹತ್ಯೆ": "murder",
    "ವಂಚನೆ": "cheating",
    "ಮೋಸ": "cheating",
    "ಸೈಬರ್ ಅಪರಾಧ": "cybercrime",
    "ಸೈಬರ್": "cyber",
    "ಅಪಹರಣ": "kidnap",
    "ಗಲಭೆ": "rioting",
    "ಹಲ್ಲೆ": "assault",
    "ಗಾಯ": "grievous hurt",
    "ಅತಿಕ್ರಮಣ": "criminal trespass",
    "ನಂಬಿಕೆ ದ್ರೋಹ": "criminal breach of trust",
}

# --- the 31 districts, exact census_2011.csv spellings (parser matches these) ---
_DISTRICT = {
    "ಬೆಂಗಳೂರು ನಗರ": "bengaluru urban",
    "ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ": "bengaluru rural",
    "ಬೆಂಗಳೂರು": "bengaluru",           # alias handled by nl2query → BNU
    "ಮೈಸೂರು": "mysuru",
    "ಬೆಳಗಾವಿ": "belagavi",
    "ಕಲಬುರಗಿ": "kalaburagi",
    "ದಕ್ಷಿಣ ಕನ್ನಡ": "dakshina kannada",
    "ಉತ್ತರ ಕನ್ನಡ": "uttara kannada",
    "ತುಮಕೂರು": "tumakuru",
    "ಬಳ್ಳಾರಿ": "ballari",
    "ದಾವಣಗೆರೆ": "davanagere",
    "ಧಾರವಾಡ": "dharwad",
    "ಶಿವಮೊಗ್ಗ": "shivamogga",
    "ಹಾಸನ": "hassan",
    "ಮಂಡ್ಯ": "mandya",
    "ಕೋಲಾರ": "kolar",
    "ರಾಮನಗರ": "ramanagara",
    "ಚಿತ್ರದುರ್ಗ": "chitradurga",
    "ಚಿಕ್ಕಬಳ್ಳಾಪುರ": "chikkaballapura",
    "ಚಿಕ್ಕಮಗಳೂರು": "chikkamagaluru",
    "ಚಾಮರಾಜನಗರ": "chamarajanagar",
    "ಕೊಡಗು": "kodagu",
    "ಉಡುಪಿ": "udupi",
    "ಹಾವೇರಿ": "haveri",
    "ಗದಗ": "gadag",
    "ಬಾಗಲಕೋಟೆ": "bagalkote",
    "ವಿಜಯಪುರ": "vijayapura",
    "ವಿಜಯನಗರ": "vijayanagara",
    "ಕೊಪ್ಪಳ": "koppal",
    "ರಾಯಚೂರು": "raichur",
    "ಬೀದರ್": "bidar",
    "ಯಾದಗಿರಿ": "yadgir",
}

# --- question / time / filler words the parser or reader benefits from ---
_MISC = {
    "ಎಷ್ಟು": "how many",
    "ಎಲ್ಲಿ": "where",
    "ಯಾರು": "who",
    "ಯಾವಾಗ": "when",
    "ತೋರಿಸು": "show",
    "ತೋರಿಸಿ": "show",
    "ಪ್ರಕರಣಗಳು": "cases",
    "ಪ್ರಕರಣಗಳನ್ನು": "cases",
    "ಪ್ರಕರಣ": "case",
    "ದೂರುಗಳು": "complaints",
    "ಜಿಲ್ಲೆಯಲ್ಲಿ": "district",
    "ಜಿಲ್ಲೆ": "district",
    "ಕಳೆದ ತಿಂಗಳು": "last 1 month",
    "ಕಳೆದ ವಾರ": "last 1 week",
    "ಕಳೆದ ವರ್ಷ": "last 12 month",
    "ಇಂದು": "last 1 day",
    "ರಾತ್ರಿ": "night",
    "ಬೆಳಿಗ್ಗೆ": "morning",
    "ಮಧ್ಯಾಹ್ನ": "afternoon",
    "ಸಂಜೆ": "evening",
    "ನಡುರಾತ್ರಿ": "midnight",
    "ವಾಹನ": "vehicle",
    "ಫೋನ್": "phone",
    "ಆರೋಪಿ": "suspect",
    "ಬಗ್ಗೆ": "about",
    "ಮತ್ತು": "and",
    "ಇತ್ತೀಚಿನ": "recent",
}

_KANNADA_RE = re.compile(r"[ಀ-೿]")
# longest phrase first so "ಬೈಕ್ ಕಳ್ಳತನ" wins over the bare "ಕಳ್ಳತನ"
_LEXICON = sorted({**_CRIME, **_DISTRICT, **_MISC}.items(),
                  key=lambda kv: -len(kv[0]))


def has_kannada(text):
    return bool(_KANNADA_RE.search(text or ""))


def _transliterate(token):
    """Leftover Kannada (names, places) → Latin for the retrieval arms."""
    try:
        from indic_transliteration import sanscript
        latin = sanscript.transliterate(token, sanscript.KANNADA, sanscript.ITRANS)
        return re.sub(r"[^A-Za-z0-9 ]", "", latin).strip().lower() or token
    except Exception:                          # noqa: BLE001 — keep the token
        return token


def kn_to_en(text):
    """Kannada(-mixed) query → English query + a replacement trace for the UI.

    Returns {"english", "replacements": [(kn, en), ...], "had_kannada"}.
    English input passes through untouched.
    """
    if not has_kannada(text):
        return {"english": text, "replacements": [], "had_kannada": False}
    out = text
    trace = []
    for kn, en in _LEXICON:
        if kn in out:
            out = out.replace(kn, " " + en + " ")
            trace.append((kn, en))
    # transliterate any remaining Kannada runs (typically person names)
    def _sub(m):
        latin = _transliterate(m.group(0))
        trace.append((m.group(0), latin))
        return " " + latin + " "
    out = re.sub(r"[ಀ-೿][ಀ-೿‌‍]*", _sub, out)
    out = re.sub(r"\s+", " ", out).strip()
    return {"english": out, "replacements": trace, "had_kannada": True}
