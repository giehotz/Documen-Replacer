"""
Validator nilai untuk jenis-jenis data dokumen administratif baru:
- doc_number: format nomor surat / SK resmi
- multiline_title: teks judul / perihal / tentang dokumen
- date_id: format tanggal standar Indonesia
"""
import re
from typing import Optional

RE_DOC_NUMBER = re.compile(r"[A-Za-z0-9]+[A-Za-z0-9./_\-–\s]*\d+[A-Za-z0-9./_\-–\s]*")
RE_DATE_ID = re.compile(
    r"\b(?:\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",
    re.IGNORECASE
)


def validate_doc_number(val: str) -> bool:
    """Validasi format nomor surat/SK (memiliki karakter dan digit angka pembeda)."""
    s = val.strip()
    if not s or len(s) < 3:
        return False
    return bool(RE_DOC_NUMBER.search(s))


def validate_multiline_title(val: str) -> bool:
    """Validasi teks judul/tentang SK/perihal (tidak boleh kosong atau hanya tanda baca)."""
    s = val.strip()
    return len(s) >= 3 and any(c.isalnum() for c in s)


def validate_date_id(val: str) -> bool:
    """Validasi teks tanggal Indonesia (misal '14 November 2026' atau '14/11/2026')."""
    s = val.strip()
    return bool(RE_DATE_ID.search(s))
