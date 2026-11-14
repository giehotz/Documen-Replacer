"""
Komponen GUI: Dialog Progres & Live Log Pemindaian Dokumen (PredictProgressDialog).
Menampilkan proses pemindaian berkas Word (.docx / .doc) secara real-time:
- Bilah progres bertingkat
- Kotak live log bergaya terminal konsol gelap
- Thread worker mandiri non-blocking
- Tombol pembatalan aman (graceful cancel)
- Integrasi ke callback pengisian tabel aturan penggantian
"""
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Any, Optional, Callable

from core.document_predictor import (
    predict_rules_from_file,
    predict_rules_from_folder,
    collect_unknown_labels,
)
from gui.ui_helpers import center_window


class PredictProgressDialog(tk.Toplevel):
    """
    Dialog modal untuk menampilkan live log dan bilah progres saat menganalisis
    dokumen contoh atau memindai seluruh folder input.
    """

    def __init__(
        self,
        parent: tk.Widget,
        target_path: str,
        is_folder: bool,
        current_rules: Optional[List[Dict[str, str]]] = None,
        field_dictionary: Optional[Any] = None,
        on_complete: Optional[Callable[[List[Dict[str, str]], Dict[str, int]], None]] = None,
        on_status_msg: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.target_path = target_path
        self.is_folder = is_folder
        self.current_rules = current_rules or []
        self.field_dictionary = field_dictionary
        self.on_complete = on_complete
        self.on_status_msg = on_status_msg

        self.msg_queue: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.is_done = False
        self.was_cancelled = False

        self.final_rules: List[Dict[str, str]] = list(self.current_rules)
        self.unknown_labels: Dict[str, int] = {}

        self.title("Pemindaian & Prediksi Dokumen - Smart RPP Replacer")
        self.geometry("740x520")
        self.minsize(620, 420)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        self._build_ui()
        center_window(self, parent, 740, 520)
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Mulai thread worker pemindaian dokumen
        self.worker_thread = threading.Thread(target=self._worker_run, daemon=True)
        self.worker_thread.start()

        self.after(50, self._poll_queue)

    def _build_ui(self):
        # 1. Header Frame
        top_frame = ttk.Frame(self, padding=(12, 10))
        top_frame.pack(side="top", fill="x")

        target_name = os.path.basename(self.target_path) or self.target_path
        title_text = f"Memindai Folder: {target_name}" if self.is_folder else f"Menganalisis Dokumen: {target_name}"

        lbl_title = ttk.Label(top_frame, text=title_text, font=("Segoe UI", 11, "bold"))
        lbl_title.pack(anchor="w")

        self.lbl_status = ttk.Label(
            top_frame,
            text="Menyiapkan pemindaian berkas...",
            font=("Segoe UI", 9),
            foreground="#555555"
        )
        self.lbl_status.pack(anchor="w", pady=(2, 0))

        # 2. Progress Frame
        prog_frame = ttk.Frame(self, padding=(12, 2))
        prog_frame.pack(side="top", fill="x")

        self.progress = ttk.Progressbar(prog_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)

        self.lbl_pct = ttk.Label(prog_frame, text="0%", width=6, anchor="e", font=("Segoe UI", 9, "bold"))
        self.lbl_pct.pack(side="right", padx=(6, 0))

        # 3. Bottom Button Frame (di-pack ke side='bottom' lebih awal agar selalu terlihat dan tidak terdorong)
        bottom_frame = ttk.Frame(self, padding=(12, 10))
        bottom_frame.pack(side="bottom", fill="x")

        self.lbl_bottom_hint = ttk.Label(
            bottom_frame,
            text="",
            font=("Segoe UI", 9, "italic"),
            foreground="#2e7d32"
        )
        self.lbl_bottom_hint.pack(side="left")

        self.btn_action = ttk.Button(
            bottom_frame,
            text="Batal",
            width=14,
            command=self._on_action_click
        )
        self.btn_action.pack(side="right")

        # 4. Live Log Box Frame (mengisi ruang tengah)
        log_frame = ttk.Frame(self, padding=(12, 6))
        log_frame.pack(side="top", fill="both", expand=True)

        ttk.Label(log_frame, text="Live Log Deteksi & Analisis:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 3))

        box_container = ttk.Frame(log_frame)
        box_container.pack(fill="both", expand=True)

        self.log_box = tk.Text(
            box_container,
            wrap="word",
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            font=("Consolas", 9),
            state="disabled",
            borderwidth=1,
            relief="sunken"
        )
        sb = ttk.Scrollbar(box_container, orient="vertical", command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=sb.set)

        self.log_box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Tag pewarnaan konsol
        self.log_box.tag_configure("info", foreground="#61afef")
        self.log_box.tag_configure("success", foreground="#98c379")
        self.log_box.tag_configure("warn", foreground="#e5c07b")
        self.log_box.tag_configure("error", foreground="#e06c75")
        self.log_box.tag_configure("cancel", foreground="#d19a66")
        self.log_box.tag_configure("bold", font=("Consolas", 9, "bold"))

    def _append_log(self, text: str):
        """Menambahkan teks log ke dalam Text widget dengan pewarnaan tag."""
        self.log_box.configure(state="normal")

        tag = None
        stripped = text.strip()
        if "🎉" in stripped or "SELESAI" in stripped or stripped.startswith("✔") or stripped.startswith("[DONE]"):
            tag = "success"
        elif stripped.startswith("[WARN]") or stripped.startswith("⚠️"):
            tag = "warn"
        elif stripped.startswith("[ERROR]"):
            tag = "error"
        elif stripped.startswith("[CANCEL]"):
            tag = "cancel"
        elif stripped.startswith("[FILE]") or stripped.startswith("[START]"):
            tag = "info"

        if tag:
            self.log_box.insert("end", text + "\n", tag)
        else:
            self.log_box.insert("end", text + "\n")

        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "main_log":
                    if self.on_status_msg:
                        try:
                            self.on_status_msg(payload)
                        except Exception:
                            pass
                elif kind == "progress":
                    cur, total, fname = payload
                    pct = int((cur / max(1, total)) * 100)
                    self.progress["maximum"] = total
                    self.progress["value"] = cur
                    self.lbl_pct.configure(text=f"{pct}%")
                    self.lbl_status.configure(text=f"Memindai berkas [{cur}/{total}]: {fname}")
                elif kind == "done":
                    self.is_done = True
                    self.final_rules, self.unknown_labels = payload
                    self.progress["value"] = self.progress["maximum"]
                    self.lbl_pct.configure(text="100%")

                    num_rules = len(self.final_rules)
                    num_unk = len(self.unknown_labels)
                    if self.was_cancelled:
                        banner = (
                            f"\n{'='*58}\n"
                            f"⚠️  PEMINDAIAN DIHENTIKAN OLEH PENGGUNA\n"
                            f"• Aturan terkumpul  : {num_rules} aturan penggantian\n"
                            f"• Label tak dikenal : {num_unk} label terdeteksi\n"
                            f"{'='*58}\n"
                            f"Klik 'Lihat Ringkasan & Terapkan ➜' di bawah untuk memeriksa hasil."
                        )
                        self._append_log(banner)
                        self.lbl_status.configure(
                            text=f"Dihentikan. Tersimpan {num_rules} aturan dari berkas sebelum pembatalan."
                        )
                    else:
                        banner = (
                            f"\n{'='*58}\n"
                            f"🎉 PEMINDAIAN DOKUMEN SELESAI (100%)\n"
                            f"• Aturan disiapkan : {num_rules} aturan penggantian\n"
                            f"• Label tak dikenal: {num_unk} label terdeteksi di kamus\n"
                            f"{'='*58}\n"
                            f"Silakan klik tombol 'Lihat Ringkasan & Terapkan ➜' di bawah."
                        )
                        self._append_log(banner)
                        self.lbl_status.configure(
                            text=f"Selesai 100%! {num_rules} aturan disiapkan. Klik 'Lihat Ringkasan & Terapkan' di bawah."
                        )

                    if hasattr(self, "lbl_bottom_hint"):
                        if self.was_cancelled:
                            self.lbl_bottom_hint.configure(
                                text=f"⚠️ Dihentikan ({num_rules} aturan tersimpan)."
                            )
                        else:
                            self.lbl_bottom_hint.configure(
                                text=f"✔ Pemindaian selesai (100% - {num_rules} aturan disiapkan)."
                            )

                    self.btn_action.configure(
                        state="normal",
                        text="Lihat Ringkasan & Terapkan ➜",
                        width=28
                    )
                elif kind == "error":
                    self.is_done = True
                    err_msg = payload
                    self._append_log(f"\n[ERROR] Terjadi kesalahan fatal: {err_msg}")
                    self.lbl_status.configure(text="Pemindaian terhenti karena kesalahan.")
                    self.btn_action.configure(state="normal", text="Tutup", width=14)
        except queue.Empty:
            pass

        if not self.is_done or not self.msg_queue.empty():
            self.after(50, self._poll_queue)

    def _worker_run(self):
        """Dijalankan di background thread untuk mengeksekusi pemindaian dokumen."""
        def log_cb(msg: str):
            self.msg_queue.put(("log", msg))

        def prog_cb(cur: int, tot: int, fname: str):
            self.msg_queue.put(("progress", (cur, tot, fname)))

        try:
            if self.is_folder:
                log_cb(f"Memulai pemindaian direktori folder:\n{self.target_path}")
                rules = predict_rules_from_folder(
                    folder_path=self.target_path,
                    current_rules=self.current_rules,
                    progress_callback=prog_cb,
                    log_callback=log_cb,
                    cancel_event=self.cancel_event,
                )
                if not self.cancel_event.is_set():
                    log_cb("\nMendeteksi label tak dikenal di kamus...")
                    unknowns = collect_unknown_labels(
                        path_or_dir=self.target_path,
                        dictionary=self.field_dictionary,
                        log_callback=log_cb,
                        cancel_event=self.cancel_event,
                    )
                else:
                    unknowns = {}
            else:
                prog_cb(1, 1, os.path.basename(self.target_path))
                rules = predict_rules_from_file(
                    docx_path=self.target_path,
                    current_rules=self.current_rules,
                    log_callback=log_cb,
                )
                unknowns = collect_unknown_labels(
                    path_or_dir=self.target_path,
                    dictionary=self.field_dictionary,
                    log_callback=log_cb,
                )

            # Laporkan ke logbox utama secara aman via msg_queue agar dieksekusi di UI thread
            fname = os.path.basename(self.target_path) or self.target_path
            main_msg = f"[PREDICT] Selesai memindai '{fname}': {len(rules)} aturan penggantian disiapkan."
            self.msg_queue.put(("main_log", main_msg))

            self.msg_queue.put(("done", (rules, unknowns)))
        except Exception as e:
            self.msg_queue.put(("error", str(e)))

    def _on_action_click(self):
        if not self.is_done:
            # Tombol berfungsi sebagai Batal
            if messagebox.askyesno(
                "Konfirmasi Pembatalan",
                "Apakah Anda yakin ingin membatalkan pemindaian dokumen?\n"
                "Aturan dari berkas yang sudah sempat selesai dipindai akan tetap disimpan."
            ):
                self.was_cancelled = True
                self.cancel_event.set()
                self.btn_action.configure(state="disabled", text="Membatalkan...")
        else:
            # Tombol berfungsi sebagai Tutup
            self._close()

    def _on_window_close(self):
        if not self.is_done:
            self._on_action_click()
        else:
            self._close()

    def _close(self):
        """Menutup dialog dan memanggil callback penyelesaian untuk menerapkan data."""
        if self.on_complete:
            try:
                self.on_complete(self.final_rules, self.unknown_labels)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menerapkan aturan hasil prediksi:\n{e}")
        self.destroy()
