"""
Unit test untuk fitur Prediksi & Inspeksi Tata Letak Tanda Tangan Dokumen (Signature Placement Prediction).
Menguji:
- Deteksi orientasi Potrait vs Lanskap
- Deteksi dimensi halaman dan lebar margin
- Deteksi tabel tanda tangan dan perhitungan lebar kolom nyata (cm)
- Ekstraksi nama terang yang terdeteksi
- Rekomendasi ukuran dan offset X/Y optimal
"""
import unittest
import os
import shutil
import tempfile
from docx import Document
from docx.shared import Inches, Cm
from docx.enum.section import WD_ORIENTATION

from core.signature_image_service import predict_signature_layout


class TestSignaturePrediction(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="pred_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_predict_portrait_table(self):
        doc_path = os.path.join(self.test_dir, "portrait_sample.docx")
        doc = Document()
        sec = doc.sections[0]
        sec.orientation = WD_ORIENTATION.PORTRAIT
        sec.page_width = Inches(8.27)  # A4 Portrait: 21.0 cm
        sec.page_height = Inches(11.69)  # 29.7 cm

        doc.add_paragraph("RPP Kurikulum Merdeka")

        # Buat tabel tanda tangan 2 kolom
        tbl = doc.add_table(rows=4, cols=2)
        tbl.rows[0].cells[0].paragraphs[0].text = "Mengetahui,\nKepala Madrasah"
        tbl.rows[0].cells[1].paragraphs[0].text = "Semarang, 10 Juli 2026\nGuru Mata Pelajaran"

        tbl.rows[2].cells[0].paragraphs[0].text = "( Drs. H. Ahmad Fauzi, M.Pd )"
        tbl.rows[2].cells[1].paragraphs[0].text = "( Siti Aminah, S.Pd )"

        tbl.rows[3].cells[0].paragraphs[0].text = "NIP. 197001012000011001"
        tbl.rows[3].cells[1].paragraphs[0].text = "NIP. 198501012010012002"

        doc.save(doc_path)

        res = predict_signature_layout(doc_path)
        self.assertFalse(res["is_landscape"])
        self.assertEqual(res["orientation_label"], "Potrait")
        self.assertEqual(res["container_type"], "TABLE")
        self.assertEqual(res["num_columns"], 2)
        self.assertEqual(len(res["col_widths_cm"]), 2)
        self.assertIn("kepala", res["detected_names"])
        self.assertIn("guru", res["detected_names"])
        self.assertEqual(res["detected_names"]["kepala"], "( Drs. H. Ahmad Fauzi, M.Pd )")
        self.assertEqual(res["detected_names"]["guru"], "( Siti Aminah, S.Pd )")

        recs = res["recommended_offsets"]
        self.assertEqual(recs["offset_x_kepala_cm"], 0.0)
        self.assertEqual(recs["offset_x_guru_cm"], 0.0)
        self.assertEqual(recs["offset_x_stempel_cm"], -1.5)

    def test_predict_landscape_table(self):
        doc_path = os.path.join(self.test_dir, "landscape_sample.docx")
        doc = Document()
        sec = doc.sections[0]
        sec.orientation = WD_ORIENTATION.LANDSCAPE
        sec.page_width = Inches(11.69)  # A4 Landscape: 29.7 cm
        sec.page_height = Inches(8.27)  # 21.0 cm

        doc.add_paragraph("Silabus Pembelajaran")

        tbl = doc.add_table(rows=3, cols=2)
        tbl.rows[0].cells[0].paragraphs[0].text = "Mengetahui,\nKepala Sekolah"
        tbl.rows[0].cells[1].paragraphs[0].text = "Guru Kelas"

        tbl.rows[1].cells[0].paragraphs[0].text = "Dr. Mulyadi, M.Pd"
        tbl.rows[1].cells[1].paragraphs[0].text = "Budi Santoso, S.Pd"

        tbl.rows[2].cells[0].paragraphs[0].text = "NIP. 196805051995031002"
        tbl.rows[2].cells[1].paragraphs[0].text = "NIP. 198002022005011003"

        doc.save(doc_path)

        res = predict_signature_layout(doc_path)
        self.assertTrue(res["is_landscape"])
        self.assertEqual(res["orientation_label"], "Lanskap")
        self.assertEqual(res["container_type"], "TABLE")

        recs = res["recommended_offsets"]
        # Pada lanskap, offset X terkompensasi otomatis ke -2.3 dan stempel ke -3.8
        self.assertEqual(recs["offset_x_kepala_cm"], -2.3)
        self.assertEqual(recs["offset_x_guru_cm"], -2.3)
        self.assertEqual(recs["offset_x_stempel_cm"], -3.8)

    def test_predict_no_signature(self):
        doc_path = os.path.join(self.test_dir, "plain.docx")
        doc = Document()
        doc.add_paragraph("Hanya teks biasa tanpa blok tanda tangan.")
        doc.save(doc_path)

        res = predict_signature_layout(doc_path)
        self.assertEqual(res["container_type"], "NOT_FOUND")
        self.assertFalse(res["is_landscape"])


if __name__ == "__main__":
    unittest.main()
