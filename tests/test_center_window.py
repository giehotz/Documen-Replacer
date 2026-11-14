"""
Unit test untuk verifikasi utilitas pemosisian popup/dialog selalu di tengah (center_window).
"""
import unittest
from unittest.mock import MagicMock
import tkinter as tk


class TestCenterWindow(unittest.TestCase):
    def test_mock_center_over_parent(self):
        """Memastikan posisi dialog dihitung tepat di tengah koordinat jendela induk."""
        from gui.ui_helpers import center_window

        mock_window = MagicMock(spec=tk.Toplevel)
        mock_parent = MagicMock(spec=tk.Tk)

        # Parent berukuran 1200x800 dengan offset root 100, 50
        mock_parent.winfo_toplevel.return_value = mock_parent
        mock_parent.winfo_viewable.return_value = True
        mock_parent.winfo_width.return_value = 1200
        mock_parent.winfo_height.return_value = 800
        mock_parent.winfo_rootx.return_value = 100
        mock_parent.winfo_rooty.return_value = 50

        # Ukuran dialog target: 600x400
        # Posisi x = 100 + (1200 - 600) // 2 = 100 + 300 = 400
        # Posisi y = 50 + (800 - 400) // 2 = 50 + 200 = 250
        center_window(mock_window, mock_parent, width=600, height=400)

        mock_window.geometry.assert_called_with("600x400+400+250")

    def test_mock_center_fallback_to_screen(self):
        """Memastikan fallback ke tengah layar jika parent bernilai None atau belum viewable."""
        from gui.ui_helpers import center_window

        mock_window = MagicMock(spec=tk.Toplevel)
        mock_window.winfo_screenwidth.return_value = 1920
        mock_window.winfo_screenheight.return_value = 1080

        # Posisi x = (1920 - 700) // 2 = 610
        # Posisi y = (1080 - 500) // 2 = 290
        center_window(mock_window, None, width=700, height=500)

        mock_window.geometry.assert_called_with("700x500+610+290")

    def test_safe_exception_handling(self):
        """Memastikan center_window aman dari crash jika terjadi error internal Tkinter."""
        from gui.ui_helpers import center_window

        mock_window = MagicMock()
        mock_window.update_idletasks.side_effect = RuntimeError("Display disconnected")

        # Tidak boleh raise exception
        try:
            center_window(mock_window, None, 500, 300)
        except Exception as e:
            self.fail(f"center_window memicu exception: {e}")

    def test_real_tkinter_center_window(self):
        """Pengujian center_window dengan instance Tkinter asli jika display tersedia."""
        try:
            root = tk.Tk()
            root.withdraw()
        except Exception:
            self.skipTest("Tkinter display tidak tersedia di lingkungan pengujian.")

        try:
            from gui.ui_helpers import center_window
            top = tk.Toplevel(root)
            center_window(top, root, 400, 300)
            self.assertTrue(top.winfo_exists())
            top.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
