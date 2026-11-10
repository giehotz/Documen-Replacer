"""
Unit test suite untuk Smart RPP Replacer (Fase 1).
"""
import unittest
import os
import shutil
from docx import Document

from core.placeholder_detector import (
    is_pure_placeholder,
    unwrap_parentheses,
    format_with_parentheses,
    find_placeholder_span,
    extract_label_and_placeholder,
)
from core.label_recognizer import match_category, load_aliases
from core.exact_matcher import build_exact_pattern
from core.replacement_engine import ReplacementEngine
from core.similarity_matcher import calculate_similarity, find_fuzzy_category_match
from core.validation_engine import validate_type_safety, evaluate_confidence, ConfidenceLevel, ReplacementPlanItem
from core.signature_image_service import (
    load_signature_settings,
    save_signature_settings,
    insert_signature_picture,
)
from services.report_service import ReportService
from document.paragraph_processor import replace_span, replace_by_pattern, replace_full_text_keep_style
from PIL import Image


class TestSignatureImageService(unittest.TestCase):
    def test_settings_persistence(self):
        temp_cfg = os.path.join(os.path.dirname(__file__), "temp_sig_cfg.json")
        try:
            data = {
                "enabled_kepala": True,
                "kepala_width_cm": 4.2,
                "offset_x_kepala_cm": 1.5,
                "offset_y_kepala_cm": -0.8,
                "behind_text": True,
            }
            save_signature_settings(data, temp_cfg)
            loaded = load_signature_settings(temp_cfg)
            self.assertTrue(loaded["enabled_kepala"])
            self.assertEqual(loaded["kepala_width_cm"], 4.2)
            self.assertEqual(loaded["offset_x_kepala_cm"], 1.5)
            self.assertEqual(loaded["offset_y_kepala_cm"], -0.8)
            self.assertTrue(loaded["behind_text"])
        finally:
            if os.path.isfile(temp_cfg):
                os.remove(temp_cfg)

    def test_insert_signature_picture_behind_text(self):
        temp_img = os.path.join(os.path.dirname(__file__), "temp_sig_behind.png")
        try:
            img = Image.new("RGBA", (120, 60), color=(0, 0, 255, 200))
            img.save(temp_img)

            doc = Document()
            p = doc.add_paragraph("Nama Pejabat")
            success = insert_signature_picture(
                p, temp_img, width_cm=3.5, alignment="CENTER",
                behind_text=True, offset_x_cm=1.2, offset_y_cm=-1.0
            )

            self.assertTrue(success)
            xml_str = p._element.xml
            self.assertIn("drawing", xml_str)
            self.assertIn("wp:anchor", xml_str)
            self.assertIn('behindDoc="1"', xml_str)
        finally:
            if os.path.isfile(temp_img):
                os.remove(temp_img)

    def test_insert_signature_picture(self):
        temp_img = os.path.join(os.path.dirname(__file__), "temp_sig_inline.png")
        try:
            img = Image.new("RGBA", (120, 60), color=(0, 0, 255, 200))
            img.save(temp_img)

            doc = Document()
            p = doc.add_paragraph("Nama Pejabat")
            p_img = p.insert_paragraph_before()
            success = insert_signature_picture(p_img, temp_img, width_cm=3.5, alignment="CENTER", behind_text=False)

            self.assertTrue(success)
            self.assertEqual(len(p_img.runs), 1)
            # Pastikan elemen drawing gambar ada di XML Word
            self.assertIn("drawing", p_img._element.xml)
            self.assertIn("wp:inline", p_img._element.xml)
        finally:
            if os.path.isfile(temp_img):
                os.remove(temp_img)


