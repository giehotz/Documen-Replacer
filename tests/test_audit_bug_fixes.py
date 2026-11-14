"""
Unit Test untuk 5 Bug Hasil Audit Sesuai prompt_perbaikan_audit_bug_smart_rpp_replacer.md:
1. Bug 2: Sinkronisasi ruang indeks paragraf (EXACT & PARAGRAPH_SPAN) & verifier verdict OK
2. Bug 3: Tanda tangan TAB_LINE persetujuan per-blok & pelestarian kolom tengah
3. Bug 4: Resolusi tumpang tindih transitif pada _deduplicate_and_resolve_overlaps
4. Bug 5: Thread safety pada _worker_apply tanpa pemanggilan method GUI
5. Bug 6: Dukungan 6 varian header/footer (first_page_header, dll.) dan tabel kop surat
"""
import unittest
import os
import shutil
import tempfile
from docx import Document
from docx.shared import Inches

from core.replacement_engine import ReplacementEngine
from core.validation_engine import ReplacementPlanItem, ConfidenceLevel
from core.change_verifier import ChangeReportGenerator
from core.field_dictionary import FieldDictionary


class TestAuditBugFixes(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dict = FieldDictionary.load()
        self.engine = ReplacementEngine(field_dictionary=self.dict)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_bug2_canonical_index_and_verifier_ok(self):
        """Memastikan EXACT dan PARAGRAPH_SPAN pada paragraf body setelah tabel terdeduplikasi dan verifier menghasilkan OK."""
        doc_path = os.path.join(self.test_dir, "test_table_before_para.docx")
        doc = Document()
        doc.add_paragraph("Pengantar Dokumen")
        tbl = doc.add_table(rows=2, cols=2)
        tbl.rows[0].cells[0].text = "Identitas 1"
        tbl.rows[0].cells[1].text = "Nilai 1"
        tbl.rows[1].cells[0].text = "Identitas 2"
        tbl.rows[1].cells[1].text = "Nilai 2"
        # Paragraf root body ke-1 (tapi di iter_all_paragraphs indeks ke-5)
        doc.add_paragraph("Tahun Pelajaran : 2025/2026")
        doc.save(doc_path)

        rules = [
            {"label": "Tahun Pelajaran", "old": "2025/2026", "new": "2026/2027"}
        ]
        plan_items = self.engine.plan_document_changes(doc_path, "test.docx", rules, mode="GABUNGAN", case_sensitive=True)

        # Harus terdeduplikasi: hanya ada 1 item rencana untuk 'Tahun Pelajaran' pada paragraf tersebut
        tp_items = [it for it in plan_items if "Tahun Pelajaran" in it.category or "2025/2026" in it.old_text]
        self.assertEqual(len(tp_items), 1)

        # Terapkan perubahan
        out_dir = os.path.join(self.test_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "test.docx")
        changes = self.engine.apply_approved_changes(doc_path, out_path, plan_items)
        self.assertGreaterEqual(changes, 1)

        # Verifikasi laporan perubahan mekanis & semantik
        verifier = ChangeReportGenerator()
        report_path, report = verifier.generate_report(
            output_dir=out_dir,
            input_dir=self.test_dir,
            plan_items=plan_items,
            rules=rules,
            mode="GABUNGAN"
        )
        self.assertIn("perubahan", report)
        self.assertEqual(len(report["perubahan"]), 1)
        # Verifier WAJIB berstatus OK (bukan SALAH)
        self.assertEqual(report["perubahan"][0]["verifikasi"]["verdict"], "OK")

    def test_bug3_tab_signature_per_block_and_middle_preserved(self):
        """Memastikan penolakan blok ke-2 tidak tertimpa dan segmen kolom tengah tetap utuh."""
        doc_path = os.path.join(self.test_dir, "test_tab_sigs.docx")
        doc = Document()
        # Blok 1
        doc.add_paragraph("Mengetahui\t\t\t\tJakarta, 15 Juli 2025")
        doc.add_paragraph("Kepala Sekolah\t\t\t\tGuru Kelas")
        doc.add_paragraph("Budi Santoso, M.Pd\t\t\t\tSiti Aminah, S.Pd")
        doc.add_paragraph("NIP. 198001012005011001\t\t\t\tNIP. 198502022010012002")

        doc.add_paragraph("--- Pembatas Antar Halaman ---")

        # Blok 2 dengan kolom tengah
        doc.add_paragraph("Mengetahui\t[TENGAH 1]\tJakarta, 15 Juli 2025")
        doc.add_paragraph("Kepala Sekolah\t[TENGAH 2]\tGuru Kelas")
        doc.add_paragraph("Budi Santoso, M.Pd\t[TENGAH 3]\tSiti Aminah, S.Pd")
        doc.add_paragraph("NIP. 198001012005011001\t[TENGAH 4]\tNIP. 198502022010012002")

        doc.save(doc_path)

        rules = [
            {"label": "Nama Kepala", "old": "", "new": "Ahmad Dahlan, M.Pd"},
            {"label": "Nama Guru", "old": "", "new": "Fatimah, S.Pd"},
        ]
        plan_items = self.engine.plan_document_changes(doc_path, "test.docx", rules, mode="GABUNGAN")
        tab_items = [it for it in plan_items if it.target_type == "TAB_LINE"]
        self.assertGreater(len(tab_items), 0)

        # Setujui HANYA item dari Blok 1 (indeks paragraf < 4)
        for it in tab_items:
            para_idx = it.target_meta.get("para_idx", 0)
            if para_idx >= 5:
                it.is_approved = False  # Tolak Blok 2!

        out_path = os.path.join(self.test_dir, "out_tab_sigs.docx")
        self.engine.apply_approved_changes(doc_path, out_path, plan_items)

        res_doc = Document(out_path)
        paras = [p.text for p in res_doc.paragraphs]

        # Blok 1 harus terupdate dengan nama baru
        self.assertIn("Ahmad Dahlan, M.Pd", paras[2])
        self.assertIn("Fatimah, S.Pd", paras[2])

        # Blok 2 harus TETAP nama lama karena DITOLAK
        self.assertIn("Budi Santoso, M.Pd", paras[7])
        self.assertIn("Siti Aminah, S.Pd", paras[7])
        # Kolom tengah [TENGAH 3] tidak boleh terhapus!
        self.assertIn("[TENGAH 3]", paras[7])

    def test_bug4_transitive_overlap_resolution(self):
        """Memastikan kandidat yang mengalahkan 2 item beririsan menghapus kedua item lama."""
        doc_path = "dummy.docx"
        # Item 1: "Tahun" di [0, 5]
        item1 = ReplacementPlanItem(
            doc_path=doc_path, rel_path="d", category="C1", old_text="Tahun", new_text="Thn",
            confidence=ConfidenceLevel.HIGH, location_info="P #0", is_approved=True, target_type="PARAGRAPH_SPAN",
            target_meta={"start": 0, "end": 5, "original_text": "Tahun Pelajaran 2025"}
        )
        # Item 2: "2025" di [16, 20]
        item2 = ReplacementPlanItem(
            doc_path=doc_path, rel_path="d", category="C2", old_text="2025", new_text="2026",
            confidence=ConfidenceLevel.HIGH, location_info="P #0", is_approved=True, target_type="PARAGRAPH_SPAN",
            target_meta={"start": 16, "end": 20, "original_text": "Tahun Pelajaran 2025"}
        )
        # Kandidat EXACT panjang yang menjembatani: "Tahun Pelajaran 2025" di [0, 20]
        candidate = ReplacementPlanItem(
            doc_path=doc_path, rel_path="d", category="Pencocokan Persis",
            old_text="Tahun Pelajaran 2025", new_text="Tahun Ajaran 2026/2027",
            confidence=ConfidenceLevel.HIGH, location_info="P #0", is_approved=True, target_type="EXACT",
            target_meta={"start": 0, "end": 20, "original_text": "Tahun Pelajaran 2025"}
        )

        resolved = self.engine._deduplicate_and_resolve_overlaps([item1, item2, candidate])
        # Hanya candidate yang boleh bertahan karena mengalahkan item1 dan item2
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].old_text, "Tahun Pelajaran 2025")

    def test_bug5_worker_apply_accepts_rules_and_mode(self):
        """Memastikan _worker_apply menerima rules dan mode tanpa memanggil GUI method."""
        from gui.app import SmartRPPReplacerApp
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            app = SmartRPPReplacerApp(root)
            rules = [{"label": "Nama Madrasah", "old": "MIN 1", "new": "MIN 2"}]
            mode = "GABUNGAN"

            # Buat file sampel
            sample_in = os.path.join(self.test_dir, "sample.docx")
            doc = Document()
            doc.add_paragraph("MIN 1")
            doc.save(sample_in)

            out_dir = os.path.join(self.test_dir, "out_worker")
            # Panggil _worker_apply langsung dengan parameter
            app._worker_apply(
                files=[(sample_in, "sample.docx")],
                out_dir=out_dir,
                plan_items=[],
                rules=rules,
                mode=mode
            )
            # Pastikan queue menerima ("done", out_dir)
            messages = []
            while not app.msg_queue.empty():
                messages.append(app.msg_queue.get_nowait())
            has_done = any(m[0] == "done" for m in messages)
            self.assertTrue(has_done)
        finally:
            root.destroy()

    def test_bug6_header_footer_variants_and_tables(self):
        """Memastikan header halaman pertama dan tabel di dalam header ikut terdeteksi dan diganti."""
        doc_path = os.path.join(self.test_dir, "test_headers.docx")
        doc = Document()
        sec = doc.sections[0]
        sec.different_first_page_header_footer = True

        # Header halaman pertama
        first_hdr = sec.first_page_header
        first_hdr.is_linked_to_previous = False
        p_first = first_hdr.paragraphs[0]
        p_first.text = "Kop Surat: MIN 1 Contoh - Halaman Pertama"

        # Header normal memiliki tabel kop surat
        hdr = sec.header
        hdr.is_linked_to_previous = False
        tbl = hdr.add_table(rows=1, cols=1, width=Inches(6))
        tbl.rows[0].cells[0].text = "Tabel Kop: MIN 1 Contoh"

        doc.add_paragraph("Isi Dokumen Body")
        doc.save(doc_path)

        rules = [
            {"label": "Nama Madrasah", "old": "MIN 1 Contoh", "new": "MIN 2 Contoh"}
        ]
        plan_items = self.engine.plan_document_changes(doc_path, "test.docx", rules, mode="GABUNGAN")
        hf_items = [it for it in plan_items if it.target_type == "HEADER_FOOTER"]

        # Harus menemukan di first_page_header dan tabel di header
        self.assertEqual(len(hf_items), 2)

        out_path = os.path.join(self.test_dir, "out_headers.docx")
        changes = self.engine.apply_approved_changes(doc_path, out_path, plan_items)
        self.assertEqual(changes, 2)

        res_doc = Document(out_path)
        res_first = res_doc.sections[0].first_page_header.paragraphs[0].text
        self.assertIn("MIN 2 Contoh", res_first)

        res_tbl_txt = res_doc.sections[0].header.tables[0].rows[0].cells[0].text
        self.assertIn("MIN 2 Contoh", res_tbl_txt)


if __name__ == "__main__":
    unittest.main()
