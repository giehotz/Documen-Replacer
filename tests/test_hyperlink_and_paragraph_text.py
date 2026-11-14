"""
Unit test untuk memastikan penanganan teks paragraf dan elemen hyperlink (<w:hyperlink>)
berjalan presisi di document/paragraph_processor.py dan core/replacement_engine.py.
"""
import os
import shutil
import tempfile
import unittest
import re
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.run import Run

from document.paragraph_processor import (
    get_paragraph_runs,
    get_paragraph_text,
    replace_span,
    replace_full_text_keep_style,
    replace_by_pattern,
)
from core.replacement_engine import ReplacementEngine
from core.field_dictionary import FieldDictionary


def _add_hyperlink(paragraph, text: str, url: str = "http://example.com"):
    """Helper untuk menambahkan elemen <w:hyperlink> dengan <w:r> dan <w:t>."""
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)

    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    new_run.append(rPr)

    t = OxmlElement("w:t")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


class TestHyperlinkAndParagraphText(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.doc = Document()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_get_paragraph_runs_and_text_with_hyperlink(self):
        """Memastikan get_paragraph_runs dan get_paragraph_text membaca run di dalam hyperlink."""
        p = self.doc.add_paragraph("Website resmi: ")
        _add_hyperlink(p, "https://old-domain.sch.id", "https://old-domain.sch.id")
        p.add_run(" (Hubungi Admin)")

        # Properti standar p.runs mengabaikan hyperlink
        self.assertEqual(len(p.runs), 2)
        # get_paragraph_runs menangkap seluruh 3 run
        runs = get_paragraph_runs(p)
        self.assertEqual(len(runs), 3)
        self.assertEqual(runs[0].text, "Website resmi: ")
        self.assertEqual(runs[1].text, "https://old-domain.sch.id")
        self.assertEqual(runs[2].text, " (Hubungi Admin)")

        # get_paragraph_text harus mengembalikan seluruh teks termasuk isi hyperlink
        text = get_paragraph_text(p)
        self.assertEqual(text, "Website resmi: https://old-domain.sch.id (Hubungi Admin)")
        self.assertEqual(text, p.text)

    def test_replace_span_inside_hyperlink(self):
        """Memastikan replace_span dapat mengganti bagian teks yang berada di dalam hyperlink."""
        p = self.doc.add_paragraph("Kunjungi ")
        _add_hyperlink(p, "https://madrasah-lama.sch.id/portal", "https://madrasah-lama.sch.id/portal")

        full = get_paragraph_text(p)
        start = full.find("madrasah-lama")
        end = start + len("madrasah-lama")

        success = replace_span(p, start, end, "madrasah-baru")
        self.assertTrue(success)

        # Teks baru harus terefleksi di run hyperlink dan teks paragraf
        self.assertEqual(get_paragraph_text(p), "Kunjungi https://madrasah-baru.sch.id/portal")
        self.assertEqual(p.text, "Kunjungi https://madrasah-baru.sch.id/portal")

    def test_replace_span_across_hyperlink_boundary(self):
        """Memastikan replace_span menangani penggantian yang melintasi batas run biasa dan hyperlink."""
        p = self.doc.add_paragraph("Kontak: admin@")
        _add_hyperlink(p, "lama.sch.id", "mailto:admin@lama.sch.id")

        full = get_paragraph_text(p)
        # Ganti "admin@lama.sch.id" -> "kepala@baru.sch.id"
        start = full.find("admin@")
        end = full.find("lama.sch.id") + len("lama.sch.id")

        success = replace_span(p, start, end, "kepala@baru.sch.id")
        self.assertTrue(success)
        self.assertEqual(get_paragraph_text(p), "Kontak: kepala@baru.sch.id")

    def test_replace_full_text_keep_style_with_hyperlink(self):
        """Memastikan replace_full_text_keep_style mengganti seluruh teks dan mengosongkan run hyperlink."""
        p = self.doc.add_paragraph("Link: ")
        _add_hyperlink(p, "http://klik.disini", "http://klik.disini")

        ok = replace_full_text_keep_style(p, "Tautan Dihapus")
        self.assertTrue(ok)
        self.assertEqual(get_paragraph_text(p), "Tautan Dihapus")
        self.assertEqual(p.text, "Tautan Dihapus")

    def test_replace_by_pattern_inside_hyperlink(self):
        """Memastikan replace_by_pattern (Exact Matcher) dapat mengganti kecocokan regex di dalam hyperlink."""
        p = self.doc.add_paragraph("Portal E-Learning: ")
        _add_hyperlink(p, "http://elearning-lama.ac.id/login")

        pattern = re.compile(re.escape("elearning-lama"))
        mapping = {"elearning-lama": ["elearning-baru"]}
        counters = {}

        count = replace_by_pattern(p, (pattern, mapping, False), counters)
        self.assertEqual(count, 1)
        self.assertEqual(get_paragraph_text(p), "Portal E-Learning: http://elearning-baru.ac.id/login")

    def test_replacement_engine_integration_with_hyperlink(self):
        """Memastikan ReplacementEngine dalam mode PERSIS/GABUNGAN mengganti teks di dalam hyperlink via apply_approved_changes."""
        doc_path = os.path.join(self.test_dir, "test_hl.docx")
        out_path = os.path.join(self.test_dir, "out_hl.docx")

        doc = Document()
        p = doc.add_paragraph("Website Madrasah: ")
        _add_hyperlink(p, "https://min1contoh.sch.id")
        doc.save(doc_path)

        engine = ReplacementEngine(field_dictionary=FieldDictionary.load())
        rules = [
            {"label": "Website", "old": "min1contoh", "new": "min2model"}
        ]

        plan_items = engine.plan_document_changes(doc_path, "test_hl.docx", rules, mode="PERSIS")
        self.assertEqual(len(plan_items), 1)

        changes = engine.apply_approved_changes(doc_path, out_path, plan_items)
        self.assertEqual(changes, 1)

        res_doc = Document(out_path)
        res_p = res_doc.paragraphs[0]
        self.assertIn("https://min2model.sch.id", get_paragraph_text(res_p))


if __name__ == "__main__":
    unittest.main()
