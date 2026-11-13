"""
Unit test untuk 7 kasus penggantian pola tahun (Golden Test Cases)
sesuai tabel bagian 1 dokumen RANCANGAN_OUTPUT_LAPORAN_PERUBAHAN.md.
"""
import unittest
import os
import tempfile
import shutil
from docx import Document

from core.replacement_engine import ReplacementEngine
from core.placeholder_detector import extract_label_and_placeholder, extract_filled_value_span


class TestYearReplacementGoldenCases(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.engine = ReplacementEngine()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_doc(self, text_line: str) -> str:
        doc = Document()
        doc.add_paragraph("KEMENTERIAN AGAMA REPUBLIK INDONESIA")
        doc.add_paragraph(text_line)
        doc.add_paragraph("Mengetahui, Kepala Madrasah")
        path = os.path.join(self.temp_dir, f"test_{abs(hash(text_line))}.docx")
        doc.save(path)
        return path

    def test_case_1_dots_with_prefix_20(self):
        """Kasus 1: '20.... / 20....' dengan 'Cari teks ini' kosong -> '2026/2027'."""
        in_p = self._create_sample_doc("Tahun Pelajaran : 20.... / 20....")
        out_p = os.path.join(self.temp_dir, "out_1.docx")
        rules = [{"label": "Tahun Pelajaran", "old": "", "new": "2026/2027"}]

        changes = self.engine.process_file(in_p, out_p, rules, mode="GABUNGAN")
        self.assertGreaterEqual(changes, 1)

        doc_out = Document(out_p)
        txt = doc_out.paragraphs[1].text
        self.assertEqual(txt, "Tahun Pelajaran : 2026/2027")
        self.assertNotIn("202026", txt)
        self.assertNotIn("20....", txt)

    def test_case_2_two_dots_with_prefix_20(self):
        """Kasus 2: '20.. / 20..' (2 titik) dengan 'Cari teks ini' kosong -> '2026/2027'."""
        in_p = self._create_sample_doc("Tahun Pelajaran : 20.. / 20..")
        out_p = os.path.join(self.temp_dir, "out_2.docx")
        rules = [{"label": "Tahun Pelajaran", "old": "", "new": "2026/2027"}]

        changes = self.engine.process_file(in_p, out_p, rules, mode="GABUNGAN")
        self.assertGreaterEqual(changes, 1)

        doc_out = Document(out_p)
        txt = doc_out.paragraphs[1].text
        self.assertEqual(txt, "Tahun Pelajaran : 2026/2027")

    def test_case_3_no_space_slash(self):
        """Kasus 3: '20..../20....' (tanpa spasi di garis miring) -> '2026/2027'."""
        in_p = self._create_sample_doc("Tahun Pelajaran : 20..../20....")
        out_p = os.path.join(self.temp_dir, "out_3.docx")
        rules = [{"label": "Tahun Pelajaran", "old": "", "new": "2026/2027"}]

        changes = self.engine.process_file(in_p, out_p, rules, mode="GABUNGAN")
        self.assertGreaterEqual(changes, 1)

        doc_out = Document(out_p)
        txt = doc_out.paragraphs[1].text
        self.assertEqual(txt, "Tahun Pelajaran : 2026/2027")

    def test_case_4_single_year_placeholder(self):
        """Kasus 4: '20...' (tahun tunggal) -> '2026/2027'."""
        in_p = self._create_sample_doc("Tahun Pelajaran : 20...")
        out_p = os.path.join(self.temp_dir, "out_4.docx")
        rules = [{"label": "Tahun Pelajaran", "old": "", "new": "2026/2027"}]

        changes = self.engine.process_file(in_p, out_p, rules, mode="GABUNGAN")
        self.assertGreaterEqual(changes, 1)

        doc_out = Document(out_p)
        txt = doc_out.paragraphs[1].text
        self.assertEqual(txt, "Tahun Pelajaran : 2026/2027")

    def test_case_5_filled_existing_year(self):
        """Kasus 5: '2025/2026' (sudah terisi) diperbarui ke '2026/2027'."""
        in_p = self._create_sample_doc("Tahun Pelajaran : 2025/2026")
        out_p = os.path.join(self.temp_dir, "out_5.docx")
        rules = [{"label": "Tahun Pelajaran", "old": "", "new": "2026/2027"}]

        changes = self.engine.process_file(in_p, out_p, rules, mode="GABUNGAN")
        self.assertGreaterEqual(changes, 1)

        doc_out = Document(out_p)
        txt = doc_out.paragraphs[1].text
        self.assertEqual(txt, "Tahun Pelajaran : 2026/2027")

    def test_case_6_explicit_full_old_text(self):
        """Kasus 6: '20.... / 20....' dengan 'Cari teks ini' = '20.... / 20....' -> '2026/2027'."""
        in_p = self._create_sample_doc("Tahun Pelajaran : 20.... / 20....")
        out_p = os.path.join(self.temp_dir, "out_6.docx")
        rules = [{"label": "Tahun Pelajaran", "old": "20.... / 20....", "new": "2026/2027"}]

        changes = self.engine.process_file(in_p, out_p, rules, mode="GABUNGAN")
        self.assertGreaterEqual(changes, 1)

        doc_out = Document(out_p)
        txt = doc_out.paragraphs[1].text
        # Tidak boleh terjadi dobel penimpaan seperti 202026/2027027
        self.assertEqual(txt, "Tahun Pelajaran : 2026/2027")
        self.assertNotIn("027", txt.replace("2027", ""))

    def test_case_7_explicit_partial_old_text(self):
        """Kasus 7: '20.... / 20....' dengan 'Cari teks ini' = '20....' -> '2026'."""
        in_p = self._create_sample_doc("Tahun Pelajaran : 20.... / 20....")
        out_p = os.path.join(self.temp_dir, "out_7.docx")
        rules = [{"label": "Tahun Pelajaran", "old": "20....", "new": "2026"}]

        changes = self.engine.process_file(in_p, out_p, rules, mode="GABUNGAN")
        self.assertGreaterEqual(changes, 1)

        doc_out = Document(out_p)
        txt = doc_out.paragraphs[1].text
        self.assertEqual(txt, "Tahun Pelajaran : 2026 / 2026")


if __name__ == "__main__":
    unittest.main()
