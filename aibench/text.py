"""Text normalization used by the checkers."""
import re
import unicodedata

THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
PT_WORDS = {"de", "da", "do", "das", "dos", "que", "o", "os", "as", "em", "no", "na", "nos", "nas", "para", "por",
            "com", "um", "uma", "nao", "e", "se", "ao", "ate", "mais", "pelo", "pela", "voce", "sua", "seu", "esta",
            "foi", "sao", "como"}
EN_WORDS = {"the", "and", "is", "of", "to", "in", "that", "it", "for", "with", "on", "are", "this", "was", "be",
            "you", "your", "will", "by", "an"}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def final_answer(s):
    """The answer without the reasoning block (<think>...</think>), as the user would see it."""
    return THINK.sub("", s or "").strip()


def normalize(s):
    """Lowercase, no accents, no <think> block, trimmed."""
    return strip_accents(final_answer(s)).lower()


def words(s):
    return re.findall(r"[^\W_]+(?:[-'][^\W_]+)*", final_answer(s))


def sentences(s):
    parts = re.split(r"(?<=[.!?])\s+", final_answer(s).strip())
    return [p for p in parts if re.search(r"\w", p)]


def is_portuguese(s):
    """Rough language check: more Portuguese function words than English ones, and at least two of them."""
    ws = [strip_accents(w).lower() for w in words(s)]
    pt = sum(w in PT_WORDS for w in ws)
    en = sum(w in EN_WORDS for w in ws)
    return pt >= 2 and pt > en
