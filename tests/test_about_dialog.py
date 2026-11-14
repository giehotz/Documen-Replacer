"""
Unit Test: Pengujian Antarmuka Dialog Tentang Aplikasi (AboutDialog).
Memverifikasi ketersediaan informasi versi, kredit @giehotz, tautan GitHub,
serta halaman terpisah untuk panduan dan perjanjian lisensi.
"""
import unittest
import tkinter as tk

from gui.about_dialog import (
    AboutDialog,
    DEVELOPER_NAME,
    GITHUB_PROFILE_URL,
    PANDUAN_TEKS,
    PERJANJIAN_TEKS,
)
from core.version import APP_NAME, __version__


class TestAboutDialog(unittest.TestCase):
    def test_constants_and_credit(self):
        """Memastikan kredit pengembang @giehotz dan tautan GitHub terdefinisi dengan tepat."""
        self.assertEqual(DEVELOPER_NAME, "@giehotz")
        self.assertEqual(GITHUB_PROFILE_URL, "https://github.com/giehotz")
        self.assertIn("1.1.0", __version__)
        self.assertIn("Smart RPP & Document Replacer", APP_NAME)

    def test_panduan_and_perjanjian_content(self):
        """Memastikan isi teks panduan dan perjanjian mencakup poin-poin penting."""
        # Cek isi panduan
        self.assertIn("ALUR PENGGANTIAN DOKUMEN", PANDUAN_TEKS)
        self.assertIn("TANDA TANGAN & STEMPEL DIGITAL", PANDUAN_TEKS)
        self.assertIn("KONVERSI MASSAL WORD KE PDF", PANDUAN_TEKS)
        self.assertIn("MAIL MERGE", PANDUAN_TEKS)

        # Cek isi perjanjian
        self.assertIn("100% OFFLINE", PERJANJIAN_TEKS)
        self.assertIn("MIT License", PERJANJIAN_TEKS)
        self.assertIn("Giehotz", PERJANJIAN_TEKS)

    def test_about_dialog_instantiation(self):
        """Memastikan AboutDialog dapat diinisialisasi dan berpindah tab dengan benar."""
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tkinter display tidak tersedia di lingkungan pengujian.")

        try:
            # Uji inisialisasi tab 0
            dlg0 = AboutDialog(root, initial_tab=0)
            self.assertEqual(dlg0.notebook.index(dlg0.notebook.select()), 0)
            self.assertEqual(dlg0.link_lbl.cget("text"), "https://github.com/giehotz")
            dlg0.destroy()

            # Uji inisialisasi tab 1 (Panduan)
            dlg1 = AboutDialog(root, initial_tab=1)
            self.assertEqual(dlg1.notebook.index(dlg1.notebook.select()), 1)
            dlg1.destroy()

            # Uji inisialisasi tab 2 (Perjanjian)
            dlg2 = AboutDialog(root, initial_tab=2)
            self.assertEqual(dlg2.notebook.index(dlg2.notebook.select()), 2)
            dlg2.destroy()

        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
