"""
Modul Lapis 5: Similarity Matcher (Fuzzy Matching).
Menggunakan pustaka standar difflib untuk menghitung rasio kemiripan teks
dan menangkap salah ketik (typo) pada label dokumen tanpa ketergantungan eksternal.
"""
from typing import Dict, List, Optional, Tuple
import difflib

from core.text_norm import normalize_string


def calculate_similarity(s1: str, s2: str) -> float:
    """Menghitung rasio kemiripan antara dua string (0.0 sampai 1.0)."""
    norm1 = normalize_string(s1)
    norm2 = normalize_string(s2)
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0
    return difflib.SequenceMatcher(None, norm1, norm2).ratio()


def find_fuzzy_category_match(
    text: str,
    aliases: Dict[str, List[str]],
    threshold: float = 0.80,
) -> Tuple[Optional[str], float, str]:
    """
    Mencari kategori dengan alias yang paling mirip dengan teks input.
    Mengembalikan: (kategori_terbaik, skor_kemiripan, alias_yang_cocok)
    Jika skor tertinggi < threshold, mengembalikan (None, 0.0, "").
    """
    clean_text = normalize_string(text)
    if not clean_text or len(clean_text) > 45 or len(clean_text.split()) > 6:
        return None, 0.0, ""

    best_cat: Optional[str] = None
    best_score: float = 0.0
    best_alias: str = ""

    # Hormati kamus: kategori yang dilarang (never_match / daftar global) tidak boleh dicocokkan fuzzy.
    resolver = getattr(aliases, "_dictionary", None)
    blocked_cats = set()
    if resolver is not None:
        blocked_cats = {c for c in aliases if resolver.is_blocked_for_category(text, c, for_fuzzy=True)}

    for cat, alias_list in aliases.items():
        if cat in blocked_cats:
            continue
        for al in alias_list:
            clean_al = normalize_string(al)
            if not clean_al:
                continue

            score = difflib.SequenceMatcher(None, clean_text, clean_al).ratio()
            if score > best_score:
                best_score = score
                best_cat = cat
                best_alias = al

    if best_score >= threshold:
        return best_cat, best_score, best_alias

    return None, best_score, ""
