"""
Panel editor terstruktur khusus Surat Dinas dan Undangan Resmi.
Menyediakan formulir input untuk Metadata Surat (Nomor, Sifat, Lampiran, Hal, Tujuan Yth)
dan Blok Agenda Kegiatan (Hari/Tgl, Waktu, Tempat, Acara).
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Optional


class SuratEditorPanel(ttk.LabelFrame):
    """
    Formulir input terstruktur untuk domain Surat Dinas / Undangan.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="Atribut Surat Dinas / Undangan", padding=10, *args, **kwargs)

        # Metadata Surat
        self.nomor_surat_var = tk.StringVar()
        self.sifat_surat_var = tk.StringVar(value="Penting")
        self.lampiran_surat_var = tk.StringVar(value="-")
        self.hal_surat_var = tk.StringVar()
        self.tujuan_surat_var = tk.StringVar()

        # Agenda Kegiatan
        self.hari_tanggal_acara_var = tk.StringVar()
        self.waktu_acara_var = tk.StringVar()
        self.tempat_acara_var = tk.StringVar()
        self.acara_kegiatan_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        # Bagian 1: Metadata Surat
        lbl_sec1 = ttk.Label(self, text="Metadata Surat Keluar", font=("Segoe UI", 9, "bold"))
        lbl_sec1.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        sec1_fields = [
            ("Nomor Surat:", self.nomor_surat_var, 1),
            ("Sifat Surat:", self.sifat_surat_var, 2),
            ("Lampiran:", self.lampiran_surat_var, 3),
            ("Hal / Perihal:", self.hal_surat_var, 4),
            ("Kepada Yth:", self.tujuan_surat_var, 5),
        ]
        for lbl_text, var, row_idx in sec1_fields:
            lbl = ttk.Label(self, text=lbl_text, font=("Segoe UI", 9))
            lbl.grid(row=row_idx, column=0, sticky="w", padx=(0, 10), pady=2)
            ent = ttk.Entry(self, textvariable=var, font=("Segoe UI", 9))
            ent.grid(row=row_idx, column=1, sticky="ew", pady=2)

        # Separator
        sep = ttk.Separator(self, orient="horizontal")
        sep.grid(row=6, column=0, columnspan=2, sticky="ew", pady=8)

        # Bagian 2: Blok Agenda Kegiatan
        lbl_sec2 = ttk.Label(self, text="Rincian Agenda Kegiatan (Undangan)", font=("Segoe UI", 9, "bold"))
        lbl_sec2.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 5))

        sec2_fields = [
            ("Hari, Tanggal Acara:", self.hari_tanggal_acara_var, 8),
            ("Waktu / Pukul:", self.waktu_acara_var, 9),
            ("Tempat Acara:", self.tempat_acara_var, 10),
            ("Acara Kegiatan:", self.acara_kegiatan_var, 11),
        ]
        for lbl_text, var, row_idx in sec2_fields:
            lbl = ttk.Label(self, text=lbl_text, font=("Segoe UI", 9))
            lbl.grid(row=row_idx, column=0, sticky="w", padx=(0, 10), pady=2)
            ent = ttk.Entry(self, textvariable=var, font=("Segoe UI", 9))
            ent.grid(row=row_idx, column=1, sticky="ew", pady=2)

    def get_rules(self) -> List[Dict[str, str]]:
        """Mengonversi nilai formulir menjadi format rules penggantian naskah."""
        rules = []
        mapping = [
            ("Nomor Surat", self.nomor_surat_var.get().strip()),
            ("Sifat Surat", self.sifat_surat_var.get().strip()),
            ("Lampiran", self.lampiran_surat_var.get().strip()),
            ("Hal / Perihal", self.hal_surat_var.get().strip()),
            ("Kepada Yth", self.tujuan_surat_var.get().strip()),
            ("Hari, Tanggal Kegiatan", self.hari_tanggal_acara_var.get().strip()),
            ("Pukul / Waktu Kegiatan", self.waktu_acara_var.get().strip()),
            ("Tempat Kegiatan", self.tempat_acara_var.get().strip()),
            ("Acara Kegiatan", self.acara_kegiatan_var.get().strip()),
        ]
        for label, val in mapping:
            if val:
                rules.append({"label": label, "old": "", "new": val})
        return rules

    def set_values(self, data: Dict[str, str]) -> None:
        """Mengisi formulir dengan data (misal hasil prediksi)."""
        def _get_val(*keys) -> Optional[str]:
            for k in keys:
                if k in data:
                    return str(data[k])
            return None

        v = _get_val("nomor_surat", "Nomor Surat", "nomor")
        if v is not None:
            self.nomor_surat_var.set(v)

        v = _get_val("sifat_surat", "Sifat Surat", "sifat", "Sifat")
        if v is not None:
            self.sifat_surat_var.set(v)

        v = _get_val("lampiran_surat", "Lampiran", "lampiran")
        if v is not None:
            self.lampiran_surat_var.set(v)

        v = _get_val("hal_surat", "Hal / Perihal", "hal", "Hal", "perihal", "Perihal")
        if v is not None:
            self.hal_surat_var.set(v)

        v = _get_val("tujuan_surat", "Kepada Yth", "tujuan", "Tujuan Yth", "tujuan_yth")
        if v is not None:
            self.tujuan_surat_var.set(v)

        v = _get_val("hari_tanggal_acara", "Hari, Tanggal Kegiatan", "Hari, Tanggal", "hari_tanggal")
        if v is not None:
            self.hari_tanggal_acara_var.set(v)

        v = _get_val("waktu_acara", "Pukul / Waktu Kegiatan", "Waktu", "waktu", "pukul")
        if v is not None:
            self.waktu_acara_var.set(v)

        v = _get_val("tempat_acara", "Tempat Kegiatan", "Tempat", "tempat")
        if v is not None:
            self.tempat_acara_var.set(v)

        v = _get_val("acara_kegiatan", "Acara Kegiatan", "Acara", "acara")
        if v is not None:
            self.acara_kegiatan_var.set(v)

    def clear(self) -> None:
        """Mengosongkan seluruh isian formulir."""
        self.nomor_surat_var.set("")
        self.sifat_surat_var.set("")
        self.lampiran_surat_var.set("")
        self.hal_surat_var.set("")
        self.tujuan_surat_var.set("")
        self.hari_tanggal_acara_var.set("")
        self.waktu_acara_var.set("")
        self.tempat_acara_var.set("")
        self.acara_kegiatan_var.set("")
