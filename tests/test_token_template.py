"""
Unit test untuk document/extensions/token_template_processor.py (DOM-06 & PRD §5.3-E).
Menguji penemuan token {{FIELD}} / <<FIELD>>, penggantian token terpecah di banyak run,
penggantian multi-token pada paragraf yang sama, dan pelaporan token tanpa kolom data.
"""
import unittest
from docx import Document

from document.extensions.token_template_processor import (
    find_tokens_in_text,
    extract_tokens_from_document,
    replace_tokens_in_paragraph,
    replace_tokens_in_document,
)
from document.paragraph_processor import get_paragraph_text


class TestTokenTemplate(unittest.TestCase):
    def test_find_tokens_in_text(self):
        """Mendeteksi token kurung ganda, sudut ganda, dan kurung siku ganda."""
        text = "Yth. {{NAMA}}, jabatan <<JABATAN>>, NIP [[NIP]]."
        matches = find_tokens_in_text(text)

        self.assertEqual(len(matches), 3)
        self.assertEqual(matches[0][2], "NAMA")
        self.assertEqual(matches[1][2], "JABATAN")
        self.assertEqual(matches[2][2], "NIP")

    def test_replace_tokens_single_run(self):
        """Mengganti token yang berada di dalam satu run tunggal."""
        doc = Document()
        p = doc.add_paragraph("Selamat datang {{NAMA}} di MIN 1 Contoh.")

        data = {"NAMA": "Budi Santoso, M.Pd"}
        replaced, unmapped = replace_tokens_in_paragraph(p, data)

        self.assertEqual(replaced, 1)
        self.assertEqual(len(unmapped), 0)
        self.assertEqual(get_paragraph_text(p), "Selamat datang Budi Santoso, M.Pd di MIN 1 Contoh.")

    def test_replace_tokens_split_runs(self):
        """Mengganti token yang terpecah di 3 run berbeda ({{ + NAMA + }})."""
        doc = Document()
        p = doc.add_paragraph()
        r1 = p.add_run("Kepada Yth. ")
        r2 = p.add_run("{{")
        r3 = p.add_run("NAMA_GURU")
        r3.bold = True
        r4 = p.add_run("}}")
        r5 = p.add_run(", selamat bertugas.")

        data = {"NAMA_GURU": "Siti Aminah, S.Pd"}
        replaced, unmapped = replace_tokens_in_paragraph(p, data)

        self.assertEqual(replaced, 1)
        self.assertEqual(len(unmapped), 0)
        self.assertEqual(get_paragraph_text(p), "Kepada Yth. Siti Aminah, S.Pd, selamat bertugas.")

    def test_multiple_tokens_in_same_paragraph(self):
        """Mengganti banyak token sekaligus pada paragraf yang sama dari belakang ke depan."""
        doc = Document()
        p = doc.add_paragraph("Nama: {{NAMA}}, Jabatan: {{JABATAN}}, Satker: {{SATKER}}.")

        data = {
            "NAMA": "Budi Santoso, M.Pd",
            "JABATAN": "Kepala Madrasah",
            "SATKER": "MIN 1 Contoh",
        }
        replaced, unmapped = replace_tokens_in_paragraph(p, data)

        self.assertEqual(replaced, 3)
        self.assertEqual(len(unmapped), 0)
        self.assertEqual(
            get_paragraph_text(p),
            "Nama: Budi Santoso, M.Pd, Jabatan: Kepala Madrasah, Satker: MIN 1 Contoh."
        )

    def test_unmapped_token_reported(self):
        """Melaporkan token yang tidak ditemukan pada dictionary data."""
        doc = Document()
        p = doc.add_paragraph("Nama: {{NAMA}}, Honor: {{HONOR}}.")

        data = {"NAMA": "Budi Santoso"}
        replaced, unmapped = replace_tokens_in_paragraph(p, data)

        self.assertEqual(replaced, 1)
        self.assertIn("HONOR", unmapped)
        self.assertIn("{{HONOR}}", get_paragraph_text(p))

    def test_replace_tokens_in_document(self):
        """Mengganti token pada seluruh bagian dokumen (badan dan tabel)."""
        doc = Document()
        doc.add_paragraph("SURAT TUGAS: {{NOMOR_SURAT}}")
        tbl = doc.add_table(rows=2, cols=2)
        tbl.rows[0].cells[0].text = "Nama"
        tbl.rows[0].cells[1].text = "Tugas"
        tbl.rows[1].cells[0].text = "{{NAMA}}"
        tbl.rows[1].cells[1].text = "{{TUGAS}}"

        data = {
            "NOMOR_SURAT": "B-001/MIN.1/2026",
            "NAMA": "Siti Aminah, S.Pd",
            "TUGAS": "Pengawas Ujian",
        }
        res = replace_tokens_in_document(doc, data)

        self.assertEqual(res["total_replaced"], 3)
        self.assertEqual(len(res["unmapped_tokens"]), 0)
        self.assertIn("B-001/MIN.1/2026", get_paragraph_text(doc.paragraphs[0]))
        self.assertIn("Siti Aminah, S.Pd", get_paragraph_text(tbl.rows[1].cells[0].paragraphs[0]))


if __name__ == "__main__":
    unittest.main()
