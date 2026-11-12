"""
Komponen GUI Tampilan Aturan Penggantian Teks.
Mendukung pemilihan field berbasis Kamus (FieldDictionary), feedback pengenalan label,
validasi lunak format data, kolom Teks Lama opsional, dan deteksi label tak dikenal.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import logging
from typing import List, Dict, Any, Tuple, Optional, Callable

from core.field_dictionary import FieldDictionary

logger = logging.getLogger(__name__)


class ReplacementView(ttk.LabelFrame):
    def __init__(
        self,
        parent,
        get_input_dir=None,
        field_dictionary: Optional[FieldDictionary] = None,
        on_dictionary_changed: Optional[Callable[[], None]] = None,
        on_signature_changed: Optional[Callable[[Dict[str, Any]], None]] = None,
        **kwargs
    ):
        super().__init__(
            parent,
            text=" 2. Aturan Penggantian Data (Kolom 'Teks Lama' opsional / otomatis dicari jika kosong) ",
            padding=10,
            **kwargs
        )
        self.rows_data: List[Tuple[Any, ttk.Entry, ttk.Entry, ttk.Frame, ttk.Button]] = []
        self.get_input_dir = get_input_dir
        self.on_dictionary_changed = on_dictionary_changed
        self.on_signature_changed = on_signature_changed
        self.field_dictionary = field_dictionary or FieldDictionary.load()

        self.search_mode_var = tk.StringVar(value="GABUNGAN")

        self.default_fields = [
            ("Nama Sekolah/Madrasah", "SD Negeri 1 Contoh", "MIN 1 Contoh"),
            ("Istilah Jabatan Kepala", "Kepala Sekolah", "Kepala Madrasah"),
            ("Tahun Ajaran", "2025/2026", "2026/2027"),
            ("Semester", "Ganjil", "Genap"),
            ("Nama Kepala Madrasah", "", "Ahmad Dahlan, M.Pd"),
            ("NIP Kepala Madrasah", "", "198001012005011001"),
            ("Nama Guru Penyusun", "", "Siti Aminah, S.Pd"),
            ("NIP / NUPTK Guru", "", "198502022010012002"),
            ("Titimangsa (Tempat, Tgl)", "", "Jakarta, 15 Juli 2026"),
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

        # 2. Bar Tombol Aksi Preset, Tambah Baris, Kamus & Prediksi
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        self.btn_add_row = ttk.Button(bar, text="+ Tambah Baris Kustom", command=lambda: self.add_row("Kustom", "", ""))
        self.btn_add_row.pack(side="left")
        self.btn_sig_designer = ttk.Button(bar, text="✍ Atur Tanda Tangan Digital...", command=self._open_signature_designer)
        self.btn_sig_designer.pack(side="left", padx=(8, 0))
        self.btn_predict = ttk.Button(bar, text="🔍 Prediksi dari Dokumen...", command=self._open_predict_menu)
        self.btn_predict.pack(side="left", padx=(8, 0))
        self.btn_dict = ttk.Button(bar, text="📖 Kelola Kamus...", command=self._open_dictionary_dialog)
        self.btn_dict.pack(side="left", padx=(8, 0))

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
        frame.columnconfigure(0, minsize=180)
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

        # Kolom 0: Label Field (Combobox dengan Badge Status)
        col0_frame = ttk.Frame(frame)
        col0_frame.grid(row=0, column=0, padx=3, sticky="ew")

        field_vals = [f.display_label for f in self.field_dictionary.fields()]
        lbl = ttk.Combobox(col0_frame, values=field_vals)
        lbl.insert(0, label_text)
        lbl.pack(side="left", fill="x", expand=True)

        lbl_badge = ttk.Label(col0_frame, text="", width=2, font=("Segoe UI", 9, "bold"))
        lbl_badge.pack(side="right", padx=(2, 0))

        # Kolom 1: Teks Lama
        old = ttk.Entry(frame)
        old.insert(0, old_text)
        old.grid(row=0, column=1, padx=3, sticky="ew")

        # Kolom 2: Teks Baru
        new = ttk.Entry(frame)
        new.insert(0, new_text)
        new.grid(row=0, column=2, padx=3, sticky="ew")

        # Baris 1 Kolom 2: Peringatan Validasi Lunak (jika format nilai kurang sesuai)
        lbl_warn = ttk.Label(frame, text="", font=("Segoe UI", 8), foreground="#b06000")
        lbl_warn.grid(row=1, column=2, sticky="w", padx=3)

        btn_del = ttk.Button(
            frame,
            text="X",
            width=3,
            command=lambda: self.remove_row(frame)
        )
        btn_del.grid(row=0, column=3, padx=3)

        frame.lbl_badge = lbl_badge
        frame.lbl_warn = lbl_warn

        row_item = (lbl, old, new, frame, btn_del)

        # Event binding untuk validasi interaktif dan status badge
        lbl.bind("<<ComboboxSelected>>", lambda e: self._update_row_feedback(row_item))
        lbl.bind("<KeyRelease>", lambda e: self.after(200, lambda: self._update_row_feedback(row_item)))
        new.bind("<KeyRelease>", lambda e: self.after(250, lambda: self._update_row_feedback(row_item)))

        if self.search_mode_var.get() == "SIGNATURE_ONLY":
            lbl.configure(state="disabled")
            old.configure(state="disabled")
            new.configure(state="disabled")
            btn_del.configure(state="disabled")

        self.rows_data.append(row_item)
        self._update_row_feedback(row_item)

    def _update_row_feedback(self, row_item: Tuple[Any, ttk.Entry, ttk.Entry, ttk.Frame, ttk.Button]):
        """Memperbarui badge status pengenalan label dan pesan validasi lunak pada baris."""
        lbl_widget, old_widget, new_widget, frame, _ = row_item
        lbl_val = lbl_widget.get().strip()
        new_val = new_widget.get().strip()

        lbl_badge = getattr(frame, "lbl_badge", None)
        lbl_warn = getattr(frame, "lbl_warn", None)

        if not lbl_val:
            if lbl_badge:
                lbl_badge.configure(text="", foreground="black")
            if lbl_warn:
                lbl_warn.configure(text="")
            return

        res = self.field_dictionary.resolve(lbl_val)
        if res.field:
            if lbl_badge:
                lbl_badge.configure(text="✔", foreground="#0b8043")
            warning = self.field_dictionary.validate_value(res.field.id, new_val) if new_val else None
            if warning:
                if lbl_warn:
                    lbl_warn.configure(text=f"⚠ {warning}", foreground="#b06000")
            else:
                if lbl_warn:
                    lbl_warn.configure(text="")
        else:
            if lbl_badge:
                lbl_badge.configure(text="?", foreground="#c5221f")
            if lbl_warn:
                lbl_warn.configure(text="")

    def remove_row(self, target_frame):
        for item in self.rows_data:
            if item[3] is target_frame:
                target_frame.destroy()
                self.rows_data.remove(item)
                break

    def _set_replacement_rules_state(self, state: str):
        """Mengubah status input rules (normal / disabled)."""
        self.btn_add_row.configure(state=state)
        self.btn_predict.configure(state=state)
        self.btn_dict.configure(state=state)
        self.btn_save_preset.configure(state=state)
        self.btn_load_preset.configure(state=state)
        for item in self.rows_data:
            lbl, old, new, frame, btn_del = item
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
        SignatureDesignerDialog(self.winfo_toplevel(), on_save_callback=self._on_sig_saved)

    def _on_sig_saved(self, new_settings):
        if self.on_signature_changed:
            try:
                self.on_signature_changed(new_settings)
            except Exception as e:
                logger.warning("Error pada on_signature_changed callback: %s", e)

    def _open_dictionary_dialog(self):
        from gui.dictionary_dialog import DictionaryManagerDialog
        DictionaryManagerDialog(
            self.winfo_toplevel(),
            dictionary=self.field_dictionary,
            on_saved_callback=self._on_dict_updated
        )

    def _open_unknown_labels_dialog(self, unknown_dict: Dict[str, int]):
        from gui.dictionary_dialog import UnknownLabelsDialog
        UnknownLabelsDialog(
            self.winfo_toplevel(),
            unknown_labels=unknown_dict,
            dictionary=self.field_dictionary,
            on_synonym_added_callback=self._on_dict_updated
        )

    def _on_dict_updated(self):
        """Dipanggil saat kamus pengguna diperbarui via dialog."""
        if self.on_dictionary_changed:
            try:
                self.on_dictionary_changed()
            except Exception as e:
                logger.warning("Error pada on_dictionary_changed callback: %s", e)

        # Refresh nilai pilihan combobox dan status badge di seluruh baris
        field_vals = [f.display_label for f in self.field_dictionary.fields()]
        for item in self.rows_data:
            lbl_widget = item[0]
            if isinstance(lbl_widget, ttk.Combobox):
                lbl_widget.configure(values=field_vals)
            self._update_row_feedback(item)

    @staticmethod
    def _get_config_dir() -> str:
        """Mengembalikan path direktori config proyek secara dinamis dan portabel antar perangkat/lokasi."""
        import sys
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg_dir = os.path.join(base_dir, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        return cfg_dir

    def save_preset(self):
        cfg_dir = self._get_config_dir()
        path = filedialog.asksaveasfilename(
            initialdir=cfg_dir,
            defaultextension=".json",
            filetypes=[("JSON Preset", "*.json")],
            title="Simpan Profil Aturan"
        )
        if not path:
            return

        rules = self.get_rules()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rules, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Berhasil", f"Profil aturan berhasil disimpan ke:\n{path}")
        except Exception as e:
            messagebox.showerror("Gagal", f"Gagal menyimpan profil:\n{e}")

    def load_preset(self):
        cfg_dir = self._get_config_dir()
        path = filedialog.askopenfilename(
            initialdir=cfg_dir,
            filetypes=[("JSON Preset", "*.json")],
            title="Pilih File Profil Aturan (.json)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.apply_rules_to_table(data)
            messagebox.showinfo("Berhasil", f"Profil aturan dimuat dari:\n{path}")
        except Exception as e:
            messagebox.showerror("Gagal", f"Gagal memuat profil:\n{e}")

    def apply_rules_to_table(self, rules: List[Dict[str, str]]):
        """Menerapkan daftar aturan ke dalam tabel input GUI."""
        for item in list(self.rows_data):
            item[3].destroy()
        self.rows_data.clear()

        for item in rules:
            self.add_row(
                item.get("label", ""),
                item.get("old", ""),
                item.get("new", "")
            )

    def _open_predict_menu(self):
        """Menampilkan popup menu opsi prediksi dokumen."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="📄 Pilih 1 File Dokumen Contoh (.docx, .doc)...",
            command=self._predict_from_single_file
        )
        menu.add_command(
            label="📁 Pindai Seluruh Folder Dokumen Input...",
            command=self._predict_from_folder
        )
        try:
            x = self.btn_predict.winfo_rootx()
            y = self.btn_predict.winfo_rooty() + self.btn_predict.winfo_height()
            menu.tk_popup(x, y)
        except (tk.TclError, RuntimeError) as e:
            logger.warning("Gagal menampilkan popup menu prediksi (%s), fallback ke dialog berkas tunggal.", e)
            self._predict_from_single_file()

    def _predict_from_single_file(self):
        """Menganalisis 1 file Word (.docx / .doc) contoh dan mengisi tabel secara cerdas."""
        path = filedialog.askopenfilename(
            filetypes=[
                ("Semua Dokumen Word", "*.docx;*.doc"),
                ("Word Modern (*.docx)", "*.docx"),
                ("Word Lawas (*.doc)", "*.doc"),
                ("Semua File", "*.*")
            ],
            title="Pilih 1 File Dokumen Contoh untuk Dianalisis"
        )
        if not path:
            return

        from core.document_predictor import predict_rules_from_file, collect_unknown_labels
        try:
            current_rules = self.get_rules()
            merged_rules = predict_rules_from_file(path, current_rules=current_rules)
            self.apply_rules_to_table(merged_rules)
            filename = os.path.basename(path)
            messagebox.showinfo(
                "Prediksi Dokumen Berhasil",
                f"Selesai menganalisis dokumen contoh:\n{filename}\n\n"
                f"• {len(merged_rules)} aturan penggantian berhasil disiapkan.\n"
                f"• Kolom 'Teks Lama' telah disesuaikan dengan format dokumen.\n"
                f"• Nilai profil 'Teks Baru' Anda tetap dipertahankan.\n\n"
                f"Silakan periksa isian atau klik 'Simpan Profil (.json)' untuk menyimpannya."
            )

            # Cek deteksi unknown labels
            unknowns = collect_unknown_labels(path, dictionary=self.field_dictionary)
            if unknowns:
                self._open_unknown_labels_dialog(unknowns)
        except Exception as e:
            messagebox.showerror("Gagal Menganalisis Dokumen", f"Terjadi kesalahan saat membaca dokumen:\n{e}")

    def _predict_from_folder(self):
        """Memindai seluruh dokumen dalam folder input dan mengumpulkan variasi unik."""
        target_dir = ""
        if self.get_input_dir:
            try:
                target_dir = self.get_input_dir().strip()
            except Exception:
                target_dir = ""

        if not target_dir or not os.path.isdir(target_dir):
            target_dir = filedialog.askdirectory(title="Pilih Folder Dokumen (.docx, .doc) yang Ingin Dipindai")
            if not target_dir:
                return

        from core.document_predictor import predict_rules_from_folder, collect_unknown_labels
        try:
            current_rules = self.get_rules()
            merged_rules = predict_rules_from_folder(target_dir, current_rules=current_rules)
            self.apply_rules_to_table(merged_rules)
            folder_name = os.path.basename(target_dir) or target_dir
            messagebox.showinfo(
                "Pemindaian Folder Berhasil",
                f"Selesai memindai folder dokumen:\n{folder_name}\n\n"
                f"• {len(merged_rules)} aturan (termasuk semua variasi format unik) berhasil disiapkan.\n"
                f"• Kolom 'Teks Lama' siap mencakup seluruh variasi dokumen.\n"
                f"• Nilai profil 'Teks Baru' Anda tetap dipertahankan."
            )

            # Cek deteksi unknown labels di seluruh folder
            unknowns = collect_unknown_labels(target_dir, dictionary=self.field_dictionary)
            if unknowns:
                self._open_unknown_labels_dialog(unknowns)
        except Exception as e:
            messagebox.showerror("Gagal Memindai Folder", f"Terjadi kesalahan saat memindai folder:\n{e}")
