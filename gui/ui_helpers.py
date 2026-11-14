"""
Utilitas bantuan antarmuka Tkinter untuk Smart RPP & Document Replacer.
Menyediakan helper untuk standarisasi interaksi widget dan pencegahan event yang tidak diinginkan.
"""
from typing import Optional, Callable
import tkinter as tk
from tkinter import ttk


def disable_combobox_mousewheel(
    combo: ttk.Combobox,
    scroll_callback: Optional[Callable[[tk.Event], None]] = None,
) -> None:
    """
    Mencegah perubahan nilai pada ttk.Combobox saat pengguna memutar scroll wheel mouse.
    Jika scroll_callback diberikan (misal self._on_wheel kanvas), event scroll dialihkan
    ke induk agar scrolling halaman tetap berjalan mulus tanpa mengubah data combobox.
    """
    def _on_wheel(event: tk.Event) -> str:
        if scroll_callback is not None:
            try:
                scroll_callback(event)
            except Exception:
                pass
        return "break"

    combo.bind("<MouseWheel>", _on_wheel)
    combo.bind("<Button-4>", _on_wheel)
    combo.bind("<Button-5>", _on_wheel)


def prevent_global_combobox_mousewheel(root: tk.Tk) -> None:
    """
    Menonaktifkan class-level binding <MouseWheel> pada TCombobox secara global
    di seluruh aplikasi agar combobox tidak pernah berubah tanpa sengaja akibat scroll.
    """
    try:
        root.unbind_class("TCombobox", "<MouseWheel>")
        root.unbind_class("TCombobox", "<Button-4>")
        root.unbind_class("TCombobox", "<Button-5>")
    except Exception:
        pass
