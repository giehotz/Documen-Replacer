"""
Komponen GUI Tampilan Tab Konversi Word ke PDF (Tkinter).
Menyediakan:
- Pemilihan folder sumber (Word) dan folder tujuan (PDF)
- Pengaturan pemindaian subfolder, struktur folder, dan penanganan file duplikat
- Tabel antrean berkas (Treeview) dengan badge status
- Bilah progres dan tombol kontrol eksekusi massal (Start, Cancel)
- Thread worker non-blocking dengan komunikasi queue aman
"""
import os
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Dict, Any, Optional

from core.pdf_converter.conversion_manager import PdfConversionManager, DocItem

DEFAULT_PDF_OUT = os.path.join(os.path.expanduser("~"), "Documents", "MODUL", "PDF")


class PdfConverterView(ttk.Frame):
    """Tampilan tab konversi dokumen Word ke PDF."""

    def __init__(self, parent, on_status_msg=None, **kwargs):
        super().__init__(parent, padding=10, **kwargs)
        self.on_status_msg = on_status_msg

        self.manager = PdfConversionManager()
        self.items: List[DocItem] = []
        self.msg_queue: queue.Queue = queue.Queue()
        self.is_converting = False
        self.cancel_requested = False

        self._init_variables()
        self._build_ui()
        self.after(50, self._poll_queue)

    def _init_variables(self):
        self.source_dir_var = tk.StringVar()
        self.target_dir_var = tk.StringVar(value=DEFAULT_PDF_OUT)

        self.recursive_var = tk.BooleanVar(value=True)
        self.preserve_tree_var = tk.BooleanVar(value=True)
        self.skip_existing_var = tk.BooleanVar(value=True)
        self.open_on_finish_var = tk.BooleanVar(value=True)

        self.progress_val = tk.DoubleVar(value=0.0)
        self.status_label_var = tk.StringVar(value="Pilih folder sumber lalu klik 'Pindai Dokumen'")

    def _build_ui(self):
        # 1. Panel Direktori Sumber & Target
        dir_frame = ttk.LabelFrame(self, text=" 1. Lokasi Direktori Dokumen ", padding=10)
        dir_frame.pack(fill="x", pady=(0, 6))
        dir_frame.columnconfigure(1, weight=1)

        ttk.Label(dir_frame, text="Folder Sumber (Word):").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(dir_frame, textvariable=self.source_dir_var).grid(row=0, column=1, padx=8, pady=3, sticky="ew")
        ttk.Button(dir_frame, text="Pilih Folder...", command=self._browse_source).grid(row=0, column=2, pady=3)

        ttk.Label(dir_frame, text="Folder Tujuan (PDF):").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(dir_frame, textvariable=self.target_dir_var).grid(row=1, column=1, padx=8, pady=3, sticky="ew")
        ttk.Button(dir_frame, text="Pilih Folder...", command=self._browse_target).grid(row=1, column=2, pady=3)

        # 2. Panel Pengaturan & Informasi Mesin
        opts_frame = ttk.LabelFrame(self, text=" 2. Pengaturan Konversi & Mesin ", padding=8)
        opts_frame.pack(fill="x", pady=(0, 6))

        row_opt1 = ttk.Frame(opts_frame)
        row_opt1.pack(fill="x", pady=2)
        ttk.Checkbutton(row_opt1, text="Sertakan subfolder (rekursif)", variable=self.recursive_var).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(row_opt1, text="Pertahankan struktur subfolder di output", variable=self.preserve_tree_var).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(row_opt1, text="Lewati jika berkas PDF sudah ada", variable=self.skip_existing_var).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(row_opt1, text="Buka folder tujuan setelah selesai", variable=self.open_on_finish_var).pack(side="left")

        row_opt2 = ttk.Frame(opts_frame)
        row_opt2.pack(fill="x", pady=(4, 0))
        engine_name = self.manager.get_engine_name()
        ttk.Label(row_opt2, text="Mesin Konversi Aktif:", font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Label(row_opt2, text=f" {engine_name}", foreground="#0066cc").pack(side="left")

        # 3. Panel Tabel Antrean Dokumen
        queue_frame = ttk.LabelFrame(self, text=" 3. Daftar Antrean Dokumen Word ", padding=8)
        queue_frame.pack(fill="both", expand=True, pady=(0, 6))
        queue_frame.columnconfigure(0, weight=1)
        queue_frame.rowconfigure(0, weight=1)

        cols = ("no", "filename", "subfolder", "size", "status", "info")
        self.tree = ttk.Treeview(queue_frame, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("no", text="#", anchor="center")
        self.tree.heading("filename", text="Nama Dokumen Word", anchor="w")
        self.tree.heading("subfolder", text="Subfolder Asal", anchor="w")
        self.tree.heading("size", text="Ukuran", anchor="e")
        self.tree.heading("status", text="Status", anchor="center")
        self.tree.heading("info", text="Keterangan", anchor="w")

        self.tree.column("no", width=40, anchor="center", stretch=False)
        self.tree.column("filename", width=300, anchor="w")
        self.tree.column("subfolder", width=180, anchor="w")
        self.tree.column("size", width=80, anchor="e", stretch=False)
        self.tree.column("status", width=95, anchor="center", stretch=False)
        self.tree.column("info", width=220, anchor="w")

        sb = ttk.Scrollbar(queue_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        # Styling tag status
        self.tree.tag_configure("ok", foreground="#107c10")
        self.tree.tag_configure("err", foreground="#a80000")
        self.tree.tag_configure("proc", foreground="#0050b3")
        self.tree.tag_configure("skip", foreground="#6c757d")

        # 4. Panel Kontrol, Progres & Status
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill="x", pady=(2, 0))

        # Progress bar
        self.progressbar = ttk.Progressbar(ctrl_frame, variable=self.progress_val, maximum=100)
        self.progressbar.pack(fill="x", pady=(0, 4))

        # Label status
        lbl_status = ttk.Label(ctrl_frame, textvariable=self.status_label_var, font=("Segoe UI", 9))
        lbl_status.pack(side="left", pady=2)

        # Tombol aksi
        btn_bar = ttk.Frame(ctrl_frame)
        btn_bar.pack(side="right", pady=2)

        self.btn_open_out = ttk.Button(btn_bar, text="📁 Buka Folder PDF", command=self._open_target_folder)
        self.btn_open_out.pack(side="left", padx=3)

        self.btn_scan = ttk.Button(btn_bar, text="🔍 Pindai Dokumen", command=self.scan_documents)
        self.btn_scan.pack(side="left", padx=3)

        self.btn_start = ttk.Button(
            btn_bar,
            text="▶ MULAI KONVERSI PDF",
            command=self.start_conversion,
            style="Accent.TButton" if "Accent.TButton" in ttk.Style().theme_names() else "TButton"
        )
        self.btn_start.pack(side="left", padx=3)

        self.btn_cancel = ttk.Button(btn_bar, text="⏹ Batalkan", command=self.cancel_conversion, state="disabled")
        self.btn_cancel.pack(side="left", padx=3)

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================
    def _browse_source(self):
        f = filedialog.askdirectory(title="Pilih Folder Berisi Dokumen Word")
        if f:
            self.source_dir_var.set(os.path.normpath(f))
            self.scan_documents()

    def _browse_target(self):
        f = filedialog.askdirectory(title="Pilih Folder Penyimpanan PDF")
        if f:
            self.target_dir_var.set(os.path.normpath(f))

    def _open_target_folder(self):
        out_p = self.target_dir_var.get().strip()
        if out_p and os.path.isdir(out_p):
            try:
                os.startfile(out_p)
            except Exception as e:
                messagebox.showwarning("Peringatan", f"Gagal membuka folder:\n{e}")
        else:
            messagebox.showinfo("Informasi", "Folder tujuan belum dibuat atau belum ada berkas.")

    def set_source_folder(self, folder_path: str):
        """Memasang folder sumber secara terprogram (mis. dari Tab 1)."""
        self.source_dir_var.set(os.path.normpath(folder_path))
        self.scan_documents()

    def scan_documents(self):
        """Memindai folder sumber dan mengisi tabel antrean."""
        src = self.source_dir_var.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showwarning("Peringatan", "Silakan pilih Folder Sumber yang valid terlebih dahulu.")
            return

        self.status_label_var.set("Memindai dokumen Word...")
        self.update_idletasks()

        rec = self.recursive_var.get()
        self.items = self.manager.scan_documents(src, recursive=rec)

        # Siapkan target PDF awal
        out_dir = self.target_dir_var.get().strip() or DEFAULT_PDF_OUT
        self.manager.prepare_targets(
            self.items,
            out_dir=out_dir,
            preserve_subfolders=self.preserve_tree_var.get(),
            skip_existing=self.skip_existing_var.get()
        )

        # Perbarui tampilan tabel
        self.tree.delete(*self.tree.get_children())
        for idx, it in enumerate(self.items, start=1):
            sub = os.path.dirname(it.rel_path) or "-"
            tag = "skip" if it.status == "Dilewati" else ""
            self.tree.insert("", "end", iid=str(idx - 1), values=(
                idx, it.filename, sub, it.size_formatted, it.status, it.error_msg
            ), tags=(tag,) if tag else ())

        total = len(self.items)
        ready_cnt = sum(1 for it in self.items if it.status == "Menunggu")
        skip_cnt = total - ready_cnt
        self.status_label_var.set(f"Ditemukan {total} dokumen Word ({ready_cnt} siap dikonversi, {skip_cnt} sudah ada PDF-nya).")
        self.progress_val.set(0.0)

    # =========================================================================
    # PROSES KONVERSI BATCH (THREADED)
    # =========================================================================
    def start_conversion(self):
        """Memulai proses batch conversion di background thread."""
        if self.is_converting:
            return

        if not self.items:
            messagebox.showwarning("Peringatan", "Tidak ada dokumen dalam antrean. Silakan pindai folder terlebih dahulu.")
            return

        out_dir = self.target_dir_var.get().strip()
        if not out_dir:
            messagebox.showwarning("Peringatan", "Silakan tentukan Folder Tujuan (PDF) terlebih dahulu.")
            return

        os.makedirs(out_dir, exist_ok=True)

        # Siapkan ulang target dengan pengaturan terakhir
        self.manager.prepare_targets(
            self.items,
            out_dir=out_dir,
            preserve_subfolders=self.preserve_tree_var.get(),
            skip_existing=self.skip_existing_var.get()
        )

        to_process = [it for it in self.items if it.status != "Dilewati"]
        if not to_process:
            messagebox.showinfo("Informasi", "Seluruh dokumen PDF sudah ada di folder tujuan (opsi 'Lewati jika sudah ada' aktif).")
            return

        self.is_converting = True
        self.cancel_requested = False
        self.btn_start.config(state="disabled")
        self.btn_scan.config(state="disabled")
        self.btn_cancel.config(state="normal")

        # Jalankan worker di background
        worker_thread = threading.Thread(
            target=self._worker_run,
            args=(self.items,),
            daemon=True
        )
        worker_thread.start()

    def cancel_conversion(self):
        """Meminta pembatalan proses konversi."""
        if self.is_converting:
            self.cancel_requested = True
            self.status_label_var.set("Membatalkan proses konversi... Harap tunggu dokumen selesai ditutup.")
            self.btn_cancel.config(state="disabled")

    def _worker_run(self, items: List[DocItem]):
        """Eksekusi konversi di thread latar belakang."""
        def progress_cb(current_idx: int, total_cnt: int, item: DocItem):
            self.msg_queue.put(("progress", current_idx, total_cnt, item))

        def cancel_chk() -> bool:
            return self.cancel_requested

        try:
            summary = self.manager.convert_batch(
                items,
                progress_callback=progress_cb,
                cancel_check=cancel_chk
            )
            self.msg_queue.put(("finished", summary))
        except Exception as e:
            self.msg_queue.put(("error", str(e)))

    def _poll_queue(self):
        """Memproses pesan dari thread latar belakang di GUI thread."""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                m_type = msg[0]

                if m_type == "progress":
                    _, cur, tot, item = msg
                    pct = (cur / max(1, tot)) * 100.0
                    self.progress_val.set(pct)
                    self.status_label_var.set(f"Mengonversi {cur}/{tot} ({pct:.0f}%): {item.filename}")

                    # Cari index item di self.items
                    try:
                        row_idx = self.items.index(item)
                        sub = os.path.dirname(item.rel_path) or "-"
                        tag = "ok" if item.status == "Berhasil" else ("err" if item.status == "Gagal" else "proc")
                        self.tree.item(str(row_idx), values=(
                            row_idx + 1, item.filename, sub, item.size_formatted, item.status, item.error_msg
                        ), tags=(tag,))
                        self.tree.see(str(row_idx))
                    except ValueError:
                        pass

                elif m_type == "finished":
                    summary = msg[1]
                    self._on_conversion_finished(summary)

                elif m_type == "error":
                    err_msg = msg[1]
                    self.is_converting = False
                    self.btn_start.config(state="normal")
                    self.btn_scan.config(state="normal")
                    self.btn_cancel.config(state="disabled")
                    messagebox.showerror("Kesalahan Konversi", f"Terjadi kesalahan saat konversi:\n{err_msg}")

        except queue.Empty:
            pass

        self.after(50, self._poll_queue)

    def _on_conversion_finished(self, summary: Dict[str, Any]):
        """Dipanggil saat seluruh proses konversi selesai."""
        self.is_converting = False
        self.btn_start.config(state="normal")
        self.btn_scan.config(state="normal")
        self.btn_cancel.config(state="disabled")

        tot = summary.get("total", 0)
        succ = summary.get("success", 0)
        fail = summary.get("failed", 0)
        skip = summary.get("skipped", 0)
        canceled = summary.get("canceled", 0)

        if canceled == 0:
            self.progress_val.set(100.0)
        status_text = f"Konversi Selesai! Berhasil: {succ}, Gagal: {fail}, Dilewati: {skip}"
        if canceled:
            status_text += f", Dibatalkan: {canceled}"
        self.status_label_var.set(f"{status_text} (Total: {tot}).")

        msg = (
            f"Proses konversi Word ke PDF telah selesai.\n\n"
            f"• Total Dokumen: {tot}\n"
            f"• Berhasil Dikonversi: {succ}\n"
            f"• Gagal: {fail}\n"
            f"• Dilewati (Sudah Ada): {skip}\n"
        )
        if canceled:
            msg += f"• Dibatalkan: {canceled}\n"
        msg += f"\nLokasi Output:\n{self.target_dir_var.get()}"
        messagebox.showinfo("Konversi Selesai", msg)

        if self.open_on_finish_var.get() and succ > 0:
            self._open_target_folder()
