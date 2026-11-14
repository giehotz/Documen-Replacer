"""
Unit test untuk verifikasi pemrosesan berkas tunggal (.docx / .doc) secara langsung.
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from gui.app import SmartRPPReplacerApp, resolve_output_subfolder


class TestSingleFileProcessing(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sample_docx = os.path.join(self.test_dir, "Contoh_RPP.docx")
        with open(self.sample_docx, "wb") as f:
            f.write(b"dummy docx content")

        self.sample_doc = os.path.join(self.test_dir, "Arsip_Lama.doc")
        with open(self.sample_doc, "wb") as f:
            f.write(b"dummy doc content")

        self.sample_txt = os.path.join(self.test_dir, "catatan.txt")
        with open(self.sample_txt, "wb") as f:
            f.write(b"dummy txt content")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_resolve_output_subfolder_for_file_and_directory(self):
        """Memastikan resolve_output_subfolder menghasilkan subfolder yang konsisten antara folder dan berkas di dalamnya."""
        folder_path = os.path.join("C:", os.sep, "Sekolah", "RPP_Kelas_4")
        file_path = os.path.join("C:", os.sep, "Sekolah", "RPP_Kelas_4", "Modul_1.docx")

        expected_subfolder = os.path.join("Sekolah", "RPP_Kelas_4")
        self.assertEqual(resolve_output_subfolder(folder_path), expected_subfolder)
        self.assertEqual(resolve_output_subfolder(file_path), expected_subfolder)
        self.assertEqual(resolve_output_subfolder(file_path), resolve_output_subfolder(folder_path))

    def test_collect_files_single_file(self):
        """Memastikan _collect_files mengembalikan list 1 tuple saat target berupa berkas tunggal yang didukung."""
        mock_app = MagicMock(spec=SmartRPPReplacerApp)

        # 1. File .docx
        res_docx = SmartRPPReplacerApp._collect_files(mock_app, self.sample_docx, self.test_dir, recursive=False)
        self.assertEqual(len(res_docx), 1)
        self.assertEqual(res_docx[0], (self.sample_docx, "Contoh_RPP.docx"))

        # 2. File .doc
        res_doc = SmartRPPReplacerApp._collect_files(mock_app, self.sample_doc, self.test_dir, recursive=False)
        self.assertEqual(len(res_doc), 1)
        self.assertEqual(res_doc[0], (self.sample_doc, "Arsip_Lama.doc"))

        # 3. File non-Word (.txt)
        res_txt = SmartRPPReplacerApp._collect_files(mock_app, self.sample_txt, self.test_dir, recursive=False)
        self.assertEqual(len(res_txt), 0)

    def test_collect_files_folder(self):
        """Memastikan _collect_files tetap berfungsi normal untuk mode folder (batch)."""
        mock_app = MagicMock(spec=SmartRPPReplacerApp)
        res = SmartRPPReplacerApp._collect_files(mock_app, self.test_dir, self.test_dir, recursive=False)
        basenames = [item[1] for item in res]
        self.assertIn("Contoh_RPP.docx", basenames)
        self.assertIn("Arsip_Lama.doc", basenames)
        self.assertNotIn("catatan.txt", basenames)

    def test_on_input_target_changed_modes(self):
        """Memastikan indikator label dan teks tombol beradaptasi otomatis antara berkas tunggal vs folder."""
        mock_app = MagicMock(spec=SmartRPPReplacerApp)
        mock_app.lbl_input_mode = MagicMock()
        mock_app.btn_process = MagicMock()
        mock_app.input_dir_var = MagicMock()

        # 1. Target kosong
        mock_app.input_dir_var.get.return_value = ""
        SmartRPPReplacerApp._on_input_target_changed(mock_app)
        mock_app.btn_process.configure.assert_called_with(text="PROSES SEMUA DOKUMEN SEKARANG")

        # 2. Target file Word yang valid
        mock_app.input_dir_var.get.return_value = self.sample_docx
        SmartRPPReplacerApp._on_input_target_changed(mock_app)
        mock_app.btn_process.configure.assert_called_with(text="PROSES 1 DOKUMEN SEKARANG")
        lbl_args = mock_app.lbl_input_mode.configure.call_args[1]
        self.assertIn("Berkas Tunggal Siap Diproses", lbl_args["text"])
        self.assertIn("Contoh_RPP.docx", lbl_args["text"])

        # 3. Target folder yang valid
        mock_app.input_dir_var.get.return_value = self.test_dir
        SmartRPPReplacerApp._on_input_target_changed(mock_app)
        mock_app.btn_process.configure.assert_called_with(text="PROSES SEMUA DOKUMEN DALAM FOLDER")
        lbl_args = mock_app.lbl_input_mode.configure.call_args[1]
        self.assertIn("Folder Siap Dipindai", lbl_args["text"])

        # 4. Target path yang tidak ada
        mock_app.input_dir_var.get.return_value = os.path.join(self.test_dir, "tidak_ada_file.docx")
        SmartRPPReplacerApp._on_input_target_changed(mock_app)
        lbl_args = mock_app.lbl_input_mode.configure.call_args[1]
        self.assertIn("tidak ditemukan", lbl_args["text"])

    @patch("gui.app.messagebox.askyesno")
    def test_start_processing_single_file_overwrite_warning(self, mock_askyesno):
        """Memastikan dialog konfirmasi penimpaan berkas muncul saat berkas output sama dengan berkas input."""
        mock_app = MagicMock()
        mock_app.input_dir_var.get.return_value = self.sample_docx
        # Set output dir sama dengan folder letak sample_docx
        mock_app.output_dir_var.get.return_value = self.test_dir

        # Simulasi user menolak menimpa (klik 'No')
        mock_askyesno.return_value = False

        SmartRPPReplacerApp._start_processing(mock_app)
        mock_askyesno.assert_called_once()
        self.assertIn("Peringatan Penimpaan Berkas", mock_askyesno.call_args[0][0])
        # Pastikan tidak memanggil get_search_mode karena dihentikan sebelum proses
        mock_app.replacement_view.get_search_mode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