class TestFuzzyAndValidation(unittest.TestCase):
    def setUp(self):
        self.aliases = load_aliases()

    def test_fuzzy_typo_matching(self):
        # Typo "Kepal Sekolah" -> harus cocok ke "Nama Kepala"
        cat, score, al = find_fuzzy_category_match("Kepal Sekolah", self.aliases, threshold=0.80)
        self.assertEqual(cat, "Nama Kepala")
        self.assertGreaterEqual(score, 0.85)

        # Typo "Thn Pelajaran" -> harus cocok ke "Tahun Ajaran"
        cat2, score2, al2 = find_fuzzy_category_match("Thn Pelajaran", self.aliases, threshold=0.80)
        self.assertEqual(cat2, "Tahun Ajaran")
        self.assertGreaterEqual(score2, 0.80)

    def test_type_safety_boundary(self):
        # NIP menimpa paragraf naratif panjang harus ditolak
        long_narrative = "Peserta didik dapat mempraktikkan gerak dasar lompat jauh di lapangan sekolah secara mandiri."
        self.assertFalse(validate_type_safety("NIP Kepala", long_narrative, "197005272007011022"))

        # NIP menimpa titik-titik harus diterima
        dots_nip = "NIP. ........................................"
        self.assertTrue(validate_type_safety("NIP Kepala", dots_nip, "197005272007011022"))

        # NIP menimpa nomor lama harus diterima
        old_nip = "NIP. 196805121994031002"
        self.assertTrue(validate_type_safety("NIP Kepala", old_nip, "197005272007011022"))

    def test_report_service(self):
        rep = ReportService()
        rep.record_document("rpp1.docx", "SUCCESS", changes_count=6, cat_breakdown={"Nama Kepala": 1, "Nama Guru": 1})
        rep.record_document("rpp2.docx", "UNCHANGED", changes_count=0)
        rep.record_document("rpp3.docx", "FAILED", changes_count=0, error_msg="Corrupt file")

        text = rep.generate_summary_text()
        self.assertIn("Total dokumen dipindai : 3", text)
        self.assertIn("Berhasil diperbarui    : 1", text)
        self.assertIn("Tidak berubah          : 1", text)
        self.assertIn("Gagal diproses         : 1", text)
        self.assertIn("Nama Kepala", text)


class TestParagraphProcessor(unittest.TestCase):
    def test_run_preservation_across_split(self):
        doc = Document()
        p = doc.add_paragraph()
        r1 = p.add_run("SD ")
        r1.bold = True
        r2 = p.add_run("Negeri 1 Contoh")
        r2.italic = True

        compiled = build_exact_pattern([("SD Negeri 1 Contoh", "MIN 2 Tanggamus")])
        counters = {}
        changes = replace_by_pattern(p, compiled, counters)

        self.assertEqual(changes, 1)
        self.assertEqual(p.text, "MIN 2 Tanggamus")
        # Run pertama tetap mempertahankan format bold
        self.assertTrue(p.runs[0].bold)


class TestPlaceholderDetector(unittest.TestCase):
    def test_pure_placeholder(self):
        self.assertTrue(is_pure_placeholder("..............."))
        self.assertTrue(is_pure_placeholder("_________________"))
        self.assertTrue(is_pure_placeholder("( ................ )"))
        self.assertTrue(is_pure_placeholder("-"))
        self.assertFalse(is_pure_placeholder("Sipulloh, M.Pd"))
        self.assertFalse(is_pure_placeholder("197005272007011022"))

    def test_parentheses_handling(self):
        inner, had = unwrap_parentheses("( Sipulloh, M.Pd )")
        self.assertTrue(had)
        self.assertEqual(inner, "Sipulloh, M.Pd")

        inner2, had2 = unwrap_parentheses("Sipulloh, M.Pd")
        self.assertFalse(had2)
        self.assertEqual(inner2, "Sipulloh, M.Pd")

        formatted = format_with_parentheses("Sipulloh, M.Pd", True)
        self.assertEqual(formatted, "( Sipulloh, M.Pd )")

        formatted2 = format_with_parentheses("( Sipulloh, M.Pd )", True)
        self.assertEqual(formatted2, "( Sipulloh, M.Pd )")

    def test_extract_label_and_placeholder(self):
        line = "Nama Kepala Madrasah : ........................"
        res = extract_label_and_placeholder(line)
        self.assertIsNotNone(res)
        label_pfx, p_text, s, e = res
        self.assertEqual(label_pfx, "Nama Kepala Madrasah :")
        self.assertTrue("..." in p_text)
        self.assertEqual(line[s:e], p_text)


