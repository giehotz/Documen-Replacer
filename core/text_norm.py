"""
Utilitas normalisasi teks umum untuk pencocokan label dan kamus.
"""
import re


def normalize_string(text: str) -> str:
    """Membersihkan dan menormalkan teks (lowercase, hilangkan tanda baca tertentu & kurung, spasi tunggal)."""
    t = (text or "").lower()
    t = re.sub(r"[:\.\-_/()\[\]{}]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
