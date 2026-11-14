"""
Unit Test untuk Fitur Live Log Pemindaian & Prediksi Dokumen.
Menguji:
1. Callback log_callback pada predict_rules_from_file
2. Callback progress_callback dan log_callback pada predict_rules_from_folder
3. Penghentian pemindaian aman (graceful cancel) dengan cancel_event
4. Callback log_callback dan cancel_event pada collect_unknown_labels
"""
import unittest
import os
import shutil
import tempfile
import threading
from typing import List, Tuple

from core.document_predictor import (
    predict_rules_from_file,
    predict_rules_from_folder,
    collect_unknown_labels,
)


class TestPredictionLiveLog(unittest.TestCase):
    def setUp(self):
        samples_dir = os.path.join(os.path.dirname(__file__), "samples")
        os.makedirs(samples_dir, exist_ok=True)
        self.doc_bab1 = os.path.join(samples_dir, "sample_bab1.docx")
        self.doc_modul = os.path.join(samples_dir, "sample_modul_ajar.docx")

        if not os.path.exists(self.doc_bab1):
            from tests.generate_samples import create_sample_bab1
            create_sample_bab1(self.doc_bab1)
        if not os.path.exists(self.doc_modul):
            from tests.generate_samples import create_sample_modul_ajar
            create_sample_modul_ajar(self.doc_modul)

        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_predict_from_file_with_log_callback(self):
        """Memastikan predict_rules_from_file mengirimkan live log saat menganalisis berkas."""
        logs: List[str] = []

        def log_cb(msg: str):
            logs.append(msg)

        rules = predict_rules_from_file(self.doc_modul, log_callback=log_cb)
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)
        self.assertGreater(len(logs), 0)

        # Cek apakah ada log awal pembacaan file
        has_file_start = any("[FILE] Memindai dokumen:" in l for l in logs)
        self.assertTrue(has_file_start)

        # Cek apakah ada entitas yang terdeteksi dicatat dalam log
        has_detection = any("✔" in l for l in logs)
        self.assertTrue(has_detection)

        # Cek log penyelesaian
        has_done = any("Selesai memindai" in l for l in logs)
        self.assertTrue(has_done)

    def test_predict_from_folder_with_progress_and_logs(self):
        """Memastikan predict_rules_from_folder mengirimkan progress dan live log ke callback."""
        # Salin 2 berkas sampel ke direktori uji coba
        shutil.copy2(self.doc_bab1, os.path.join(self.test_dir, "doc1.docx"))
        shutil.copy2(self.doc_modul, os.path.join(self.test_dir, "doc2.docx"))

        progress_records: List[Tuple[int, int, str]] = []
        logs: List[str] = []

        def prog_cb(cur: int, tot: int, fname: str):
            progress_records.append((cur, tot, fname))

        def log_cb(msg: str):
            logs.append(msg)

        rules = predict_rules_from_folder(
            self.test_dir,
            progress_callback=prog_cb,
            log_callback=log_cb,
        )

        self.assertGreater(len(rules), 0)
        # Harus ada 2 berkas diproses
        self.assertEqual(len(progress_records), 2)
        self.assertEqual(progress_records[0][0], 1)
        self.assertEqual(progress_records[0][1], 2)
        self.assertEqual(progress_records[1][0], 2)
        self.assertEqual(progress_records[1][1], 2)

        # Cek log awal dan akhir folder
        self.assertTrue(any("[START] Ditemukan 2 berkas Word" in l for l in logs))
        self.assertTrue(any("[DONE] Pemindaian selesai" in l for l in logs))

    def test_predict_from_folder_graceful_cancel(self):
        """Memastikan pembatalan aman (cancel_event) menghentikan proses tanpa kehilangan aturan awal."""
        # Salin 3 berkas sampel
        shutil.copy2(self.doc_bab1, os.path.join(self.test_dir, "doc1.docx"))
        shutil.copy2(self.doc_modul, os.path.join(self.test_dir, "doc2.docx"))
        shutil.copy2(self.doc_bab1, os.path.join(self.test_dir, "doc3.docx"))

        cancel_evt = threading.Event()
        progress_records: List[Tuple[int, int, str]] = []
        logs: List[str] = []

        def prog_cb(cur: int, tot: int, fname: str):
            progress_records.append((cur, tot, fname))
            # Batalkan setelah berkas pertama selesai
            if cur >= 1:
                cancel_evt.set()

        def log_cb(msg: str):
            logs.append(msg)

        rules = predict_rules_from_folder(
            self.test_dir,
            progress_callback=prog_cb,
            log_callback=log_cb,
            cancel_event=cancel_evt,
        )

        # Harus mengembalikan hasil dari berkas 1 tanpa crash
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)
        # Iterasi tidak mencapai berkas 3
        self.assertLess(len(progress_records), 3)
        self.assertTrue(any("[CANCEL]" in l for l in logs))

    def test_collect_unknown_labels_with_callbacks(self):
        """Memastikan collect_unknown_labels menerima log_callback dan cancel_event."""
        logs: List[str] = []
        cancel_evt = threading.Event()

        def log_cb(msg: str):
            logs.append(msg)

        unknowns = collect_unknown_labels(
            self.doc_modul,
            log_callback=log_cb,
            cancel_event=cancel_evt,
        )
        self.assertIsInstance(unknowns, dict)

    def test_prediction_summary_dialog_instantiation(self):
        """Memastikan PredictionSummaryDialog terinisialisasi dan fungsi on_apply bekerja."""
        import tkinter as tk
        from unittest.mock import patch
        from gui.prediction_summary_dialog import PredictionSummaryDialog

        root = tk.Tk()
        root.withdraw()
        try:
            dummy_rules = [
                {"label": "Nama Madrasah", "old": "MIN 1 Contoh", "new": "MIN 2 Contoh"},
                {"label": "Tahun Pelajaran", "old": "2025/2026", "new": "2026/2027"},
            ]
            dummy_unknowns = {"Tujuan Pembelajaran": 5, "Alur Tujuan": 2}
            applied_rules = []

            def on_apply(r):
                applied_rules.extend(r)

            with patch("gui.prediction_summary_dialog.messagebox.showinfo"):
                dlg = PredictionSummaryDialog(
                    parent=root,
                    target_path=self.test_dir,
                    is_folder=True,
                    rules=dummy_rules,
                    unknown_labels=dummy_unknowns,
                    on_apply=on_apply
                )

                # Verifikasi metrik dan treeview
                self.assertEqual(len(dlg.tree_rules.get_children()), 2)
                self.assertEqual(len(dlg.tree_unk.get_children()), 2)

                # Uji tombol terapkan
                dlg._on_apply_click()
                self.assertEqual(len(applied_rules), 2)
                self.assertEqual(applied_rules[0]["label"], "Nama Madrasah")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
