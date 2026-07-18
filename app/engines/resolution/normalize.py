"""GARUDA - normalization, transliteration and phonetic keys for entity resolution.

Pure-Python, local/free. Optional libs degrade gracefully so the module imports even
in a minimal environment (the AppSail health probe must never crash on import):
  - indic-transliteration : Kannada -> Latin so script variants align (ರವಿ -> "ravi").
  - jellyfish             : NYSIIS / Metaphone phonetic keys (better than Soundex for
                            Indian names) used for blocking.
Falls back to crude prefixes / identity when a lib is absent.
"""
from __future__ import annotations

import re
import unicodedata

try:  # Kannada <-> Latin
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate as _translit
    _HAS_INDIC = True
except Exception:  # noqa: BLE001
    _HAS_INDIC = False

try:  # phonetic keys
    import jellyfish
    _HAS_JELLY = True
except Exception:  # noqa: BLE001
    _HAS_JELLY = False

_KANNADA_RE = re.compile(r"[ಀ-೿]")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
# honorifics / titles stripped before comparison (lowercased, no punctuation)
_HONORIFICS = {
    "sri", "shri", "sree", "smt", "kum", "kumari", "mr", "mrs", "ms", "dr",
    "late", "thiru", "ms", "sft", "m", "s",
}


def has_kannada(s: str) -> bool:
    return bool(_KANNADA_RE.search(s or ""))


def transliterate_kn(s: str) -> str:
    """Transliterate Kannada-script tokens to Latin (Harvard-Kyoto), leaving Latin
    tokens untouched. No-op if the lib is missing or there's no Kannada."""
    if not s or not _HAS_INDIC or not has_kannada(s):
        return s
    out = []
    for tok in s.split():
        if has_kannada(tok):
            try:
                tok = _translit(tok, sanscript.KANNADA, sanscript.HK)
            except Exception:  # noqa: BLE001
                pass
        out.append(tok)
    return " ".join(out)


def normalize_name(s: str) -> str:
    """lowercase, transliterate Kannada, strip diacritics/punctuation/honorifics,
    collapse whitespace. 'Dr. ರವಿ Kumar @' -> 'ravi kumar'."""
    s = transliterate_kn(s or "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _PUNCT_RE.sub(" ", s).lower()
    toks = [t for t in s.split() if t and t not in _HONORIFICS]
    return " ".join(toks)


def name_parts(norm: str):
    """(first, last) from a normalized name; last == '' for single-token names."""
    toks = norm.split()
    if not toks:
        return "", ""
    if len(toks) == 1:
        return toks[0], ""
    return toks[0], toks[-1]


def phonetic(token: str) -> str:
    """NYSIIS phonetic key (good for Indian names); crude prefix fallback."""
    if not token:
        return ""
    if _HAS_JELLY:
        try:
            return jellyfish.nysiis(token)
        except Exception:  # noqa: BLE001
            pass
    return token[:4]


def metaphone(token: str) -> str:
    """Metaphone key (collapses ph->f etc.); crude prefix fallback."""
    if not token:
        return ""
    if _HAS_JELLY:
        try:
            return jellyfish.metaphone(token)
        except Exception:  # noqa: BLE001
            pass
    return token[:4]


def normalize_phone(s: str) -> str:
    """Digits only, India-normalized to the trailing 10 (drops +91 / 0 prefixes)."""
    d = re.sub(r"\D", "", s or "")
    if len(d) > 10 and d.startswith("91"):
        d = d[-10:]
    if len(d) == 11 and d.startswith("0"):
        d = d[1:]
    return d


def normalize_vehicle(s: str) -> str:
    """Uppercase alphanumerics only: 'KA-68 MC 3164' -> 'KA68MC3164'."""
    return re.sub(r"[^A-Za-z0-9]", "", (s or "").upper())
