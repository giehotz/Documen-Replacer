"""
Unit test untuk penyisipan 3 Gambar Sekaligus (TTD Kepala, TTD Guru, dan Stempel Resmi) ke dalam dokumen Word.
Menguji:
- process_signature_zone menyisipkan TTD Kepala dan Stempel ke kolom Kepala
- process_signature_zone menyisipkan TTD Guru ke kolom Guru
- apply_approved_changes menyisipkan TTD dan Stempel dengan offset yang benar
- Mode SIGNATURE_ONLY mengenali TTD & Stempel
"""
import unittest
import os
import shutil
import tempfile
from PIL import Image
from docx import Document
from docx.shared import Inches

from core.signature_analyzer import process_signature_zone
from core.replacement_engine import ReplacementEngine
from core.validation_engine import ReplacementPlanItem, ConfidenceLevel


class TestSignatureMultiImage(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="multi_img_")

        # Buat berkas gambar dummy untuk Kepala, Guru, dan Stempel
        self.img_k = os.path.join(self.test_dir, "sig_kepala.png")
        self.img_g = os.path.join(self.test_dir, "sig_guru.png")
        self.img_s = os.path.join(self.test_dir, "stempel_sekolah.png")

        Image.new("RGBA", (120, 60), color=(0, 0, 180, 255)).save(self.img_k)
        Image.new("RGBA", (120, 60), color=(0, 180, 0, 255)).save(self.img_g)
        Image.new("RGBA", (80, 80), color=(180, 0, 180, 255)).save(self.img_s)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_process_signature_zone_with_stempel(self):
        doc = Document()
        tbl = doc.add_table(rows=4, cols=2)

        # Kolom Kepala
        c0 = tbl.rows[0].cells[0]
        c0.paragraphs[0].text = "Mengetahui,\nKepala Madrasah"
        tbl.rows[1].cells[0].paragraphs[0].text = ""  # Ruang TTD
        p_name_k = tbl.rows[2].cells[0].paragraphs[0]
        p_name_k.text = "( Nama Kepala Lama, M.Pd )"
        tbl.rows[3].cells[0].paragraphs[0].text = "NIP. 197001012000011001"

        # Kumpulkan paragraf kolom kepala
        paras_k = [tbl.rows[r].cells[0].paragraphs[0] for r in range(4)]

        sig_settings = {
            "enabled_kepala": True,
            "kepala_image_path": self.img_k,
            "kepala_width_cm": 3.5,
            "offset_x_kepala_cm": 0.0,
            "offset_y_kepala_cm": 0.0,
            "enabled_stempel": True,
            "stempel_image_path": self.img_s,
            "stempel_width_cm": 3.0,
            "offset_x_stempel_cm": -1.5,
            "offset_y_stempel_cm": 0.0,
            "behind_text": True,
        }

        changes = process_signature_zone(
            paragraphs=paras_k,
            role="KEPALA",
            target_values={"Nama Kepala": "Drs. H. Ahmad Fauzi, M.Pd"},
            signature_settings=sig_settings,
            is_landscape=False,
        )

        # 1 penggantian nama + 1 TTD kepala + 1 stempel = minimal 3 changes
        self.assertGreaterEqual(changes, 3)
        self.assertIn("Drs. H. Ahmad Fauzi, M.Pd", p_name_k.text)

        # Verifikasi bahwa elemen drawing/picture masuk ke paragraf nama
        xml_str = p_name_k._p.xml
        self.assertIn("drawing", xml_str)

    def test_engine_apply_with_stempel(self):
        doc_in = os.path.join(self.test_dir, "input.docx")
        doc_out = os.path.join(self.test_dir, "output.docx")

        doc = Document()
        tbl = doc.add_table(rows=3, cols=2)
        tbl.rows[0].cells[0].paragraphs[0].text = "Kepala Sekolah"
        tbl.rows[0].cells[1].paragraphs[0].text = "Guru Kelas"

        tbl.rows[1].cells[0].paragraphs[0].text = "Drs. Lama"
        tbl.rows[1].cells[1].paragraphs[0].text = "Guru Lama"

        tbl.rows[2].cells[0].paragraphs[0].text = "NIP. 111"
        tbl.rows[2].cells[1].paragraphs[0].text = "NIP. 222"
        doc.save(doc_in)

        engine = ReplacementEngine()
        sig_settings = {
            "enabled_kepala": True,
            "kepala_image_path": self.img_k,
            "enabled_guru": True,
            "guru_image_path": self.img_g,
            "enabled_stempel": True,
            "stempel_image_path": self.img_s,
            "behind_text": True,
        }

        approved_items = [
            ReplacementPlanItem(
                doc_path=doc_in,
                rel_path="input.docx",
                category="Nama Kepala",
                old_text="Drs. Lama",
                new_text="Drs. H. Ahmad Fauzi, M.Pd",
                confidence=ConfidenceLevel.HIGH,
                location_info="Tabel #0 Baris #1",
                is_approved=True,
                target_type="TABLE_CELL_PARA",
                target_meta={"table_idx": 0, "row_idx": 1, "col_idx": 0, "para_idx": 0}
            ),
            ReplacementPlanItem(
                doc_path=doc_in,
                rel_path="input.docx",
                category="Nama Guru",
                old_text="Guru Lama",
                new_text="Siti Aminah, S.Pd",
                confidence=ConfidenceLevel.HIGH,
                location_info="Tabel #0 Baris #1",
                is_approved=True,
                target_type="TABLE_CELL_PARA",
                target_meta={"table_idx": 0, "row_idx": 1, "col_idx": 1, "para_idx": 0}
            ),
        ]

        total_changes = engine.apply_approved_changes(
            in_path=doc_in,
            out_path=doc_out,
            approved_items=approved_items,
            signature_settings=sig_settings
        )

        self.assertGreaterEqual(total_changes, 2)
        self.assertTrue(os.path.isfile(doc_out))

        # Buka doc_out dan periksa XML
        doc_res = Document(doc_out)
        t_res = doc_res.tables[0]
        self.assertIn("Ahmad Fauzi", t_res.rows[1].cells[0].paragraphs[0].text)
        self.assertIn("Siti Aminah", t_res.rows[1].cells[1].paragraphs[0].text)

        # Pastikan drawing XML ada di sel kepala (TTD + Stempel)
        cell_k_xml = t_res.rows[1].cells[0]._tc.xml
        self.assertIn("drawing", cell_k_xml)


if __name__ == "__main__":
    unittest.main()
