"""Arabic text normalization for matching (KB retrieval + keyword scan).

Dependency-free. Collapses the spelling variants that make naive keyword
matching miss obvious hits: diacritics (tashkeel), tatweel, the alef/ya/ta-marbuta
variants, and Arabic-Indic vs Latin digits. Used on BOTH the query and the
candidate text so they meet in the same normalized space.

Not a stemmer: it does not strip prefixes/suffixes. When pgvector embeddings land
later, this stays useful as the lexical pre-filter.
"""
from __future__ import annotations

import re

# Harakat (U+064B..U+0652), superscript alef (U+0670), and the dagger/maddah marks
# (U+0653..U+0655) — all dropped. Tatweel (U+0640) is also dropped.
_TASHKEEL_RE = re.compile("[ً-ٰٕـ]")

# Character-level folds applied after diacritics are removed.
_FOLD = {
    # Alef variants -> bare alef
    "آ": "ا",  # آ
    "أ": "ا",  # أ
    "إ": "ا",  # إ
    "ٱ": "ا",  # ٱ
    # Ya / alef-maqsura
    "ى": "ي",  # ى -> ي
    # Ta marbuta -> ha
    "ة": "ه",  # ة -> ه
    # Hamza carriers -> their base letter (common normalization)
    "ئ": "ي",  # ئ -> ي
    "ؤ": "و",  # ؤ -> و
    "ء": "",        # ء (standalone) -> drop
}
# Arabic-Indic (U+0660..U+0669) and Extended/Persian (U+06F0..U+06F9) digits -> ASCII.
for _i in range(10):
    _FOLD[chr(0x0660 + _i)] = str(_i)
    _FOLD[chr(0x06F0 + _i)] = str(_i)

_TRANSLATE = {ord(k): (v or None) for k, v in _FOLD.items()}

# Anything that is not a word char (Unicode-aware \w matches Arabic letters) or
# whitespace becomes a space: strips Arabic (، ؛ ؟) and Latin punctuation alike.
_NONWORD_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

_TOKEN_MIN_LEN = 2


def normalize_ar(text: str | None) -> str:
    """Return a normalized, lowercased form suitable for lexical matching."""
    if not text:
        return ""
    text = _TASHKEEL_RE.sub("", text)
    text = text.translate(_TRANSLATE)
    text = text.lower()
    text = _NONWORD_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def tokens(text: str | None, *, min_len: int = _TOKEN_MIN_LEN) -> set[str]:
    """Normalized token set (words shorter than `min_len` dropped)."""
    return {t for t in normalize_ar(text).split() if len(t) >= min_len}


def contains_any(text: str | None, needles) -> list[str]:
    """Normalized substring match: which `needles` appear in `text`.

    Both sides are normalized, so "اتأخر" matches "اتاخر" and digit variants align.
    Returns the matched needles (original spelling) — empty list if none.
    """
    hay = normalize_ar(text)
    if not hay:
        return []
    hits = []
    for n in needles or []:
        nn = normalize_ar(n)
        if nn and nn in hay:
            hits.append(n)
    return hits
