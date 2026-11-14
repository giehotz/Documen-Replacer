"""
Unit test untuk workflows/batch_mail_merge.py (DOM-06 & PRD §5.3-E).
Menguji pemuatan CSV (koma & titik koma), sanitasi nama file Windows,
validasi kolom, generasi dokumen massal, pembatalan bersih, dan pelaporan eksekusi.
"""
import unittest
import os
import shutil
import tempfile
from docx import Document

from workflows.batch_mail_merge import (
    sanitize_filename,
    load_csv_data,
    load_excel_data,
    validate_dataset_against_template,
    BatchMailMerge,
)
from document.paragraph_processor import get_paragraph_text


class TestBatchMailMerge(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_mail_merge_")
        self.generator = BatchMailMerge()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        """Memastikan karakter terlarang Windows dan path traversal dibersihkan."""
        self.assertEqual(sanitize_filename("SK: Guru / Pelajaran?"), "SK_ Guru _ Pelajaran")
        self.assertEqual(sanitize_filename("../../../rahasia.docx"), "rahasia.docx")
        self.assertEqual(sanitize_filename("   Nama Guru...  "), "Nama Guru")
        self.assertEqual(sanitize_filename(""), "dokumen")

    def test_load_csv_comma_and_semicolon(self):
        """Memuat CSV dengan pemisah koma maupun titik koma secara otomatis."""
        csv_comma = os.path.join(self.test_dir, "data_comma.csv")
        with open(csv_comma, "w", encoding="utf-8-sig") as f:
            f.write("Nama,NIP,Jabatan\n")
            f.write("Budi Santoso,19800101,Kepala\n")
            f.write("Siti Aminah,19850202,Guru\n")

        headers, rows = load_csv_data(csv_comma)
        self.assertEqual(headers, ["Nama", "NIP", "Jabatan"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Nama"], "Budi Santoso")

        csv_semi = os.path.join(self.test_dir, "data_semi.csv")
        with open(csv_semi, "w", encoding="utf-8") as f:
            f.write("Nama;NIP;Jabatan\n")
            f.write("Ahmad Fauzi;19880303;Guru PAI\n")

        headers_s, rows_s = load_csv_data(csv_semi)
        self.assertEqual(headers_s, ["Nama", "NIP", "Jabatan"])
        self.assertEqual(len(rows_s), 1)
        self.assertEqual(rows_s[0]["Nama"], "Ahmad Fauzi")

    def test_validate_dataset_against_template(self):
        """Validasi token templat vs ketersediaan kolom pada data sumber."""
        headers = ["Nama", "NIP"]
        rows = [{"Nama": "Budi", "NIP": "1980", "_row_number": "1"}]
        template_tokens = ["Nama", "NIP", "Alamat"]

        val = validate_dataset_against_template(headers, rows, template_tokens)
        self.assertFalse(val["is_valid"])
        self.assertIn("Alamat", val["unmapped_tokens"])

        # Sukses bila seluruh token tersedia
        val_ok = validate_dataset_against_template(headers, rows, ["Nama", "NIP"])
        self.assertTrue(val_ok["is_valid"])

    def test_generate_batch_success(self):
        """Generasi batch dokumen massal dari templat dan berkas CSV."""
        tpl_path = os.path.join(self.test_dir, "template.docx")
        doc_tpl = Document()
        doc_tpl.add_heading("SURAT KEPUTUSAN PENUGASAN", level=1)
        doc_tpl.add_paragraph("Menugaskan kepada: {{NAMA}}, NIP: {{NIP}}, Jabatan: {{JABATAN}}.")
        doc_tpl.save(tpl_path)

        csv_path = os.path.join(self.test_dir, "pegawai.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("NAMA,NIP,JABATAN\n")
            f.write("Budi Santoso,19800101,Kepala\n")
            f.write("Siti Aminah,19850202,Guru Kelas\n")
            f.write("Ahmad Fauzi,19880303,Guru PAI\n")

        out_dir = os.path.join(self.test_dir, "out_batch")
        res = self.generator.generate_batch(
            template_path=tpl_path,
            data_path=csv_path,
            output_dir=out_dir,
            filename_pattern="SK_{NO}_{NAMA}",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["generated_count"], 3)
        self.assertTrue(os.path.isfile(res["report_path"]))

        # Periksa isi salah satu dokumen hasil
        file_siti = os.path.join(out_dir, "SK_002_Siti Aminah.docx")
        self.assertTrue(os.path.isfile(file_siti))

        doc_siti = Document(file_siti)
        p_txt = get_paragraph_text(doc_siti.paragraphs[1])
        self.assertIn("Siti Aminah", p_txt)
        self.assertIn("19850202", p_txt)
        self.assertIn("Guru Kelas", p_txt)

    def test_cancellation_cleans_up_files(self):
        """Pembatalan di tengah jalan harus menghapus berkas yang setengah dibuat."""
        tpl_path = os.path.join(self.test_dir, "tpl.docx")
        doc_tpl = Document()
        doc_tpl.add_paragraph("Halo {{NAMA}}")
        doc_tpl.save(tpl_path)

        csv_path = os.path.join(self.test_dir, "data.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("NAMA\nSatu\nDua\nTiga\n")

        out_dir = os.path.join(self.test_dir, "out_cancel")

        # Batalkan saat proses mencapai baris ke-2
        def cancel_on_second():
            return len(os.listdir(out_dir)) >= 1 if os.path.exists(out_dir) else False

        res = self.generator.generate_batch(
            template_path=tpl_path,
            data_path=csv_path,
            output_dir=out_dir,
            filename_pattern="Dok_{NAMA}",
            cancel_check=cancel_on_second,
        )

        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "CANCELED")
        # Pastikan tidak ada file setengah jadi tertinggal
        docx_left = [f for f in os.listdir(out_dir) if f.endswith(".docx")] if os.path.exists(out_dir) else []
        self.assertEqual(len(docx_left), 0)

    def test_openpyxl_missing_friendly_error(self):
        """Memastikan jika openpyxl tidak ada, pesan galat ramah pengguna dimunculkan."""
        dummy_xlsx = os.path.join(self.test_dir, "test.xlsx")
        with open(dummy_xlsx, "wb") as f:
            f.write(b"PK")

        with self.assertRaises(ImportError) as ctx:
            load_excel_data(dummy_xlsx)

        self.assertIn("openpyxl", str(ctx.exception))
        self.assertIn("pip install openpyxl", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
