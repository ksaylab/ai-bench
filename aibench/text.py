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


# a number with ':', '/', '.' or ',' inside ("14:02", "100/100", "1.234,56") is one word, as a reader counts it
WORD = re.compile(r"\d+(?:[:/.,]\d+)+|[^\W_]+(?:[-'][^\W_]+)*")
HEADING = re.compile(r"^[ \t]*#{1,6}[ \t].*$", re.M)


def words(s):
    return WORD.findall(final_answer(s))


# a part ending in one of these is not a sentence: an initial ("D. Pedro") or a title ("Dr. Silva"). A sentence
# that really ends in a one-letter capital ("we chose plan B. Then...") is joined to the next one: rarer than initials.
NOT_AN_END = re.compile(r"(?:^|\s)(?:[A-ZÀ-Ý]|Sr|Sra|Srta|Dr|Dra|Prof|Profa|Mr|Mrs|Ms|St)\.$")


def sentences(s):
    """Sentences of the answer; a markdown heading line ("# What is a VPN?") is a title, not a sentence."""
    parts = re.split(r"(?<=[.!?])\s+", HEADING.sub("", final_answer(s)).strip())
    out = []
    for p in parts:
        if out and NOT_AN_END.search(out[-1]):
            out[-1] += " " + p
        else:
            out.append(p)
    return [p for p in out if re.search(r"\w", p)]


def is_portuguese(s):
    """Rough language check: more Portuguese function words than English ones, and at least two of them."""
    ws = [strip_accents(w).lower() for w in words(s)]
    pt = sum(w in PT_WORDS for w in ws)
    en = sum(w in EN_WORDS for w in ws)
    return pt >= 2 and pt > en
