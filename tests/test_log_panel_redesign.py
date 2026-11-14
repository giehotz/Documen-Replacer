"""
Unit test untuk verifikasi redisain panel log di sebelah kanan (Global Sidebar),
tombol toggle Sembunyikan/Tampilkan Log, tombol Salin, dan tombol Bersihkan Log.
"""
import unittest
from unittest.mock import MagicMock
import tkinter as tk
from tkinter import ttk


class TestLogPanelRedesign(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.root = None

    def tearDown(self):
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def test_log_panel_structure_and_toggle(self):
        """Memastikan struktur PanedWindow, Sidebar Log, dan mekanisme toggle berfungsi semestinya."""
        if not self.root:
            self.skipTest("Tkinter display tidak tersedia di lingkungan pengujian.")

        from gui.app import SmartRPPReplacerApp
        app = SmartRPPReplacerApp(self.root)

        # 1. Verifikasi inisialisasi awal
        self.assertTrue(hasattr(app, "paned_main"))
        self.assertIsInstance(app.paned_main, ttk.PanedWindow)
        self.assertTrue(hasattr(app, "log_container"))
        self.assertTrue(hasattr(app, "btn_toggle_log"))
        self.assertTrue(hasattr(app, "log_box"))
        self.assertTrue(app.log_visible)
        self.assertIn("Sembunyikan Log", app.btn_toggle_log.cget("text"))

        # 2. Verifikasi penulisan log
        app._log("[TEST] Pesan log pertama")
        content = app.log_box.get("1.0", "end")
        self.assertIn("[TEST] Pesan log pertama", content)

        # 3. Verifikasi toggle sembunyikan log
        app._toggle_log_panel()
        self.assertFalse(app.log_visible)
        self.assertIn("Tampilkan Log", app.btn_toggle_log.cget("text"))

        # 4. Verifikasi toggle tampilkan log kembali
        app._toggle_log_panel()
        self.assertTrue(app.log_visible)
        self.assertIn("Sembunyikan Log", app.btn_toggle_log.cget("text"))

        # 5. Verifikasi pembersihan log
        app._clear_log()
        cleared_content = app.log_box.get("1.0", "end").strip()
        self.assertEqual(cleared_content, "")

        # 6. Verifikasi penyalinan log
        app._log("[TEST] Pesan untuk clipboard")
        app._copy_log()

    def test_mock_toggle_logic(self):
        """Memverifikasi logika toggle dan pembersihan log dengan mock tanpa display fisik."""
        from gui.app import SmartRPPReplacerApp

        mock_app = MagicMock(spec=SmartRPPReplacerApp)
        mock_app.log_visible = True
        mock_app.paned_main = MagicMock()
        mock_app.log_container = MagicMock()
        mock_app.btn_toggle_log = MagicMock()
        mock_app.log_box = MagicMock()

        # Eksekusi _toggle_log_panel dengan unbound method
        SmartRPPReplacerApp._toggle_log_panel(mock_app)
        self.assertFalse(mock_app.log_visible)
        mock_app.paned_main.forget.assert_called_with(mock_app.log_container)
        mock_app.btn_toggle_log.configure.assert_called_with(text="📋 Tampilkan Log")

        SmartRPPReplacerApp._toggle_log_panel(mock_app)
        self.assertTrue(mock_app.log_visible)
        mock_app.paned_main.add.assert_called_with(mock_app.log_container, weight=1)
        mock_app.btn_toggle_log.configure.assert_called_with(text="📋 Sembunyikan Log")

        # Eksekusi _clear_log
        SmartRPPReplacerApp._clear_log(mock_app)
        mock_app.log_box.delete.assert_called_with("1.0", "end")


if __name__ == "__main__":
    unittest.main()
