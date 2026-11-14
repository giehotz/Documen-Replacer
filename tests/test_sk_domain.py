"""
Unit test untuk modul domain Surat Keputusan (SKDomain).
Menguji deteksi SK, prediksi field, perencanaan perubahan judul & diktum,
sinkronisasi otomatis ke header lampiran, serta verifikasi laporan perubahan.
"""
import unittest
import os
import shutil
import tempfile
from docx import Document

from domains.sk.sk_domain import SKDomain
from tests.fixtures.make_sample_docs import (
    create_sample_sk,
    create_sample_sk_with_attachment,
    create_sample_sk_with_textbox_kop,
)
from document.paragraph_processor import get_paragraph_text
from document.extensions.kop_surat_processor import iter_kop_paragraphs
from core.change_verifier import ChangeReportGenerator


class TestSKDomain(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_sk_domain_")
        self.domain = SKDomain()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_detect_score_sk(self):
        """SKDomain harus memberikan skor deteksi tinggi (>= 0.60) pada naskah SK."""
        sk_path = os.path.join(self.test_dir, "sample_sk.docx")
        create_sample_sk(sk_path)

        res = self.domain.detect_score(sk_path)
        self.assertGreaterEqual(res.score, 0.60)
        self.assertTrue(any("utama" in r.lower() for r in res.reasons))

    def test_predict_fields_sk(self):
        """SKDomain harus mampu mengekstrak nomor, tentang, tempat, tanggal penetapan, dan nama kepala."""
        sk_path = os.path.join(self.test_dir, "sample_sk.docx")
        create_sample_sk(sk_path)

        fields = self.domain.predict_fields(sk_path)
        self.assertEqual(fields.get("nomor_sk"), "421.2/015/MIN.1/SK/2025")
        self.assertIn("PEMBAGIAN TUGAS GURU", fields.get("tentang_sk", ""))
        self.assertEqual(fields.get("tempat_penetapan"), "Kota Contoh")
        self.assertEqual(fields.get("tanggal_penetapan"), "14 Juli 2025")
        self.assertEqual(fields.get("nama_kepala"), "Budi Santoso, M.Pd")

    def test_plan_and_apply_with_attachment_sync(self):
        """SKDomain harus merencanakan dan menyinkronkan Nomor, Tanggal, dan Tentang ke Lampiran SK."""
        in_dir = self.test_dir
        out_dir = os.path.join(self.test_dir, "output")
        os.makedirs(out_dir, exist_ok=True)

        sk_path = os.path.join(in_dir, "sk_with_att.docx")
        create_sample_sk_with_attachment(sk_path)
        out_path = os.path.join(out_dir, "sk_with_att.docx")

        rules = [
            {"label": "Nomor SK", "old": "421.2/015/MIN.1/SK/2025", "new": "421.2/099/MIN.1/SK/2026"},
            {"label": "Tanggal Penetapan", "old": "14 Juli 2025", "new": "20 Juli 2026"},
            {"label": "Tentang / Judul SK", "old": "PEMBAGIAN TUGAS GURU TAHUN PELAJARAN 2025/2026", "new": "PEMBAGIAN TUGAS GURU TAHUN PELAJARAN 2026/2027"},
        ]

        items = self.domain.plan_document_changes(sk_path, "sk_with_att.docx", rules)
        self.assertGreater(len(items), 0)

        # Pastikan ada item yang menargetkan lampiran
        sync_items = [it for it in items if "Lampiran" in (it.category or "")]
        self.assertGreater(len(sync_items), 0)

        # Pastikan setiap item tertempel domain_id
        for it in items:
            self.assertEqual(it.target_meta.get("domain_id"), "sk_keputusan")

        # Terapkan perubahan
        changes_count = self.domain.apply_approved_changes(sk_path, out_path, items)
        self.assertGreater(changes_count, 0)
        self.assertTrue(os.path.exists(out_path))

        # Verifikasi isi dokumen hasil
        doc_out = Document(out_path)
        out_texts = [get_paragraph_text(p) for p in doc_out.paragraphs]
        full_out_text = "\n".join(out_texts)

        # Cek naskah utama
        self.assertIn("421.2/099/MIN.1/SK/2026", full_out_text)
        self.assertIn("20 Juli 2026", full_out_text)
        self.assertIn("PEMBAGIAN TUGAS GURU TAHUN PELAJARAN 2026/2027", full_out_text)

        # Cek ketergantian di lampiran (minimal muncul 2 kali: di naskah utama dan di lampiran)
        self.assertGreaterEqual(full_out_text.count("421.2/099/MIN.1/SK/2026"), 2)
        self.assertGreaterEqual(full_out_text.count("20 Juli 2026"), 2)

        # Evaluasi ekstra checks: SINKRON_ANTAR_ZONA harus 0 masalah
        for it in sync_items:
            issues = self.domain.extra_checks(it, full_out_text)
            self.assertEqual(len(issues), 0)

        # Evaluasi laporan verifikasi perubahan: 0 butir SALAH
        verifier = ChangeReportGenerator()
        _, report = verifier.generate_report(out_dir, in_dir, items, rules=rules)
        self.assertEqual(report["ringkasan"]["verdict"]["SALAH"], 0)

    def test_sk_with_textbox_kop_alternate_content(self):
        """Kop surat dalam AlternateContent harus dibaca tanpa duplikasi Choice vs Fallback."""
        sk_path = os.path.join(self.test_dir, "sk_textbox.docx")
        create_sample_sk_with_textbox_kop(sk_path)

        doc = Document(sk_path)
        kop_items = iter_kop_paragraphs(doc)
        textbox_paras = [p for p, m in kop_items if m.get("is_textbox")]
        self.assertEqual(len(textbox_paras), 1)
        self.assertIn("KOP SURAT MADRASAH", get_paragraph_text(textbox_paras[0]))


if __name__ == "__main__":
    unittest.main()
