"""
Modul Kamus Field Terstruktur (Field Dictionary).
Menyediakan pengelolaan definisi field, pencocokan label cerdas berbasis batas kata
(word-boundary), proteksi kata negatif (never_match), sinonim kustom pengguna,
serta validasi nilai lunak (soft validation).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
import os
import sys
import re
import json
import logging

from core.label_recognizer import normalize_string

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FieldDef:
    """Definisi skema field data dokumen."""
    id: str
    category: str
    display_label: str
    value_type: str  # text | person_name | nip | year_single | year_range | date_place | semester | role_title
    match_mode: str = "word_boundary"
    priority: int = 50
    synonyms: List[str] = field(default_factory=list)
    exact_only_synonyms: List[str] = field(default_factory=list)
    never_match: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class MatchResult:
    """Hasil pencocokan label input terhadap definisi field kamus."""
    field: Optional[FieldDef]
    score: float  # 1.0 untuk cocok pasti, 0.0 jika tidak ditemukan
    how: str      # "exact" | "word_boundary" | "nip_rule" | "fuzzy" | "none"
    matched_synonym: str = ""


class FieldDictionary:
    """
    Manajer kamus field dokumen.
    Menggabungkan kamus bawaan (dictionary.default.json) dengan sinonim kustom pengguna (dictionary.user.json).
    """
    def __init__(
        self,
        fields_list: List[FieldDef],
        default_path: str = "",
        user_path: str = "",
        user_synonyms: Optional[Dict[str, List[str]]] = None
    ):
        self._fields: List[FieldDef] = fields_list
        self._fields_by_id: Dict[str, FieldDef] = {f.id: f for f in fields_list}
        self.default_path = default_path
        self.user_path = user_path
        self._user_synonyms: Dict[str, List[str]] = user_synonyms or {}

    @classmethod
    def get_default_user_path(cls) -> str:
        """Menentukan lokasi penyimpanan berkas kamus kustom pengguna."""
        override = os.environ.get("SMART_RPP_USER_DIR", "").strip()
        if override:
            return os.path.join(override, "dictionary.user.json")

        if sys.platform == "win32":
            app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
            user_dir = os.path.join(app_data, "SmartRPPReplacer")
        else:
            user_dir = os.path.join(os.path.expanduser("~"), ".config", "SmartRPPReplacer")

        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, "dictionary.user.json")

    @classmethod
    def load(cls, default_path: str = "", user_path: str = "") -> "FieldDictionary":
        """
        Memuat kamus bawaan dan menggabungkannya dengan kamus pengguna.
        Toleran terhadap berkas pengguna yang rusak/korup (fallback aman ke kamus bawaan).
        """
        if not default_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            default_path = os.path.join(base_dir, "config", "dictionary.default.json")

        fields_list: List[FieldDef] = []
        if os.path.isfile(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("fields", []):
                        f_def = FieldDef(
                            id=item["id"],
                            category=item["category"],
                            display_label=item.get("display_label", item["category"]),
                            value_type=item.get("value_type", "text"),
                            match_mode=item.get("match_mode", "word_boundary"),
                            priority=int(item.get("priority", 50)),
                            synonyms=[s.strip() for s in item.get("synonyms", []) if s.strip()],
                            exact_only_synonyms=[s.strip() for s in item.get("exact_only_synonyms", []) if s.strip()],
                            never_match=[s.strip() for s in item.get("never_match", []) if s.strip()],
                        )
                        fields_list.append(f_def)
            except Exception as e:
                logger.error("Gagal membaca kamus bawaan %s: %s", default_path, e)

        if not fields_list:
            # Fallback bawaan darurat jika berkas json tidak ada
            fields_list = [
                FieldDef("nama_lembaga", "Nama Madrasah", "Nama Sekolah/Madrasah", "text", synonyms=["nama sekolah", "nama madrasah", "satuan pendidikan"]),
                FieldDef("nama_kepala", "Nama Kepala", "Nama Kepala Madrasah", "person_name", synonyms=["kepala sekolah", "kepala madrasah", "nama kepala"]),
                FieldDef("nip_kepala", "NIP Kepala", "NIP Kepala Madrasah", "nip", priority=60, synonyms=["nip kepala", "nip kepala sekolah", "nip kepala madrasah"]),
                FieldDef("nama_guru", "Nama Guru", "Nama Guru Penyusun", "person_name", synonyms=["nama penyusun", "guru penyusun", "nama guru", "guru kelas"]),
                FieldDef("nip_guru", "NIP Guru", "NIP / NUPTK Guru", "nip", priority=60, synonyms=["nip guru", "nuptk", "nip penyusun"]),
                FieldDef("jabatan_kepala", "Jabatan Kepala", "Istilah Jabatan Kepala", "role_title", synonyms=["jabatan kepala", "istilah jabatan"]),
                FieldDef("tahun_pelajaran", "Tahun Ajaran", "Tahun Pelajaran", "year_range", synonyms=["tahun pelajaran", "tahun ajaran"], exact_only_synonyms=["tp"], never_match=["output"]),
                FieldDef("tahun_penyusunan", "Tahun Penyusunan", "Tahun Penyusunan", "year_single", synonyms=["tahun penyusunan", "tahun pembuatan"]),
                FieldDef("semester", "Semester", "Semester", "semester", synonyms=["semester", "semester ganjil", "semester genap"], exact_only_synonyms=["smt"]),
                FieldDef("titimangsa", "Titimangsa", "Titimangsa (Tempat, Tgl)", "date_place", synonyms=["titimangsa", "tempat, tanggal", "tanggal pengesahan"], exact_only_synonyms=["tanggal"], never_match=["tanggal lahir"]),
            ]

        # Muat kamus pengguna jika ada
        if not user_path:
            user_path = cls.get_default_user_path()

        user_synonyms: Dict[str, List[str]] = {}
        if os.path.isfile(user_path):
            try:
                with open(user_path, "r", encoding="utf-8") as f:
                    u_data = json.load(f)
                    user_synonyms = u_data.get("user_synonyms", {})
            except Exception as e:
                logger.warning("Kamus pengguna %s rusak atau tidak valid: %s. Menggunakan kamus bawaan.", user_path, e)

        return cls(fields_list, default_path=default_path, user_path=user_path, user_synonyms=user_synonyms)

    def fields(self) -> List[FieldDef]:
        """Mengembalikan seluruh daftar field yang terdaftar."""
        return list(self._fields)

    def field_by_id(self, field_id: str) -> Optional[FieldDef]:
        """Mencari definisi field berdasarkan id."""
        return self._fields_by_id.get(field_id)

    def get_all_synonyms_for_field(self, field_id: str) -> List[str]:
        """Mengembalikan kombinasi sinonim bawaan dan sinonim kustom pengguna."""
        f_def = self.field_by_id(field_id)
        if not f_def:
            return []
        user_list = self._user_synonyms.get(field_id, [])
        combined = list(f_def.synonyms)
        for s in user_list:
            if s not in combined:
                combined.append(s)
        return combined

    def get_user_synonyms_for_field(self, field_id: str) -> List[str]:
        """Mengembalikan daftar sinonim kustom pengguna untuk field tertentu."""
        return list(self._user_synonyms.get(field_id, []))

    def resolve(self, label: str) -> MatchResult:
        """
        Mencocokkan teks label terhadap kamus field secara deterministik.
        Urutan prioritas:
        1. Normalisasi teks
        2. Aturan khusus NIP / NUPTK
        3. Pemeriksaan exact_only_synonyms
        4. Pemeriksaan never_match & word_boundary matching
        """
        clean_target = normalize_string(label)
        if not clean_target:
            return MatchResult(None, 0.0, "none", "")

        # 1. Aturan Prioritas Khusus NIP / NUPTK
        is_nip = bool(re.search(r"\b(nip|nuptk)\b", clean_target))
        if is_nip:
            if "kepala" in clean_target or "kamad" in clean_target:
                return MatchResult(self.field_by_id("nip_kepala"), 1.0, "nip_rule", "nip kepala")
            return MatchResult(self.field_by_id("nip_guru"), 1.0, "nip_rule", "nip guru")

        # 2. Pemeriksaan Exact-Only Synonyms
        for f_def in self._fields:
            # Cek never match untuk field ini
            if self._matches_never_match(clean_target, f_def.never_match):
                continue

            for ex_syn in f_def.exact_only_synonyms:
                clean_ex = normalize_string(ex_syn)
                if clean_target == clean_ex:
                    return MatchResult(f_def, 1.0, "exact", ex_syn)

        # 3. Kumpulkan seluruh sinonim umum (bawaan + pengguna) untuk word-boundary matching
        matched_candidates: List[Tuple[FieldDef, str, int]] = []
        for f_def in self._fields:
            if self._matches_never_match(clean_target, f_def.never_match):
                continue

            all_syns = self.get_all_synonyms_for_field(f_def.id)
            for syn in all_syns:
                clean_syn = normalize_string(syn)
                if not clean_syn:
                    continue
                pattern = rf"\b{re.escape(clean_syn)}\b"
                if re.search(pattern, clean_target):
                    matched_candidates.append((f_def, syn, len(clean_syn)))

        if matched_candidates:
            # Urutkan berdasarkan: panjang kecocokan terpanjang, lalu prioritas field tertinggi
            matched_candidates.sort(key=lambda x: (x[2], x[0].priority), reverse=True)
            best_field, best_syn, _ = matched_candidates[0]
            return MatchResult(best_field, 1.0, "word_boundary", best_syn)

        return MatchResult(None, 0.0, "none", "")

    def _matches_never_match(self, clean_target: str, never_match_list: List[str]) -> bool:
        """Memeriksa apakah target mengandung frasa negatif yang dilarang untuk field ini."""
        for nm in never_match_list:
            clean_nm = normalize_string(nm)
            if clean_nm and re.search(rf"\b{re.escape(clean_nm)}\b", clean_target):
                return True
        return False

    def resolve_category(self, label: str) -> Optional[str]:
        """Helper kompatibel yang mengembalikan string kategori engine (contoh: 'Nama Kepala')."""
        res = self.resolve(label)
        if res.field:
            return res.field.category
        return None

    def add_user_synonym(self, field_id: str, synonym: str) -> None:
        """
        Menambahkan sinonim kustom pengguna ke field terpilih.
        Memvalidasi agar tidak ada benturan sinonim duplikat lintas field.
        """
        clean_s = normalize_string(synonym)
        if not clean_s:
            raise ValueError("Sinonim tidak boleh kosong.")

        target_field = self.field_by_id(field_id)
        if not target_field:
            raise ValueError(f"Field dengan id '{field_id}' tidak ditemukan.")

        # Cek kepemilikan di seluruh field (bawaan & user)
        for f in self._fields:
            # Cek di exact_only
            for es in f.exact_only_synonyms:
                if normalize_string(es) == clean_s:
                    raise ValueError(f"Sinonim '{synonym}' sudah menjadi istilah eksklusif pada '{f.display_label}'.")
            # Cek di sinonim umum
            all_s = self.get_all_synonyms_for_field(f.id)
            for s in all_s:
                if normalize_string(s) == clean_s:
                    if f.id == field_id:
                        return  # Sudah ada di field yang sama, tidak perlu diduplikasi
                    raise ValueError(f"Sinonim '{synonym}' sudah dimiliki oleh field '{f.display_label}'.")

        self._user_synonyms.setdefault(field_id, [])
        if synonym.strip() not in self._user_synonyms[field_id]:
            self._user_synonyms[field_id].append(synonym.strip())

    def remove_user_synonym(self, field_id: str, synonym: str) -> bool:
        """Menghapus sinonim pengguna dari field tertentu."""
        clean_s = synonym.strip()
        user_list = self._user_synonyms.get(field_id, [])
        if clean_s in user_list:
            user_list.remove(clean_s)
            return True
        return False

    def save_user(self) -> None:
        """Menyimpan seluruh sinonim kustom pengguna ke berkas JSON pengguna."""
        if not self.user_path:
            self.user_path = self.get_default_user_path()

        os.makedirs(os.path.dirname(self.user_path), exist_ok=True)
        payload = {
            "version": 2,
            "user_synonyms": self._user_synonyms
        }
        with open(self.user_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("Kamus pengguna berhasil disimpan ke %s", self.user_path)

    def to_legacy_aliases(self) -> Dict[str, List[str]]:
        """
        Menghasilkan kamus aliases datar yang kompatibel dengan format lama
        Dict[category, List[synonym]] untuk digunakan oleh similarity_matcher dan test legacy.
        """
        legacy: Dict[str, List[str]] = {}
        for f_def in self._fields:
            cat = f_def.category
            legacy.setdefault(cat, [])
            all_s = self.get_all_synonyms_for_field(f_def.id)
            for s in all_s:
                if s not in legacy[cat]:
                    legacy[cat].append(s)
            for es in f_def.exact_only_synonyms:
                if es not in legacy[cat]:
                    legacy[cat].append(es)
        return legacy

    def validate_value(self, field_id: str, value: str) -> Optional[str]:
        """
        Melakukan validasi lunak (soft validation) terhadap format teks baru.
        Mengembalikan None jika valid atau string peringatan jika format meragukan.
        """
        val = value.strip()
        if not val:
            return None

        f_def = self.field_by_id(field_id)
        if not f_def:
            return None

        v_type = f_def.value_type

        # 1. Validasi NIP (18 digit angka)
        if v_type == "nip":
            digits_only = re.sub(r"\D", "", val)
            if digits_only and len(digits_only) != 18:
                return f"NIP biasanya terdiri dari 18 digit angka (terdeteksi {len(digits_only)} digit)."

        # 2. Validasi Tahun Pelajaran (year_range: 2025/2026 atau 20.. /20..)
        elif v_type == "year_range":
            if not re.search(r"20(?:\d{2}|\.\.)\s*[/–-]\s*20(?:\d{2}|\.\.)", val):
                return "Tahun Pelajaran sebaiknya berupa rentang dua tahun (contoh: 2026/2027)."

        # 3. Validasi Tahun Tunggal (year_single: 2026)
        elif v_type == "year_single":
            if not re.match(r"^20\d{2}$", val):
                return "Tahun Penyusunan sebaiknya berupa 4 digit tahun (contoh: 2026)."

        # 4. Validasi Semester
        elif v_type == "semester":
            clean_s = val.lower()
            valid_sem = {"ganjil", "genap", "1", "2", "i", "ii"}
            if clean_s not in valid_sem:
                return "Semester biasanya diisi 'Ganjil', 'Genap', '1', atau '2'."

        # 5. Validasi Titimangsa
        elif v_type == "date_place":
            has_comma = "," in val
            has_year = bool(re.search(r"20(?:\d{2}|\.\.)", val))
            if not (has_comma and has_year):
                return "Titimangsa sebaiknya memuat kota dan tanggal (contoh: Jakarta, 15 Juli 2026)."

        return None
