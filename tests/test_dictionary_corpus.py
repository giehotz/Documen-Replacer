"""
Uji korpus kamus lengkap + jalur engine (bukan hanya GUI).
Memastikan perlindungan never_match / exact_only / daftar global benar-benar berlaku
saat dokumen diproses, bukan hanya pada badge pengenalan di GUI.
"""
import os
import json
import tempfile
import unittest

from docx import Document

from core.field_dictionary import FieldDictionary, FieldDef, LegacyAliases
from core.label_recognizer import match_category
from core.similarity_matcher import find_fuzzy_category_match
from core.replacement_engine import ReplacementEngine

POSITIF = {
    "Nama Sekolah": "nama_lembaga", "Nama Madrasah": "nama_lembaga", "Satuan Pendidikan": "nama_lembaga",
    "Satuan Pendidikan/Madrasah": "nama_lembaga", "Instansi": "nama_lembaga", "Madrasah": "nama_lembaga",
    "Kepala Madrasah": "nama_kepala", "Kepala Sekolah": "nama_kepala", "Mengetahui, Kepala Madrasah": "nama_kepala",
    "Plt. Kepala Madrasah": "nama_kepala", "Nama Kepala Sekolah": "nama_kepala", "Kamad": "nama_kepala",
    "Istilah Jabatan Kepala": "jabatan_kepala",
    "NIP Kepala Sekolah": "nip_kepala", "NIP Kepala Madrasah": "nip_kepala", "NIP. Kamad": "nip_kepala",
    "Guru Kelas IV": "nama_guru", "Guru Kelas VI": "nama_guru", "Nama Guru Mata Pelajaran": "nama_guru",
    "Disusun oleh": "nama_guru", "Penyusun": "nama_guru", "Nama Penyusun": "nama_guru",
    "Pengembang Modul": "nama_guru", "Guru Penyusun": "nama_guru", "Wali Kelas": "nama_guru",
    "Pendidik": "nama_guru", "Dibuat oleh": "nama_guru",
    "NIP Guru Mata Pelajaran": "nip_guru", "NUPTK": "nip_guru", "NIP": "nip_guru", "NIP/NUPTK Guru": "nip_guru",
    "NIP Penyusun": "nip_guru", "NIY": "nip_guru",
    "Tahun Pelajaran": "tahun_pelajaran", "Tahun Ajaran": "tahun_pelajaran", "TP": "tahun_pelajaran",
    "T.P.": "tahun_pelajaran", "Thn Pelajaran": "tahun_pelajaran", "Tahun Akademik": "tahun_pelajaran",
    "Tahun Penyusunan": "tahun_penyusunan", "Tahun Pembuatan": "tahun_penyusunan", "Tahun Disusun": "tahun_penyusunan",
    "Semester": "semester", "Semester Ganjil": "semester", "Smt": "semester",
    "Titimangsa": "titimangsa", "Tempat, Tanggal": "titimangsa", "Tanggal Pengesahan": "titimangsa",
    "Tanggal": "titimangsa", "Ditetapkan di": "titimangsa", "Tempat dan Tanggal": "titimangsa",
    "(Nama Kepala Sekolah)": "nama_kepala",
    "[Nama SD/MI Anda]": "nama_lembaga",
    "[Nama Sekolah Anda]": "nama_lembaga",
    "[Tempat], [Tanggal]": "titimangsa",
    "(Guru Mata Pelajaran)": "nama_guru",
    "Mata Pelajaran": "mata_pelajaran",
    "Mapel": "mata_pelajaran",
    "Fase / Kelas": "fase_kelas",
    "Fase, Kelas / Semester": "fase_kelas",
    "Kelas": "fase_kelas",
    "Fase": "fase_kelas",
    "Kelas / Semester": "fase_kelas",
}

NEGATIF = [
    "Output", "Setup", "Tanggal Lahir Siswa", "Tempat Tanggal Lahir", "Jumlah Guru", "Alokasi Waktu", "", "....",
    "Penilaian Akhir Semester", "Program Semester",
    "Kegiatan Guru", "Kegiatan Siswa", "Nama Siswa", "Alamat Sekolah", "Wakil Kepala Madrasah", "Tenaga Pendidik",
    "Peserta Didik", "Tahun Lahir", "Tempat Tinggal", "Guru", "Tahun", "Tempat", "Kepala", "Tema",
    "Capaian Pembelajaran", "Pertemuan ke", "Ruang Kelas", "Jumlah Kelas",
]


