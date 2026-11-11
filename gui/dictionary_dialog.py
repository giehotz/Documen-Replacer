"""
Komponen GUI: Dialog Pengelola Kamus Field & Dialog Penanganan Unknown Labels.
Menyediakan antarmuka untuk:
1. DictionaryManagerDialog: Melihat dan mengedit sinonim pengguna, serta uji coba pengenalan label.
2. UnknownLabelsDialog: Memetakan label tak dikenal yang ditemukan pasca-prediksi ke field kamus.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional, Callable, List
import logging

from core.field_dictionary import FieldDictionary, FieldDef

logger = logging.getLogger(__name__)


class DictionaryManagerDialog(tk.Toplevel):
    """
    Dialog Modal Pengelola Kamus Field & Sinonim.
    Memungkinkan pengguna melihat sinonim bawaan, menambah/menghapus sinonim pengguna,
    dan menguji pencocokan label dokumen secara real-time.
    """
    def __init__(
        self,
        parent: tk.Tk,
        dictionary: Optional[FieldDictionary] = None,
        on_saved_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.title("📖 Kamus Field & Pemetaan Sinonim Label Dokumen")
        self.geometry("880x620")
        self.minsize(780, 520)
        self.transient(parent)
        self.grab_set()

        self.dictionary = dictionary or FieldDictionary.load()
        self.on_saved_callback = on_saved_callback
        self.fields: List[FieldDef] = self.dictionary.fields()
        self.selected_field: Optional[FieldDef] = None
        self._modified = False

        self._build_ui()
        if self.fields:
            self.field_listbox.selection_set(0)
            self._on_field_selected()

    def _build_ui(self):
        # 1. Header Ringkasan
        header = ttk.Frame(self, padding=(12, 10, 12, 5))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Kelola Kamus Istilah & Sinonim Dokumen RPP",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Kamus ini digunakan oleh sistem cerdas untuk mengenali label dokumen Word secara otomatis.\n"
                 "Anda dapat menambahkan variasi istilah lokal sekolah/madrasah Anda tanpa mengubah kode program.",
            foreground="#555"
        ).pack(anchor="w", pady=(2, 0))

        # 2. Main Content (PanedWindow: Kiri daftar Field, Kanan Detail & Sinonim)
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=12, pady=8)

        # Panel Kiri: Daftar Field
        left_frame = ttk.LabelFrame(paned, text=" Daftar Field Kamus ", padding=8)
        paned.add(left_frame, weight=1)

        self.field_listbox = tk.Listbox(left_frame, exportselection=False, font=("Segoe UI", 9))
        self.field_listbox.pack(fill="both", expand=True, side="left")
        self.field_listbox.bind("<<ListboxSelect>>", lambda e: self._on_field_selected())

        sb_left = ttk.Scrollbar(left_frame, orient="vertical", command=self.field_listbox.yview)
        sb_left.pack(side="right", fill="y")
        self.field_listbox.configure(yscrollcommand=sb_left.set)

        for f in self.fields:
            self.field_listbox.insert("end", f" {f.display_label}")

        # Panel Kanan: Detail Field Terpilih
        right_frame = ttk.Frame(paned, padding=8)
        paned.add(right_frame, weight=2)

        # Detail Info Field
        info_lf = ttk.LabelFrame(right_frame, text=" Informasi Field ", padding=8)
        info_lf.pack(fill="x", pady=(0, 6))

        self.lbl_field_title = ttk.Label(info_lf, text="-", font=("Segoe UI", 10, "bold"))
        self.lbl_field_title.pack(anchor="w")
        self.lbl_field_desc = ttk.Label(info_lf, text="-", foreground="#555")
        self.lbl_field_desc.pack(anchor="w", pady=(2, 0))

        # Frame Dua Kolom Sinonim (Bawaan & Pengguna)
        syn_container = ttk.Frame(right_frame)
        syn_container.pack(fill="both", expand=True, pady=(0, 6))

        # Kolom Kiri: Sinonim Bawaan (Read-only)
        default_lf = ttk.LabelFrame(syn_container, text=" Sinonim Bawaan (Resmi) ", padding=6)
        default_lf.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.list_default_syn = tk.Listbox(default_lf, font=("Segoe UI", 9), bg="#f8f9fa", fg="#333")
        self.list_default_syn.pack(fill="both", expand=True, side="left")
        sb_def = ttk.Scrollbar(default_lf, orient="vertical", command=self.list_default_syn.yview)
        sb_def.pack(side="right", fill="y")
        self.list_default_syn.configure(yscrollcommand=sb_def.set)

        # Kolom Kanan: Sinonim Pengguna (Bisa Tambah/Hapus)
        user_lf = ttk.LabelFrame(syn_container, text=" Sinonim Tambahan Pengguna ", padding=6)
        user_lf.pack(side="right", fill="both", expand=True, padx=(4, 0))

        self.list_user_syn = tk.Listbox(user_lf, font=("Segoe UI", 9))
        self.list_user_syn.pack(fill="both", expand=True, side="left")
        sb_user = ttk.Scrollbar(user_lf, orient="vertical", command=self.list_user_syn.yview)
        sb_user.pack(side="right", fill="y")
        self.list_user_syn.configure(yscrollcommand=sb_user.set)

        # Input Tambah Sinonim Pengguna
        add_frame = ttk.Frame(right_frame)
        add_frame.pack(fill="x", pady=(0, 6))
        self.entry_new_syn = ttk.Entry(add_frame)
        self.entry_new_syn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.entry_new_syn.bind("<Return>", lambda e: self._add_user_synonym())
        ttk.Button(add_frame, text="+ Tambah", command=self._add_user_synonym).pack(side="left", padx=(0, 4))
        ttk.Button(add_frame, text="Hapus Terpilih", command=self._delete_user_synonym).pack(side="left")

        # 3. Uji Coba Pengenalan Label (Real-time Tester)
        tester_lf = ttk.LabelFrame(right_frame, text=" 🧪 Uji Coba Pencocokan Label ", padding=8)
        tester_lf.pack(fill="x", pady=(0, 4))

        test_row = ttk.Frame(tester_lf)
        test_row.pack(fill="x")
        ttk.Label(test_row, text="Ketik teks label dokumen:").pack(side="left", padx=(0, 6))
        self.test_entry = ttk.Entry(test_row)
        self.test_entry.pack(side="left", fill="x", expand=True)
        self.test_entry.bind("<KeyRelease>", lambda e: self._on_test_changed())

        self.lbl_test_result = ttk.Label(tester_lf, text="Hasil: Masukkan teks label di atas untuk menguji.", foreground="#666")
        self.lbl_test_result.pack(anchor="w", pady=(4, 0))

        # 4. Bar Tombol Simpan & Tutup
        bottom_bar = ttk.Frame(self, padding=(12, 6, 12, 12))
        bottom_bar.pack(fill="x")

        self.lbl_status = ttk.Label(bottom_bar, text="", foreground="green")
        self.lbl_status.pack(side="left")

        ttk.Button(bottom_bar, text="Tutup / Batal", command=self.destroy).pack(side="right", padx=(6, 0))
        btn_save = ttk.Button(bottom_bar, text="💾 Simpan Perubahan Kamus", command=self._save_and_close)
        btn_save.pack(side="right")

    def _on_field_selected(self):
        sel = self.field_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.selected_field = self.fields[idx]
        f = self.selected_field

        # Update info header
        self.lbl_field_title.configure(text=f"{f.display_label} (ID: {f.id})")
        never_txt = f" | Hindari: {', '.join(f.never_match)}" if f.never_match else ""
        self.lbl_field_desc.configure(
            text=f"Kategori: {f.category} | Tipe: {f.value_type} | Mode: {f.match_mode}{never_txt}"
        )

        # Refresh sinonim bawaan
        self.list_default_syn.delete(0, "end")
        for s in f.synonyms:
            self.list_default_syn.insert("end", f" • {s}")
        for s in f.exact_only_synonyms:
            self.list_default_syn.insert("end", f" • {s} (persis)")

        # Refresh sinonim pengguna
        self._refresh_user_syn_list()

    def _refresh_user_syn_list(self):
        self.list_user_syn.delete(0, "end")
        if not self.selected_field:
            return
        user_syns = self.dictionary.get_user_synonyms_for_field(self.selected_field.id)
        for s in user_syns:
            self.list_user_syn.insert("end", f" • {s}")

    def _add_user_synonym(self):
        if not self.selected_field:
            return
        val = self.entry_new_syn.get().strip()
        if not val:
            return

        try:
            self.dictionary.add_user_synonym(self.selected_field.id, val)
            self._modified = True
            self.entry_new_syn.delete(0, "end")
            self._refresh_user_syn_list()
            self._on_test_changed()
            self.lbl_status.configure(text=f"Sinonim '{val}' ditambahkan (belum disimpan permanen).", foreground="blue")
        except ValueError as e:
            messagebox.showerror("Gagal Menambahkan Sinonim", str(e), parent=self)

    def _delete_user_synonym(self):
        if not self.selected_field:
            return
        sel = self.list_user_syn.curselection()
        if not sel:
            messagebox.showwarning("Peringatan", "Pilih salah satu sinonim pengguna yang ingin dihapus.", parent=self)
            return

        idx = sel[0]
        user_syns = self.dictionary.get_user_synonyms_for_field(self.selected_field.id)
        if 0 <= idx < len(user_syns):
            to_del = user_syns[idx]
            if self.dictionary.remove_user_synonym(self.selected_field.id, to_del):
                self._modified = True
                self._refresh_user_syn_list()
                self._on_test_changed()
                self.lbl_status.configure(text=f"Sinonim '{to_del}' dihapus.", foreground="blue")

    def _on_test_changed(self):
        query = self.test_entry.get().strip()
        if not query:
            self.lbl_test_result.configure(
                text="Hasil: Masukkan teks label di atas untuk menguji.",
                foreground="#666"
            )
            return

        res = self.dictionary.resolve(query)
        if res.field:
            how_txt = f" (via {res.how}: '{res.matched_synonym}')" if res.matched_synonym else ""
            self.lbl_test_result.configure(
                text=f"✔ Cocok: {res.field.display_label}{how_txt}",
                foreground="#0b8043"
            )
        else:
            self.lbl_test_result.configure(
                text="⚠ Tidak Dikenal (Label ini tidak cocok dengan field mana pun)",
                foreground="#c5221f"
            )

    def _save_and_close(self):
        try:
            self.dictionary.save_user()
            if self.on_saved_callback:
                self.on_saved_callback()
            messagebox.showinfo(
                "Kamus Berhasil Disimpan",
                "Sinonim kustom pengguna berhasil disimpan ke profil lokal Anda.",
                parent=self
            )
            self.destroy()
        except Exception as e:
            messagebox.showerror("Gagal Menyimpan Kamus", f"Terjadi kesalahan saat menyimpan:\n{e}", parent=self)


class UnknownLabelsDialog(tk.Toplevel):
    """
    Dialog Modal Penanganan Label Tak Dikenal.
    Ditampilkan setelah pemindaian dokumen/folder jika ada label yang belum terdaftar di Kamus.
    Pengguna dapat memetakannya secara cepat ke salah satu field kamus.
    """
    def __init__(
        self,
        parent: tk.Tk,
        unknown_labels: Dict[str, int],
        dictionary: Optional[FieldDictionary] = None,
        on_synonym_added_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.title("🔍 Deteksi Label Dokumen Tak Dikenal")
        self.geometry("740x500")
        self.minsize(660, 420)
        self.transient(parent)
        self.grab_set()

        self.unknown_labels = dict(unknown_labels)
        self.dictionary = dictionary or FieldDictionary.load()
        self.on_synonym_added_callback = on_synonym_added_callback
        self.fields = self.dictionary.fields()

        self._build_ui()

    def _build_ui(self):
        header = ttk.Frame(self, padding=(12, 10, 12, 5))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Ditemukan Label Dokumen yang Belum Terdaftar di Kamus",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Sistem menemukan beberapa label di dokumen yang belum memiliki pemetaan.\n"
                 "Petakan label tersebut ke field yang sesuai agar pada pemindaian berikutnya terdeteksi otomatis.",
            foreground="#555"
        ).pack(anchor="w", pady=(2, 0))

        # Tabel Unknown Labels
        table_frame = ttk.Frame(self, padding=(12, 6, 12, 6))
        table_frame.pack(fill="both", expand=True)

        cols = ("label", "count")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("label", text="Teks Label Dokumen")
        self.tree.heading("count", text="Jumlah Ditemukan")
        self.tree.column("label", width=480, anchor="w")
        self.tree.column("count", width=140, anchor="center")
        self.tree.pack(fill="both", expand=True, side="left")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_tree_selected())

        # Isi data
        for lbl, count in self.unknown_labels.items():
            self.tree.insert("", "end", iid=lbl, values=(lbl, f"{count} kali"))

        # Panel Aksi Pemetaan
        action_lf = ttk.LabelFrame(self, text=" Petakan Label Terpilih ", padding=10)
        action_lf.pack(fill="x", padx=12, pady=(0, 6))

        row1 = ttk.Frame(action_lf)
        row1.pack(fill="x")

        ttk.Label(row1, text="Petakan label:").pack(side="left")
        self.lbl_selected_target = ttk.Label(row1, text="(Pilih salah satu baris di atas)", font=("Segoe UI", 9, "bold"))
        self.lbl_selected_target.pack(side="left", padx=(6, 16))

        ttk.Label(row1, text="Ke Field Kamus:").pack(side="left")
        self.combo_field = ttk.Combobox(
            row1,
            values=[f.display_label for f in self.fields],
            state="readonly",
            width=28
        )
        if self.fields:
            self.combo_field.current(0)
        self.combo_field.pack(side="left", padx=(6, 10))

        self.btn_map = ttk.Button(row1, text="➕ Tambahkan ke Kamus", command=self._map_selected_label, state="disabled")
        self.btn_map.pack(side="left")

        # Tombol Bawah
        bottom_bar = ttk.Frame(self, padding=(12, 6, 12, 12))
        bottom_bar.pack(fill="x")
        self.lbl_action_status = ttk.Label(bottom_bar, text="", foreground="green")
        self.lbl_action_status.pack(side="left")

        ttk.Button(bottom_bar, text="Selesai / Tutup", command=self.destroy).pack(side="right")

    def _on_tree_selected(self):
        sel = self.tree.selection()
        if not sel:
            self.lbl_selected_target.configure(text="(Pilih salah satu baris di atas)")
            self.btn_map.configure(state="disabled")
            return
        lbl = sel[0]
        self.lbl_selected_target.configure(text=f"'{lbl}'")
        self.btn_map.configure(state="normal")

    def _map_selected_label(self):
        sel = self.tree.selection()
        if not sel:
            return
        target_lbl = sel[0]
        field_display = self.combo_field.get().strip()

        # Cari field def
        field_def = next((f for f in self.fields if f.display_label == field_display), None)
        if not field_def:
            return

        try:
            self.dictionary.add_user_synonym(field_def.id, target_lbl)
            self.dictionary.save_user()
            self.tree.delete(target_lbl)
            self.lbl_selected_target.configure(text="(Pilih salah satu baris di atas)")
            self.btn_map.configure(state="disabled")
            self.lbl_action_status.configure(
                text=f"✔ Berhasil memetakan '{target_lbl}' ke '{field_def.display_label}'!",
                foreground="#0b8043"
            )
            if self.on_synonym_added_callback:
                self.on_synonym_added_callback()
        except ValueError as e:
            messagebox.showerror("Gagal Memetakan", str(e), parent=self)
