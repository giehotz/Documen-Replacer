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


def center_window(
    window: tk.Toplevel,
    parent: Optional[tk.Widget] = None,
    width: Optional[int] = None,
    height: Optional[int] = None
) -> None:
    """
    Memposisikan jendela dialog (Toplevel / popup) tepat di tengah jendela induk (parent),
    atau di tengah layar jika jendela induk tidak tersedia / diminimize.
    """
    try:
        window.update_idletasks()
        w = width or window.winfo_reqwidth() or window.winfo_width() or 600
        h = height or window.winfo_reqheight() or window.winfo_height() or 400

        top_parent = None
        if parent:
            try:
                top_parent = parent.winfo_toplevel()
            except Exception:
                top_parent = parent

        if top_parent and top_parent.winfo_viewable() and top_parent.winfo_width() > 100:
            pw = top_parent.winfo_width()
            ph = top_parent.winfo_height()
            px = top_parent.winfo_rootx()
            py = top_parent.winfo_rooty()
            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
        else:
            sw = window.winfo_screenwidth()
            sh = window.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)

        window.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass
