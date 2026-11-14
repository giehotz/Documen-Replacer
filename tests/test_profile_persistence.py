"""
Unit test untuk verifikasi persistensi profil sesi terakhir dan indikator profil aktif pada header tabel.
"""
import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import tkinter as tk


class TestProfilePersistence(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.last_profile_file = os.path.join(self.test_dir, "last_profile.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_mock_set_active_profile_name(self):
        """Memastikan set_active_profile_name memperbarui teks badge [Default Profile] vs [Profil: X]."""
        from gui.replacement_view import ReplacementView

        mock_view = MagicMock(spec=ReplacementView)
        mock_view.lbl_profile_badge = MagicMock()

        # 1. Default Profile
        ReplacementView.set_active_profile_name(mock_view, "Default Profile")
        self.assertEqual(mock_view.active_profile_name, "Default Profile")
        mock_view.lbl_profile_badge.configure.assert_called_with(
            text="[Default Profile]",
            foreground="#0d47a1"
        )

        # 2. Custom Profile
        ReplacementView.set_active_profile_name(mock_view, "RPP_Modul_Ajar_2026")
        self.assertEqual(mock_view.active_profile_name, "RPP_Modul_Ajar_2026")
        mock_view.lbl_profile_badge.configure.assert_called_with(
            text="[Profil: RPP_Modul_Ajar_2026]",
            foreground="#1b5e20"
        )

    def test_save_and_load_last_profile_data(self):
        """Memastikan data profil tersimpan dengan format JSON yang benar dan dapat dimuat kembali."""
        from gui.replacement_view import ReplacementView

        mock_view = MagicMock(spec=ReplacementView)
        mock_view._get_last_profile_path.return_value = self.last_profile_file
        mock_view.get_rules.return_value = [
            {"label": "Nama Sekolah/Madrasah", "old": "SD A", "new": "MIN 1"}
        ]

        # Simpan profil
        sample_rules = [{"label": "Nama Sekolah/Madrasah", "old": "SD A", "new": "MIN 1"}]
        ReplacementView.save_last_used_profile(
            mock_view,
            profile_name="MIN_1_Malang",
            rules=sample_rules,
            path="C:/dummy/MIN_1_Malang.json"
        )

        self.assertTrue(os.path.isfile(self.last_profile_file))
        with open(self.last_profile_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["profile_name"], "MIN_1_Malang")
        self.assertEqual(data["rules"][0]["new"], "MIN 1")

        # Muat kembali
        loaded_rules = []
        mock_view.apply_rules_to_table = lambda r: loaded_rules.extend(r)
        mock_view.set_active_profile_name = MagicMock()

        ReplacementView.load_initial_profile(mock_view)
        self.assertEqual(len(loaded_rules), 1)
        self.assertEqual(loaded_rules[0]["new"], "MIN 1")
        mock_view.set_active_profile_name.assert_called_with("MIN_1_Malang")

    def test_real_tkinter_view_initialization(self):
        """Memastikan widget ReplacementView asli memuat badge dan fallback default jika file belum ada."""
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tkinter display tidak tersedia di lingkungan pengujian.")

        try:
            from gui.replacement_view import ReplacementView
            with patch.object(ReplacementView, "_get_config_dir", return_value=self.test_dir):
                view = ReplacementView(root)
                self.assertTrue(hasattr(view, "lbl_profile_badge"))
                # Karena file belum ada, harus [Default Profile]
                self.assertEqual(view.lbl_profile_badge.cget("text"), "[Default Profile]")

                # Set custom profile
                view.set_active_profile_name("Profil_Khusus")
                self.assertEqual(view.lbl_profile_badge.cget("text"), "[Profil: Profil_Khusus]")

                # Reset to default
                view.reset_to_default_profile()
                self.assertEqual(view.lbl_profile_badge.cget("text"), "[Default Profile]")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
