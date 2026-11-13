"""
Unit Test: Perlindungan Anti-Blind Replacement pada Dokumen Word.
Memastikan:
1. Kolom pencarian yang murni placeholder (mis. '______________________')
   TIDAK diganti secara global tanpa label (No Blind Replacement).
2. Ketika beberapa identitas dan soal latihan memiliki placeholder yang identik,
   hanya target yang sesuai dengan label yang berubah.
3. Bagian tanpa label atau konteks tidak jelas TIDAK diganti.
"""
import os
import tempfile
import unittest
import docx

from core.placeholder_detector import is_pure_placeholder
from core.replacement_engine import ReplacementEngine


class TestAntiBlindReplacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ReplacementEngine()
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.test_doc_path = os.path.join(cls.tmpdir.name, "doc_with_shared_placeholders.docx")

        # Buat dokumen uji dengan placeholder identik pada berbagai label dan soal latihan
        doc = docx.Document()
        doc.add_heading("MODUL AJAR KURIKULUM MERDEKA", level=1)
        doc.add_paragraph("Nama Penyusun : ______________________")
        doc.add_paragraph("NIP           : ______________________")
        doc.add_paragraph("Nama Sekolah  : ______________________")
        doc.add_paragraph("Mata Pelajaran: ______________________")
        doc.add_paragraph("Tahun Ajaran  : ______________________")

        doc.add_heading("LATIHAN SISWA / ASESMEN FORMATIF", level=2)
        doc.add_paragraph("1. Sebutkan lambang sila kedua Pancasila: ______________________")
        doc.add_paragraph("2. Tuliskan nama ibukota negara Indonesia: ______________________")
        doc.save(cls.test_doc_path)

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def test_is_pure_placeholder_validation(self):
        """Memastikan fungsi is_pure_placeholder mengenali variasi placeholder."""
        self.assertTrue(is_pure_placeholder("______________________"))
        self.assertTrue(is_pure_placeholder("......................"))
        self.assertTrue(is_pure_placeholder("…"))
        self.assertTrue(is_pure_placeholder("..."))
        self.assertTrue(is_pure_placeholder("( .................... )"))
        self.assertTrue(is_pure_placeholder("[ _______ ]"))
        self.assertTrue(is_pure_placeholder("---"))
        self.assertTrue(is_pure_placeholder("-"))

        # Bukan pure placeholder (memiliki huruf/angka)
        self.assertFalse(is_pure_placeholder("2025/2026"))
        self.assertFalse(is_pure_placeholder("Tahun 20…"))
        self.assertFalse(is_pure_placeholder("SD ..................."))
        self.assertFalse(is_pure_placeholder("Nama Guru"))

    def test_anti_blind_replacement_ignores_pure_placeholder_exact_rule(self):
        """
        Jika pengguna memasukkan old='______________________' pada exact matching,
        engine DILARANG mengganti seluruh placeholder secara global.
        Hanya placeholder yang terikat label 'Tahun Ajaran' yang boleh diusulkan.
        """
        rules = [
            {
                "label": "Tahun Ajaran",
                "old": "______________________",
                "new": "2026/2027",
            }
        ]
        items = self.engine.plan_document_changes(
            self.test_doc_path, "test.docx", rules, mode="GABUNGAN"
        )

        # Harus hanya ada 1 usulan yang terikat ke kategori Tahun Ajaran
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, "Tahun Ajaran")
        self.assertEqual(items[0].old_text, "______________________")
        self.assertEqual(items[0].new_text, "2026/2027")
        self.assertEqual(items[0].target_type, "PARAGRAPH_SPAN")

    def test_execution_leaves_other_placeholders_intact(self):
        """
        Menerapkan perubahan hanya untuk Tahun Ajaran dan memastikan:
        - Nama Penyusun tetap ______________________
        - NIP tetap ______________________
        - Nama Sekolah tetap ______________________
        - Mata Pelajaran tetap ______________________
        - Soal latihan 1 & 2 tetap ______________________
        - Tahun Ajaran berubah menjadi 2026/2027
        """
        rules = [
            {
                "label": "Tahun Ajaran",
                "old": "______________________",
                "new": "2026/2027",
            }
        ]
        items = self.engine.plan_document_changes(
            self.test_doc_path, "test.docx", rules, mode="GABUNGAN"
        )
        out_path = os.path.join(self.tmpdir.name, "out_safe.docx")
        changes_count = self.engine.apply_approved_changes(self.test_doc_path, out_path, items)
        self.assertEqual(changes_count, 1)

        # Verifikasi isi dokumen yang disimpan
        doc = docx.Document(out_path)
        paras = [p.text for p in doc.paragraphs]

        # Tahun Ajaran harus berubah
        self.assertIn("Tahun Ajaran  : 2026/2027", paras)

        # Bagian lain harus TETAP memiliki placeholder aslinya
        self.assertIn("Nama Penyusun : ______________________", paras)
        self.assertIn("NIP           : ______________________", paras)
        self.assertIn("Nama Sekolah  : ______________________", paras)
        self.assertIn("Mata Pelajaran: ______________________", paras)
        self.assertIn("1. Sebutkan lambang sila kedua Pancasila: ______________________", paras)
        self.assertIn("2. Tuliskan nama ibukota negara Indonesia: ______________________", paras)


if __name__ == "__main__":
    unittest.main()