class TestLabelRecognizer(unittest.TestCase):
    def setUp(self):
        self.aliases = load_aliases()

    def test_category_matching(self):
        self.assertEqual(match_category("Kepala Madrasah", self.aliases), "Nama Kepala")
        self.assertEqual(match_category("NIP Kepala Sekolah", self.aliases), "NIP Kepala")
        self.assertEqual(match_category("Guru Kelas IV", self.aliases), "Nama Guru")
        self.assertEqual(match_category("Nama Guru Mata Pelajaran", self.aliases), "Nama Guru")
        self.assertEqual(match_category("NIP Guru Mata Pelajaran", self.aliases), "NIP Guru")
        self.assertEqual(match_category("Satuan Pendidikan", self.aliases), "Nama Madrasah")
        self.assertEqual(match_category("Tahun Pelajaran", self.aliases), "Tahun Ajaran")


class TestReplacementEngineEndToEnd(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.samples_dir = os.path.join(self.test_dir, "samples")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.engine = ReplacementEngine()

    def tearDown(self):
        if os.path.isdir(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_sample_dotted_table_smart_mode(self):
        in_file = os.path.join(self.samples_dir, "sample_rpp_dotted_table.docx")
        out_file = os.path.join(self.output_dir, "out_dotted.docx")

        rules = [
            {"label": "Nama Madrasah", "old": "SD Negeri 1 Contoh", "new": "MIN 2 Tanggamus"},
            {"label": "Tahun Ajaran", "old": "2025/2026", "new": "2026/2027"},
            {"label": "Nama Kepala", "old": "", "new": "Sipulloh, M.Pd"},
            {"label": "NIP Kepala", "old": "", "new": "197005272007011022"},
            {"label": "Nama Guru", "old": "", "new": "Misri Kurniati, S.Pd.I"},
            {"label": "NIP Guru", "old": "", "new": "197703232007102004"},
            {"label": "Titimangsa", "old": "", "new": "Tanggamus, 13 Juli 2026"},
        ]

        changes = self.engine.process_file(in_file, out_file, rules, mode="GABUNGAN")
        self.assertGreater(changes, 0)

        # Verifikasi konten dokumen hasil
        out_doc = Document(out_file)
        full_text = []
        for p in out_doc.paragraphs:
            full_text.append(p.text)
        for t in out_doc.tables:
            for r in t.rows:
                for c in r.cells:
                    full_text.append(c.text)
        doc_str = "\n".join(full_text)

        self.assertIn("MIN 2 Tanggamus", doc_str)
        self.assertIn("2026/2027", doc_str)
        self.assertIn("( Sipulloh, M.Pd )", doc_str)
        self.assertIn("197005272007011022", doc_str)
        self.assertIn("( Misri Kurniati, S.Pd.I )", doc_str)
        self.assertIn("197703232007102004", doc_str)
        self.assertIn("Tanggamus, 13 Juli 2026", doc_str)

    def test_sample_existing_names_smart_mode(self):
        in_file = os.path.join(self.samples_dir, "sample_rpp_existing_names.docx")
        out_file = os.path.join(self.output_dir, "out_existing.docx")

        rules = [
            {"label": "Nama Madrasah", "old": "", "new": "MIN 1 Bandar Lampung"},
            {"label": "Tahun Ajaran", "old": "", "new": "2025/2026"},
            {"label": "Nama Kepala", "old": "", "new": "Sipulloh, M.Pd"},
            {"label": "NIP Kepala", "old": "", "new": "197005272007011022"},
            {"label": "Nama Guru", "old": "", "new": "Misri Kurniati, S.Pd.I"},
            {"label": "NIP Guru", "old": "", "new": "197703232007102004"},
            {"label": "Titimangsa", "old": "", "new": "Kotaagung, 10 Agustus 2026"},
        ]

        changes = self.engine.process_file(in_file, out_file, rules, mode="GABUNGAN")
        self.assertGreater(changes, 0)

        out_doc = Document(out_file)
        full_text = []
        for t in out_doc.tables:
            for r in t.rows:
                for c in r.cells:
                    full_text.append(c.text)
        doc_str = "\n".join(full_text)

        self.assertIn("MIN 1 Bandar Lampung", doc_str)
        self.assertIn("( Sipulloh, M.Pd )", doc_str)
        self.assertIn("197005272007011022", doc_str)
        self.assertIn("( Misri Kurniati, S.Pd.I )", doc_str)
        self.assertIn("197703232007102004", doc_str)

    def test_sample_tab_signature_smart_mode(self):
        in_file = os.path.join(self.samples_dir, "sample_rpp_tab_signature.docx")
        out_file = os.path.join(self.output_dir, "out_tab.docx")

        rules = [
            {"label": "Nama Guru", "old": "", "new": "Misri Kurniati, S.Pd.I"},
            {"label": "Nama Kepala", "old": "", "new": "Sipulloh, M.Pd"},
            {"label": "NIP Kepala", "old": "", "new": "197005272007011022"},
            {"label": "NIP Guru", "old": "", "new": "197703232007102004"},
            {"label": "Titimangsa", "old": "", "new": "Tanggamus, 20 Juli 2026"},
        ]

        changes = self.engine.process_file(in_file, out_file, rules, mode="GABUNGAN")
        self.assertGreater(changes, 0)

        out_doc = Document(out_file)
        full_text = "\n".join(p.text for p in out_doc.paragraphs)

        self.assertIn("Misri Kurniati, S.Pd.I", full_text)
        self.assertIn("Sipulloh, M.Pd", full_text)
        self.assertIn("197005272007011022", full_text)
        self.assertIn("197703232007102004", full_text)
        self.assertIn("Tanggamus, 20 Juli 2026", full_text)

    def test_sample_underline_smart_mode(self):
        in_file = os.path.join(self.samples_dir, "sample_rpp_underline.docx")
        out_file = os.path.join(self.output_dir, "out_underline.docx")

        rules = [
            {"label": "Nama Kepala", "old": "", "new": "Sipulloh, M.Pd"},
            {"label": "NIP Kepala", "old": "", "new": "197005272007011022"},
            {"label": "Nama Guru", "old": "", "new": "Misri Kurniati, S.Pd.I"},
        ]

        changes = self.engine.process_file(in_file, out_file, rules, mode="GABUNGAN")
        self.assertGreater(changes, 0)

        out_doc = Document(out_file)
        full_text = "\n".join(p.text for p in out_doc.paragraphs)

        self.assertIn("Sipulloh, M.Pd", full_text)
        self.assertIn("197005272007011022", full_text)
        self.assertIn("Misri Kurniati, S.Pd.I", full_text)

    def test_signature_only_mode_preserves_text_and_inserts_images(self):
        """Uji mode SIGNATURE_ONLY: teks dokumen 100% utuh dan gambar tanda tangan terpasang."""
        from PIL import Image

        # 1. Buat dokumen tiruan yang sudah terlanjur diedit sebelumnya
        doc = Document()
        doc.add_heading("RPP PJOK - Sudah Diedit", level=1)
        p_intro = doc.add_paragraph("Kompetensi Dasar PJOK Kelas 4 semester ganjil.")

        table = doc.add_table(rows=5, cols=2)
        # Kolom 0: Kepala
        table.rows[0].cells[0].paragraphs[0].text = "Mengetahui,"
        table.rows[1].cells[0].paragraphs[0].text = "Kepala Madrasah"
        table.rows[2].cells[0].paragraphs[0].text = ""  # Ruang kosong tanda tangan
        p_k = table.rows[3].cells[0].paragraphs[0]
        p_k.text = "Sipulloh, M.Pd"
        p_k.runs[0].bold = True
        table.rows[4].cells[0].paragraphs[0].text = "NIP. 197005272007011022"

        # Kolom 1: Guru
        table.rows[0].cells[1].paragraphs[0].text = "Tanggamus, 13 Juli 2026"
        table.rows[1].cells[1].paragraphs[0].text = "Guru PJOK"
        table.rows[2].cells[1].paragraphs[0].text = ""  # Ruang kosong tanda tangan
        p_g = table.rows[3].cells[1].paragraphs[0]
        p_g.text = "Misri Kurniati, S.Pd.I"
        p_g.runs[0].bold = True
        table.rows[4].cells[1].paragraphs[0].text = "NIP. 197703232007102004"

        in_file = os.path.join(self.output_dir, "doc_already_edited.docx")
        out_file = os.path.join(self.output_dir, "doc_with_signatures_only.docx")
        doc.save(in_file)

        # 2. Buat gambar tanda tangan dummy
        img_k_path = os.path.join(self.output_dir, "dummy_sig_k.png")
        img_g_path = os.path.join(self.output_dir, "dummy_sig_g.png")
        Image.new("RGBA", (100, 50), color=(0, 0, 255, 255)).save(img_k_path)
        Image.new("RGBA", (100, 50), color=(255, 0, 0, 255)).save(img_g_path)

        # 3. Konfigurasi signature settings
        sig_settings = {
            "enabled_kepala": True,
            "kepala_image_path": img_k_path,
            "kepala_width_cm": 3.0,
            "enabled_guru": True,
            "guru_image_path": img_g_path,
            "guru_width_cm": 3.0,
            "alignment": "CENTER",
            "spacing_before_pt": 2,
            "spacing_after_pt": 2,
        }
        self.engine.signature_settings = sig_settings

        # 4. Rencanakan perubahan (planning phase) dengan mode SIGNATURE_ONLY
        items = self.engine.plan_document_changes(
            in_file,
            "doc_already_edited.docx",
            rules=[],  # Kosong karena mode tanda tangan saja
            mode="SIGNATURE_ONLY"
        )

        self.assertEqual(len(items), 2)
        categories = [it.category for it in items]
        self.assertIn("Tanda Tangan Kepala", categories)
        self.assertIn("Tanda Tangan Guru", categories)

        for it in items:
            self.assertEqual(it.target_type, "INSERT_SIGNATURE_TABLE")
            self.assertTrue(it.is_approved)
            self.assertEqual(it.confidence, "HIGH")

        # 5. Terapkan perubahan
        changes = self.engine.apply_approved_changes(
            in_file,
            out_file,
            items,
            signature_settings=sig_settings
        )
        self.assertEqual(changes, 2)

        # 6. Validasi file keluaran: teks tidak berubah sama sekali, gambar tersisip
        out_doc = Document(out_file)
        out_table = out_doc.tables[0]

        # Teks tetap sama persis
        self.assertEqual(out_table.rows[1].cells[0].text.strip(), "Kepala Madrasah")
        self.assertEqual(out_table.rows[3].cells[0].text.strip(), "Sipulloh, M.Pd")
        self.assertEqual(out_table.rows[4].cells[0].text.strip(), "NIP. 197005272007011022")

        self.assertEqual(out_table.rows[0].cells[1].text.strip(), "Tanggamus, 13 Juli 2026")
        self.assertEqual(out_table.rows[1].cells[1].text.strip(), "Guru PJOK")
        self.assertEqual(out_table.rows[3].cells[1].text.strip(), "Misri Kurniati, S.Pd.I")
        self.assertEqual(out_table.rows[4].cells[1].text.strip(), "NIP. 197703232007102004")

        # Pastikan elemen drawing gambar ada di dalam tabel
        xml_table = out_table._tbl.xml
        self.assertIn("w:drawing", xml_table)

    def test_replacement_view_ui_signature_only_toggle(self):
        """Uji UI ReplacementView: saat mode SIGNATURE_ONLY dipilih, kolom dinonaktifkan (disabled)."""
        import tkinter as tk
        from gui.replacement_view import ReplacementView

        root = tk.Tk()
        root.withdraw()
        try:
            view = ReplacementView(root)
            # Default awal GABUNGAN -> normal
            self.assertEqual(str(view.btn_add_row["state"]), "normal")
            self.assertEqual(str(view.btn_save_preset["state"]), "normal")
            self.assertEqual(str(view.btn_load_preset["state"]), "normal")
            self.assertEqual(str(view.btn_sig_designer["state"]), "normal")
            for item in view.rows_data:
                self.assertEqual(str(item[0]["state"]), "normal")
                self.assertEqual(str(item[1]["state"]), "normal")
                self.assertEqual(str(item[2]["state"]), "normal")
                self.assertEqual(str(item[4]["state"]), "normal")

            # Ubah ke SIGNATURE_ONLY
            view.search_mode_var.set("SIGNATURE_ONLY")
            view._on_mode_changed()

            self.assertEqual(str(view.btn_add_row["state"]), "disabled")
            self.assertEqual(str(view.btn_save_preset["state"]), "disabled")
            self.assertEqual(str(view.btn_load_preset["state"]), "disabled")
            self.assertEqual(str(view.btn_sig_designer["state"]), "normal")  # Tombol TTD tetap aktif
            for item in view.rows_data:
                self.assertEqual(str(item[0]["state"]), "disabled")
                self.assertEqual(str(item[1]["state"]), "disabled")
                self.assertEqual(str(item[2]["state"]), "disabled")
                self.assertEqual(str(item[4]["state"]), "disabled")

            # Kembalikan ke GABUNGAN
            view.search_mode_var.set("GABUNGAN")
            view._on_mode_changed()

            self.assertEqual(str(view.btn_add_row["state"]), "normal")
            self.assertEqual(str(view.btn_save_preset["state"]), "normal")
            for item in view.rows_data:
                self.assertEqual(str(item[0]["state"]), "normal")
                self.assertEqual(str(item[1]["state"]), "normal")
        finally:
            root.destroy()

    def test_atomic_save_document(self):
        """Uji penyimpanan berkas secara atomik tanpa menyisakan berkas sementara."""
        from document.docx_writer import save_document
        doc = Document()
        doc.add_paragraph("Uji simpan atomik")
        out_path = os.path.join(self.output_dir, "test_atomic.docx")
        save_document(doc, out_path)

        self.assertTrue(os.path.isfile(out_path))
        # Pastikan tidak ada sisa file .tmp.docx
        dir_files = os.listdir(self.output_dir)
        tmp_files = [f for f in dir_files if f.endswith(".tmp.docx")]
        self.assertEqual(len(tmp_files), 0)

    def test_header_footer_replacement(self):
        """Uji penggantian exact match pada header dan footer dokumen."""
        doc = Document()
        sec = doc.sections[0]
        sec.header.paragraphs[0].text = "RPP PJOK - SD Negeri 1 Contoh"
        sec.footer.paragraphs[0].text = "Tahun Ajaran 2025/2026 - SD Negeri 1 Contoh"
        doc.add_paragraph("Isi paragraf biasa.")

        test_in = os.path.join(self.output_dir, "doc_with_header.docx")
        test_out = os.path.join(self.output_dir, "doc_with_header_out.docx")
        doc.save(test_in)

        rules = [
            {"label": "Nama Sekolah", "old": "SD Negeri 1 Contoh", "new": "MIN 2 Tanggamus"},
            {"label": "Tahun Ajaran", "old": "2025/2026", "new": "2026/2027"},
        ]

        # Rencanakan perubahan
        items = self.engine.plan_document_changes(test_in, "doc_with_header.docx", rules, mode="GABUNGAN")
        hf_items = [it for it in items if it.target_type == "HEADER_FOOTER"]
        self.assertGreaterEqual(len(hf_items), 2)

        # Terapkan perubahan
        changes = self.engine.apply_approved_changes(test_in, test_out, items)
        self.assertGreaterEqual(changes, 2)

        out_doc = Document(test_out)
        out_sec = out_doc.sections[0]
        self.assertIn("MIN 2 Tanggamus", out_sec.header.paragraphs[0].text)
        self.assertIn("MIN 2 Tanggamus", out_sec.footer.paragraphs[0].text)
        self.assertIn("2026/2027", out_sec.footer.paragraphs[0].text)

    def test_tab_line_contract_respects_approval(self):
        """Uji K2: Blok tanda tangan tabulasi hanya menerapkan item TAB_LINE yang disetujui."""
        doc = Document()
        p1 = doc.add_paragraph("Mengetahui,\t\t\t\tTanggamus, 10 Juli 2026")
        p2 = doc.add_paragraph("Kepala Sekolah\t\t\t\tGuru Kelas")
        p3 = doc.add_paragraph("Sipulloh, M.Pd\t\t\t\tMisri Kurniati, S.Pd.I")

        test_in = os.path.join(self.output_dir, "doc_tab_approval.docx")
        test_out = os.path.join(self.output_dir, "doc_tab_approval_out.docx")
        doc.save(test_in)

        rules = [
            {"label": "Nama Kepala", "old": "", "new": "H. Ahmad, M.Pd"},
            {"label": "Nama Guru", "old": "", "new": "Siti Rahma, S.Pd"},
        ]

        items = self.engine.plan_document_changes(test_in, "doc_tab_approval.docx", rules, mode="GABUNGAN")
        tab_items = [it for it in items if it.target_type == "TAB_LINE"]
        self.assertGreaterEqual(len(tab_items), 2)

        # Setujui Kepala, TOLAK Guru
        for it in tab_items:
            if it.category == "Nama Kepala":
                it.is_approved = True
            elif it.category == "Nama Guru":
                it.is_approved = False

        self.engine.apply_approved_changes(test_in, test_out, tab_items)

        out_doc = Document(test_out)
        paras = [p.text for p in out_doc.paragraphs]
        name_line = paras[2]

        # Kepala berubah
        self.assertIn("H. Ahmad, M.Pd", name_line)
        # Guru TIDAK berubah karena ditolak user
        self.assertIn("Misri Kurniati, S.Pd.I", name_line)
        self.assertNotIn("Siti Rahma, S.Pd", name_line)

    def test_double_counting_elimination(self):
        """Uji T1: TABLE_CELL_PARA dengan penyisipan gambar hanya dihitung 1 kali per item."""
        temp_img = os.path.join(self.output_dir, "temp_cnt_sig.png")
        Image.new("RGBA", (100, 50), color=(0, 0, 255, 200)).save(temp_img)

        doc = Document()
        table = doc.add_table(rows=3, cols=2)
        table.rows[0].cells[0].paragraphs[0].text = "Mengetahui,"
        table.rows[1].cells[0].paragraphs[0].text = "Kepala Sekolah"
        table.rows[2].cells[0].paragraphs[0].text = "Nama Asli Lama"

        test_in = os.path.join(self.output_dir, "doc_count.docx")
        test_out = os.path.join(self.output_dir, "doc_count_out.docx")
        doc.save(test_in)

        sig_cfg = {
            "enabled_kepala": True,
            "kepala_image_path": temp_img,
            "kepala_width_cm": 3.0,
            "behind_text": True,
        }

        # Buat plan item 1 buah untuk Nama Kepala
        plan_item = ReplacementPlanItem(
            doc_path=test_in,
            rel_path="doc_count.docx",
            category="Nama Kepala",
            old_text="Nama Asli Lama",
            new_text="Sipulloh, M.Pd",
            confidence=ConfidenceLevel.HIGH,
            location_info="Tabel",
            is_approved=True,
            target_type="TABLE_CELL_PARA",
            target_meta={"table_idx": 0, "row_idx": 2, "col_idx": 0, "para_idx": 0}
        )

        changes = self.engine.apply_approved_changes(test_in, test_out, [plan_item], signature_settings=sig_cfg)
        # Harus tepat 1, BUKAN 2!
        self.assertEqual(changes, 1)


if __name__ == "__main__":
    unittest.main()
