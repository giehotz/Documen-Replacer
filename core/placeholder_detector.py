"""
Modul Lapis 3: Placeholder Detector.
Mendeteksi pola ruang isian titik-titik (....), garis bawah (____),
tanda kurung kosong/placeholder ( ............ ), dan spasi titik dua.
"""
from typing import Optional, Tuple
import re

# Regex pola titik-titik (minimal 2 titik untuk mengakomodasi template .. dan ...)
RE_DOTS = re.compile(r"\.{2,}")

# Regex pola garis bawah (minimal 2 underscore)
RE_UNDERLINE = re.compile(r"_{2,}")

# Regex placeholder di dalam kurung: ( .... ), [ ____ ], {   }, ([ .... ])
RE_PAREN_PLACEHOLDER = re.compile(r"[\(\[\{]\s*[\._\s\-\u2013\u2014]{2,}\s*[\)\]\}]")

# Regex baris yang murni merupakan placeholder (titik, garis bawah, kurung kosong (), [], {}, dll)
RE_PURE_PLACEHOLDER = re.compile(r"^[\s\._\-\u2013\u2014\(\)\[\]{}]+$")

# Regex khusus pola rentang tahun berbasis placeholder (misal 20.... / 20...., 20.. / 20.., .... / ...., dst.)
RE_YEAR_RANGE_PLACEHOLDER = re.compile(
    r"(?:20)?[\._\s\-\u2013\u2014]{2,}\s*[/\\-]\s*(?:20)?[\._\s\-\u2013\u2014]{2,}",
    re.IGNORECASE
)

# Regex khusus pola tahun tunggal dengan awalan 20 atau titik (misal 20...., 20..., 20..)
RE_YEAR_SINGLE_PLACEHOLDER = re.compile(
    r"\b20[\._\s\-\u2013\u2014]{2,}\b|\b20[\.]{2,}",
    re.IGNORECASE
)

# Regex rentang tahun yang sudah terisi (misal: 2025/2026, 2024-2025)
RE_FILLED_YEAR_RANGE = re.compile(
    r"(?<!\d)(20\d{2})\s*[/\\-]\s*(20\d{2})(?!\d)"
)


def is_year_context(text: str) -> bool:
    """Memeriksa apakah label atau teks berkaitan dengan tahun ajaran / tahun pelajaran."""
    return bool(re.search(r"(?i)\b(tahun|thn|th\.?|ajaran|pelajaran|tp|ta)\b", text))


def is_pure_placeholder(text: str) -> bool:
    """Memeriksa apakah teks murni berupa placeholder (titik-titik, garis bawah, strip/dash, kurung kosong (), [], {})."""
    stripped = text.strip()
    if not stripped:
        return False
    # Jika hanya berupa strip atau dash tunggal/ganda
    if stripped in ("-", "--", "---", "\u2013", "\u2014"):
        return True
    # Minimal mengandung setidaknya 2 karakter titik, underscore, atau strip
    has_symbols = bool(re.search(r"[\._\-\u2013\u2014]{2,}", stripped))
    return has_symbols and bool(RE_PURE_PLACEHOLDER.match(stripped))


def has_enclosing_parentheses(text: str) -> bool:
    """Memeriksa apakah teks dibungkus tanda kurung bulat (), siku [], atau kurawal {}."""
    stripped = text.strip()
    if len(stripped) < 2:
        return False
    pairs = [("([", "])"), ("(", ")"), ("[", "]"), ("{", "}")]
    for open_b, close_b in pairs:
        if stripped.startswith(open_b) and stripped.endswith(close_b):
            return True
    return False


def unwrap_parentheses(text: str) -> Tuple[str, bool]:
    """
    Jika teks dibungkus tanda kurung (bulat, siku, atau kurawal),
    mengembalikan (isi_di_dalam_kurung, True).
    Jika tidak, mengembalikan (teks, False).
    """
    stripped = text.strip()
    pairs = [("([", "])"), ("(", ")"), ("[", "]"), ("{", "}")]
    for open_b, close_b in pairs:
        if stripped.startswith(open_b) and stripped.endswith(close_b) and len(stripped) >= len(open_b) + len(close_b):
            return stripped[len(open_b):-len(close_b)].strip(), True
    return stripped, False


def format_with_parentheses(text: str, preserve_parens: bool) -> str:
    """
    Membungkus teks baru dengan tanda kurung jika preserve_parens True
    dan teks baru itu sendiri belum dibungkus kurung.
    """
    trimmed = text.strip()
    if not trimmed:
        return text
    if preserve_parens and not has_enclosing_parentheses(trimmed):
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


def extract_label_and_placeholder(
    text: str,
    category_hint: Optional[str] = None
) -> Optional[Tuple[str, str, int, int]]:
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

    # Jika konteks berkaitan dengan tahun, prioritaskan pola rentang tahun penuh
    is_yr = is_year_context(label_part) or (category_hint and is_year_context(category_hint))
    if is_yr:
        m_range = RE_YEAR_RANGE_PLACEHOLDER.search(remainder)
        if m_range:
            start_abs = colon_idx + 1 + m_range.start()
            end_abs = colon_idx + 1 + m_range.end()
            return label_part.strip(), text[start_abs:end_abs], start_abs, end_abs

        m_single = RE_YEAR_SINGLE_PLACEHOLDER.search(remainder)
        if m_single:
            start_abs = colon_idx + 1 + m_single.start()
            end_abs = colon_idx + 1 + m_single.end()
            return label_part.strip(), text[start_abs:end_abs], start_abs, end_abs

    span = find_placeholder_span(remainder)
    if span:
        start_rel, end_rel = span
        start_abs = colon_idx + 1 + start_rel
        end_abs = colon_idx + 1 + end_rel
        placeholder_str = text[start_abs:end_abs]
        return label_part.strip(), placeholder_str, start_abs, end_abs

    return None


def extract_filled_value_span(
    text: str,
    category_hint: Optional[str] = None
) -> Optional[Tuple[str, str, int, int]]:
    """
    Mendeteksi nilai yang SUDAH terisi setelah label (mis. 'Tahun Pelajaran : 2025/2026')
    ketika tidak ada placeholder titik-titik.
    Mengembalikan: (label_prefix, filled_text, start_index, end_index)
    """
    if ":" not in text:
        return None

    colon_idx = text.find(":")
    label_part = text[:colon_idx + 1]
    remainder = text[colon_idx + 1:]

    is_yr = is_year_context(label_part) or (category_hint and is_year_context(category_hint))
    if is_yr:
        m_filled = RE_FILLED_YEAR_RANGE.search(remainder)
        if m_filled:
            start_abs = colon_idx + 1 + m_filled.start()
            end_abs = colon_idx + 1 + m_filled.end()
            return label_part.strip(), text[start_abs:end_abs], start_abs, end_abs

    return None

