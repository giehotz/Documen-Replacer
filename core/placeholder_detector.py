"""
Modul Lapis 3: Placeholder Detector.
Mendeteksi pola ruang isian titik-titik (....), garis bawah (____),
tanda kurung kosong/placeholder ( ............ ), dan spasi titik dua.
"""
from typing import Optional, Tuple
import re

# Regex pola titik-titik (minimal 3 titik)
RE_DOTS = re.compile(r"\.{3,}")

# Regex pola garis bawah (minimal 3 underscore)
RE_UNDERLINE = re.compile(r"_{3,}")

# Regex placeholder di dalam kurung: ( .... ), ( ____ ), (   )
RE_PAREN_PLACEHOLDER = re.compile(r"\(\s*[\._\s-]{2,}\s*\)")

# Regex baris yang murni merupakan placeholder
RE_PURE_PLACEHOLDER = re.compile(r"^[\s\._\-\(\)]+$")


def is_pure_placeholder(text: str) -> bool:
    """Memeriksa apakah teks murni berupa placeholder (titik-titik, garis bawah, strip/dash, kurung kosong)."""
    stripped = text.strip()
    if not stripped:
        return False
    # Jika hanya berupa strip atau dash tunggal/ganda
    if stripped in ("-", "--", "---", "–", "—"):
        return True
    # Minimal mengandung setidaknya 2 karakter titik, underscore, atau strip
    has_symbols = bool(re.search(r"[\._\-–—]{2,}", stripped))
    return has_symbols and bool(RE_PURE_PLACEHOLDER.match(stripped))


def has_enclosing_parentheses(text: str) -> bool:
    """Memeriksa apakah teks diawali '(' dan diakhiri ')'."""
    stripped = text.strip()
    return stripped.startswith("(") and stripped.endswith(")") and len(stripped) >= 2


def unwrap_parentheses(text: str) -> Tuple[str, bool]:
    """
    Jika teks dibungkus tanda kurung, mengembalikan (isi_di_dalam_kurung, True).
    Jika tidak, mengembalikan (teks, False).
    """
    stripped = text.strip()
    if has_enclosing_parentheses(stripped):
        return stripped[1:-1].strip(), True
    return stripped, False


def format_with_parentheses(text: str, preserve_parens: bool) -> str:
    """
    Membungkus teks baru dengan tanda kurung jika preserve_parens True
    dan teks baru itu sendiri belum dibungkus kurung.
    """
    trimmed = text.strip()
    if not trimmed:
        return text
    if preserve_parens and not (trimmed.startswith("(") and trimmed.endswith(")")):
        return f"( {trimmed} )"
    return trimmed


def find_placeholder_span(text: str) -> Optional[Tuple[int, int]]:
    """
    Mencari lokasi span (start, end) placeholder pertama di dalam teks:
    Mengutamakan pola kurung ( .... ), lalu titik-titik, lalu garis bawah.
    """
    # Cek placeholder dalam kurung
    m_paren = RE_PAREN_PLACEHOLDER.search(text)
    if m_paren:
        return m_paren.span()

    # Cek titik-titik
    m_dot = RE_DOTS.search(text)
    if m_dot:
        return m_dot.span()

    # Cek garis bawah
    m_und = RE_UNDERLINE.search(text)
    if m_und:
        return m_und.span()

    return None


def extract_label_and_placeholder(text: str) -> Optional[Tuple[str, str, int, int]]:
    """
    Mendeteksi pola: "<Label> : <Placeholder>"
    Contoh: "Nama Kepala Madrasah : ........................"
    Mengembalikan: (label_prefix, placeholder_text, start_index, end_index)
    """
    if ":" not in text:
        return None

    colon_idx = text.find(":")
    label_part = text[:colon_idx + 1]
    remainder = text[colon_idx + 1:]

    span = find_placeholder_span(remainder)
    if span:
        start_rel, end_rel = span
        start_abs = colon_idx + 1 + start_rel
        end_abs = colon_idx + 1 + end_rel
        placeholder_str = text[start_abs:end_abs]
        return label_part.strip(), placeholder_str, start_abs, end_abs

    return None
