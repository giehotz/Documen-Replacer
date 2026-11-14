"""
Komponen GUI: Dialog Ringkasan Hasil Prediksi Dokumen (PredictionSummaryDialog).
Menampilkan laporan eksekutif pasca-pemindaian dokumen:
- Kartu metrik ringkasan (Berkas, Aturan, Kategori, Label Tak Dikenal)
- Tabulir rincian Aturan Penggantian yang disiapkan
- Tabulir daftar Label Tak Dikenal beserta frekuensinya
- Tombol aksi terpadu untuk langsung menerapkan ke tabel atau memetakan ke kamus
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Any, Optional, Callable


class PredictionSummaryDialog(tk.Toplevel):
    """
    Dialog modal ringkasan eksekutif hasil analisis & prediksi dokumen.
    """

    def __init__(
        self,
        parent: tk.Widget,
        target_path: str,
        is_folder: bool,
        rules: List[Dict[str, str]],
        unknown_labels: Dict[str, int],
        field_dictionary: Optional[Any] = None,
        on_apply: Optional[Callable[[List[Dict[str, str]]], None]] = None,
        on_open_dictionary: Optional[Callable[[Dict[str, int]], None]] = None,
    ):
        super().__init__(parent)
        self.target_path = target_path
        self.is_folder = is_folder
        self.rules = rules
        self.unknown_labels = unknown_labels
        self.field_dictionary = field_dictionary
        self.on_apply = on_apply
        self.on_open_dictionary = on_open_dictionary

        self.applied = False

        self.title("Ringkasan Hasil Analisis & Prediksi Dokumen - Smart RPP Replacer")
        self.geometry("820x580")
        self.minsize(700, 460)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        # 1. Header Frame
        header = ttk.Frame(self, padding=(14, 12, 14, 6))
        header.pack(fill="x")

        target_name = os.path.basename(self.target_path) or self.target_path
        tipe_sumber = "Folder Input" if self.is_folder else "Berkas Dokumen"

        lbl_title = ttk.Label(
            header,
            text="✨ Hasil Analisis & Prediksi Aturan Dokumen",
            font=("Segoe UI", 12, "bold")
        )
        lbl_title.pack(anchor="w")

        lbl_sub = ttk.Label(
            header,
            text=f"Sumber {tipe_sumber}: {target_name} ({self.target_path})",
            foreground="#555555",
            font=("Segoe UI", 9)
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))

        # 2. Kartu Metrik Ringkasan
        metrics_frame = ttk.LabelFrame(self, text=" Ringkasan Metrik Hasil Pemindaian ", padding=8)
        metrics_frame.pack(fill="x", padx=14, pady=6)
        for i in range(4):
            metrics_frame.columnconfigure(i, weight=1)

        unique_cats = len({r.get("label", "").strip() for r in self.rules if r.get("label", "").strip()})
        cards_data = [
            ("Sumber Data", "Folder" if self.is_folder else "1 Dokumen", "#1e1e1e"),
            ("Aturan Disiapkan", f"{len(self.rules)} Aturan", "#0b8043"),
            ("Kategori Dikenali", f"{unique_cats} Kategori", "#1a73e8"),
            ("Label Belum Terdaftar", f"{len(self.unknown_labels)} Label", "#b06000" if self.unknown_labels else "#555555"),
        ]

        for col, (label, val, color) in enumerate(cards_data):
            card = ttk.Frame(metrics_frame, padding=4)
            card.grid(row=0, column=col, sticky="ew")
            ttk.Label(card, text=val, font=("Segoe UI", 13, "bold"), foreground=color).pack()
            ttk.Label(card, text=label, font=("Segoe UI", 8)).pack()

        # 3. Tabulir Konten (Notebook)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=14, pady=(4, 8))

        # --- TAB 1: DAFTAR ATURAN PENGGANTIAN ---
        tab_rules = ttk.Frame(notebook, padding=6)
        notebook.add(tab_rules, text=f" 📝 Aturan Penggantian Data ({len(self.rules)}) ")

        tree_rules_frame = ttk.Frame(tab_rules)
        tree_rules_frame.pack(fill="both", expand=True)

        cols_rules = ("no", "label", "old", "new")
        self.tree_rules = ttk.Treeview(tree_rules_frame, columns=cols_rules, show="headings", selectmode="browse")
        self.tree_rules.heading("no", text="#", anchor="center")
        self.tree_rules.heading("label", text="Kategori / Label", anchor="w")
        self.tree_rules.heading("old", text="Teks Lama (Ditemukan di Dokumen)", anchor="w")
        self.tree_rules.heading("new", text="Teks Baru (Target Isian)", anchor="w")

        self.tree_rules.column("no", width=38, anchor="center", stretch=False)
        self.tree_rules.column("label", width=200, anchor="w")
        self.tree_rules.column("old", width=260, anchor="w")
        self.tree_rules.column("new", width=240, anchor="w")

        sb_r = ttk.Scrollbar(tree_rules_frame, orient="vertical", command=self.tree_rules.yview)
        self.tree_rules.configure(yscrollcommand=sb_r.set)

        self.tree_rules.pack(side="left", fill="both", expand=True)
        sb_r.pack(side="right", fill="y")

        for idx, r in enumerate(self.rules, start=1):
            lbl_val = r.get("label", "")
            old_val = r.get("old", "")
            new_val = r.get("new", "")
            self.tree_rules.insert("", "end", values=(idx, lbl_val, old_val or "(dicari otomatis saat proses)", new_val or "(kosong - isi di tabel)"))

        # --- TAB 2: LABEL TAK DIKENAL DI KAMUS ---
        tab_unknowns = ttk.Frame(notebook, padding=6)
        notebook.add(tab_unknowns, text=f" ❓ Label Belum Terdaftar ({len(self.unknown_labels)}) ")

        tree_unk_frame = ttk.Frame(tab_unknowns)
        tree_unk_frame.pack(fill="both", expand=True)

        cols_unk = ("no", "label", "count")
        self.tree_unk = ttk.Treeview(tree_unk_frame, columns=cols_unk, show="headings", selectmode="browse")
        self.tree_unk.heading("no", text="#", anchor="center")
        self.tree_unk.heading("label", text="Label Ditemukan di Dokumen", anchor="w")
        self.tree_unk.heading("count", text="Kemunculan", anchor="center")

        self.tree_unk.column("no", width=45, anchor="center", stretch=False)
        self.tree_unk.column("label", width=520, anchor="w")
        self.tree_unk.column("count", width=110, anchor="center")

        sb_u = ttk.Scrollbar(tree_unk_frame, orient="vertical", command=self.tree_unk.yview)
        self.tree_unk.configure(yscrollcommand=sb_u.set)

        self.tree_unk.pack(side="left", fill="both", expand=True)
        sb_u.pack(side="right", fill="y")

        if self.unknown_labels:
            for idx, (lbl, cnt) in enumerate(self.unknown_labels.items(), start=1):
                self.tree_unk.insert("", "end", values=(idx, lbl, f"{cnt}x"))
        else:
            self.tree_unk.insert("", "end", values=("-", "(Semua label dokumen sudah cocok dengan kamus)", "-"))

        # 4. Action Button Bar
        btn_bar = ttk.Frame(self, padding=(14, 8, 14, 12))
        btn_bar.pack(fill="x")

        if self.unknown_labels and self.on_open_dictionary:
            btn_dict = ttk.Button(
                btn_bar,
                text=f"📖 Petakan Label ke Kamus ({len(self.unknown_labels)})...",
                command=self._on_map_to_dictionary
            )
            btn_dict.pack(side="left")

        btn_apply = ttk.Button(
            btn_bar,
            text="✔ Terapkan ke Tabel Aturan",
            command=self._on_apply_click
        )
        btn_apply.pack(side="right", padx=(8, 0))

        btn_close = ttk.Button(
            btn_bar,
            text="Tutup",
            command=self.destroy
        )
        btn_close.pack(side="right")

    def _on_apply_click(self):
        """Menerapkan aturan ke tabel penggantian di Tab 1."""
        if self.on_apply:
            try:
                self.on_apply(self.rules)
                self.applied = True
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menerapkan aturan:\n{e}")
                return

        messagebox.showinfo(
            "Aturan Berhasil Diterapkan",
            f"Berhasil memuat {len(self.rules)} aturan penggantian ke dalam tabel Tab 1!\n\n"
            f"• Kolom 'Teks Lama' telah disesuaikan dengan format dokumen.\n"
            f"• Nilai profil 'Teks Baru' Anda tetap dipertahankan."
        )
        self.destroy()

    def _on_map_to_dictionary(self):
        """Membuka dialog pemetaan label tak dikenal."""
        if self.on_open_dictionary and self.unknown_labels:
            self.on_open_dictionary(self.unknown_labels)