class TestKorpusKamus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.d = FieldDictionary.load(user_path=os.path.join(cls.tmp, "none.json"))
        cls.aliases = cls.d.to_legacy_aliases()

    def test_integritas_kamus_bawaan_sehat(self):
        self.assertEqual(self.d.validate_integrity(), [])

    def test_korpus_positif_resolve(self):
        for label, fid in POSITIF.items():
            with self.subTest(label=label):
                res = self.d.resolve(label)
                self.assertIsNotNone(res.field, f"{label!r} tidak dikenali ({res.how})")
                self.assertEqual(res.field.id, fid)

    def test_korpus_negatif_resolve(self):
        for label in NEGATIF:
            with self.subTest(label=label):
                self.assertIsNone(self.d.resolve(label).field)

    def test_jalur_engine_match_category_menghormati_kamus(self):
        """Bug sebelumnya: engine memakai match_category(aliases) yang mengabaikan never_match."""
        self.assertIsInstance(self.aliases, LegacyAliases)
        for label in NEGATIF:
            with self.subTest(label=label):
                self.assertIsNone(match_category(label, self.aliases))
        for label, fid in POSITIF.items():
            with self.subTest(label=label):
                self.assertEqual(match_category(label, self.aliases), self.d.field_by_id(fid).category)

    def test_fuzzy_tidak_memakai_exact_only_dan_menghormati_never_match(self):
        cat, score, _ = find_fuzzy_category_match("Kepal Sekolah", self.aliases, threshold=0.80)
        self.assertEqual(cat, "Nama Kepala")
        self.assertGreaterEqual(score, 0.85)
        cat, _, _ = find_fuzzy_category_match("Thn Pelajaran", self.aliases, threshold=0.80)
        self.assertEqual(cat, "Tahun Ajaran")
        for label in ("Tanggal Lahir Siswa", "Ruang Kelas", "Penilaian Akhir Semester",
                      "Wakil Kepala Madrasah", "Alamat Sekolah"):
            with self.subTest(label=label):
                self.assertIsNone(find_fuzzy_category_match(label, self.aliases, threshold=0.80)[0])

    def test_koma_tidak_menghalangi_pencocokan(self):
        self.assertEqual(self.d.resolve("Tempat, Tanggal").field.id, "titimangsa")
        self.assertEqual(self.d.resolve("Tempat,Tanggal").field.id, "titimangsa")

    def test_aturan_nip_diperluas(self):
        self.assertEqual(self.d.resolve("NIY").field.id, "nip_guru")
        self.assertEqual(self.d.resolve("Nomor Induk Pegawai Kepala Madrasah").field.id, "nip_kepala")
        self.assertEqual(self.d.resolve("NIP Plt. Kepala").field.id, "nip_kepala")

    def test_skor_exact_bare(self):
        self.assertEqual(self.d.resolve("Madrasah").score, 0.85)
        self.assertEqual(self.d.resolve("Nama Madrasah").score, 1.0)

    def test_variasi_tanda_kurung_dan_placeholder(self):
        from core.placeholder_detector import is_pure_placeholder, unwrap_parentheses
        from core.signature_analyzer import is_titimangsa_line

        # 1. Pure placeholder dengan berbagai tanda kurung
        self.assertTrue(is_pure_placeholder("(__________________________)"))
        self.assertTrue(is_pure_placeholder("[__________________________]"))
        self.assertTrue(is_pure_placeholder("{__________________________}"))
        self.assertTrue(is_pure_placeholder("([__________________________])"))
        self.assertTrue(is_pure_placeholder("( .......................... )"))
        self.assertTrue(is_pure_placeholder("[ .......................... ]"))

        # 2. Titimangsa bertanda kurung atau berawalan titimangsa
        self.assertTrue(is_titimangsa_line("[Tempat], [Tanggal]"))
        self.assertTrue(is_titimangsa_line("(Tempat), (Tanggal)"))
        self.assertTrue(is_titimangsa_line("{Tempat}, {Tanggal}"))
        self.assertTrue(is_titimangsa_line("titimangsa ..........................., ................. 20..."))
        self.assertTrue(is_titimangsa_line("titimangsa : ............., .............. 20.."))
        self.assertTrue(is_titimangsa_line("..........................., ................. 20..."))

        # 3. Unwrap kurung berbagai variasi
        self.assertEqual(unwrap_parentheses("(Nama Kepala)"), ("Nama Kepala", True))
        self.assertEqual(unwrap_parentheses("[Nama Guru]"), ("Nama Guru", True))
        self.assertEqual(unwrap_parentheses("{Nama Sekolah}"), ("Nama Sekolah", True))
        self.assertEqual(unwrap_parentheses("([Nama Penyusun])"), ("Nama Penyusun", True))

    def test_validate_value_nip_nuptk_dan_strip(self):
        self.assertIsNone(self.d.validate_value("nip_guru", "-"))
        self.assertIsNone(self.d.validate_value("nip_guru", "1234567890123456"))        # NUPTK 16
        self.assertIsNone(self.d.validate_value("nip_guru", "198001012005011001"))      # NIP 18
        self.assertIsNone(self.d.validate_value("nip_guru", "19800101 200501 1 001"))
        self.assertIsNotNone(self.d.validate_value("nip_guru", "12345678901234567"))    # 17
        self.assertIsNotNone(self.d.validate_value("tahun_pelajaran", "2026/2028"))
        self.assertIsNone(self.d.validate_value("tahun_pelajaran", "2026/2027"))

    def test_ambiguous_tidak_menebak(self):
        f1 = FieldDef("a", "Kategori A", "A", "text", synonyms=["nomor registrasi"])
        f2 = FieldDef("b", "Kategori B", "B", "text", synonyms=["nomor registrasi"])
        d = FieldDictionary([f1, f2], user_path=os.path.join(self.tmp, "x.json"))
        res = d.resolve("Nomor Registrasi")
        self.assertIsNone(res.field)
        self.assertEqual(res.how, "ambiguous")

    def test_daftar_global_dimuat_dari_json(self):
        path = os.path.join(self.tmp, "mini.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "version": 2,
                "global_never_match": ["tanggal lahir"],
                "global_ignore_exact": ["catatan"],
                "fields": [{"id": "x", "category": "Titimangsa", "display_label": "X", "value_type": "date_place",
                            "synonyms": ["tanggal"], "exact_only_synonyms": []}],
            }, f)
        d = FieldDictionary.load(default_path=path, user_path=os.path.join(self.tmp, "none2.json"))
        self.assertIsNotNone(d.resolve("Tanggal Pengesahan").field)
        self.assertEqual(d.resolve("Tanggal Lahir Siswa").how, "ignored")
        self.assertEqual(d.resolve("Catatan").how, "ignored")


