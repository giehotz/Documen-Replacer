"""
Titik Masuk Utama (Entry Point) Smart RPP Replacer.
"""
import sys
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox


def ensure_dependencies() -> bool:
    """Memastikan dependensi python-docx dan Pillow terpasang."""
    missing = []
    try:
        import docx  # noqa: F401
    except ImportError:
        missing.append("python-docx")

    try:
        import PIL  # noqa: F401
    except ImportError:
        missing.append("Pillow")

    if not missing:
        return True

    tmp = tk.Tk()
    tmp.withdraw()
    missing_str = ", ".join(missing)
    jawab = messagebox.askyesno(
        "Dependensi Belum Lengkap",
        f"Pustaka berikut belum terpasang: {missing_str}\n\n"
        "Pasang otomatis sekarang? (membutuhkan koneksi internet)\n"
        "Atau Anda dapat menjalankan: pip install -r requirements.txt",
    )
    if not jawab:
        tmp.destroy()
        return False
    try:
        req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
        if os.path.isfile(req_file):
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        tmp.destroy()
        return True
    except Exception as e:
        messagebox.showerror(
            "Gagal Memasang",
            f"Pemasangan otomatis gagal:\n{e}\n\n"
            f"Silakan pasang manual lewat Command Prompt:\n  pip install -r requirements.txt",
        )
        tmp.destroy()
        return False


def main():
    if not ensure_dependencies():
        sys.exit(1)

    # Dukungan layar tajam HiDPI di Windows
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass

    from gui.app import SmartRPPReplacerApp
    SmartRPPReplacerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
