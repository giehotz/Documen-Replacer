"""
Unit test untuk modul verifikasi dan generator laporan perubahan JSON
(core/change_verifier.py).
"""
import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime
from docx import Document

from core.change_verifier import ChangeReportGenerator, highlight_span, anonymize_pii_text
from core.validation_engine import ReplacementPlanItem, ConfidenceLevel


class TestChangeVerifier(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.out_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.out_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_highlight_span(self):
        txt = "Tahun Pelajaran : 2026/2027"
        res = highlight_span(txt, 18, 27)
        self.assertEqual(res, "Tahun Pelajaran : ⟦2026/2027⟧")

    def test_anonymize_pii_text(self):
        raw = "NIP : 198001012005011001"
        res = anonymize_pii_text(raw)
        self.assertEqual(res, "NIP : 19800101••••••1001")

    def test_report_generation_clean_ok(self):
        """Uji dokumen dengan penggantian yang bersih dan benar menghasilkan verdict OK."""
        # Buat dokumen hasil di out_dir
        doc = Document()
        doc.add_paragraph("KEMENTERIAN AGAMA")
        doc.add_paragraph("Tahun Pelajaran : 2026/2027")
        out_file = os.path.join(self.out_dir, "sample.docx")
        doc.save(out_file)

        plan_items = [
            ReplacementPlanItem(
                doc_path="dummy.docx",
                rel_path="sample.docx",
                category="Tahun Pelajaran",
                old_text="20.... / 20....",
                new_text="2026/2027",
                confidence=ConfidenceLevel.HIGH,
                location_info="Paragraf #1",
                is_approved=True,
                target_type="PARAGRAPH_SPAN",
                target_meta={
                    "para_idx": 1,
                    "start": 18,
                    "end": 33,
                    "original_text": "Tahun Pelajaran : 20.... / 20....",
                }
            )
        ]
        rules = [{"label": "Tahun Pelajaran", "old": "", "new": "2026/2027"}]

        generator = ChangeReportGenerator(anonymize_pii=False)
        json_path, report = generator.generate_report(
            output_dir=self.out_dir,
            input_dir=self.temp_dir,
            plan_items=plan_items,
            rules=rules,
            mode="GABUNGAN",
            report_time=datetime(2026, 11, 13, 20, 0, 0)
        )

        self.assertTrue(os.path.isfile(json_path))
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["ringkasan"]["verdict"]["OK"], 1)
        self.assertEqual(data["ringkasan"]["verdict"]["SALAH"], 0)
        self.assertEqual(len(data["perubahan"]), 1)
        self.assertEqual(data["perubahan"][0]["verifikasi"]["verdict"], "OK")

    def test_report_flags_tahun_awalan_ganda_as_salah(self):
        """Uji jika dokumen memuat '202026', laporan harus otomatis menandai SALAH dengan kode TAHUN_AWALAN_GANDA."""
        # Dokumen hasil yang bermasalah (memuat 202026)
        doc = Document()
        doc.add_paragraph("KEMENTERIAN AGAMA")
        doc.add_paragraph("Tahun Pelajaran : 202026/2027 / 20....")
        out_file = os.path.join(self.out_dir, "problematic.docx")
        doc.save(out_file)

        plan_items = [
            ReplacementPlanItem(
                doc_path="dummy.docx",
                rel_path="problematic.docx",
                category="Tahun Pelajaran",
                old_text="....",
                new_text="2026/2027",
                confidence=ConfidenceLevel.HIGH,
                location_info="Paragraf #1",
                is_approved=True,
                target_type="PARAGRAPH_SPAN",
                target_meta={
                    "para_idx": 1,
                    "start": 20,
                    "end": 24,
                    "original_text": "Tahun Pelajaran : 20.... / 20....",
                }
            )
        ]
        rules = [{"label": "Tahun Pelajaran", "old": "", "new": "2026/2027"}]

        generator = ChangeReportGenerator(anonymize_pii=False)
        json_path, report = generator.generate_report(
            output_dir=self.out_dir,
            input_dir=self.temp_dir,
            plan_items=plan_items,
            rules=rules
        )

        self.assertEqual(report["ringkasan"]["verdict"]["SALAH"], 1)
        self.assertIn("P-0001", report["ringkasan"]["perlu_tinjau"])

        item_res = report["perubahan"][0]
        self.assertEqual(item_res["verifikasi"]["verdict"], "SALAH")
        flag_codes = [b["kode"] for b in item_res["verifikasi"]["bendera"]]
        self.assertIn("TAHUN_AWALAN_GANDA", flag_codes)


if __name__ == "__main__":
    unittest.main()
