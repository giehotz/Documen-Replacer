"""
Komponen GUI: Jendela Pratinjau Terpadu (Integrated Preview Dialog).
Menampilkan seluruh rencana perubahan teks dari semua dokumen sebelum ditulis ke disk.
Memungkinkan pengguna menyetujui, menolak, memfilter berdasarkan tingkat keyakinan,
dan mengedit teks target.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
from core.validation_engine import ReplacementPlanItem, ConfidenceLevel


class IntegratedPreviewDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, plan_items: List[ReplacementPlanItem]):
        super().__init__(parent)
        self.title("Pratinjau Terpadu Perubahan Dokumen - Smart RPP Replacer")
        self.geometry("1000x620")
        self.minsize(850, 500)
        self.transient(parent)
        self.grab_set()

        self.plan_items = plan_items
        self.confirmed = False
        self.filter_mode = "ALL"  # 'ALL' atau 'REVIEW_ONLY'

        self._build_ui()
        self._populate_tree()

    def _build_ui(self):
        # 1. Header & Deskripsi
        top_frame = ttk.Frame(self, padding=(12, 10))
        top_frame.pack(fill="x")

        lbl_title = ttk.Label(
            top_frame,
            text="Tinjau Rencana Perubahan Sebelum Disimpan",
            font=("Segoe UI", 11, "bold")
        )
        lbl_title.pack(anchor="w")

        total_pts = len(self.plan_items)
        high_cnt = sum(1 for it in self.plan_items if it.confidence == ConfidenceLevel.HIGH)
        med_cnt = sum(1 for it in self.plan_items if it.confidence == ConfidenceLevel.MEDIUM)
        low_cnt = sum(1 for it in self.plan_items if it.confidence == ConfidenceLevel.LOW)

        desc_text = (
            f"Ditemukan {total_pts} titik perubahan pada dokumen. "
            f"[Keyakinan: {high_cnt} Tinggi, {med_cnt} Sedang, {low_cnt} Rendah]. "
            "Klik dua kali atau tekan Spasi pada baris untuk menyetujui (✓) atau membatalkan (✗)."
        )
        ttk.Label(top_frame, text=desc_text, foreground="#444444").pack(anchor="w", pady=(2, 0))

        # 2. Toolbar Filter & Seleksi Cepat
        toolbar = ttk.Frame(self, padding=(12, 4))
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="✓ Setujui Semua", command=self._approve_all).pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="✗ Batalkan Semua", command=self._reject_all).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Lewati Keyakinan Rendah", command=self._skip_low_confidence).pack(side="left", padx=4)

        # Filter mode
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        self.btn_filter_all = ttk.Button(toolbar, text="Tampilkan Semua", command=lambda: self._set_filter("ALL"))
        self.btn_filter_all.pack(side="left", padx=2)
        self.btn_filter_rev = ttk.Button(toolbar, text="Hanya Sedang & Rendah", command=lambda: self._set_filter("REVIEW_ONLY"))
        self.btn_filter_rev.pack(side="left", padx=2)

        # 3. Tabel Treeview
        tree_frame = ttk.Frame(self, padding=(12, 6))
        tree_frame.pack(fill="both", expand=True)

        columns = ("approved", "file", "category", "confidence", "old_text", "new_text", "location")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("approved", text="Status")
        self.tree.heading("file", text="Dokumen")
        self.tree.heading("category", text="Kategori")
        self.tree.heading("confidence", text="Keyakinan")
        self.tree.heading("old_text", text="Teks Asli di Dokumen")
        self.tree.heading("new_text", text="Teks Baru Pengganti")
        self.tree.heading("location", text="Struktur Lokasi")

        self.tree.column("approved", width=65, anchor="center")
        self.tree.column("file", width=180, anchor="w")
        self.tree.column("category", width=130, anchor="w")
        self.tree.column("confidence", width=90, anchor="center")
        self.tree.column("old_text", width=190, anchor="w")
        self.tree.column("new_text", width=190, anchor="w")
        self.tree.column("location", width=140, anchor="w")

        sb_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        sb_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        sb_y.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")

        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._toggle_selection)
        self.tree.bind("<space>", self._toggle_selection)

        # Konfigurasi Tag Warna Keyakinan
        self.tree.tag_configure("HIGH", foreground="#006600")
        self.tree.tag_configure("MEDIUM", foreground="#8a6d00")
        self.tree.tag_configure("LOW", foreground="#b30000")
        self.tree.tag_configure("REJECTED", foreground="#888888")

        # 4. Tombol Aksi Bawah
        bottom_frame = ttk.Frame(self, padding=(12, 10))
        bottom_frame.pack(fill="x")

        self.lbl_approved_count = ttk.Label(bottom_frame, text="", font=("Segoe UI", 9, "bold"))
        self.lbl_approved_count.pack(side="left")

        btn_cancel = ttk.Button(bottom_frame, text="Batal", command=self._on_cancel)
        btn_cancel.pack(side="right", padx=(6, 0))

        btn_save = ttk.Button(
            bottom_frame,
            text="LANJUTKAN & SIMPAN PERUBAHAN DOKUMEN",
            command=self._on_confirm
        )
        btn_save.pack(side="right", ipady=3)

    def _populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        approved_count = 0
        for idx, it in enumerate(self.plan_items):
            if self.filter_mode == "REVIEW_ONLY" and it.confidence == ConfidenceLevel.HIGH:
                continue

            status_mark = "✓ Setuju" if it.is_approved else "✗ Batal"
            tag = it.confidence if it.is_approved else "REJECTED"

            values = (
                status_mark,
                it.rel_path,
                it.category,
                it.confidence,
                it.old_text.strip() if it.old_text else "(kosong/placeholder)",
                it.new_text.strip(),
                it.location_info
            )
            self.tree.insert("", "end", iid=str(idx), values=values, tags=(tag,))

        total_approved = sum(1 for it in self.plan_items if it.is_approved)
        self.lbl_approved_count.config(text=f"Total disetujui: {total_approved} dari {len(self.plan_items)} titik")

    def _toggle_selection(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        item = self.plan_items[idx]
        item.is_approved = not item.is_approved

        status_mark = "✓ Setuju" if item.is_approved else "✗ Batal"
        tag = item.confidence if item.is_approved else "REJECTED"

        cur_values = list(self.tree.item(str(idx), "values"))
        cur_values[0] = status_mark
        self.tree.item(str(idx), values=cur_values, tags=(tag,))

        total_approved = sum(1 for it in self.plan_items if it.is_approved)
        self.lbl_approved_count.config(text=f"Total disetujui: {total_approved} dari {len(self.plan_items)} titik")

    def _approve_all(self):
        for it in self.plan_items:
            it.is_approved = True
        self._populate_tree()

    def _reject_all(self):
        for it in self.plan_items:
            it.is_approved = False
        self._populate_tree()

    def _skip_low_confidence(self):
        for it in self.plan_items:
            if it.confidence == ConfidenceLevel.LOW:
                it.is_approved = False
        self._populate_tree()

    def _set_filter(self, mode: str):
        self.filter_mode = mode
        self._populate_tree()

    def _on_confirm(self):
        approved = sum(1 for it in self.plan_items if it.is_approved)
        if approved == 0:
            if not messagebox.askyesno(
                "Konfirmasi",
                "Tidak ada perubahan yang disetujui. Dokumen tidak akan mengalami perubahan.\nLanjutkan?"
            ):
                return
        self.confirmed = True
        self.destroy()

    def _on_cancel(self):
        self.confirmed = False
        self.destroy()
