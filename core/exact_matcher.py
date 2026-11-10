"""
Modul Lapis 1: Exact Matcher (Pencocokan String Persis).
Mengkompilasi pola regex dari aturan penggantian (teks_lama, teks_baru)
dan mendukung pemetaan kemunculan berurutan.
"""
from typing import List, Tuple, Dict, Optional, Any
import re


def build_exact_pattern(rules: List[Tuple[str, str]], case_sensitive: bool = True) -> Optional[Tuple[Any, Dict[str, List[str]], bool]]:
    """
    rules: daftar (teks_lama, teks_baru) sesuai urutan.
    Hanya menyertakan baris yang teks_lama-nya tidak kosong.
    Jika tidak ada aturan yang valid, mengembalikan None.
    """
    valid_rules = [(old.strip(), new) for old, new in rules if old and old.strip()]
    if not valid_rules:
        return None

    mapping: Dict[str, List[str]] = {}
    for old, new in valid_rules:
        key = old if case_sensitive else old.lower()
        mapping.setdefault(key, []).append(new)

    keys = sorted({old for old, _ in valid_rules}, key=len, reverse=True)
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile("|".join(re.escape(k) for k in keys), flags)

    return pattern, mapping, case_sensitive