class TestEngineEndToEndKamus(unittest.TestCase):
    """Dokumen nyata: label berbahaya TIDAK boleh ikut diganti oleh engine."""

    def test_label_berbahaya_tidak_diganti(self):
        tmp = tempfile.mkdtemp()
        src = os.path.join(tmp, "in.docx")
        doc = Document()
        doc.add_paragraph("Kelas / Semester : VI / 1")
        doc.add_paragraph("Penilaian Akhir Semester : ......")
        doc.add_paragraph("Wakil Kepala Madrasah : ......")
        doc.add_paragraph("Tanggal Lahir Siswa : ......")
        doc.add_paragraph("Semester : ......")
        doc.add_paragraph("Nama Madrasah : ......")
        doc.save(src)

        rules = [
            {"label": "Semester", "old": "", "new": "Genap"},
            {"label": "Nama Kepala", "old": "", "new": "Budi Santoso, S.Pd"},
            {"label": "Titimangsa", "old": "", "new": "Contoh, 12 Juli 2026"},
            {"label": "Nama Madrasah", "old": "", "new": "MIN Contoh"},
        ]
        eng = ReplacementEngine(field_dictionary=FieldDictionary.load(user_path=os.path.join(tmp, "n.json")))
        out = os.path.join(tmp, "out.docx")
        eng.process_file(src, out, rules, mode="GABUNGAN")
        text = [p.text for p in Document(out).paragraphs]

        self.assertEqual(text[0], "Kelas / Semester : VI / 1")
        self.assertEqual(text[1], "Penilaian Akhir Semester : ......")
        self.assertEqual(text[2], "Wakil Kepala Madrasah : ......")
        self.assertEqual(text[3], "Tanggal Lahir Siswa : ......")
        self.assertIn("Genap", text[4])
        self.assertIn("MIN Contoh", text[5])


if __name__ == "__main__":
    unittest.main()
