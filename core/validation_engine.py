"""
Modul Validation Engine & Matriks Tingkat Keyakinan (Confidence Scoring).
Memastikan keamanan penggantian teks:
- Menilai tingkat keyakinan (HIGH, MEDIUM, LOW, NONE)
- Memeriksa batasan tipe data (NIP, Nama, Madrasah)
- Mengelola struktur data usulan penggantian (ReplacementPlanItem)
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import re


class ConfidenceLevel:
    HIGH = "HIGH"        # Eksekusi otomatis aman
    MEDIUM = "MEDIUM"    # Masuk antrean pratinjau
    LOW = "LOW"          # Ambigu / kemiripan rendah (disarankan dilewati)
    NONE = "NONE"        # Ditolak mutlak (contoh: placeholder tak terikat di LKPD)


@dataclass
class ReplacementPlanItem:
    """Mewakili satu titik usulan perubahan teks dalam dokumen."""
    doc_path: str
    rel_path: str
    category: str
    old_text: str
    new_text: str
    confidence: str = ConfidenceLevel.HIGH
    location_info: str = ""
    is_approved: bool = True
    target_type: str = "EXACT"  # 'EXACT', 'SPAN', 'PARAGRAPH_FULL', 'TABLE_CELL', 'HEADER_FOOTER', 'TAB_LINE'
    target_meta: Dict[str, Any] = field(default_factory=dict)


def validate_type_safety(category: str, old_text: str, new_text: str) -> bool:
    """
    Memeriksa apakah teks target yang akan ditimpa masuk akal sesuai tipe datanya.
    Mencegah rusaknya dokumen karena salah sasaran (No Blind Replacement).
    """
    clean_old = old_text.strip()

    # 1. Validasi Kategori NIP
    if "NIP" in category or "NUPTK" in category:
        # Hitung panjang huruf selain kata NIP/NUPTK
        without_nip = re.sub(r"\b(NIP|NUPTK)\b", "", clean_old, flags=re.IGNORECASE)
        letters_only = re.sub(r"[^A-Za-z]", "", without_nip)
        # Jika ada lebih dari 30 karakter huruf tanpa angka sama sekali, kemungkinan salah sasaran
        if len(letters_only) > 30 and not re.search(r"\d", clean_old):
            return False

    # 2. Validasi Kategori Nama Terang
    if "Nama" in category:
        # Jika sangat panjang (> 120 huruf) dan tanpa karakter placeholder/gelar
        letters_only = re.sub(r"[^A-Za-z]", "", clean_old)
        if len(letters_only) > 100 and not re.search(r"[\._\-\(\)]", clean_old):
            return False

    # 3. Validasi Titimangsa
    if "Titimangsa" in category:
        letters_only = re.sub(r"[^A-Za-z]", "", clean_old)
        if len(letters_only) > 60:
            return False

    return True


def evaluate_confidence(
    category: str,
    old_text: str,
    match_source: str,
    similarity_score: float = 1.0,
    has_anchor: bool = True
) -> str:
    """
    Menghitung skor keyakinan berdasarkan sumber pencocokan dan konteks sekitar.
    """
    # Jika match_source adalah EXACT atau struktur tabel tanda tangan lengkap
    if match_source == "EXACT":
        return ConfidenceLevel.HIGH

    if match_source == "SIGNATURE_BLOCK":
        return ConfidenceLevel.HIGH if has_anchor else ConfidenceLevel.MEDIUM

    if match_source == "IDENTITY_TABLE":
        return ConfidenceLevel.HIGH if has_anchor else ConfidenceLevel.MEDIUM

    if match_source == "INLINE_LABEL":
        return ConfidenceLevel.HIGH

    if match_source == "FUZZY":
        if similarity_score >= 0.90:
            return ConfidenceLevel.MEDIUM
        elif similarity_score >= 0.80:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.NONE

    return ConfidenceLevel.MEDIUM
