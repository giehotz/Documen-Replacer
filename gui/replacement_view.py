"""
Komponen GUI Tampilan Aturan Penggantian Teks.
Mendukung kolom Teks Lama opsional dan pilihan Mode Pencarian.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from typing import List, Dict, Any, Tuple


class ReplacementView(ttk.LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            text=" 2. Aturan Penggantian Data (Kolom 'Teks Lama' opsional / otomatis dicari jika kosong) ",
            padding=10,
            **kwargs
        )
        self.rows_data: List[Tuple[ttk.Entry, ttk.Entry, ttk.Entry, ttk.Frame, ttk.Button]] = []

        self.search_mode_var = tk.StringVar(value="GABUNGAN")

        self.default_fields = [
            ("Nama Sekolah/Madrasah", "SD Negeri 1 Contoh", "MIN 2 Tanggamus"),
            ("Istilah Jabatan Kepala", "Kepala Sekolah", "Kepala Madrasah"),
            ("Tahun Ajaran", "2025/2026", "2026/2027"),
            ("Semester", "Ganjil", "Genap"),
            ("Nama Kepala Madrasah", "", "Sipulloh, M.Pd"),
            ("NIP Kepala Madrasah", "", "197005272007011022"),
            ("Nama Guru Penyusun", "", "Misri Kurniati, S.Pd.I"),
            ("NIP / NUPTK Guru", "", "197703232007102004"),
            ("Titimangsa (Tempat, Tgl)", "", "Tanggamus, 13 Juli 2026"),
        ]

        self._build_ui()
        self.load_default_rows()

    def _build_ui(self):
        # 1. Panel Mode Pencarian
        mode_frame = ttk.LabelFrame(self, text=" Mode Pencarian & Deteksi ", padding=(8, 4))
        mode_frame.pack(fill="x", pady=(0, 8))

        row1 = ttk.Frame(mode_frame)
        row1.pack(fill="x", pady=1)
        row2 = ttk.Frame(mode_frame)
        row2.pack(fill="x", pady=(2, 1))

        modes_text = [
            ("Gabungan (Disarankan: Exact Match lalu Cerdas Otomatis)", "GABUNGAN"),
            ("Pencarian Persis Saja (Exact Match)", "PERSIS"),
            ("Otomatis Cerdas Murni (Abaikan Teks Lama)", "OTOMATIS"),
        ]
        for text, val in modes_text:
            ttk.Radiobutton(
                row1,
                text=text,
                value=val,
                variable=self.search_mode_var,
                command=self._on_mode_changed
            ).pack(side="left", padx=10, pady=1)

        ttk.Radiobutton(
            row2,
            text="✍ Hanya Sisipkan Tanda Tangan (Tanpa Ubah Teks Dokumen Yang Sudah Diedit)",
            value="SIGNATURE_ONLY",
            variable=self.search_mode_var,
            command=self._on_mode_changed
        ).pack(side="left", padx=10, pady=1)

        # 2. Bar Tombol Aksi Preset & Tambah Baris
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        self.btn_add_row = ttk.Button(bar, text="+ Tambah Baris Kustom", command=lambda: self.add_row("Kustom", "", ""))
        self.btn_add_row.pack(side="left")
        self.btn_sig_designer = ttk.Button(bar, text="✍ Atur Tanda Tangan Digital...", command=self._open_signature_designer)
        self.btn_sig_designer.pack(side="left", padx=(10, 0))
        self.btn_save_preset = ttk.Button(bar, text="Simpan Profil (.json)", command=self.save_preset)
        self.btn_save_preset.pack(side="right", padx=(5, 0))
        self.btn_load_preset = ttk.Button(bar, text="Muat Profil (.json)", command=self.load_preset)
        self.btn_load_preset.pack(side="right")

        # 3. Header Kolom
        header = ttk.Frame(self)
        header.pack(fill="x", padx=(0, 18), pady=(0, 4))
        self._configure_cols(header)
        bold = ("Segoe UI", 9, "bold")
        ttk.Label(header, text="Kategori / Label", font=bold).grid(row=0, column=0, sticky="w", padx=3)
        ttk.Label(header, text="Teks Lama di RPP (opsional / cari persis)", font=bold).grid(row=0, column=1, sticky="w", padx=3)
        ttk.Label(header, text="Teks Baru (Target Isian)", font=bold).grid(row=0, column=2, sticky="w", padx=3)
        ttk.Label(header, width=4).grid(row=0, column=3)

        # 4. Canvas Scrollable untuk Baris
        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, highlightthickness=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.scrollable = ttk.Frame(self.canvas)
        self.win_id = self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)

        self.scrollable.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win_id, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True, pady=2)
        sb.pack(side="right", fill="y", pady=2)
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    @staticmethod
    def _configure_cols(frame):
        frame.columnconfigure(0, minsize=170)
        frame.columnconfigure(1, weight=1, uniform="c")
        frame.columnconfigure(2, weight=1, uniform="c")
        frame.columnconfigure(3, minsize=36)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def load_default_rows(self):
        for label, old, new in self.default_fields:
            self.add_row(label, old, new)

    def add_row(self, label_text: str = "", old_text: str = "", new_text: str = ""):
        frame = ttk.Frame(self.scrollable)
        frame.pack(fill="x", pady=2)
        self._configure_cols(frame)

        lbl = ttk.Entry(frame)
        lbl.insert(0, label_text)
        lbl.grid(row=0, column=0, padx=3, sticky="ew")

        old = ttk.Entry(frame)
        old.insert(0, old_text)
        old.grid(row=0, column=1, padx=3, sticky="ew")

        new = ttk.Entry(frame)
        new.insert(0, new_text)
        new.grid(row=0, column=2, padx=3, sticky="ew")

        btn_del = ttk.Button(
            frame,
            text="X",
            width=3,
            command=lambda: self.remove_row(frame)
        )
        btn_del.grid(row=0, column=3, padx=3)

        if self.search_mode_var.get() == "SIGNATURE_ONLY":
            lbl.configure(state="disabled")
            old.configure(state="disabled")
            new.configure(state="disabled")
            btn_del.configure(state="disabled")

        self.rows_data.append((lbl, old, new, frame, btn_del))

    def remove_row(self, target_frame):
        for item in self.rows_data:
            if item[3] is target_frame:
                target_frame.destroy()
                self.rows_data.remove(item)
                break

    def _set_replacement_rules_state(self, state: str):
        """Mengubah status input rules (normal / disabled)."""
        self.btn_add_row.configure(state=state)
        self.btn_save_preset.configure(state=state)
        self.btn_load_preset.configure(state=state)
        for lbl, old, new, frame, btn_del in self.rows_data:
            try:
                lbl.configure(state=state)
                old.configure(state=state)
                new.configure(state=state)
                btn_del.configure(state=state)
            except Exception:
                pass

    def _on_mode_changed(self):
        """Dipanggil saat radio button mode pencarian berubah."""
        mode = self.search_mode_var.get()
        if mode == "SIGNATURE_ONLY":
            self.configure(text=" 2. Aturan Penggantian Data [NONAKTIF: Mode Hanya Sisipkan Tanda Tangan Tanpa Ubah Teks] ")
            self._set_replacement_rules_state("disabled")
        else:
            self.configure(text=" 2. Aturan Penggantian Data (Kolom 'Teks Lama' opsional / otomatis dicari jika kosong) ")
            self._set_replacement_rules_state("normal")

    def get_rules(self) -> List[Dict[str, str]]:
        rules = []
        for item in self.rows_data:
            lbl, old, new = item[0], item[1], item[2]
            k_lbl = lbl.get().strip()
            k_old = old.get().strip()
            k_new = new.get().strip()
            # Hanya simpan baris yang memiliki label atau old/new
            if k_lbl or k_old or k_new:
                rules.append({"label": k_lbl, "old": k_old, "new": k_new})
        return rules

    def get_search_mode(self) -> str:
        return self.search_mode_var.get()

    def _open_signature_designer(self):
        from gui.signature_designer_dialog import SignatureDesignerDialog
        SignatureDesignerDialog(self.winfo_toplevel())

    def save_preset(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Preset", "*.json")],
            title="Simpan Profil Aturan"
        )
        if not path:
            return
        data = self.get_rules()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Berhasil", f"Profil berhasil disimpan:\n{path}")
        except Exception as e:
            messagebox.showerror("Gagal", f"Gagal menyimpan profil:\n{e}")

    def load_preset(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON Preset", "*.json")],
            title="Pilih File Profil Aturan (.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Gagal", f"File profil tidak valid:\n{e}")
            return

        # Hapus baris lama
        for item in list(self.rows_data):
            item[3].destroy()
        self.rows_data.clear()

        for item in data:
            self.add_row(
                item.get("label", ""),
                item.get("old", ""),
                item.get("new", "")
            )
