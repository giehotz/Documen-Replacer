"""
Tampilan antarmuka Mail Merge / Generator Dokumen Massal (DOM-06 & PRD §7).
Menyediakan formulir pemilih templat Word, pengunggah CSV/Excel, pratinjau data tabular,
konfigurasi pola nama berkas keluaran, dan tombol eksekusi massal berulir (thread-safe).
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import os
from typing import Optional, Callable, Dict, Any, List

from workflows.batch_mail_merge import BatchMailMerge, load_data_file


class MailMergeView(ttk.Frame):
    """
    Panel / Tab Mail Merge terintegrasi.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, padding=10, *args, **kwargs)

        self.template_path_var = tk.StringVar()
        self.data_path_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.pattern_var = tk.StringVar(value="{NO}_{NAMA}")
        self.status_var = tk.StringVar(value="Siap. Pilih templat dan berkas data untuk memulai.")

        self.generator = BatchMailMerge()
        self.event_queue: queue.Queue = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self._cancel_requested = False

        self._build_ui()
        self._poll_queue()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        # 1. Pemilihan Berkas
        lbl_sec1 = ttk.Label(self, text="Konfigurasi Sumber Berkas", font=("Segoe UI", 10, "bold"))
        lbl_sec1.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        # Templat Word
        ttk.Label(self, text="Templat (.docx):").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(self, textvariable=self.template_path_var).grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        ttk.Button(self, text="Pilih Templat...", command=self._browse_template).grid(row=1, column=2, pady=3)

        # Berkas Data (CSV / Excel)
        ttk.Label(self, text="Data (CSV / Excel):").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(self, textvariable=self.data_path_var).grid(row=2, column=1, sticky="ew", padx=5, pady=3)
        ttk.Button(self, text="Pilih Data...", command=self._browse_data).grid(row=2, column=2, pady=3)

        # Folder Keluaran
        ttk.Label(self, text="Folder Simpan:").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(self, textvariable=self.output_dir_var).grid(row=3, column=1, sticky="ew", padx=5, pady=3)
        ttk.Button(self, text="Pilih Folder...", command=self._browse_output).grid(row=3, column=2, pady=3)

        # Pola Nama Berkas
        ttk.Label(self, text="Pola Nama File:").grid(row=4, column=0, sticky="w", pady=3)
        ttk.Entry(self, textvariable=self.pattern_var).grid(row=4, column=1, sticky="ew", padx=5, pady=3)
        ttk.Label(self, text="Contoh: {NO}_{NAMA}", font=("Segoe UI", 8, "italic"), foreground="gray").grid(row=4, column=2, sticky="w")

        # 2. Pratinjau Data (Preview)
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 5))

        self.btn_preview = ttk.Button(btn_frame, text="🔍 Pratinjau Data Contoh", command=self._preview_data)
        self.btn_preview.pack(side="left", padx=(0, 5))

        self.btn_generate = ttk.Button(btn_frame, text="⚡ Mulai Generasi Massal", command=self._start_generation)
        self.btn_generate.pack(side="left", padx=5)

        self.btn_cancel = ttk.Button(btn_frame, text="⛔ Batal", command=self._cancel_generation, state="disabled")
        self.btn_cancel.pack(side="left", padx=5)

        # Tabel Pratinjau
        lbl_preview = ttk.Label(self, text="Pratinjau 3 Baris Pertama Data:", font=("Segoe UI", 9, "bold"))
        lbl_preview.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 3))

        self.tree_frame = ttk.Frame(self)
        self.tree_frame.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=3)
        self.rowconfigure(7, weight=1)
        self.tree_frame.columnconfigure(0, weight=1)
        self.tree_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(self.tree_frame, selectmode="browse", show="headings", height=5)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll_y = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll_y.set)

        # 3. Status dan Progress Bar
        self.prog_bar = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.prog_bar.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(10, 2))

        lbl_status = ttk.Label(self, textvariable=self.status_var, font=("Segoe UI", 9))
        lbl_status.grid(row=9, column=0, columnspan=3, sticky="w", pady=(0, 5))

    def _browse_template(self) -> None:
        path = filedialog.askopenfilename(
            title="Pilih Berkas Templat Word",
            filetypes=[("Word Document", "*.docx")]
        )
        if path:
            self.template_path_var.set(os.path.normpath(path))

    def _browse_data(self) -> None:
        path = filedialog.askopenfilename(
            title="Pilih Berkas Sumber Data",
            filetypes=[("Data Tabular (CSV / Excel)", "*.csv;*.xlsx"), ("CSV UTF-8", "*.csv"), ("Excel Workbook", "*.xlsx")]
        )
        if path:
            self.data_path_var.set(os.path.normpath(path))

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(title="Pilih Folder Penyimpanan Berkas Hasil")
        if folder:
            self.output_dir_var.set(os.path.normpath(folder))

    def _preview_data(self) -> None:
        data_path = self.data_path_var.get().strip()
        if not data_path or not os.path.isfile(data_path):
            messagebox.showwarning("Peringatan", "Silakan pilih berkas data (CSV / Excel) terlebih dahulu.")
            return

        try:
            headers, rows = self.generator.preview_data(data_path, limit=5)
            self._render_tree(headers, rows)
            self.status_var.set(f"Pratinjau siap. Terdeteksi {len(headers)} kolom data.")
        except Exception as e:
            messagebox.showerror("Gagal Membaca Data", f"Gagal membaca data: {e}")

    def _render_tree(self, headers: List[str], rows: List[Dict[str, str]]) -> None:
        # Bersihkan treeview lama
        for c in self.tree.get_children():
            self.tree.delete(c)

        self.tree["columns"] = headers
        for h in headers:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=120, anchor="w")

        for r in rows:
            values = [r.get(h, "") for h in headers]
            self.tree.insert("", "end", values=values)

    def _start_generation(self) -> None:
        tpl_path = self.template_path_var.get().strip()
        data_path = self.data_path_var.get().strip()
        out_dir = self.output_dir_var.get().strip()
        pattern = self.pattern_var.get().strip() or "{NO}_{NAMA}"

        if not tpl_path or not os.path.isfile(tpl_path):
            messagebox.showwarning("Peringatan", "Silakan pilih templat Word (.docx) yang sah.")
            return
        if not data_path or not os.path.isfile(data_path):
            messagebox.showwarning("Peringatan", "Silakan pilih berkas data (CSV / Excel).")
            return
        if not out_dir:
            messagebox.showwarning("Peringatan", "Silakan tentukan folder penyimpanan hasil.")
            return

        self._cancel_requested = False
        self.btn_generate.config(state="disabled")
        self.btn_preview.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.prog_bar["value"] = 0
        self.status_var.set("Memulai proses pembuatan dokumen massal...")

        # Jalankan background thread
        self.worker_thread = threading.Thread(
            target=self._worker_run,
            args=(tpl_path, data_path, out_dir, pattern),
            daemon=True
        )
        self.worker_thread.start()

    def _worker_run(self, tpl_path: str, data_path: str, out_dir: str, pattern: str) -> None:
        def _prog(curr, total, fname):
            self.event_queue.put(("progress", curr, total, fname))

        def _is_canceled():
            return self._cancel_requested

        try:
            res = self.generator.generate_batch(
                template_path=tpl_path,
                data_path=data_path,
                output_dir=out_dir,
                filename_pattern=pattern,
                progress_callback=_prog,
                cancel_check=_is_canceled,
            )
            self.event_queue.put(("done", res))
        except Exception as e:
            self.event_queue.put(("error", str(e)))

    def _cancel_generation(self) -> None:
        self._cancel_requested = True
        self.status_var.set("Membatalkan proses...")

    def _poll_queue(self) -> None:
        """Memproses event dari background thread ke main GUI thread secara aman."""
        try:
            while True:
                msg = self.event_queue.get_nowait()
                ev_type = msg[0]

                if ev_type == "progress":
                    _, curr, total, fname = msg
                    pct = (curr / total) * 100 if total > 0 else 0
                    self.prog_bar["value"] = pct
                    self.status_var.set(f"Memproses ({curr}/{total}): {fname}")

                elif ev_type == "done":
                    _, res = msg
                    self.btn_generate.config(state="normal")
                    self.btn_preview.config(state="normal")
                    self.btn_cancel.config(state="disabled")

                    if res.get("status") == "CANCELED":
                        self.status_var.set("Proses dibatalkan oleh pengguna. File sementara telah dibersihkan.")
                        messagebox.showinfo("Dibatalkan", "Proses pembuatan dokumen dibatalkan.")
                    elif not res.get("success"):
                        self.status_var.set("Validasi gagal. Terdapat token templat yang tidak cocok.")
                        errs = res.get("validation", {}).get("unmapped_tokens", [])
                        messagebox.showerror(
                            "Validasi Gagal",
                            f"Token berikut pada templat tidak ditemukan di kolom data:\n{', '.join(errs)}"
                        )
                    else:
                        self.prog_bar["value"] = 100
                        count = res.get("generated_count", 0)
                        self.status_var.set(f"Selesai! Berhasil membuat {count} dokumen.")
                        messagebox.showinfo(
                            "Generasi Massal Berhasil",
                            f"Berhasil menghasilkan {count} dokumen Word di folder:\n{res.get('report_path')}"
                        )

                elif ev_type == "error":
                    _, err_msg = msg
                    self.btn_generate.config(state="normal")
                    self.btn_preview.config(state="normal")
                    self.btn_cancel.config(state="disabled")
                    self.status_var.set(f"Terjadi kesalahan: {err_msg}")
                    messagebox.showerror("Kesalahan", f"Terjadi kesalahan: {err_msg}")

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)
