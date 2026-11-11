"""
Unit test suite untuk FieldDictionary (core/field_dictionary.py).
Menguji:
- Resolusi positif seluruh field standar RPP
- Proteksi kasus negatif (never_match, batas kata, exact-only)
- Penambahan & benturan sinonim pengguna
- Toleransi berkas pengguna yang rusak
- Validasi nilai lunak (soft validation)
- Kompatibilitas to_legacy_aliases
"""
import unittest
import os
import shutil
import tempfile
import json

from core.field_dictionary import FieldDictionary, FieldDef, MatchResult


class TestFieldDictionary(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_dict_")
        self.user_file = os.path.join(self.test_dir, "dictionary.user.json")
        os.environ["SMART_RPP_USER_DIR"] = self.test_dir
        self.dict = FieldDictionary.load(user_path=self.user_file)

    def tearDown(self):
        if "SMART_RPP_USER_DIR" in os.environ:
            del os.environ["SMART_RPP_USER_DIR"]
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_positive_resolutions(self):
        """Memastikan semua istilah resmi dan sinonim standar terpetakan ke field yang benar."""
        # Lembaga
        self.assertEqual(self.dict.resolve("Nama Sekolah").field.id, "nama_lembaga")
        self.assertEqual(self.dict.resolve("Nama Madrasah").field.id, "nama_lembaga")
        self.assertEqual(self.dict.resolve("Satuan Pendidikan").field.id, "nama_lembaga")

        # Guru
        self.assertEqual(self.dict.resolve("Disusun oleh").field.id, "nama_guru")
        self.assertEqual(self.dict.resolve("Guru Penyusun").field.id, "nama_guru")
        self.assertEqual(self.dict.resolve("Penyusun").field.id, "nama_guru")
        self.assertEqual(self.dict.resolve("Nama Penyusun").field.id, "nama_guru")
        self.assertEqual(self.dict.resolve("Guru Kelas IV").field.id, "nama_guru")

        # Tahun Pelajaran vs Tahun Penyusunan
        self.assertEqual(self.dict.resolve("Tahun Pelajaran").field.id, "tahun_pelajaran")
        self.assertEqual(self.dict.resolve("Tahun Ajaran").field.id, "tahun_pelajaran")
        self.assertEqual(self.dict.resolve("TP").field.id, "tahun_pelajaran")
        self.assertEqual(self.dict.resolve("Tahun Penyusunan").field.id, "tahun_penyusunan")
        self.assertEqual(self.dict.resolve("Tahun Pembuatan").field.id, "tahun_penyusunan")

        # NIP
        self.assertEqual(self.dict.resolve("NIP Kepala Madrasah").field.id, "nip_kepala")
        self.assertEqual(self.dict.resolve("NIP Guru Mata Pelajaran").field.id, "nip_guru")
        self.assertEqual(self.dict.resolve("NUPTK").field.id, "nip_guru")

        # Titimangsa
        self.assertEqual(self.dict.resolve("Tanggal Pengesahan").field.id, "titimangsa")
        self.assertEqual(self.dict.resolve("Titimangsa").field.id, "titimangsa")
        self.assertEqual(self.dict.resolve("Tanggal").field.id, "titimangsa")

    def test_negative_resolutions(self):
        """Memastikan kata-kata jebakan tidak salah dicocokkan (never_match & word-boundary)."""
        self.assertIsNone(self.dict.resolve("Output").field)
        self.assertIsNone(self.dict.resolve("Setup").field)
        self.assertIsNone(self.dict.resolve("Tanggal Lahir Siswa").field)
        self.assertIsNone(self.dict.resolve("Jumlah Guru").field)
        self.assertIsNone(self.dict.resolve("Alokasi Waktu").field)
        self.assertIsNone(self.dict.resolve("").field)
        self.assertIsNone(self.dict.resolve(".....").field)

    def test_user_synonym_management_and_collision(self):
        """Memastikan penambahan sinonim pengguna berjalan dan benturan lintas field dicegah."""
        # Tambah sinonim unik baru
        self.dict.add_user_synonym("nama_guru", "Pengembang Perangkat Ajar")
        res = self.dict.resolve("Pengembang Perangkat Ajar")
        self.assertIsNotNone(res.field)
        self.assertEqual(res.field.id, "nama_guru")

        # Benturan lintas field harus melempar ValueError
        with self.assertRaises(ValueError):
            self.dict.add_user_synonym("nama_lembaga", "Pengembang Perangkat Ajar")

        with self.assertRaises(ValueError):
            self.dict.add_user_synonym("nama_lembaga", "Kepala Sekolah")

        # Simpan dan muat ulang kamus
        self.dict.save_user()
        self.assertTrue(os.path.isfile(self.user_file))

        reloaded_dict = FieldDictionary.load(user_path=self.user_file)
        res_reloaded = reloaded_dict.resolve("Pengembang Perangkat Ajar")
        self.assertIsNotNone(res_reloaded.field)
        self.assertEqual(res_reloaded.field.id, "nama_guru")

    def test_corrupted_user_file_fallback(self):
        """Memastikan jika file JSON pengguna rusak, aplikasi tetap berfungsi dengan kamus bawaan."""
        with open(self.user_file, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON DATA --- ")

        safe_dict = FieldDictionary.load(user_path=self.user_file)
        self.assertEqual(safe_dict.resolve("Nama Sekolah").field.id, "nama_lembaga")

    def test_to_legacy_aliases_compatibility(self):
        """Memastikan adapter to_legacy_aliases menghasilkan struktur Dict[str, List[str]]."""
        aliases = self.dict.to_legacy_aliases()
        self.assertIn("Nama Madrasah", aliases)
        self.assertIn("Tahun Ajaran", aliases)
        self.assertIn("Nama Guru", aliases)
        self.assertIn("Satuan Pendidikan", aliases["Nama Madrasah"])
        self.assertIn("TP", aliases["Tahun Ajaran"])

    def test_validate_value_soft(self):
        """Memastikan validasi nilai lunak memberikan pesan peringatan yang akurat tanpa memblokir."""
        # NIP
        self.assertIsNone(self.dict.validate_value("nip_kepala", "198001012005011001"))
        self.assertIsNotNone(self.dict.validate_value("nip_kepala", "12345678901234567"))  # 17 digit

        # Tahun Tunggal
        self.assertIsNone(self.dict.validate_value("tahun_penyusunan", "2026"))
        self.assertIsNotNone(self.dict.validate_value("tahun_penyusunan", "2026/2027"))

        # Tahun Pelajaran (rentang)
        self.assertIsNone(self.dict.validate_value("tahun_pelajaran", "2026/2027"))
        self.assertIsNone(self.dict.validate_value("tahun_pelajaran", "20.. /20.."))
        self.assertIsNotNone(self.dict.validate_value("tahun_pelajaran", "2026"))

    def test_collect_unknown_labels(self):
        """Memastikan collect_unknown_labels mendeteksi label baru yang belum ada di kamus."""
        from docx import Document
        from core.document_predictor import collect_unknown_labels

        doc_path = os.path.join(self.test_dir, "unknown_sample.docx")
        doc = Document()
        doc.add_heading("RPP Inovatif", level=1)
        doc.add_paragraph("Pengembang Perangkat : ................................................")
        doc.add_paragraph("Nama Sekolah : SD Contoh")

        table = doc.add_table(rows=2, cols=3)
        table.rows[0].cells[0].text = "Tahun Pelajaran"
        table.rows[0].cells[1].text = ":"
        table.rows[0].cells[2].text = "2026/2027"

        table.rows[1].cells[0].text = "Instruktur Lapangan"
        table.rows[1].cells[1].text = ":"
        table.rows[1].cells[2].text = "................"

        doc.save(doc_path)

        unknowns = collect_unknown_labels(doc_path, self.dict)
        self.assertIn("Pengembang Perangkat", unknowns)
        self.assertIn("Instruktur Lapangan", unknowns)
        self.assertNotIn("Nama Sekolah", unknowns)
        self.assertNotIn("Tahun Pelajaran", unknowns)


class TestDictionaryGuiIntegration(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.skipTest("Lingkungan pengujian tidak memiliki display GUI Tkinter.")

        self.test_dir = tempfile.mkdtemp(prefix="test_gui_dict_")
        self.user_file = os.path.join(self.test_dir, "dictionary.user.json")
        self.dict = FieldDictionary.load(user_path=self.user_file)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dictionary_manager_dialog_flow(self):
        """Memastikan DictionaryManagerDialog dapat menampilkan field, menambah sinonim, dan menguji teks."""
        from gui.dictionary_dialog import DictionaryManagerDialog
        from unittest.mock import patch
        saved_called = [False]

        def on_saved():
            saved_called[0] = True

        dlg = DictionaryManagerDialog(self.root, dictionary=self.dict, on_saved_callback=on_saved)

        # Uji seleksi field & tambah sinonim
        dlg.field_listbox.selection_clear(0, "end")
        dlg.field_listbox.selection_set(0)
        dlg._on_field_selected()
        current_field_id = dlg.selected_field.id

        dlg.entry_new_syn.insert(0, "Nama Instansi Pendidikan")
        dlg._add_user_synonym()
        self.assertIn("Nama Instansi Pendidikan", self.dict.get_user_synonyms_for_field(current_field_id))

        # Uji live tester
        dlg.test_entry.delete(0, "end")
        dlg.test_entry.insert(0, "Nama Instansi Pendidikan")
        dlg._on_test_changed()
        self.assertIn("✔", dlg.lbl_test_result["text"])

        # Uji simpan dengan mock showinfo
        with patch("tkinter.messagebox.showinfo"):
            dlg._save_and_close()
        self.assertTrue(saved_called[0])
        self.assertTrue(os.path.isfile(self.user_file))

    def test_unknown_labels_dialog_mapping(self):
        """Memastikan UnknownLabelsDialog dapat memetakan unknown label langsung ke field kamus."""
        from gui.dictionary_dialog import UnknownLabelsDialog
        added_called = [False]

        def on_added():
            added_called[0] = True

        unknowns = {"Guru Pembimbing Lapangan": 3}
        dlg = UnknownLabelsDialog(
            self.root,
            unknown_labels=unknowns,
            dictionary=self.dict,
            on_synonym_added_callback=on_added
        )

        # Pilih item di treeview
        dlg.tree.selection_set("Guru Pembimbing Lapangan")
        dlg._on_tree_selected()
        self.assertEqual(str(dlg.btn_map["state"]), "normal")

        # Petakan ke Nama Guru
        dlg.combo_field.set("Nama Guru Penyusun")
        dlg._map_selected_label()

        self.assertTrue(added_called[0])
        res = self.dict.resolve("Guru Pembimbing Lapangan")
        self.assertIsNotNone(res.field)
        self.assertEqual(res.field.id, "nama_guru")
        dlg.destroy()

    def test_replacement_view_dictionary_and_validation(self):
        """Memastikan ReplacementView menggunakan Combobox, menampilkan badge pengenalan, dan validasi lunak."""
        from gui.replacement_view import ReplacementView
        view = ReplacementView(self.root, field_dictionary=self.dict)

        # Cek baris pertama (Nama Sekolah/Madrasah)
        first_row = view.rows_data[0]
        lbl_widget, old_widget, new_widget, frame, btn_del = first_row

        # Widget label harus berupa Combobox
        from tkinter import ttk
        self.assertIsInstance(lbl_widget, ttk.Combobox)
        self.assertIn("Nama Sekolah/Madrasah", lbl_widget["values"])

        # Cek badge pengenalan
        self.assertEqual(frame.lbl_badge["text"], "✔")

        # Cek baris NIP untuk validasi lunak
        nip_row = next(r for r in view.rows_data if "NIP Kepala" in r[0].get())
        nip_lbl, nip_old, nip_new, nip_frame, _ = nip_row

        # Isi NIP tidak valid (17 digit)
        nip_new.delete(0, "end")
        nip_new.insert(0, "12345678901234567")
        view._update_row_feedback(nip_row)
        self.assertIn("⚠", nip_frame.lbl_warn["text"])

        # Perbaiki jadi 18 digit
        nip_new.delete(0, "end")
        nip_new.insert(0, "198001012005011001")
        view._update_row_feedback(nip_row)
        self.assertEqual(nip_frame.lbl_warn["text"], "")


if __name__ == "__main__":
    unittest.main()
