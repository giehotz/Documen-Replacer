"""
Jendela Utama Aplikasi Smart RPP Replacer & Word to PDF Converter (Tkinter GUI).
Mengintegrasikan:
- Tab 1: Penggantian RPP, aturan data, tanda tangan digital, pratinjau, dan eksekusi batch
- Tab 2: Modul Konversi Word ke PDF massal dengan antrean berkas dan progress bar
- Opsi ekspor otomatis ke PDF pasca pengeditan dokumen
"""
import os
import shutil
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Tuple, Dict, Any, Set, Optional

from core.version import APP_TITLE, APP_NAME
from gui.ui_helpers import prevent_global_combobox_mousewheel
from core.doc_compat_service import is_supported_word_file
from core.replacement_engine import ReplacementEngine
from core.field_dictionary import FieldDictionary
from core.validation_engine import ReplacementPlanItem, ConfidenceLevel
from gui.replacement_view import ReplacementView
from gui.preview_view import IntegratedPreviewDialog
from gui.report_view import ReportDialog
from gui.pdf_converter_view import PdfConverterView
from services.report_service import ReportService

try:
    from gui.modules.domain_selector_bar import DomainSelectorBar
    from gui.modules.mail_merge_view import MailMergeView
except ImportError:
    DomainSelectorBar = None
    MailMergeView = None

BASE_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "MODUL", "Edited")


def resolve_output_subfolder(input_path: str, base_docs_dir: str = "") -> str:
    """
    Menentukan subfolder tujuan dengan menyertakan folder induk untuk mencegah
    tumpang tindih nama folder yang sama.
    Contoh: '...\\docs\\06_Kelas 6\\Tahun Pelajaran 2020-2021'
    -> '06_Kelas 6\\Tahun Pelajaran 2020-2021'
    """
    norm_in = os.path.normpath(input_path)
    if os.path.isfile(norm_in) or (not os.path.isdir(norm_in) and os.path.splitext(norm_in)[1]):
        norm_in = os.path.dirname(norm_in)
    if not base_docs_dir:
        base_docs_dir = os.path.normpath(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
        )

    # 1. Jika folder berada di dalam direktori 'docs' proyek ini
    if base_docs_dir and os.path.isdir(base_docs_dir):
        try:
            rel = os.path.relpath(norm_in, base_docs_dir)
            if not rel.startswith("..") and rel != ".":
                return rel
        except Exception:
            pass

    # 2. Jika dari direktori umum luar mana pun: ambil 2 tingkat terakhir jika induk valid
    parts = norm_in.split(os.sep)
    if len(parts) >= 2:
        parent = parts[-2]
        current = parts[-1]
        if not parent.endswith(":") and parent.lower() not in ("desktop", "documents", "downloads", "user"):
            return os.path.join(parent, current)
        return current

    return os.path.basename(norm_in)


class SmartRPPReplacerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1080x820")
        self.root.minsize(920, 680)

        # Otomatis Maximized menyesuaikan layar monitor
        try:
            self.root.state("zoomed")
        except Exception:
            try:
                self.root.attributes("-zoomed", True)
            except Exception:
                pass

        self.field_dictionary = FieldDictionary.load()
        self.engine = ReplacementEngine(field_dictionary=self.field_dictionary)
        self.report_service = ReportService()
        self.msg_queue = queue.Queue()

        self._build_ui()
        self.root.after(100, self._poll_queue)

    def _build_ui(self):
        # 0. Menonaktifkan scroll wheel pada combobox secara global
        prevent_global_combobox_mousewheel(self.root)

        # 0. Menu Bar Sistem
        self._build_menu_bar()

        # Top Bar (Header Branding & Tombol Tentang Cepat)
        top_bar = ttk.Frame(self.root, padding=(10, 6, 10, 4))
        top_bar.pack(fill="x")

        ttk.Label(
            top_bar,
            text=f"📚 {APP_NAME}",
            font=("Segoe UI", 11, "bold"),
            foreground="#1e3a8a",
        ).pack(side="left")

        about_btn = ttk.Button(
            top_bar,
            text="ℹ️ Tentang & Panduan",
            command=lambda: self._open_about_dialog(0),
        )
        about_btn.pack(side="right", padx=(4, 0))

        self.btn_toggle_log = ttk.Button(
            top_bar,
            text="📋 Sembunyikan Log",
            command=self._toggle_log_panel,
        )
        self.btn_toggle_log.pack(side="right", padx=(0, 4))

        # Container Utama Horizontal: Notebook di Kiri, Sidebar Log Global di Kanan
        self.paned_main = ttk.PanedWindow(self.root, orient="horizontal")
        self.paned_main.pack(fill="both", expand=True, padx=6, pady=(2, 2))

        # Pane Kiri: Lembar Kerja Seluruh Tab
        self.left_container = ttk.Frame(self.paned_main)
        self.paned_main.add(self.left_container, weight=3)

        self.notebook = ttk.Notebook(self.left_container)
        self.notebook.pack(fill="both", expand=True)

        # =====================================================================
        # TAB 1: PENGGANTIAN DATA DOKUMEN & TANDA TANGAN
        # =====================================================================
        self.tab_replacer = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_replacer, text=" 📝 Penggantian Data RPP & Tanda Tangan ")
        self._build_replacer_tab(self.tab_replacer)

        # =====================================================================
        # TAB 2: KONVERSI WORD KE PDF
        # =====================================================================
        self.tab_pdf = PdfConverterView(self.notebook, on_status_msg=self._log)
        self.notebook.add(self.tab_pdf, text=" 📄 Konversi Word ke PDF ")

        # =====================================================================
        # TAB 3: GENERATOR DOKUMEN MASSAL (MAIL MERGE)
        # =====================================================================
        if MailMergeView is not None:
            self.tab_mail_merge = MailMergeView(self.notebook)
            self.notebook.add(self.tab_mail_merge, text=" 🖨️ Mail Merge Massal ")
        else:
            self.tab_mail_merge = None

        # Pane Kanan: Sidebar Log Global
        self.log_container = ttk.Frame(self.paned_main, width=340)
        self.paned_main.add(self.log_container, weight=1)
        self.log_visible = True
        self._build_log_sidebar(self.log_container)

    def _build_menu_bar(self):
        """Membangun Menu Bar sistem di bagian paling atas aplikasi."""
        menubar = tk.Menu(self.root)

        # Menu Berkas
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="📄 Pilih 1 Berkas Asli (Input)...", command=self._browse_input_file)
        file_menu.add_command(label="📁 Pilih Folder Asli (Input)...", command=self._browse_input_folder)
        file_menu.add_command(label="📁 Pilih Folder Hasil (Output)...", command=self._browse_output)
        file_menu.add_separator()
        file_menu.add_command(label="Keluar", command=self.root.quit)
        menubar.add_cascade(label="Berkas", menu=file_menu)

        # Menu Tampilan
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="📋 Sembunyikan / Tampilkan Log", command=self._toggle_log_panel)
        menubar.add_cascade(label="Tampilan", menu=view_menu)

        # Menu Bantuan
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="📖 Panduan Penggunaan", command=lambda: self._open_about_dialog(1))
        help_menu.add_command(label="⚖️ Perjanjian & Lisensi", command=lambda: self._open_about_dialog(2))
        help_menu.add_separator()
        help_menu.add_command(label=f"ℹ️ Tentang {APP_NAME}...", command=lambda: self._open_about_dialog(0))
        menubar.add_cascade(label="Bantuan", menu=help_menu)

        self.root.config(menu=menubar)

    def _open_about_dialog(self, initial_tab: int = 0):
        """Membuka dialog modular Tentang Aplikasi."""
        try:
            from gui.about_dialog import AboutDialog
            AboutDialog(self.root, initial_tab=initial_tab)
        except Exception as e:
            self._log(f"[ERROR] Gagal membuka dialog Tentang: {e}")

    def _build_replacer_tab(self, parent: ttk.Frame):
        """Membangun antarmuka Tab 1: Penggantian RPP."""
        # 0. Bilah Pemilih Jenis Dokumen Modular (PRD §7 & Fase 4)
        if DomainSelectorBar is not None:
            self.domain_selector = DomainSelectorBar(
                parent,
                on_domain_changed=self._on_domain_changed
            )
            self.domain_selector.pack(fill="x", padx=10, pady=(6, 2))
        else:
            self.domain_selector = None

        # 1. Panel Folder & Berkas
        folder_frame = ttk.LabelFrame(parent, text=" 1. Dokumen Word atau Folder Input (.docx, .doc) ", padding=10)
        folder_frame.pack(fill="x", padx=10, pady=(8, 4))
        folder_frame.columnconfigure(1, weight=1)

        ttk.Label(folder_frame, text="Dokumen Asli (Input):").grid(row=0, column=0, sticky="w", pady=3)
        self.input_dir_var = tk.StringVar()
        ttk.Entry(folder_frame, textvariable=self.input_dir_var).grid(row=0, column=1, padx=8, pady=3, sticky="ew")

        btn_input_frame = ttk.Frame(folder_frame)
        btn_input_frame.grid(row=0, column=2, pady=3, sticky="e")
        ttk.Button(btn_input_frame, text="📄 Pilih Berkas...", command=self._browse_input_file).pack(side="left", padx=(0, 4))
        ttk.Button(btn_input_frame, text="📁 Pilih Folder...", command=self._browse_input_folder).pack(side="left")

        ttk.Label(folder_frame, text="Folder Hasil (Output):").grid(row=1, column=0, sticky="w", pady=3)
        self.output_dir_var = tk.StringVar(value=BASE_OUTPUT_DIR)
        ttk.Entry(folder_frame, textvariable=self.output_dir_var).grid(row=1, column=1, padx=8, pady=3, sticky="ew")
        ttk.Button(folder_frame, text="📁 Pilih Folder...", command=self._browse_output).grid(row=1, column=2, pady=3)

        opts_frame = ttk.Frame(folder_frame)
        opts_frame.grid(row=2, column=1, sticky="w", pady=(4, 0))
        self.case_var = tk.BooleanVar(value=True)
        self.sub_var = tk.BooleanVar(value=False)
        self.preview_var = tk.BooleanVar(value=True)
        self.skip_low_var = tk.BooleanVar(value=True)
        self.auto_pdf_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(opts_frame, text="Peka huruf besar/kecil", variable=self.case_var).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(opts_frame, text="Sertakan subfolder", variable=self.sub_var).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(opts_frame, text="Tampilkan pratinjau", variable=self.preview_var).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(opts_frame, text="Lewati keyakinan rendah", variable=self.skip_low_var).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(opts_frame, text="Langsung ekspor ke PDF setelah selesai", variable=self.auto_pdf_var).pack(side="left")

        # Label status/mode input dinamis (single file vs folder)
        self.lbl_input_mode = ttk.Label(
            folder_frame,
            text="Belum memilih berkas atau folder input.",
            font=("Segoe UI", 8, "italic"),
            foreground="#666666"
        )
        self.lbl_input_mode.grid(row=3, column=1, sticky="w", padx=8, pady=(2, 0))

        # Hubungkan listener perubahan path input
        self.input_dir_var.trace_add("write", lambda *args: self._on_input_target_changed())

        # 2. Panel Aturan Penggantian
        self.replacement_view = ReplacementView(
            parent,
            get_input_dir=lambda: self.input_dir_var.get(),
            field_dictionary=self.field_dictionary,
            on_dictionary_changed=self._on_dictionary_changed,
            on_signature_changed=self._on_signature_changed,
            on_status_msg=self._log
        )
        self.replacement_view.pack(fill="both", expand=True, padx=10, pady=4)

        # 3. Panel Bawah (Eksekusi Pemrosesan Dokumen)
        bottom_frame = ttk.Frame(parent, padding=8)
        bottom_frame.pack(fill="x", padx=2, pady=2)

        self.btn_process = ttk.Button(
            bottom_frame,
            text="PROSES SEMUA DOKUMEN SEKARANG",
            command=self._start_processing
        )
        self.btn_process.pack(fill="x", ipady=5, pady=(0, 4))

        self.progress = ttk.Progressbar(bottom_frame, mode="determinate")
        self.progress.pack(fill="x")

    def _build_log_sidebar(self, parent: ttk.Frame):
        """Membangun bilah samping (sidebar) panel log aktivitas di sisi kanan."""
        container = ttk.Frame(parent, padding=(4, 2, 4, 4))
        container.pack(fill="both", expand=True)

        # Header Panel Log
        header = ttk.Frame(container)
        header.pack(fill="x", pady=(0, 4))

        ttk.Label(
            header,
            text="📋 Log Aktivitas",
            font=("Segoe UI", 9, "bold"),
            foreground="#1e3a8a"
        ).pack(side="left", anchor="w")

        btn_box = ttk.Frame(header)
        btn_box.pack(side="right")

        ttk.Button(
            btn_box,
            text="📋 Salin",
            width=7,
            command=self._copy_log
        ).pack(side="left", padx=2)

        ttk.Button(
            btn_box,
            text="🗑 Bersihkan",
            width=9,
            command=self._clear_log
        ).pack(side="left", padx=2)

        ttk.Button(
            btn_box,
            text="✖",
            width=3,
            command=self._toggle_log_panel
        ).pack(side="left", padx=(2, 0))

        # Box Teks Log dengan Scrollbar Vertikal
        text_frame = ttk.Frame(container)
        text_frame.pack(fill="both", expand=True)

        self.log_box = tk.Text(
            text_frame,
            wrap="word",
            state="disabled",
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#ffffff",
            font=("Consolas", 9)
        )
        self.log_box.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(text_frame, orient="vertical", command=self.log_box.yview)
        sb.pack(side="right", fill="y")
        self.log_box.configure(yscrollcommand=sb.set)

    def _toggle_log_panel(self):
        """Menampilkan atau menyembunyikan panel log aktivitas di sisi kanan."""
        if getattr(self, "log_visible", True):
            try:
                self.paned_main.forget(self.log_container)
            except Exception:
                pass
            self.log_visible = False
            self.btn_toggle_log.configure(text="📋 Tampilkan Log")
        else:
            try:
                self.paned_main.add(self.log_container, weight=1)
            except Exception:
                pass
            self.log_visible = True
            self.btn_toggle_log.configure(text="📋 Sembunyikan Log")

    def _clear_log(self):
        """Mengosongkan teks riwayat log aktivitas."""
        if hasattr(self, "log_box") and self.log_box:
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.configure(state="disabled")

    def _copy_log(self):
        """Menyalin seluruh isi riwayat log aktivitas ke clipboard sistem."""
        if hasattr(self, "log_box") and self.log_box:
            content = self.log_box.get("1.0", "end").strip()
            if content:
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(content)
                    self._log("[INFO] Seluruh riwayat log disalin ke clipboard.")
                except Exception as e:
                    self._log(f"[WARN] Gagal menyalin ke clipboard: {e}")

    def _browse_input_file(self):
        filetypes = [
            ("Semua Dokumen Word", "*.docx;*.doc"),
            ("Word Document (.docx)", "*.docx"),
            ("Word 97-2003 Document (.doc)", "*.doc"),
            ("Semua File", "*.*")
        ]
        file_path = filedialog.askopenfilename(
            title="Pilih 1 Berkas Dokumen Word Asli",
            filetypes=filetypes
        )
        if file_path:
            norm = os.path.normpath(file_path)
            self.input_dir_var.set(norm)
            subfolder = resolve_output_subfolder(norm)
            self.output_dir_var.set(os.path.join(BASE_OUTPUT_DIR, subfolder))
            self._log(f"[INFO] Memilih berkas tunggal: {os.path.basename(norm)}")

    def _browse_input_folder(self):
        folder = filedialog.askdirectory(title="Pilih Folder Berisi Dokumen Asli (.docx/.doc)")
        if folder:
            norm = os.path.normpath(folder)
            self.input_dir_var.set(norm)
            subfolder = resolve_output_subfolder(norm)
            self.output_dir_var.set(os.path.join(BASE_OUTPUT_DIR, subfolder))
            self._log(f"[INFO] Memilih folder input: {norm}")

    def _browse_input(self):
        """Alias kompatibilitas pemilih folder input."""
        self._browse_input_folder()

    def _on_input_target_changed(self):
        """Memperbarui indikator status mode (berkas tunggal vs folder) dan label tombol aksi."""
        target = self.input_dir_var.get().strip()
        if not target:
            if hasattr(self, "lbl_input_mode"):
                self.lbl_input_mode.configure(
                    text="Belum memilih berkas atau folder input.",
                    foreground="#666666"
                )
            if hasattr(self, "btn_process"):
                self.btn_process.configure(text="PROSES SEMUA DOKUMEN SEKARANG")
            return

        if os.path.isfile(target):
            fname = os.path.basename(target)
            if is_supported_word_file(fname):
                msg = f"📄 Berkas Tunggal Siap Diproses: {fname}"
                color = "#0066cc"
            else:
                msg = f"⚠️ Berkas '{fname}' bukan format Word (.docx/.doc) yang didukung!"
                color = "#cc6600"
            if hasattr(self, "lbl_input_mode"):
                self.lbl_input_mode.configure(text=msg, foreground=color)
            if hasattr(self, "btn_process"):
                self.btn_process.configure(text="PROSES 1 DOKUMEN SEKARANG")
        elif os.path.isdir(target):
            dname = os.path.basename(target) or target
            if hasattr(self, "lbl_input_mode"):
                self.lbl_input_mode.configure(
                    text=f"📁 Folder Siap Dipindai: {dname}",
                    foreground="#2e7d32"
                )
            if hasattr(self, "btn_process"):
                self.btn_process.configure(text="PROSES SEMUA DOKUMEN DALAM FOLDER")
        else:
            if hasattr(self, "lbl_input_mode"):
                self.lbl_input_mode.configure(
                    text="⚠️ Lokasi berkas atau folder tidak ditemukan di penyimpanan komputer.",
                    foreground="#cc0000"
                )
            if hasattr(self, "btn_process"):
                self.btn_process.configure(text="PROSES SEMUA DOKUMEN SEKARANG")

    def _browse_output(self):
        folder = filedialog.askdirectory(title="Pilih Folder Penyimpanan Hasil")
        if folder:
            self.output_dir_var.set(os.path.normpath(folder))

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_domain_changed(self, domain_id: str):
        """Handler pembaruan pilihan domain aktif dari DomainSelectorBar."""
        self._log(f"[INFO] Domain dokumen aktif: {domain_id}")

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "progress":
                    self.progress["value"] = payload
                elif kind == "show_preview":
                    if len(payload) == 6:
                        plan_items, files, out_dir, failed_planning_rels, rules, mode = payload
                    elif len(payload) == 4:
                        plan_items, files, out_dir, failed_planning_rels = payload
                        rules = self.replacement_view.get_rules()
                        mode = self.replacement_view.get_search_mode()
                    else:
                        plan_items, files, out_dir = payload
                        failed_planning_rels = set()
                        rules = self.replacement_view.get_rules()
                        mode = self.replacement_view.get_search_mode()
                    self._handle_preview_dialog(plan_items, files, out_dir, failed_planning_rels, rules, mode)
                elif kind == "done":
                    out_dir = payload
                    self.btn_process.configure(state="normal")
                    self._log(f"--- Selesai! Dokumen dan laporan disimpan di: {out_dir} ---\n")
                    # Tampilkan dialog laporan eksekutif
                    dialog = ReportDialog(self.root, self.report_service, out_dir)

                    # Picu konversi PDF hanya setelah dialog laporan ditutup, agar
                    # prompt tidak bertabrakan dengan grab_set() dialog laporan.
                    if self.auto_pdf_var.get():
                        self.root.wait_window(dialog)
                        self._trigger_auto_pdf_export(out_dir)

        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _trigger_auto_pdf_export(self, out_dir: str):
        """Memindahkan alur kerja ke Tab 2 untuk mengekspor dokumen hasil edit ke PDF."""
        # Pindahkan tab aktif ke Tab 2 (PDF Converter)
        self.notebook.select(self.tab_pdf)
        pdf_out_dir = os.path.join(out_dir, "PDF")
        self.tab_pdf.source_dir_var.set(os.path.normpath(out_dir))
        self.tab_pdf.target_dir_var.set(os.path.normpath(pdf_out_dir))
        self.tab_pdf.scan_documents()

        tanya = messagebox.askyesno(
            "Ekspor Otomatis ke PDF",
            f"Dokumen Word berhasil diperbarui di:\n{out_dir}\n\n"
            f"Opsi 'Langsung ekspor ke PDF' aktif.\n"
            f"Apakah Anda ingin memulai konversi {len(self.tab_pdf.items)} dokumen ke PDF sekarang?"
        )
        if tanya:
            self.tab_pdf.start_conversion()

    def _handle_preview_dialog(
        self,
        plan_items: List[ReplacementPlanItem],
        files: List[Tuple[str, str]],
        out_dir: str,
        failed_planning_rels: Optional[Set[str]] = None,
        rules: Optional[List[Dict[str, str]]] = None,
        mode: str = "GABUNGAN"
    ):
        failed_planning_rels = failed_planning_rels or set()
        if not plan_items and not failed_planning_rels:
            self.btn_process.configure(state="normal")
            messagebox.showinfo("Info", "Tidak ditemukan teks atau struktur dokumen yang cocok dengan aturan.")
            return

        if plan_items:
            dialog = IntegratedPreviewDialog(self.root, plan_items)
            self.root.wait_window(dialog)

            if not dialog.confirmed:
                self.btn_process.configure(state="normal")
                self._log("[INFO] Pemrosesan dibatalkan oleh pengguna dari jendela pratinjau.")
                return

        # Eksekusi penulisan file berdasarkan item yang disetujui
        self._log("--- Menerapkan perubahan yang disetujui ke dokumen ---")
        self.progress.configure(maximum=len(files), value=0)
        threading.Thread(
            target=self._worker_apply,
            args=(files, out_dir, plan_items, failed_planning_rels, rules or [], mode),
            daemon=True
        ).start()

    def _collect_files(self, in_dir: str, out_dir: str, recursive: bool) -> List[Tuple[str, str]]:
        result = []
        out_abs = os.path.abspath(out_dir)

        # Kasus 1: Input adalah Berkas Tunggal (.docx / .doc)
        if os.path.isfile(in_dir):
            if is_supported_word_file(in_dir):
                result.append((in_dir, os.path.basename(in_dir)))
            return result

        # Kasus 2: Input adalah Folder
        if os.path.isdir(in_dir):
            if recursive:
                for base, dirs, names in os.walk(in_dir):
                    dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(base, d)) != out_abs]
                    for n in names:
                        if is_supported_word_file(n):
                            full = os.path.join(base, n)
                            result.append((full, os.path.relpath(full, in_dir)))
            else:
                for n in os.listdir(in_dir):
                    full = os.path.join(in_dir, n)
                    if os.path.isfile(full) and is_supported_word_file(n):
                        result.append((full, n))
        return result

    def _on_dictionary_changed(self):
        """Dipanggil saat pengguna mengubah atau memperbarui sinonim di Kamus Field."""
        if hasattr(self, "engine"):
            self.engine.reload_dictionary()
        self._log("Kamus field berhasil diperbarui.")

    def _on_signature_changed(self, new_settings=None):
        """Dipanggil saat pengguna menyimpan konfigurasi tanda tangan / stempel digital."""
        if hasattr(self, "engine") and hasattr(self.engine, "reload_signature_settings"):
            self.engine.reload_signature_settings()
        self._log("Pengaturan tanda tangan & stempel berhasil disinkronkan.")

    def _start_processing(self):
        in_dir = self.input_dir_var.get().strip()
        out_dir = self.output_dir_var.get().strip()

        if not in_dir or not os.path.exists(in_dir):
            messagebox.showwarning("Peringatan", "Pilih Berkas atau Folder Dokumen Word yang valid terlebih dahulu!")
            return
        if not out_dir:
            messagebox.showwarning("Peringatan", "Tentukan Folder Hasil (Output) terlebih dahulu!")
            return

        if os.path.isfile(in_dir):
            out_file = os.path.join(out_dir, os.path.basename(in_dir))
            if os.path.abspath(in_dir) == os.path.abspath(out_file):
                if not messagebox.askyesno(
                    "Peringatan Penimpaan Berkas",
                    f"Berkas hasil akan disimpan di lokasi yang sama persis dengan berkas asli:\n{out_file}\n\n"
                    "Berkas asli akan TERTIMPA secara permanen.\nApakah Anda yakin ingin melanjutkan?"
                ):
                    return
        elif os.path.isdir(in_dir):
            if os.path.abspath(in_dir) == os.path.abspath(out_dir):
                if not messagebox.askyesno(
                    "Peringatan",
                    "Folder hasil sama dengan folder asli.\nFile asli di dalam folder akan TERTIMPA.\n\nLanjutkan?"
                ):
                    return

        mode = self.replacement_view.get_search_mode()

        if mode == "SIGNATURE_ONLY":
            from core.signature_image_service import load_signature_settings
            sig_cfg = load_signature_settings()
            en_k = sig_cfg.get("enabled_kepala", False) and os.path.isfile(sig_cfg.get("kepala_image_path", ""))
            en_g = sig_cfg.get("enabled_guru", False) and os.path.isfile(sig_cfg.get("guru_image_path", ""))
            en_s = sig_cfg.get("enabled_stempel", False) and os.path.isfile(sig_cfg.get("stempel_image_path", ""))
            if not (en_k or en_g or en_s):
                messagebox.showwarning(
                    "Peringatan Tanda Tangan",
                    "Mode 'Hanya Sisipkan Tanda Tangan' aktif, tetapi belum ada tanda tangan digital atau stempel resmi yang diaktifkan atau berkas gambarnya tidak ditemukan.\n\nSilakan klik tombol '✍ Atur Tanda Tangan Digital...' terlebih dahulu untuk memilih gambar dan mengaktifkannya."
                )
                return
            rules = []
        else:
            rules = self.replacement_view.get_rules()
            has_target = any(r.get("new", "").strip() for r in rules)
            if not has_target:
                messagebox.showwarning("Peringatan", "Isi minimal satu kolom 'Teks Baru' sebagai target penggantian!")
                return

        files = self._collect_files(in_dir, out_dir, self.sub_var.get())
        if not files:
            if os.path.isfile(in_dir):
                messagebox.showinfo("Info", "Berkas yang dipilih bukan dokumen Word yang didukung (.docx atau .doc).")
            else:
                messagebox.showinfo("Info", "Tidak ditemukan file Word (.docx atau .doc) di folder input.")
            return

        case_sensitive = self.case_var.get()
        use_preview = self.preview_var.get()
        skip_low = self.skip_low_var.get()

        self.report_service.reset()
        os.makedirs(out_dir, exist_ok=True)

        self.btn_process.configure(state="disabled")
        self.progress.configure(maximum=len(files), value=0)

        count_desc = f"1 dokumen ({files[0][1]})" if len(files) == 1 else f"{len(files)} dokumen"
        if use_preview:
            self._log(f"--- Memindai {count_desc} untuk Pratinjau Terpadu (Mode: {mode}) ---")
            threading.Thread(
                target=self._worker_plan,
                args=(files, out_dir, rules, mode, case_sensitive, skip_low),
                daemon=True
            ).start()
        else:
            self._log(f"--- Memulai pemrosesan langsung {count_desc} (Mode: {mode}) ---")
            threading.Thread(
                target=self._worker_direct,
                args=(files, out_dir, rules, mode, case_sensitive, skip_low),
                daemon=True
            ).start()

    def _worker_plan(self, files: List[Tuple[str, str]], out_dir: str, rules: List[Dict[str, str]], mode: str, case_sensitive: bool, skip_low: bool):
        all_plan_items: List[ReplacementPlanItem] = []
        failed_planning_rels: Set[str] = set()
        for idx, (full, rel) in enumerate(files, 1):
            try:
                items = self.engine.plan_document_changes(full, rel, rules, mode, case_sensitive)
                for it in items:
                    if skip_low and it.confidence == ConfidenceLevel.LOW:
                        it.is_approved = False
                all_plan_items.extend(items)
            except Exception as e:
                failed_planning_rels.add(rel)
                self.msg_queue.put(("log", f"[GAGAL PINDAI] {rel} -> {e}"))
            self.msg_queue.put(("progress", idx))

        self.msg_queue.put(("show_preview", (all_plan_items, files, out_dir, failed_planning_rels, rules, mode)))

    def _generate_change_report(
        self,
        out_dir: str,
        files: List[Tuple[str, str]],
        plan_items: List[ReplacementPlanItem],
        rules: List[Dict[str, str]],
        mode: str,
    ) -> None:
        """Menerbitkan Laporan Perubahan JSON Lengkap dan menyimpannya ke report_service."""
        try:
            from core.change_verifier import ChangeReportGenerator
            input_dir = os.path.dirname(files[0][0]) if files else out_dir
            generator = ChangeReportGenerator(anonymize_pii=False)
            json_path, report_data = generator.generate_report(
                output_dir=out_dir,
                input_dir=input_dir,
                plan_items=plan_items,
                rules=rules,
                mode=mode,
            )
            self.report_service.set_verification_report(json_path, report_data.get("ringkasan", {}))
            self.msg_queue.put(("log", f"[LAPORAN JSON] Diterbitkan ke: {json_path}"))
        except Exception as e:
            self.msg_queue.put(("log", f"[LAPORAN JSON] Catatan: {e}"))

    def _worker_apply(
        self,
        files: List[Tuple[str, str]],
        out_dir: str,
        plan_items: List[ReplacementPlanItem],
        failed_planning_rels: Optional[Set[str]] = None,
        rules: Optional[List[Dict[str, str]]] = None,
        mode: str = "GABUNGAN"
    ):
        failed_planning_rels = failed_planning_rels or set()
        # Kelompokkan item yang disetujui berdasarkan rel_path
        items_by_rel: Dict[str, List[ReplacementPlanItem]] = {}
        for it in plan_items:
            items_by_rel.setdefault(it.rel_path, []).append(it)

        for idx, (full, rel) in enumerate(files, 1):
            root_name, ext = os.path.splitext(rel)
            out_rel = (root_name + ".docx") if ext.lower() == ".doc" else rel
            out_file = os.path.join(out_dir, out_rel)
            disp_rel = f"{rel} -> {out_rel}" if out_rel != rel else rel

            if rel in failed_planning_rels:
                self.report_service.record_document(disp_rel, "FAILED", 0, error_msg="Gagal pada tahap pemindaian/analisis dokumen")
                self.msg_queue.put(("log", f"[GAGAL PINDAI] {rel} dilewati"))
                self.msg_queue.put(("progress", idx))
                continue

            file_items = items_by_rel.get(rel, [])
            approved_file_items = [it for it in file_items if it.is_approved]

            cat_breakdown: Dict[str, int] = {}
            for it in approved_file_items:
                cat_breakdown[it.category] = cat_breakdown.get(it.category, 0) + 1

            try:
                os.makedirs(os.path.dirname(out_file), exist_ok=True)
                if approved_file_items:
                    changes = self.engine.apply_approved_changes(full, out_file, approved_file_items)
                    self.report_service.record_document(disp_rel, "SUCCESS", changes, cat_breakdown)
                    self.msg_queue.put(("log", f"[BERHASIL] {disp_rel} ({changes} titik diganti)"))
                else:
                    # Tidak ada perubahan disetujui untuk file ini
                    if full.lower().endswith(".doc") and out_file.lower().endswith(".docx"):
                        from core.doc_compat_service import convert_doc_to_docx
                        convert_doc_to_docx(full, out_file)
                    else:
                        shutil.copy2(full, out_file)
                    self.report_service.record_document(disp_rel, "UNCHANGED", 0)
                    self.msg_queue.put(("log", f"[TIDAK BERUBAH] {disp_rel}"))
            except PermissionError:
                self.report_service.record_document(disp_rel, "FAILED", 0, error_msg="File sedang dibuka di Word")
                self.msg_queue.put(("log", f"[GAGAL] {disp_rel} -> file sedang dibuka di Word"))
            except Exception as e:
                self.report_service.record_document(disp_rel, "FAILED", 0, error_msg=str(e))
                self.msg_queue.put(("log", f"[GAGAL] {disp_rel} -> {e}"))

            self.msg_queue.put(("progress", idx))

        # Terbitkan Laporan Perubahan JSON Lengkap
        rules_used = rules or []
        mode_used = mode
        try:
            self._generate_change_report(out_dir, files, plan_items, rules_used, mode_used)
        except Exception as e:
            self.msg_queue.put(("log", f"[GAGAL LAPORAN JSON] -> {e}"))

        self.report_service.write_report_file(out_dir)
        self.msg_queue.put(("done", out_dir))

    def _worker_direct(self, files: List[Tuple[str, str]], out_dir: str, rules: List[Dict[str, str]], mode: str, case_sensitive: bool, skip_low: bool):
        all_direct_plan_items: List[ReplacementPlanItem] = []
        for idx, (full, rel) in enumerate(files, 1):
            root_name, ext = os.path.splitext(rel)
            out_rel = (root_name + ".docx") if ext.lower() == ".doc" else rel
            out_file = os.path.join(out_dir, out_rel)
            disp_rel = f"{rel} -> {out_rel}" if out_rel != rel else rel
            try:
                os.makedirs(os.path.dirname(out_file), exist_ok=True)
                # S3: Hitung breakdown kategori agar laporan eksekutif lengkap di mode langsung
                plan_items = self.engine.plan_document_changes(full, rel, rules, mode, case_sensitive)
                approved = []
                cat_breakdown: Dict[str, int] = {}
                for it in plan_items:
                    if skip_low and it.confidence == ConfidenceLevel.LOW:
                        it.is_approved = False
                    else:
                        it.is_approved = True
                        cat_breakdown[it.category] = cat_breakdown.get(it.category, 0) + 1
                    approved.append(it)
                all_direct_plan_items.extend(approved)

                if any(it.is_approved for it in approved):
                    changes = self.engine.apply_approved_changes(full, out_file, approved)
                    self.report_service.record_document(disp_rel, "SUCCESS", changes, cat_breakdown)
                    self.msg_queue.put(("log", f"[BERHASIL] {disp_rel} ({changes} titik diganti)"))
                else:
                    if full.lower().endswith(".doc") and out_file.lower().endswith(".docx"):
                        from core.doc_compat_service import convert_doc_to_docx
                        convert_doc_to_docx(full, out_file)
                    else:
                        shutil.copy2(full, out_file)
                    self.report_service.record_document(disp_rel, "UNCHANGED", 0)
                    self.msg_queue.put(("log", f"[TIDAK BERUBAH] {disp_rel}"))
            except PermissionError:
                self.report_service.record_document(disp_rel, "FAILED", 0, error_msg="File sedang dibuka di Word")
                self.msg_queue.put(("log", f"[GAGAL] {disp_rel} -> file sedang dibuka di Word"))
            except Exception as e:
                self.report_service.record_document(disp_rel, "FAILED", 0, error_msg=str(e))
                self.msg_queue.put(("log", f"[GAGAL] {disp_rel} -> {e}"))

            self.msg_queue.put(("progress", idx))

        # Terbitkan Laporan Perubahan JSON untuk mode langsung
        self._generate_change_report(out_dir, files, all_direct_plan_items, rules, mode)

        self.report_service.write_report_file(out_dir)
        self.msg_queue.put(("done", out_dir))
