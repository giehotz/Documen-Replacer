"""
Bilah pemilih jenis dokumen modular (DomainSelectorBar).
Memungkinkan pengguna memilih domain dokumen yang sedang diproses
atau membiarkan AutoClassifier mendeteksi secara cerdas.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Dict, List


DOMAIN_OPTIONS = [
    ("auto", "🔍 Deteksi Otomatis (Semua Dokumen)"),
    ("rpp_modul", "📘 Perangkat Ajar (RPP / Modul Ajar)"),
    ("sk_keputusan", "📜 Surat Keputusan (SK)"),
    ("surat_dinas", "✉️ Surat Dinas / Undangan"),
    ("spt_penugasan", "📋 Surat Perintah Tugas (SPT)"),
    ("berita_acara", "🤝 Berita Acara / MOU"),
]


class DomainSelectorBar(ttk.Frame):
    """
    Toolbar pemilihan jenis dokumen aktif.
    """

    def __init__(
        self,
        parent,
        on_domain_changed: Optional[Callable[[str], None]] = None,
        *args,
        **kwargs
    ):
        super().__init__(parent, *args, **kwargs)
        self.on_domain_changed = on_domain_changed
        self._id_to_label: Dict[str, str] = dict(DOMAIN_OPTIONS)
        self._label_to_id: Dict[str, str] = {v: k for k, v in DOMAIN_OPTIONS}

        self.selected_domain_var = tk.StringVar(value="auto")
        self.display_label_var = tk.StringVar(value=self._id_to_label["auto"])

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        lbl_title = ttk.Label(self, text="Jenis Dokumen:", font=("Segoe UI", 9, "bold"))
        lbl_title.grid(row=0, column=0, padx=(5, 10), pady=5, sticky="w")

        labels = [v for _, v in DOMAIN_OPTIONS]
        self.combo = ttk.Combobox(
            self,
            textvariable=self.display_label_var,
            values=labels,
            state="readonly",
            font=("Segoe UI", 9),
            width=36,
        )
        self.combo.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="w")
        self.combo.bind("<<ComboboxSelected>>", self._on_combo_selected)

        self.lbl_status = ttk.Label(self, text="", font=("Segoe UI", 8, "italic"), foreground="gray")
        self.lbl_status.grid(row=0, column=2, padx=(5, 5), pady=5, sticky="w")

    def _on_combo_selected(self, event=None) -> None:
        selected_label = self.display_label_var.get()
        domain_id = self._label_to_id.get(selected_label, "auto")
        self.selected_domain_var.set(domain_id)

        if self.on_domain_changed:
            self.on_domain_changed(domain_id)

    def get_selected_domain(self) -> str:
        """Mengambil domain_id yang sedang dipilih."""
        return self.selected_domain_var.get()

    def set_domain(self, domain_id: str) -> None:
        """Mengatur pilihan domain secara terprogram."""
        if domain_id in self._id_to_label:
            self.selected_domain_var.set(domain_id)
            self.display_label_var.set(self._id_to_label[domain_id])
            if self.on_domain_changed:
                self.on_domain_changed(domain_id)

    def set_status_message(self, message: str, is_warning: bool = False) -> None:
        """Menampilkan pesan status (misalnya jika hasil klasifikasi ambigu / NEEDS_SELECTION)."""
        self.lbl_status.config(
            text=message,
            foreground="darkred" if is_warning else "gray"
        )
