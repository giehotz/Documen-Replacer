"""
Titik Masuk Utama (Entry Point) Smart RPP Replacer.
"""
import sys
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox


def ensure_docx() -> bool:
    """Memastikan python-docx terpasang. Tawarkan pemasangan otomatis jika belum ada."""
    try:
        import docx  # noqa: F401
        return True
    except ImportError:
        pass

    tmp = tk.Tk()
    tmp.withdraw()
    jawab = messagebox.askyesno(
        "Komponen belum terpasang",
        "Pustaka 'python-docx' belum terpasang.\n\n"
        "Pasang otomatis sekarang? (membutuhkan koneksi internet)",
    )
    if not jawab:
        tmp.destroy()
        return False
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
        tmp.destroy()
        return True
    except Exception as e:
        messagebox.showerror(
            "Gagal memasang",
            f"Pemasangan otomatis gagal:\n{e}\n\n"
            "Pasang manual lewat Command Prompt:\n  pip install python-docx",
        )
        tmp.destroy()
        return False


def main():
    if not ensure_docx():
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
