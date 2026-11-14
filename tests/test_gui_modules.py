"""
Unit test untuk komponen antarmuka GUI modular (Fase 4 & PRD §7).
Menguji DomainSelectorBar, SKEditorPanel, SuratEditorPanel, MailMergeView,
serta integrasi tab pada SmartRPPReplacerApp.
"""
import unittest
import tkinter as tk
from tkinter import ttk

from gui.modules.domain_selector_bar import DomainSelectorBar, DOMAIN_OPTIONS
from gui.modules.sk_editor_panel import SKEditorPanel
from gui.modules.surat_editor_panel import SuratEditorPanel
from gui.modules.mail_merge_view import MailMergeView
from gui.app import SmartRPPReplacerApp


class TestGuiModules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.gui_available = True
        except Exception:
            cls.gui_available = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "gui_available", False) and getattr(cls, "root", None):
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.gui_available:
            self.skipTest("GUI display tidak tersedia pada lingkungan ini")

    def test_domain_selector_bar(self):
        """DomainSelectorBar memicu callback dan mengembalikan domain yang dipilih."""
        selected_log = []

        def on_change(domain_id):
            selected_log.append(domain_id)

        bar = DomainSelectorBar(self.root, on_domain_changed=on_change)
        self.assertEqual(bar.get_selected_domain(), "auto")

        # Uji pemilihan domain terprogram
        bar.set_domain("sk_keputusan")
        self.assertEqual(bar.get_selected_domain(), "sk_keputusan")

        bar.set_domain("surat_dinas")
        self.assertEqual(bar.get_selected_domain(), "surat_dinas")

        bar.destroy()

    def test_sk_editor_panel(self):
        """SKEditorPanel menghasilkan daftar rules yang sesuai."""
        panel = SKEditorPanel(self.root)
        panel.set_values({
            "Nomor SK": "123/SK/2026",
            "Tentang / Judul SK": "Penetapan Panitia Ujian",
            "Tempat Penetapan": "Kota Contoh",
            "Tanggal Penetapan": "14 Juli 2026",
            "Nama Kepala": "Budi Santoso, M.Pd",
            "NIP Kepala": "198001012005011001",
        })

        rules = panel.get_rules()
        self.assertTrue(len(rules) >= 4)
        rule_dict = {r["label"]: r["new"] for r in rules}
        self.assertEqual(rule_dict.get("Nomor SK"), "123/SK/2026")
        self.assertEqual(rule_dict.get("Nama Kepala"), "Budi Santoso, M.Pd")
        self.assertTrue(panel.sync_lampiran_var.get())

        panel.destroy()

    def test_surat_editor_panel(self):
        """SuratEditorPanel menghasilkan daftar rules metadata dan agenda."""
        panel = SuratEditorPanel(self.root)
        panel.set_values({
            "Nomor Surat": "B-001/Surat/2026",
            "Sifat": "Penting",
            "Hal": "Undangan Rapat Kerja",
            "Tujuan Yth": "Bapak/Ibu Dewan Guru",
            "Hari, Tanggal": "Senin, 17 Juli 2026",
            "Waktu": "08.00 WIB s.d Selesai",
            "Tempat": "Aula Madrasah",
            "Acara": "Koordinasi Awal Tahun Ajaran",
        })

        rules = panel.get_rules()
        self.assertTrue(len(rules) >= 5)
        rule_dict = {r["label"]: r["new"] for r in rules}
        self.assertEqual(rule_dict.get("Nomor Surat"), "B-001/Surat/2026")
        self.assertEqual(rule_dict.get("Hal / Perihal"), "Undangan Rapat Kerja")
        self.assertEqual(rule_dict.get("Tempat Kegiatan"), "Aula Madrasah")

        panel.destroy()

    def test_mail_merge_view_init(self):
        """MailMergeView terinisialisasi dengan variabel default yang aman."""
        view = MailMergeView(self.root)
        self.assertEqual(view.pattern_var.get(), "{NO}_{NAMA}")
        self.assertIsNotNone(view.generator)
        self.assertFalse(view._cancel_requested)

        view.destroy()

    def test_app_modular_tabs_integration(self):
        """SmartRPPReplacerApp mengintegrasikan Tab 3 Mail Merge dan DomainSelectorBar."""
        app = SmartRPPReplacerApp(self.root)
        self.assertIsNotNone(app.domain_selector)
        self.assertIsNotNone(app.tab_mail_merge)

        # Tab count minimal 3: Tab Replacer, Tab PDF, Tab Mail Merge
        tab_names = [app.notebook.tab(i, "text") for i in range(app.notebook.index("end"))]
        self.assertTrue(any("Mail Merge" in name for name in tab_names))
        self.assertTrue(any("Penggantian" in name for name in tab_names))
        self.assertTrue(any("PDF" in name for name in tab_names))

        # Test domain change handler
        app._on_domain_changed("sk_keputusan")


if __name__ == "__main__":
    unittest.main()
