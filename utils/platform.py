"""
Modul Utilitas Kompatibilitas Lintas Platform (Windows, Linux, macOS).
Menyediakan pembungkus transparan untuk fungsi-fungsi spesifik sistem operasi:
- Membuka berkas / folder di file manager native
- Konfigurasi resolusi tinggi (HiDPI)
"""
import os
import sys
import subprocess
import logging

logger = logging.getLogger(__name__)


def open_path(path: str) -> None:
    """Membuka berkas atau folder di file explorer native sistem operasi."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path tidak ditemukan: {path}")

    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def enable_hidpi() -> None:
    """Mengaktifkan dukungan resolusi tinggi (HiDPI) pada Windows jika tersedia."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception as e:
            logger.debug("HiDPI awareness tidak dapat diaktifkan: %s", e)
