"""
Unit test untuk modul domain Surat Dinas & Undangan Resmi (SuratDinasDomain).
Menguji deteksi Surat Dinas, ekstraksi metadata & agenda acara,
perencanaan dan penerapan perubahan dengan jaminan tanggal acara tidak tertukar tanggal surat,
serta verifikasi laporan perubahan.
"""
import unittest
import os
import shutil
import tempfile
from docx import Document

from domains.surat_dinas.surat_dinas_domain import SuratDinasDomain
from tests.fixtures.make_sample_docs import create_sample_surat_dinas
from document.paragraph_processor import get_paragraph_text
from core.change_verifier import ChangeReportGenerator


class TestSuratDinasDomain(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_surat_domain_")
        self.domain = SuratDinasDomain()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_detect_score_surat_dinas(self):
        """SuratDinasDomain harus memberikan skor deteksi tinggi (>= 0.60) pada naskah surat dinas."""
        surat_path = os.path.join(self.test_dir, "sample_surat.docx")
        create_sample_surat_dinas(surat_path)

        res = self.domain.detect_score(surat_path)
        self.assertGreaterEqual(res.score, 0.60)
        self.assertTrue(any("utama" in r.lower() or "pendukung" in r.lower() for r in res.reasons))

    def test_predict_fields_surat_dinas(self):
        """SuratDinasDomain harus mampu mengekstrak nomor surat, hal, tujuan, dan agenda acara."""
        surat_path = os.path.join(self.test_dir, "sample_surat.docx")
        create_sample_surat_dinas(surat_path)

        fields = self.domain.predict_fields(surat_path)
        self.assertEqual(fields.get("nomor_surat"), "B-025/Min.01/PP.00/07/2025")
        self.assertIn("Undangan Rapat Kerja", fields.get("hal_surat", ""))
        self.assertIn("Dewan Guru", fields.get("tujuan_surat", ""))
        self.assertEqual(fields.get("hari_tanggal_acara"), "Senin, 14 Juli 2025")
        self.assertEqual(fields.get("tempat_acara"), "Aula Pertemuan Madrasah")
        self.assertIn("Koordinasi Pembagian Tugas", fields.get("acara_kegiatan", ""))

    def test_plan_and_apply_agenda_isolated(self):
        """Merencanakan dan menerapkan perubahan metadata dan blok agenda tanpa bentrok."""
        in_dir = self.test_dir
        out_dir = os.path.join(self.test_dir, "output")
        os.makedirs(out_dir, exist_ok=True)

        surat_path = os.path.join(in_dir, "surat.docx")
        create_sample_surat_dinas(surat_path)
        out_path = os.path.join(out_dir, "surat.docx")

        rules = [
            {"label": "Nomor Surat", "old": "B-025/Min.01/PP.00/07/2025", "new": "B-088/Min.01/PP.00/11/2026"},
            {"label": "Hal / Perihal", "old": "Undangan Rapat Kerja Pembagian Tugas", "new": "Undangan Sosialisasi Kurikulum Merdeka"},
            {"label": "Hari, Tanggal Kegiatan", "old": "Senin, 14 Juli 2025", "new": "Kamis, 20 November 2026"},
            {"label": "Pukul / Waktu Kegiatan", "old": "Pukul 09.00 WIB s.d Selesai", "new": "Pukul 13.00 WIB s.d 15.30 WIB"},
            {"label": "Tempat Kegiatan", "old": "Aula Pertemuan Madrasah", "new": "Ruang Guru MIN 1 Contoh"},
        ]

        items = self.domain.plan_document_changes(surat_path, "surat.docx", rules)
        self.assertGreater(len(items), 0)

        # Pastikan domain_id tertempel
        for it in items:
            self.assertEqual(it.target_meta.get("domain_id"), "surat_dinas")

        # Terapkan perubahan
        changes_count = self.domain.apply_approved_changes(surat_path, out_path, items)
        self.assertGreater(changes_count, 0)
        self.assertTrue(os.path.exists(out_path))

        # Verifikasi isi teks hasil
        doc_out = Document(out_path)
        out_texts = [get_paragraph_text(p) for p in doc_out.paragraphs]
        full_out_text = "\n".join(out_texts)

        self.assertIn("B-088/Min.01/PP.00/11/2026", full_out_text)
        self.assertIn("Undangan Sosialisasi Kurikulum Merdeka", full_out_text)
        self.assertIn("Kamis, 20 November 2026", full_out_text)
        self.assertIn("Pukul 13.00 WIB s.d 15.30 WIB", full_out_text)
        self.assertIn("Ruang Guru MIN 1 Contoh", full_out_text)

        # Evaluasi ekstra checks: tidak ada tanggal acara yang tertukar tanggal surat
        for it in items:
            issues = self.domain.extra_checks(it, full_out_text)
            self.assertEqual(len(issues), 0)

        # Evaluasi laporan verifikasi perubahan: 0 butir SALAH
        verifier = ChangeReportGenerator()
        _, report = verifier.generate_report(out_dir, in_dir, items, rules=rules)
        self.assertEqual(report["ringkasan"]["verdict"]["SALAH"], 0)


if __name__ == "__main__":
    unittest.main()
