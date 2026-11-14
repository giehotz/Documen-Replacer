"""
Helper konversi dua arah tanggal kalender ke kalimat terbilang Bahasa Indonesia.
Mendukung rentang tahun 2000-2099 dengan jaminan properti bolak-balik (roundtrip) 100% konsisten.
Digunakan pada Berita Acara, Perjanjian Kerjasama, dan Pakta Integritas.
"""
from typing import Dict, Any, Optional, Tuple
import datetime
import re

ANGKA_DASAR = {
    0: "Nol", 1: "Satu", 2: "Dua", 3: "Tiga", 4: "Empat", 5: "Lima",
    6: "Enam", 7: "Tujuh", 8: "Delapan", 9: "Sembilan", 10: "Sepuluh",
    11: "Sebelas"
}

NAMA_BULAN = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]

NAMA_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def bilang_puluhan(n: int) -> str:
    """Mengubah bilangan 1-99 ke kata terbilang (misal 14 -> Empat Belas, 25 -> Dua Puluh Lima)."""
    if n <= 11:
        return ANGKA_DASAR[n]
    if n < 20:
        return ANGKA_DASAR[n - 10] + " Belas"
    puluh = n // 10
    sisa = n % 10
    res = ANGKA_DASAR[puluh] + " Puluh"
    if sisa > 0:
        res += " " + ANGKA_DASAR[sisa]
    return res


def bilang_tahun(y: int) -> str:
    """Mengubah tahun 2000-2099 ke kata terbilang (misal 2026 -> Dua Ribu Dua Puluh Enam)."""
    if y == 2000:
        return "Dua Ribu"
    sisa = y - 2000
    if 1 <= sisa <= 99:
        return "Dua Ribu " + bilang_puluhan(sisa)
    return str(y)


# Peta balik (reverse mapping) O(1) untuk pengujian properti dan parsing teks
DAY_WORDS_MAP: Dict[str, int] = {bilang_puluhan(d).lower(): d for d in range(1, 32)}
MONTH_WORDS_MAP: Dict[str, int] = {NAMA_BULAN[m].lower(): m for m in range(1, 13)}
YEAR_WORDS_MAP: Dict[str, int] = {bilang_tahun(y).lower(): y for y in range(2000, 2100)}


def format_date_to_words(dt: datetime.date, capitalize: bool = True) -> Dict[str, str]:
    """
    Menghasilkan komponen terbilang lengkap dari objek datetime.date:
    - hari: "Sabtu"
    - tanggal: "Empat Belas"
    - bulan: "November"
    - tahun: "Dua Ribu Dua Puluh Enam"
    - kalimat_lengkap: "Pada hari ini Sabtu tanggal Empat Belas bulan November tahun Dua Ribu Dua Puluh Enam (14-11-2026)"
    """
    hari = NAMA_HARI[dt.weekday()]
    tgl = bilang_puluhan(dt.day)
    bln = NAMA_BULAN[dt.month]
    thn = bilang_tahun(dt.year)
    tgl_angka = dt.strftime("%d-%m-%Y")

    if not capitalize:
        hari = hari.lower()
        tgl = tgl.lower()
        bln = bln.lower()
        thn = thn.lower()

    kalimat = f"Pada hari ini {hari} tanggal {tgl} bulan {bln} tahun {thn} ({tgl_angka})"

    return {
        "hari": hari,
        "tanggal": tgl,
        "bulan": bln,
        "tahun": thn,
        "tanggal_angka": tgl_angka,
        "kalimat_lengkap": kalimat,
    }


def parse_date_string(date_str: str) -> Optional[datetime.date]:
    """
    Mengenali berbagai format tanggal masukan:
    - YYYY-MM-DD (2026-11-14)
    - DD-MM-YYYY (14-11-2026)
    - DD/MM/YYYY (14/11/2026)
    - 14 November 2026
    """
    if not date_str:
        return None
    s = date_str.strip()

    # Cek format ISO YYYY-MM-DD
    m_iso = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if m_iso:
        try:
            return datetime.date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        except Exception:
            pass

    # Cek format DD-MM-YYYY atau DD/MM/YYYY
    m_dmy = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m_dmy:
        try:
            return datetime.date(int(m_dmy.group(3)), int(m_dmy.group(2)), int(m_dmy.group(1)))
        except Exception:
            pass

    # Cek format nama bulan Indonesia (14 November 2026)
    m_txt = re.match(r"^(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})$", s)
    if m_txt:
        d = int(m_txt.group(1))
        m_name = m_txt.group(2).lower()
        y = int(m_txt.group(3))
        m = MONTH_WORDS_MAP.get(m_name)
        if m and 1 <= d <= 31:
            try:
                return datetime.date(y, m, d)
            except Exception:
                pass

    return None


def parse_terbilang_sentence(text: str) -> Optional[datetime.date]:
    """
    Mengekstrak tanggal kalender dari kalimat pembuka Berita Acara yang memuat kata terbilang.
    Contoh: 'Pada hari ini Sabtu tanggal Empat Belas bulan November tahun Dua Ribu Dua Puluh Enam...'
    """
    # 1. Bila memuat angka di dalam tanda kurung (14-11-2026)
    m_paren = re.search(r"\((\d{1,2})[-/](\d{1,2})[-/](\d{4})\)", text)
    if m_paren:
        try:
            return datetime.date(int(m_paren.group(3)), int(m_paren.group(2)), int(m_paren.group(1)))
        except Exception:
            pass

    # 2. Rekonstruksi dari kata-kata terbilang
    norm = text.lower()
    m_parts = re.search(r"tanggal\s+([a-z\s]+?)\s+bulan\s+([a-z]+)\s+tahun\s+([a-z\s]+?)(?:\s*\(|\s*\.|\s*$)", norm)
    if m_parts:
        tgl_str = m_parts.group(1).strip()
        bln_str = m_parts.group(2).strip()
        thn_str = m_parts.group(3).strip()

        d = DAY_WORDS_MAP.get(tgl_str)
        m = MONTH_WORDS_MAP.get(bln_str)
        y = YEAR_WORDS_MAP.get(thn_str)
        if d and m and y:
            try:
                return datetime.date(y, m, d)
            except Exception:
                pass

    return None


def verify_terbilang_sync(text: str, expected_date: datetime.date) -> bool:
    """
    Memverifikasi apakah kalimat terbilang pada teks naskah selaras dengan expected_date.
    Mengembalikan True bila nama hari, tanggal, bulan, dan tahun terbilang cocok.
    """
    comp = format_date_to_words(expected_date, capitalize=False)
    norm = text.lower()
    return (
        comp["hari"] in norm and
        comp["tanggal"] in norm and
        comp["bulan"] in norm and
        comp["tahun"] in norm
    )
