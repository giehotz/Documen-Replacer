"""
Unit test suite untuk Modul Konversi Word ke PDF (Fase Fitur Tambahan).
Menguji:
- Pemindaian berkas & pemfilteran berkas sementara (~$)
- Resolusi path tujuan (preservasi subfolder & penanganan duplikasi nama)
- Deteksi mesin konversi aktif (Word COM / LibreOffice)
- Konversi nyata berkas Word (.docx) menjadi berkas PDF (.pdf) valid
"""
import os
import shutil
import unittest
from unittest import mock
from docx import Document

from core.pdf_converter.conversion_manager import PdfConversionManager, DocItem
from core.pdf_converter.libreoffice_engine import LibreOfficeConverter
from core.pdf_converter.word_com_engine import WordComConverter


class TestPdfConverter(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp_pdf_test"))
        self.src_dir = os.path.join(self.test_dir, "src")
        self.out_dir = os.path.join(self.test_dir, "out")
        os.makedirs(self.src_dir, exist_ok=True)
        os.makedirs(self.out_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_docitem_properties(self):
        """Uji format ukuran file pada DocItem."""
        it = DocItem(
            path="C:\\test.docx",
            rel_path="test.docx",
            filename="test.docx",
            size_bytes=2048,
            ext=".docx"
        )
        self.assertEqual(it.size_formatted, "2.0 KB")

        it_mb = DocItem(
            path="C:\\large.docx",
            rel_path="large.docx",
            filename="large.docx",
            size_bytes=1024 * 1024 * 3,
            ext=".docx"
        )
        self.assertEqual(it_mb.size_formatted, "3.0 MB")

    def test_scan_documents_and_filter_temp_files(self):
        """Uji scanner menemukan .doc/.docx dan mengabaikan berkas sementara Word (~$)."""
        # Berkas valid
        doc1 = os.path.join(self.src_dir, "Dokumen1.docx")
        with open(doc1, "w", encoding="utf-8") as f:
            f.write("mock content")

        # Berkas di subfolder
        sub = os.path.join(self.src_dir, "Semester 1")
        os.makedirs(sub, exist_ok=True)
        doc2 = os.path.join(sub, "Modul.doc")
        with open(doc2, "w", encoding="utf-8") as f:
            f.write("mock content 2")

        # Berkas sementara yang harus diabaikan (~$Dokumen1.docx)
        temp_doc = os.path.join(self.src_dir, "~$Dokumen1.docx")
        with open(temp_doc, "w", encoding="utf-8") as f:
            f.write("temp")

        # Berkas lain yang tidak didukung
        txt_file = os.path.join(self.src_dir, "catatan.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("text")

        mgr = PdfConversionManager()
        items = mgr.scan_documents(self.src_dir, recursive=True)

        found_names = [it.filename for it in items]
        self.assertIn("Dokumen1.docx", found_names)
        self.assertIn("Modul.doc", found_names)
        self.assertNotIn("~$Dokumen1.docx", found_names)
        self.assertNotIn("catatan.txt", found_names)
        self.assertEqual(len(items), 2)

    def test_prepare_targets_with_subfolders(self):
        """Uji pembentukan path tujuan dengan mempertahankan struktur subfolder."""
        sub_dir = os.path.join(self.src_dir, "Bab 1")
        os.makedirs(sub_dir, exist_ok=True)
        f_path = os.path.join(sub_dir, "RPP.docx")
        with open(f_path, "w", encoding="utf-8") as f:
            f.write("content")

        mgr = PdfConversionManager()
        items = mgr.scan_documents(self.src_dir, recursive=True)
        mgr.prepare_targets(items, self.out_dir, preserve_subfolders=True, skip_existing=True)

        self.assertEqual(len(items), 1)
        expected_pdf = os.path.normpath(os.path.join(self.out_dir, "Bab 1", "RPP.pdf"))
        self.assertEqual(os.path.normpath(items[0].target_pdf), expected_pdf)
        self.assertEqual(items[0].status, "Menunggu")

    def test_prepare_targets_flat_duplicate_names(self):
        """Uji penomoran otomatis nama berkas PDF jika nama sama di subfolder berbeda pada mode flat."""
        dir1 = os.path.join(self.src_dir, "Folder A")
        dir2 = os.path.join(self.src_dir, "Folder B")
        os.makedirs(dir1, exist_ok=True)
        os.makedirs(dir2, exist_ok=True)

        with open(os.path.join(dir1, "RPP.docx"), "w", encoding="utf-8") as f:
            f.write("a")
        with open(os.path.join(dir2, "RPP.docx"), "w", encoding="utf-8") as f:
            f.write("b")

        mgr = PdfConversionManager()
        items = mgr.scan_documents(self.src_dir, recursive=True)
        mgr.prepare_targets(items, self.out_dir, preserve_subfolders=False, skip_existing=False)

        target_names = [os.path.basename(it.target_pdf) for it in items]
        self.assertIn("RPP.pdf", target_names)
        self.assertIn("RPP (2).pdf", target_names)

    def test_skip_existing_pdf(self):
        """Uji jika berkas PDF sudah ada dan skip_existing=True, status menjadi 'Dilewati'."""
        f_path = os.path.join(self.src_dir, "RPP_Selesai.docx")
        with open(f_path, "w", encoding="utf-8") as f:
            f.write("docx")

        # Buat PDF tiruan di output
        pdf_path = os.path.join(self.out_dir, "RPP_Selesai.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 dummy content")

        mgr = PdfConversionManager()
        items = mgr.scan_documents(self.src_dir, recursive=False)
        mgr.prepare_targets(items, self.out_dir, preserve_subfolders=True, skip_existing=True)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, "Dilewati")

    def test_active_engine_detection(self):
        """Uji deteksi mesin konversi yang terpasang pada komputer."""
        mgr = PdfConversionManager()
        engine = mgr.get_active_engine()
        if engine is None:
            self.skipTest("Tidak ada mesin konversi (Word/LibreOffice) di lingkungan pengujian.")
        name = mgr.get_engine_name()
        self.assertTrue("Word" in name or "LibreOffice" in name)

    def test_libreoffice_duplicate_basename_no_data_loss(self):
        """Uji fallback LibreOffice: dua berkas bernama sama di folder berbeda tidak saling menimpa."""
        src_a = os.path.join(self.src_dir, "Folder A")
        src_b = os.path.join(self.src_dir, "Folder B")
        os.makedirs(src_a, exist_ok=True)
        os.makedirs(src_b, exist_ok=True)
        in_a = os.path.join(src_a, "RPP.docx")
        in_b = os.path.join(src_b, "RPP.docx")
        with open(in_a, "w", encoding="utf-8") as f:
            f.write("A")
        with open(in_b, "w", encoding="utf-8") as f:
            f.write("B")

        conv = LibreOfficeConverter()
        conv.soffice_path = "soffice"
        conv.is_available = lambda: True

        def fake_run(cmd, **kwargs):
            out_dir = cmd[cmd.index("--outdir") + 1]
            in_path = cmd[-1]
            with open(in_path, "r", encoding="utf-8") as f:
                content = f.read()
            base = os.path.splitext(os.path.basename(in_path))[0] + ".pdf"
            with open(os.path.join(out_dir, base), "w", encoding="utf-8") as f:
                f.write(content)

            class Result:
                returncode = 0
                stderr = ""

            return Result()

        out_a = os.path.join(self.out_dir, "RPP.pdf")
        out_b = os.path.join(self.out_dir, "RPP (2).pdf")

        with mock.patch("core.pdf_converter.libreoffice_engine.subprocess.run", side_effect=fake_run):
            self.assertTrue(conv.convert_file(in_a, out_a))
            self.assertTrue(conv.convert_file(in_b, out_b))

        with open(out_a, encoding="utf-8") as f:
            self.assertEqual(f.read(), "A")
        with open(out_b, encoding="utf-8") as f:
            self.assertEqual(f.read(), "B")

    def test_real_word_com_conversion(self):
        """Uji konversi Word COM riil: membuat dokumen docx dan mengonversinya ke PDF."""
        engine = WordComConverter()
        if not engine.is_available():
            self.skipTest("Microsoft Word COM tidak tersedia di lingkungan pengujian.")

        test_doc_path = os.path.join(self.src_dir, "Sample_Real.docx")
        doc = Document()
        doc.add_heading("Uji Coba Konversi PDF", level=1)
        p = doc.add_paragraph("Ini adalah dokumen uji untuk konverter Word ke PDF.")
        p.add_run(" Teks tebal.").bold = True
        doc.save(test_doc_path)

        out_pdf_path = os.path.join(self.out_dir, "Sample_Real.pdf")
        success = engine.convert_file(test_doc_path, out_pdf_path)

        self.assertTrue(success, "Konversi berkas ke PDF harus mengembalikan True.")
        self.assertTrue(os.path.isfile(out_pdf_path), "Berkas PDF keluaran harus terbentuk.")
        self.assertGreater(os.path.getsize(out_pdf_path), 100, "Ukuran berkas PDF harus valid (>100 bytes).")

        # Periksa magic number PDF (%PDF)
        with open(out_pdf_path, "rb") as f:
            header = f.read(5)
            self.assertTrue(header.startswith(b"%PDF"), f"Header harus berawalan %PDF, didapat: {header}")

    def test_real_batch_conversion_manager(self):
        """Uji eksekusi batch melalui PdfConversionManager."""
        mgr = PdfConversionManager()
        if mgr.get_active_engine() is None:
            self.skipTest("Tidak ada mesin konversi (Word/LibreOffice) di lingkungan pengujian.")

        for i in range(1, 3):
            p = os.path.join(self.src_dir, f"Batch_Doc_{i}.docx")
            doc = Document()
            doc.add_heading(f"Dokumen Batch {i}", level=1)
            doc.add_paragraph(f"Paragraf pengujian nomor {i}")
            doc.save(p)

        items = mgr.scan_documents(self.src_dir, recursive=False)
        mgr.prepare_targets(items, self.out_dir, preserve_subfolders=True, skip_existing=False)

        summary = mgr.convert_batch(items)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["failed"], 0)


if __name__ == "__main__":
    unittest.main()
