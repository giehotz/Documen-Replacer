"""
Komponen GUI: Jendela Laporan Hasil Pemrosesan (Report Dialog).
Menampilkan ringkasan eksekutif dokumen dan statistik penggantian per kategori.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from services.report_service import ReportService
from utils.platform import open_path


class ReportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, report_service: ReportService, output_dir: str):
        super().__init__(parent)
        self.title("Laporan Hasil Pemrosesan Dokumen - Smart RPP Replacer")
        self.geometry("720x540")
        self.minsize(620, 440)
        self.transient(parent)
        self.grab_set()

        self.report_service = report_service
        self.output_dir = output_dir

        self._build_ui()

    def _build_ui(self):
        # 1. Header
        header = ttk.Frame(self, padding=(14, 12))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Laporan Rekapitulasi Pemrosesan RPP",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=f"Folder Penyimpanan: {self.output_dir}",
            foreground="#555555"
        ).pack(anchor="w", pady=(2, 0))

        v_summary = self.report_service.verification_summary
        if v_summary:
            v_dict = v_summary.get("verdict", {})
            ok_cnt = v_dict.get("OK", 0)
            periksa_cnt = v_dict.get("PERIKSA", 0)
            salah_cnt = v_dict.get("SALAH", 0)

            v_frame = ttk.Frame(header)
            v_frame.pack(anchor="w", pady=(4, 0))
            ttk.Label(v_frame, text="Audit Kualitas Verifikasi: ", font=("Segoe UI", 9, "bold")).pack(side="left")
            ttk.Label(v_frame, text=f"OK: {ok_cnt}", foreground="#007700", font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)
            if periksa_cnt > 0:
                ttk.Label(v_frame, text=f"PERIKSA: {periksa_cnt}", foreground="#b38600", font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)
            if salah_cnt > 0:
                ttk.Label(v_frame, text=f"SALAH: {salah_cnt}", foreground="#cc0000", font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)

        # 2. Kartu Ringkasan Metrik
        metrics_frame = ttk.LabelFrame(self, text=" Ringkasan Dokumen ", padding=10)
        metrics_frame.pack(fill="x", padx=14, pady=5)
        for i in range(5):
            metrics_frame.columnconfigure(i, weight=1)

        cards = [
            ("Dipindai", self.report_service.total_scanned, "#1e1e1e"),
            ("Berhasil", self.report_service.succeeded, "#007700"),
            ("Tidak Berubah", self.report_service.unchanged, "#555555"),
            ("Perlu Tinjau", self.report_service.needs_review, "#b38600"),
            ("Gagal", self.report_service.failed, "#cc0000"),
        ]

        for col, (label, val, color) in enumerate(cards):
            card = ttk.Frame(metrics_frame, padding=6)
            card.grid(row=0, column=col, sticky="ew")
            lbl_val = ttk.Label(card, text=str(val), font=("Segoe UI", 14, "bold"), foreground=color)
            lbl_val.pack()
            lbl_name = ttk.Label(card, text=label, font=("Segoe UI", 8))
            lbl_name.pack()

        # 3. Rincian Penggantian per Kategori
        detail_frame = ttk.LabelFrame(self, text=" Rincian Penggantian per Kategori ", padding=10)
        detail_frame.pack(fill="both", expand=True, padx=14, pady=8)

        cols = ("category", "count")
        tree = ttk.Treeview(detail_frame, columns=cols, show="headings", height=8)
        tree.heading("category", text="Kategori Data")
        tree.heading("count", text="Jumlah Penggantian")
        tree.column("category", width=340, anchor="w")
        tree.column("count", width=120, anchor="center")

        sb = ttk.Scrollbar(detail_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)

        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        if self.report_service.category_counts:
            for cat, count in sorted(self.report_service.category_counts.items(), key=lambda x: x[1], reverse=True):
                tree.insert("", "end", values=(cat, f"{count} titik"))
        else:
            tree.insert("", "end", values=("(Tidak ada penggantian)", "0"))

        # 4. Tombol Aksi Bawah
        bottom = ttk.Frame(self, padding=(14, 12))
        bottom.pack(fill="x")

        ttk.Button(bottom, text="Buka Folder Hasil", command=self._open_folder).pack(side="left", padx=(0, 6))
        ttk.Button(bottom, text="Buka File Laporan (.txt)", command=self._open_report_file).pack(side="left", padx=(0, 6))

        if self.report_service.json_report_path:
            ttk.Button(
                bottom,
                text="📄 Buka Laporan JSON",
                command=self._open_json_report_file
            ).pack(side="left")

        ttk.Button(bottom, text="Tutup", command=self.destroy).pack(side="right")

    def _open_folder(self):
        try:
            open_path(self.output_dir)
        except Exception as e:
            messagebox.showwarning("Gagal Membuka Folder", f"Tidak dapat membuka folder:\n{e}")

    def _open_report_file(self):
        report_path = os.path.join(self.output_dir, "LAPORAN_PENGGANTIAN_RPP.txt")
        if os.path.isfile(report_path):
            try:
                open_path(report_path)
            except Exception as e:
                messagebox.showwarning("Gagal Membuka Laporan", f"Tidak dapat membuka file laporan:\n{e}")
        else:
            messagebox.showinfo("Laporan", "Berkas laporan belum tersedia di folder output.")

    def _open_json_report_file(self):
        json_path = self.report_service.json_report_path
        if json_path and os.path.isfile(json_path):
            try:
                open_path(json_path)
            except Exception as e:
                messagebox.showwarning("Gagal Membuka Laporan JSON", f"Tidak dapat membuka berkas JSON:\n{e}")
        else:
            messagebox.showinfo("Laporan JSON", "Berkas laporan perubahan JSON belum tersedia.")
