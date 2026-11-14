"""
Unit test untuk modul domain Berita Acara & MOU (BeritaAcaraDomain).
Menguji deteksi Berita Acara, isolasi ketat PIHAK KESATU vs PIHAK KEDUA (agar tidak tertukar),
dan konversi otomatis tanggal pembuka ke kalimat terbilang.
"""
import unittest
import os
import shutil
import tempfile
from docx import Document

from domains.berita_acara.berita_acara_domain import BeritaAcaraDomain
from tests.fixtures.make_sample_docs import create_sample_berita_acara
from document.paragraph_processor import get_paragraph_text
from core.change_verifier import ChangeReportGenerator


class TestBeritaAcaraDomain(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_ba_domain_")
        self.domain = BeritaAcaraDomain()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_detect_score_ba(self):
        """BeritaAcaraDomain harus memberikan skor deteksi tinggi (>= 0.60) pada naskah Berita Acara."""
        ba_path = os.path.join(self.test_dir, "sample_ba.docx")
        create_sample_berita_acara(ba_path)

        res = self.domain.detect_score(ba_path)
        self.assertGreaterEqual(res.score, 0.60)
        self.assertTrue(any("utama" in r.lower() or "pendukung" in r.lower() for r in res.reasons))

    def test_predict_fields_ba(self):
        """BeritaAcaraDomain harus mampu mengekstrak nomor BA, tanggal terbilang, pihak kesatu, dan pihak kedua."""
        ba_path = os.path.join(self.test_dir, "sample_ba.docx")
        create_sample_berita_acara(ba_path)

        fields = self.domain.predict_fields(ba_path)
        self.assertEqual(fields.get("nomor_ba"), "001/BA-STJ/2025")
        self.assertEqual(fields.get("tanggal_ba"), "15-07-2025")
        self.assertEqual(fields.get("nama_pihak_kesatu"), "Budi Santoso, M.Pd")
        self.assertEqual(fields.get("nama_pihak_kedua"), "Ahmad Dahlan, M.Pd")

    def test_pihak_kesatu_dan_kedua_tidak_tertukar(self):
        """Atribut Nama Pihak Kesatu dan Pihak Kedua tidak boleh tertukar atau saling menimpa."""
        in_dir = self.test_dir
        out_dir = os.path.join(self.test_dir, "output")
        os.makedirs(out_dir, exist_ok=True)

        ba_path = os.path.join(in_dir, "ba.docx")
        create_sample_berita_acara(ba_path)
        out_path = os.path.join(out_dir, "ba.docx")

        rules = [
            {"label": "Nomor Berita Acara", "old": "001/BA-STJ/2025", "new": "005/BA-STJ/2026"},
            {"label": "Tanggal Berita Acara", "old": "15-07-2025", "new": "2026-11-20"},
            {"label": "Nama Pihak Kesatu", "old": "Budi Santoso, M.Pd", "new": "Drs. H. Mulyadi, M.Pd"},
            {"label": "Nama Pihak Kedua", "old": "Ahmad Dahlan, M.Pd", "new": "Zulkifli, S.Ag, M.Pd.I"},
        ]

        items = self.domain.plan_document_changes(ba_path, "ba.docx", rules)
        self.assertGreater(len(items), 0)

        # Pastikan domain_id tertempel
        for it in items:
            self.assertEqual(it.target_meta.get("domain_id"), "berita_acara")

        # Terapkan perubahan
        changes_count = self.domain.apply_approved_changes(ba_path, out_path, items)
        self.assertGreater(changes_count, 0)
        self.assertTrue(os.path.exists(out_path))

        # Verifikasi isi naskah hasil
        doc_out = Document(out_path)
        out_texts = [get_paragraph_text(p) for p in doc_out.paragraphs]
        full_out_text = "\n".join(out_texts)

        # Pastikan tanggal terbilang baru terpasang
        self.assertIn("Jumat tanggal Dua Puluh bulan November tahun Dua Ribu Dua Puluh Enam (20-11-2026)", full_out_text)

        # Pastikan Pihak Kesatu dan Kedua terpasang pada baris masing-masing
        self.assertIn("PIHAK KESATU: Drs. H. Mulyadi, M.Pd", full_out_text)
        self.assertIn("PIHAK KEDUA: Zulkifli, S.Ag, M.Pd.I", full_out_text)

        # Pastikan nama lama tidak tersisa
        self.assertNotIn("Budi Santoso, M.Pd", full_out_text)
        self.assertNotIn("Ahmad Dahlan, M.Pd", full_out_text)

        # Evaluasi ekstra checks: sinkronisasi tanggal terbilang 0 masalah
        for it in items:
            issues = self.domain.extra_checks(it, full_out_text)
            self.assertEqual(len(issues), 0)

        # Evaluasi laporan verifikasi perubahan: 0 butir SALAH
        verifier = ChangeReportGenerator()
        _, report = verifier.generate_report(out_dir, in_dir, items, rules=rules)
        self.assertEqual(report["ringkasan"]["verdict"]["SALAH"], 0)


if __name__ == "__main__":
    unittest.main()
