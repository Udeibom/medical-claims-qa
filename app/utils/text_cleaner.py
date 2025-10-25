import re
import unicodedata


def clean_text(raw_text: str) -> str:
    """
    Normalize OCR text: remove non-printable chars, normalize unicode,
    collapse multiple spaces/newlines, and trim.
    """
    if not raw_text:
        return ""

    # normalize unicode characters (e.g., fancy quotes)
    text = unicodedata.normalize("NFKC", raw_text)

    # replace carriage returns with newline for consistency
    text = text.replace("\r", "\n")

    # remove non-printable or control chars except newline and tab
    text = "".join(ch for ch in text if ch.isprintable() or ch in ["\n", "\t"])

    # collapse multiple spaces and newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)

    # trim spaces at start/end of lines
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n".join(ln for ln in lines if ln)

    return cleaned.strip()


def remove_extra_spaces(text: str) -> str:
    """Quick helper for collapsing duplicate spaces."""
    return re.sub(r"\s{2,}", " ", text.strip()) if text else ""


def normalize_amount(text: str) -> str:
    """
    Simple currency normalization: remove unwanted spaces,
    keep ₦/$/NGN prefix if present.
    """
    if not text:
        return ""
    text = text.strip()
    text = text.replace("NGN ", "₦").replace("N ", "₦")
    text = re.sub(r"\s+", " ", text)
    return text
