"""
Unit test untuk modul domain Surat Perintah Tugas (SPTDomain).
Menguji deteksi SPT, ekstraksi metadata, pemetaan dataset pegawai kolektif (datasets={"pegawai": [...]}),
deteksi ketidaksesuaian jumlah baris (JUMLAH_BARIS_TIDAK_SAMA), dan laporan verifikasi perubahan.
"""
import unittest
import os
import shutil
import tempfile
from docx import Document

from domains.spt.spt_domain import SPTDomain
from tests.fixtures.make_sample_docs import create_sample_spt
from document.paragraph_processor import get_paragraph_text
from core.change_verifier import ChangeReportGenerator


class TestSPTDomain(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_spt_domain_")
        self.domain = SPTDomain()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_detect_score_spt(self):
        """SPTDomain harus memberikan skor deteksi tinggi (>= 0.60) pada naskah SPT."""
        spt_path = os.path.join(self.test_dir, "sample_spt.docx")
        create_sample_spt(spt_path)

        res = self.domain.detect_score(spt_path)
        self.assertGreaterEqual(res.score, 0.60)
        self.assertTrue(any("utama" in r.lower() or "pendukung" in r.lower() for r in res.reasons))

    def test_predict_fields_spt(self):
        """SPTDomain harus mampu mengekstrak nomor SPT dan dasar penugasan."""
        spt_path = os.path.join(self.test_dir, "sample_spt.docx")
        create_sample_spt(spt_path)

        fields = self.domain.predict_fields(spt_path)
        self.assertEqual(fields.get("nomor_spt"), "800/012/SPT/2025")
        self.assertIn("Surat Kepala Kantor", fields.get("dasar_penugasan", ""))

    def test_plan_and_apply_collective_spt_with_dataset(self):
        """Menerapkan perubahan baris tabel pegawai SPT kolektif via parameter datasets."""
        in_dir = self.test_dir
        out_dir = os.path.join(self.test_dir, "output")
        os.makedirs(out_dir, exist_ok=True)

        spt_path = os.path.join(in_dir, "spt.docx")
        create_sample_spt(spt_path)
        out_path = os.path.join(out_dir, "spt.docx")

        rules = [
            {"label": "Nomor SPT", "old": "800/012/SPT/2025", "new": "800/099/SPT/2026"},
        ]

        pegawai_data = [
            {
                "nama": "Ahmad Fauzi, S.Pd.I",
                "nip": "198803032014031003",
                "pangkat_gol": "Penata Muda Tk. I / III.b",
                "jabatan": "Guru PAI",
            }
        ]

        items = self.domain.plan_document_changes(
            spt_path, "spt.docx", rules, datasets={"pegawai": pegawai_data}
        )
        self.assertGreater(len(items), 0)

        # Pastikan domain_id tertempel
        for it in items:
            self.assertEqual(it.target_meta.get("domain_id"), "spt_penugasan")

        # Terapkan perubahan
        changes_count = self.domain.apply_approved_changes(spt_path, out_path, items)
        self.assertGreater(changes_count, 0)
        self.assertTrue(os.path.exists(out_path))

        # Verifikasi isi tabel hasil
        doc_out = Document(out_path)
        tbl = doc_out.tables[0]
        row1_texts = [" ".join(get_paragraph_text(p) for p in c.paragraphs) for c in tbl.rows[1].cells]
        row1_combined = " ".join(row1_texts)

        self.assertIn("Ahmad Fauzi, S.Pd.I", row1_combined)
        self.assertIn("198803032014031003", row1_combined)
        self.assertIn("Penata Muda Tk. I / III.b", row1_combined)
        self.assertIn("Guru PAI", row1_combined)

        # Pastikan nomor SPT juga terganti
        full_text = "\n".join(get_paragraph_text(p) for p in doc_out.paragraphs)
        self.assertIn("800/099/SPT/2026", full_text)

        # Evaluasi laporan verifikasi perubahan: 0 butir SALAH
        verifier = ChangeReportGenerator()
        _, report = verifier.generate_report(out_dir, in_dir, items, rules=rules)
        self.assertEqual(report["ringkasan"]["verdict"]["SALAH"], 0)

    def test_row_count_mismatch_warning(self):
        """Memverifikasi terbitnya bendera JUMLAH_BARIS_TIDAK_SAMA saat record data melebihi baris tabel."""
        spt_path = os.path.join(self.test_dir, "spt_mismatch.docx")
        create_sample_spt(spt_path)

        rules = [{"label": "Nomor SPT", "old": "800/012/SPT/2025", "new": "800/099/SPT/2026"}]
        # Kirim 2 pegawai padahal tabel hanya punya 1 baris data
        pegawai_data = [
            {"nama": "Pegawai Satu", "nip": "19800101", "pangkat_gol": "III/a", "jabatan": "Guru"},
            {"nama": "Pegawai Dua", "nip": "19800202", "pangkat_gol": "III/b", "jabatan": "Staf"},
        ]

        items = self.domain.plan_document_changes(
            spt_path, "spt_mismatch.docx", rules, datasets={"pegawai": pegawai_data}
        )
        has_issue = False
        for it in items:
            issues = self.domain.extra_checks(it, "")
            if any(iss.get("code") == "JUMLAH_BARIS_TIDAK_SAMA" for iss in issues):
                has_issue = True
                break

        self.assertTrue(has_issue)


if __name__ == "__main__":
    unittest.main()
