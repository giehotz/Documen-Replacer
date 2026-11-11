"""
Unit Test untuk Layanan Kompatibilitas Dokumen Word (.doc & .docx).
Menguji konversi otomatis, cache transparan, pembacaan berkas .doc nyata,
serta siklus penuh penggantian data pada berkas .doc.
"""
import unittest
import os
import shutil
import tempfile
from docx import Document

from docx.document import Document as DocxDocumentClass

from core.doc_compat_service import (
    is_doc_format,
    is_docx_format,
    is_supported_word_file,
    ensure_docx,
    convert_doc_to_docx,
    convert_docx_to_doc,
)
from document.docx_reader import load_document
from document.docx_writer import save_document
from core.replacement_engine import ReplacementEngine


class TestDocCompatService(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.real_doc_file = r"G:\MODUL 2627\KELAS 1\ATP\ATP Seni Rupa Kelas 1 - modulguruku.com.doc"

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_extension_detection_helpers(self):
        """Memastikan fungsi pendeteksi ekstensi dan filter berkas sementara bekerja akurat."""
        self.assertTrue(is_doc_format("dokumen.doc"))
        self.assertTrue(is_doc_format("path/to/dokumen.DOC"))
        self.assertFalse(is_doc_format("dokumen.docx"))

        self.assertTrue(is_docx_format("dokumen.docx"))
        self.assertFalse(is_docx_format("dokumen.doc"))

        self.assertTrue(is_supported_word_file("modul.docx"))
        self.assertTrue(is_supported_word_file("modul.doc"))
        self.assertFalse(is_supported_word_file("~$modul.docx"))
        self.assertFalse(is_supported_word_file("~$modul.doc"))
        self.assertFalse(is_supported_word_file("catatan.pdf"))

    def test_ensure_docx_on_real_doc(self):
        """Memastikan berkas .doc nyata dapat dikonversi dan dibaca sebagai .docx."""
        if not os.path.exists(self.real_doc_file):
            self.skipTest(f"Berkas uji .doc tidak ditemukan di {self.real_doc_file}")

        docx_path, is_temp = ensure_docx(self.real_doc_file)
        self.assertTrue(is_temp)
        self.assertTrue(os.path.isfile(docx_path))
        self.assertTrue(docx_path.endswith(".docx"))

        # Pastikan berkas hasil konversi valid dan dapat dibaca python-docx
        doc = Document(docx_path)
        self.assertGreater(len(doc.tables), 0)

    def test_load_document_transparent_doc(self):
        """Memastikan load_document dapat langsung membuka berkas .doc tanpa error."""
        if not os.path.exists(self.real_doc_file):
            self.skipTest(f"Berkas uji .doc tidak ditemukan di {self.real_doc_file}")

        doc = load_document(self.real_doc_file)
        self.assertIsInstance(doc, DocxDocumentClass)
        self.assertGreater(len(doc.tables), 0)

    def test_save_document_raises_runtime_error_on_failure(self):
        """Memastikan save_document melempar RuntimeError jika konversi ke .doc gagal."""
        from unittest import mock
        doc = Document()
        doc.add_paragraph("Test failure handling")
        out_doc = os.path.join(self.test_dir, "fail.doc")

        with mock.patch("core.doc_compat_service.convert_docx_to_doc", return_value=False):
            with self.assertRaises(RuntimeError):
                save_document(doc, out_doc)

    def test_save_document_docx_and_doc(self):
        """Memastikan save_document mendukung output .docx dan konversi kembali ke .doc."""
        doc = Document()
        doc.add_paragraph("Uji Coba Kompatibilitas Dokumen Word.")

        # 1. Simpan sebagai .docx
        out_docx = os.path.join(self.test_dir, "test_out.docx")
        save_document(doc, out_docx)
        self.assertTrue(os.path.isfile(out_docx))
        self.assertGreater(os.path.getsize(out_docx), 0)

        # 2. Simpan sebagai .doc (via Word COM)
        out_doc = os.path.join(self.test_dir, "test_out.doc")
        save_document(doc, out_doc)
        self.assertTrue(os.path.isfile(out_doc))
        self.assertGreater(os.path.getsize(out_doc), 0)

    def test_replacement_engine_on_doc_file(self):
        """Memastikan ReplacementEngine dapat memproses berkas .doc dan menghasilkan .docx hasil edit."""
        if not os.path.exists(self.real_doc_file):
            self.skipTest(f"Berkas uji .doc tidak ditemukan di {self.real_doc_file}")

        engine = ReplacementEngine()
        rules = [
            {"label": "Mata Pelajaran", "old": "Seni Rupa", "new": "Seni Rupa Modifikasi"},
        ]

        out_docx = os.path.join(self.test_dir, "seni_rupa_hasil.docx")
        changes = engine.process_file(self.real_doc_file, out_docx, rules, mode="GABUNGAN")

        self.assertTrue(os.path.isfile(out_docx))
        self.assertGreater(os.path.getsize(out_docx), 0)

        # Verifikasi bahwa file hasil edit berisi teks pengganti
        res_doc = Document(out_docx)
        full_text = " ".join([p.text for p in res_doc.paragraphs] + [c.text for t in res_doc.tables for r in t.rows for c in r.cells])
        self.assertIn("Seni Rupa Modifikasi", full_text)


if __name__ == "__main__":
    unittest.main()
