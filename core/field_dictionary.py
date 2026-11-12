"""
Modul Kamus Field Terstruktur (Field Dictionary).
Menyediakan pengelolaan definisi field, pencocokan label cerdas berbasis batas kata
(word-boundary), proteksi kata negatif (never_match), sinonim kustom pengguna,
serta validasi nilai lunak (soft validation).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import os
import sys
import re
import json
import logging

from core.label_recognizer import normalize_string

logger = logging.getLogger(__name__)

DEFAULT_NIP_TOKENS = ("nip", "nipy", "niy", "nuptk", "nomor induk pegawai", "nomor induk yayasan")
DEFAULT_KEPALA_CONTEXT = ("kepala", "kamad", "kepsek", "pimpinan", "plt", "plh", "pjs", "mengetahui", "menyetujui")


def _norm(text: str) -> str:
    """
    Normalisasi khusus kamus: seperti normalize_string() tetapi koma, titik koma, tanda kurung
    bulat (), kurung siku [], kurung kurawal {}, dan backslash juga dibuang menjadi spasi.
    """
    t = normalize_string(text or "")
    t = re.sub(r"[,;()\[\]{}\\]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _wb(phrase: str, text: str) -> bool:
    """True bila frasa muncul sebagai kata utuh (berbatas-kata) di dalam teks."""
    return bool(phrase) and re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


class LegacyAliases(dict):
    """
    Dict[kategori, List[sinonim]] kompatibel format lama, yang MEMBAWA rujukan ke FieldDictionary asalnya.
    match_category() dan find_fuzzy_category_match() memakai rujukan ini agar never_match,
    exact_only_synonyms, dan daftar global ikut berlaku pada jalur engine (bukan hanya di GUI).
    """
    _dictionary: Optional["FieldDictionary"] = None


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
        user_synonyms: Optional[Dict[str, List[str]]] = None,
        nip_tokens: Optional[List[str]] = None,
        nip_kepala_context: Optional[List[str]] = None,
        global_never_match: Optional[List[str]] = None,
        global_ignore_exact: Optional[List[str]] = None,
    ):
        self._nip_tokens: List[str] = [_norm(x) for x in (nip_tokens or DEFAULT_NIP_TOKENS) if _norm(x)]
        self._nip_kepala_context: List[str] = [_norm(x) for x in (nip_kepala_context or DEFAULT_KEPALA_CONTEXT) if _norm(x)]
        self._global_never_match: List[str] = [_norm(x) for x in (global_never_match or []) if _norm(x)]
        self._global_ignore_exact: List[str] = [_norm(x) for x in (global_ignore_exact or []) if _norm(x)]
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
        root_cfg: Dict[str, Any] = {}
        if os.path.isfile(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    root_cfg = data if isinstance(data, dict) else {}
                    if root_cfg.get("version") not in (None, 2):
                        logger.warning("Versi skema kamus %r tidak dikenal (diharapkan 2).", root_cfg.get("version"))
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

        nip_cfg = root_cfg.get("nip_rule") or {}
        return cls(
            fields_list,
            default_path=default_path,
            user_path=user_path,
            user_synonyms=user_synonyms,
            nip_tokens=nip_cfg.get("tokens"),
            nip_kepala_context=nip_cfg.get("kepala_context"),
            global_never_match=root_cfg.get("global_never_match"),
            global_ignore_exact=root_cfg.get("global_ignore_exact"),
        )

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

    def _is_globally_ignored(self, clean_target: str) -> bool:
        if clean_target in self._global_ignore_exact:
            return True
        return any(_wb(p, clean_target) for p in self._global_never_match)

    def is_blocked_for_category(self, label: str, category: str, for_fuzzy: bool = False) -> bool:
        """
        True bila label dilarang cocok ke kategori ini (daftar global atau never_match field-nya).
        for_fuzzy=True: kategori bertipe nip juga diblokir, karena NIP/NUPTK hanya boleh dikenali lewat
        aturan NIP (token eksplisit). Tanpa ini 'Wakil Kepala Madrasah' mirip dengan alias 'NIP Kepala Madrasah'.
        """
        clean = _norm(label)
        if self._is_globally_ignored(clean):
            return True
        if for_fuzzy and any(f.category == category and f.value_type == "nip" for f in self._fields):
            return True
        return any(
            f.category == category and self._matches_never_match(clean, f.never_match)
            for f in self._fields
        )

    def resolve(self, label: str) -> MatchResult:
        """
        Mencocokkan teks label terhadap kamus field secara deterministik. Urutan:
        1. Normalisasi (koma ikut dibuang); label kosong/placeholder -> none
        2. global_ignore_exact dan global_never_match -> ignored
        3. Aturan NIP (nip, nipy, niy, nuptk, nomor induk ...) -> nip_kepala / nip_guru
        4. Per field: lewati bila never_match cocok; kandidat dari exact_only (label sama persis)
           dan synonyms (berbatas-kata). Pemenang: label-sama-persis > sinonim terpanjang > priority
        5. Dua field berbeda seri -> ambiguous (field=None, tidak menebak)
        """
        clean_target = _norm(label)
        if not clean_target or not re.search(r"[a-z0-9]", clean_target):
            return MatchResult(None, 0.0, "none", "")

        if self._is_globally_ignored(clean_target):
            return MatchResult(None, 0.0, "ignored", "")

        for tok in self._nip_tokens:
            if _wb(tok, clean_target):
                is_kepala = any(_wb(k, clean_target) for k in self._nip_kepala_context)
                f_nip = self.field_by_id("nip_kepala" if is_kepala else "nip_guru")
                if f_nip is not None:
                    return MatchResult(f_nip, 1.0, "nip_rule", tok)
                break

        cands: List[Tuple[Tuple[int, int, int], FieldDef, str, str]] = []
        for f_def in self._fields:
            if self._matches_never_match(clean_target, f_def.never_match):
                continue
            for ex in f_def.exact_only_synonyms:
                if _norm(ex) == clean_target:
                    how = "exact" if " " in clean_target else "exact_bare"
                    cands.append(((2, len(clean_target), f_def.priority), f_def, ex, how))
            for syn in self.get_all_synonyms_for_field(f_def.id):
                cs = _norm(syn)
                if cs and _wb(cs, clean_target):
                    whole = cs == clean_target
                    cands.append(((2 if whole else 1, len(cs), f_def.priority), f_def, syn,
                                  "exact" if whole else "word_boundary"))

        if not cands:
            return MatchResult(None, 0.0, "none", "")

        cands.sort(key=lambda c: c[0], reverse=True)
        top_key, top_field, top_syn, top_how = cands[0]
        rivals = [c for c in cands[1:] if c[0] == top_key and c[1].id != top_field.id]
        if rivals:
            names = "+".join([top_field.id] + [r[1].id for r in rivals])
            return MatchResult(None, 0.0, "ambiguous", names)
        score = 0.85 if top_how == "exact_bare" else 1.0
        return MatchResult(top_field, score, top_how, top_syn)

    def _matches_never_match(self, clean_target: str, never_match_list: List[str]) -> bool:
        """Memeriksa apakah target mengandung frasa negatif (berbatas-kata) yang dilarang untuk field ini."""
        return any(_wb(_norm(nm), clean_target) for nm in never_match_list if _norm(nm))

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
        clean_s = _norm(synonym)
        if not clean_s:
            raise ValueError("Sinonim tidak boleh kosong.")

        target_field = self.field_by_id(field_id)
        if not target_field:
            raise ValueError(f"Field dengan id '{field_id}' tidak ditemukan.")

        # Cek kepemilikan di seluruh field (bawaan & user)
        for f in self._fields:
            # Cek di exact_only
            for es in f.exact_only_synonyms:
                if _norm(es) == clean_s:
                    raise ValueError(f"Sinonim '{synonym}' sudah menjadi istilah eksklusif pada '{f.display_label}'.")
            # Cek di sinonim umum
            all_s = self.get_all_synonyms_for_field(f.id)
            for s in all_s:
                if _norm(s) == clean_s:
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
        Kamus datar Dict[kategori, List[sinonim]] untuk kode lama dan fuzzy-match.
        HANYA berisi `synonyms` (bukan exact_only_synonyms): kata tunggal seperti 'sekolah' membuat
        fuzzy salah mengenali 'Kepal Sekolah' sebagai Nama Madrasah. Hasilnya LegacyAliases yang
        membawa rujukan ke kamus ini sehingga aturan never_match tetap berlaku di jalur engine.
        """
        legacy = LegacyAliases()
        legacy._dictionary = self
        for f_def in self._fields:
            lst = legacy.setdefault(f_def.category, [])
            for s in self.get_all_synonyms_for_field(f_def.id):
                if s not in lst:
                    lst.append(s)
        return legacy

    def validate_integrity(self) -> List[str]:
        """Memeriksa kesehatan kamus. Mengembalikan daftar masalah (kosong = sehat)."""
        problems: List[str] = []
        owner: Dict[str, str] = {}
        for f in self._fields:
            for s in list(f.synonyms) + list(f.exact_only_synonyms):
                cs = _norm(s)
                if cs != s:
                    problems.append(f"[{f.id}] istilah belum ternormalisasi: {s!r} (seharusnya {cs!r})")
                if cs in owner and owner[cs] != f.id:
                    problems.append(f"duplikat lintas field: {cs!r} dimiliki {owner[cs]} dan {f.id}")
                owner.setdefault(cs, f.id)
                for p in self._global_never_match:
                    if _wb(p, cs):
                        problems.append(f"[{f.id}] sinonim {cs!r} memuat frasa global_never_match {p!r}")
            both = {_norm(x) for x in f.synonyms} & {_norm(x) for x in f.exact_only_synonyms}
            if both:
                problems.append(f"[{f.id}] tumpang tindih synonyms/exact_only: {sorted(both)}")
        return problems

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

        # 1. Validasi NIP: '-' (non-NIP), 16 digit (NUPTK), atau 18 digit (NIP PNS)
        if v_type == "nip":
            if val in {"-", "\u2013", "\u2014"}:
                return None
            digits_only = re.sub(r"\D", "", val)
            if digits_only and len(digits_only) not in (16, 18):
                return (f"NIP biasanya 18 digit (PNS) atau NUPTK 16 digit "
                        f"(terdeteksi {len(digits_only)} digit).")

        # 2. Validasi Tahun Pelajaran (year_range: 2025/2026 atau 20.. /20..)
        elif v_type == "year_range":
            if not re.search(r"20(?:\d{2}|\.\.)\s*[/–-]\s*20(?:\d{2}|\.\.)", val):
                return "Tahun Pelajaran sebaiknya berupa rentang dua tahun (contoh: 2026/2027)."
            m_yr = re.search(r"(20\d{2})\s*[/\u2013-]\s*(20\d{2})", val)
            if m_yr and int(m_yr.group(2)) != int(m_yr.group(1)) + 1:
                return "Tahun Pelajaran biasanya dua tahun berurutan (contoh: 2026/2027)."

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
