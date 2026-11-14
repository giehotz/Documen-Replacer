"""
Panel editor terstruktur khusus Surat Keputusan (SK).
Menyediakan formulir input untuk Nomor SK, Tentang / Judul SK,
Titi Mangsa Penetapan (Tempat & Tanggal), Penandatangan, dan opsi sinkronisasi lampiran.
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any


class SKEditorPanel(ttk.LabelFrame):
    """
    Formulir input terstruktur khusus untuk domain Surat Keputusan.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="Atribut Surat Keputusan (SK)", padding=10, *args, **kwargs)

        self.nomor_sk_var = tk.StringVar()
        self.tentang_sk_var = tk.StringVar()
        self.tempat_penetapan_var = tk.StringVar(value="Kota Contoh")
        self.tanggal_penetapan_var = tk.StringVar()
        self.nama_kepala_var = tk.StringVar()
        self.nip_kepala_var = tk.StringVar()
        self.sync_lampiran_var = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        fields = [
            ("Nomor SK:", self.nomor_sk_var, 0),
            ("Tentang / Judul SK:", self.tentang_sk_var, 1),
            ("Tempat Penetapan:", self.tempat_penetapan_var, 2),
            ("Tanggal Penetapan:", self.tanggal_penetapan_var, 3),
            ("Nama Kepala:", self.nama_kepala_var, 4),
            ("NIP Kepala:", self.nip_kepala_var, 5),
        ]

        for lbl_text, var, row_idx in fields:
            lbl = ttk.Label(self, text=lbl_text, font=("Segoe UI", 9))
            lbl.grid(row=row_idx, column=0, sticky="w", padx=(0, 10), pady=3)
            ent = ttk.Entry(self, textvariable=var, font=("Segoe UI", 9))
            ent.grid(row=row_idx, column=1, sticky="ew", pady=3)

        chk_sync = ttk.Checkbutton(
            self,
            text="Sinkronkan Nomor, Tanggal, dan Tentang otomatis ke seluruh halaman Lampiran SK",
            variable=self.sync_lampiran_var
        )
        chk_sync.grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def get_rules(self) -> List[Dict[str, str]]:
        """Mengonversi nilai formulir menjadi format rules penggantian naskah."""
        rules = []
        mapping = [
            ("Nomor SK", self.nomor_sk_var.get().strip()),
            ("Tentang / Judul SK", self.tentang_sk_var.get().strip()),
            ("Tempat Penetapan", self.tempat_penetapan_var.get().strip()),
            ("Tanggal Penetapan", self.tanggal_penetapan_var.get().strip()),
            ("Nama Kepala", self.nama_kepala_var.get().strip()),
            ("NIP Kepala", self.nip_kepala_var.get().strip()),
        ]
        for label, val in mapping:
            if val:
                rules.append({"label": label, "old": "", "new": val})
        return rules

    def set_values(self, data: Dict[str, str]) -> None:
        """Mengisi formulir dengan data (misal hasil prediksi)."""
        if "nomor_sk" in data or "Nomor SK" in data:
            self.nomor_sk_var.set(data.get("nomor_sk", data.get("Nomor SK", "")))
        if "tentang_sk" in data or "Tentang / Judul SK" in data:
            self.tentang_sk_var.set(data.get("tentang_sk", data.get("Tentang / Judul SK", "")))
        if "tempat_penetapan" in data or "Tempat Penetapan" in data:
            self.tempat_penetapan_var.set(data.get("tempat_penetapan", data.get("Tempat Penetapan", "")))
        if "tanggal_penetapan" in data or "Tanggal Penetapan" in data:
            self.tanggal_penetapan_var.set(data.get("tanggal_penetapan", data.get("Tanggal Penetapan", "")))
        if "nama_kepala" in data or "Nama Kepala" in data:
            self.nama_kepala_var.set(data.get("nama_kepala", data.get("Nama Kepala", "")))
        if "nip_kepala" in data or "NIP Kepala" in data:
            self.nip_kepala_var.set(data.get("nip_kepala", data.get("NIP Kepala", "")))

    def clear(self) -> None:
        """Mengosongkan seluruh isian formulir."""
        self.nomor_sk_var.set("")
        self.tentang_sk_var.set("")
        self.tempat_penetapan_var.set("")
        self.tanggal_penetapan_var.set("")
        self.nama_kepala_var.set("")
        self.nip_kepala_var.set("")
