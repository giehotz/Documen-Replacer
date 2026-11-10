"""
Modul Lapis 2: Label & Alias Recognition.
Memindai label dan mengenali kategori data berdasarkan kamus aliases.json.
"""
from typing import Dict, List, Optional, Tuple
import os
import json
import re


def load_aliases(config_path: str = "") -> Dict[str, List[str]]:
    """Memuat kamus aliases dari file JSON. Fallback ke default jika tidak ditemukan."""
    if not config_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config", "aliases.json")

    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Kamus bawaan jika file tidak dapat dibaca
    return {
        "Nama Kepala": ["Kepala Madrasah", "Kepala Sekolah", "Nama Kepala", "Mengetahui Kepala", "Plt. Kepala"],
        "NIP Kepala": ["NIP Kepala", "NIP Kepala Sekolah", "NIP Kepala Madrasah", "NIP."],
        "Nama Guru": ["Nama Penyusun", "Guru Penyusun", "Disusun Oleh", "Nama Guru", "Guru Kelas", "Guru Mata Pelajaran", "Pendidik", "Wali Kelas", "Penyusun"],
        "NIP Guru": ["NIP Guru", "NIP Guru Mata Pelajaran", "NIP Guru Kelas", "NUPTK", "Identitas Guru", "NIP Penyusun"],
        "Nama Madrasah": ["Nama Sekolah", "Satuan Pendidikan", "Nama Madrasah", "Unit Kerja", "Instansi"],
        "Jabatan Kepala": ["Kepala Sekolah", "Kepala Madrasah", "Plt. Kepala"],
        "Tahun Ajaran": ["Tahun Pelajaran", "Tahun Ajaran", "TP", "Th. Pelajaran"],
        "Semester": ["Semester", "Semester Ganjil", "Semester Genap", "Smt"],
        "Titimangsa": ["Titimangsa", "Tempat, Tanggal", "Tanggal Pengesahan", "Tanggal"],
    }


def normalize_string(text: str) -> str:
    """Membersihkan dan menormalkan teks (lowercase, hilangkan tanda baca tertentu, spasi tunggal)."""
    t = text.lower()
    t = re.sub(r"[:\.\-_/]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def match_category(text: str, aliases: Dict[str, List[str]]) -> Optional[str]:
    """
    Mencari kategori yang cocok untuk teks yang diberikan berdasarkan kamus alias.
    Memprioritaskan pencocokan alias terpanjang terlebih dahulu.
    """
    clean_target = normalize_string(text)
    if not clean_target:
        return None

    # ATURAN PRIORITAS TINGGI NIP / NUPTK:
    # Jika label mengandung 'nip' atau 'nuptk', HARUS dikategorikan ke NIP
    # (bukan Nama Guru / Kepala walau mengandung kata 'Guru' atau 'Kepala').
    is_nip = bool(re.search(r"\b(nip|nuptk)\b", clean_target))
    if is_nip:
        if "kepala" in clean_target or "kamad" in clean_target:
            return "NIP Kepala"
        return "NIP Guru"

    # Urutkan alias dari yang paling panjang agar lebih spesifik
    # (misal "NIP Kepala Madrasah" cocok sebelum "NIP")
    all_candidates: List[Tuple[str, str]] = []
    for cat, alias_list in aliases.items():
        if cat in ("NIP Kepala", "NIP Guru"):
            continue  # Sudah ditangani di atas
        for al in alias_list:
            all_candidates.append((cat, al))

    all_candidates.sort(key=lambda x: len(x[1]), reverse=True)

    for cat, al in all_candidates:
        clean_al = normalize_string(al)
        if clean_al and clean_al in clean_target:
            return cat

    return None


def split_label_and_value(text: str) -> Optional[Tuple[str, str]]:
    """
    Jika teks memiliki tanda titik dua ':', pisahkan menjadi (label, value).
    Contoh: 'Disusun oleh : Misri Kurniati' -> ('Disusun oleh', 'Misri Kurniati')
    """
    if ":" not in text:
        return None
    parts = text.split(":", 1)
    return parts[0].strip(), parts[1].strip()
