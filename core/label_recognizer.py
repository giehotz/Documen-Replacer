"""
Modul Lapis 2: Label & Alias Recognition.
Memindai label dan mengenali kategori data berdasarkan kamus aliases.json.
"""
from typing import Dict, List, Optional, Tuple
import os
import json
import re
import logging

logger = logging.getLogger(__name__)

# Alias pendek yang wajib cocok persis dengan seluruh teks label (bukan potongan kata)
SHORT_EXACT_ALIASES = {"tp", "smt", "tanggal"}


def load_aliases(config_path: str = "") -> Dict[str, List[str]]:
    """Memuat kamus aliases. Memprioritaskan FieldDictionary lalu fallback ke aliases.json."""
    try:
        from core.field_dictionary import FieldDictionary
        f_dict = FieldDictionary.load()
        aliases_map = f_dict.to_legacy_aliases()
        if aliases_map:
            return aliases_map
    except Exception as e:
        logger.debug("Tidak dapat memuat aliases dari FieldDictionary (%s). Mencoba berkas json.", e)

    if not config_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config", "aliases.json")

    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Gagal membaca aliases dari %s (%s). Menggunakan kamus bawaan.", config_path, e)

    # Kamus bawaan darurat jika semua berkas tidak dapat dibaca
    return {
        "Nama Kepala": ["Kepala Madrasah", "Kepala Sekolah", "Nama Kepala", "Mengetahui Kepala", "Plt. Kepala"],
        "NIP Kepala": ["NIP Kepala", "NIP Kepala Sekolah", "NIP Kepala Madrasah", "NIP."],
        "Nama Guru": ["Nama Penyusun", "Guru Penyusun", "Disusun Oleh", "Nama Guru", "Guru Kelas", "Guru Mata Pelajaran", "Pendidik", "Wali Kelas", "Penyusun"],
        "NIP Guru": ["NIP Guru", "NIP Guru Mata Pelajaran", "NIP Guru Kelas", "NUPTK", "Identitas Guru", "NIP Penyusun"],
        "Nama Madrasah": ["Nama Sekolah", "Satuan Pendidikan", "Nama Madrasah", "Unit Kerja", "Instansi"],
        "Jabatan Kepala": ["Jabatan Kepala", "Istilah Jabatan", "Jabatan Pimpinan"],
        "Tahun Ajaran": ["Tahun Pelajaran", "Tahun Ajaran", "TP", "Th. Pelajaran"],
        "Semester": ["Semester", "Semester Ganjil", "Semester Genap", "Smt"],
        "Titimangsa": ["Titimangsa", "Tempat, Tanggal", "Tanggal Pengesahan", "Tanggal"],
        "Mata Pelajaran": ["Mata Pelajaran", "Mapel", "Muatan Pelajaran", "Mata Uji", "Nama Mata Pelajaran", "Bidang Studi"],
        "Fase / Kelas": ["Fase / Kelas", "Fase, Kelas / Semester", "Fase", "Kelas", "Kelas / Semester", "Tingkat Kelas", "Rombel"],
    }


from core.text_norm import normalize_string


def match_category(text: str, aliases: Optional[Dict[str, List[str]]] = None) -> Optional[str]:
    """
    Mencari kategori yang cocok untuk teks yang diberikan.
    Jika aliases tidak disediakan (atau bernilai None), menggunakan resolusi cerdas FieldDictionary.
    Jika aliases disediakan, mencocokkan dengan word boundary dan exact-only short aliases.
    """
    if aliases is None:
        try:
            from core.field_dictionary import FieldDictionary
            f_dict = FieldDictionary.load()
            return f_dict.resolve_category(text)
        except Exception as e:
            logger.debug("FieldDictionary fallback: %s", e)
            aliases = load_aliases()

    # Jalur kamus: aliases hasil to_legacy_aliases() membawa rujukan ke FieldDictionary,
    # sehingga never_match / exact_only / daftar global ikut berlaku di engine.
    resolver = getattr(aliases, "_dictionary", None)
    if resolver is not None:
        return resolver.resolve_category(text)

    clean_target = normalize_string(text)
    if not clean_target:
        return None

    # ATURAN PRIORITAS TINGGI NIP / NUPTK:
    is_nip = bool(re.search(r"\b(nip|nuptk)\b", clean_target))
    if is_nip:
        if "kepala" in clean_target or "kamad" in clean_target:
            return "NIP Kepala"
        return "NIP Guru"

    # Urutkan alias dari yang paling panjang agar lebih spesifik
    all_candidates: List[Tuple[str, str]] = []
    for cat, alias_list in aliases.items():
        if cat in ("NIP Kepala", "NIP Guru"):
            continue  # Sudah ditangani di atas
        for al in alias_list:
            all_candidates.append((cat, al))

    all_candidates.sort(key=lambda x: len(x[1]), reverse=True)

    for cat, al in all_candidates:
        clean_al = normalize_string(al)
        if not clean_al:
            continue

        # Alias pendek wajib cocok persis dengan seluruh label
        if clean_al in SHORT_EXACT_ALIASES:
            if clean_target == clean_al:
                return cat
            continue

        # Alias umum dicocokkan dengan batas kata regex (\b)
        pattern = rf"\b{re.escape(clean_al)}\b"
        if re.search(pattern, clean_target):
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
