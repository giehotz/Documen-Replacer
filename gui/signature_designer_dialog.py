"""
Komponen GUI: Jendela Desain & Pengatur Tanda Tangan Digital (Signature Designer).
Menyediakan:
- Kontrol slider ukuran (cm), pemilihan berkas gambar, perataan, dan spasi
- Simulasi visual Kanvas real-time blok tanda tangan Microsoft Word
- Penyimpanan pengaturan permanen ke config/signature_settings.json
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Any, Optional
from PIL import Image, ImageTk

from core.signature_image_service import (
    load_signature_settings,
    save_signature_settings,
    DEFAULT_SETTINGS,
)


class SignatureDesignerDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, on_save_callback=None):
        super().__init__(parent)
        self.title("Pengatur Tanda Tangan Digital & Presisi Penempatan")
        self.geometry("980x620")
        self.minsize(860, 540)
        self.transient(parent)
        self.grab_set()

        self.on_save_callback = on_save_callback
        self.settings: Dict[str, Any] = load_signature_settings()

        # Cache untuk referensi objek PhotoImage Tkinter agar tidak di-garbage collect
        self._photo_cache = {}

        self._init_variables()
        self._build_ui()
        self._update_preview()

    def _init_variables(self):
        self.enable_kepala_var = tk.BooleanVar(value=self.settings.get("enabled_kepala", False))
        self.path_kepala_var = tk.StringVar(value=self.settings.get("kepala_image_path", ""))
        self.width_kepala_var = tk.DoubleVar(value=float(self.settings.get("kepala_width_cm", 3.5)))

        self.enable_guru_var = tk.BooleanVar(value=self.settings.get("enabled_guru", False))
        self.path_guru_var = tk.StringVar(value=self.settings.get("guru_image_path", ""))
        self.width_guru_var = tk.DoubleVar(value=float(self.settings.get("guru_width_cm", 3.5)))

        self.alignment_var = tk.StringVar(value=self.settings.get("alignment", "CENTER"))
        self.spacing_var = tk.IntVar(value=int(self.settings.get("spacing_before_pt", 2)))

    def _build_ui(self):
        # 1. Header
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Pengatur Posisi & Ukuran Tanda Tangan Digital",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Atur ukuran dan posisi gambar tanda tangan secara presisi. Lihat hasil simulasi real-time di sisi kanan.",
            foreground="#555555"
        ).pack(anchor="w", pady=(2, 0))

        # 2. Main Container (Split: Kiri Kontrol, Kanan Kanvas)
        container = ttk.Frame(self, padding=(12, 4))
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=4, minsize=380)
        container.columnconfigure(1, weight=5, minsize=420)
        container.rowconfigure(0, weight=1)

        # =====================================================================
        # PANEL KIRI: KONTROL PENGATURAN
        # =====================================================================
        left_frame = ttk.Frame(container)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # A. Tanda Tangan Kepala Madrasah
        frame_kepala = ttk.LabelFrame(left_frame, text=" 1. Tanda Tangan Kepala Madrasah/Sekolah ", padding=8)
        frame_kepala.pack(fill="x", pady=(0, 6))

        ttk.Checkbutton(
            frame_kepala,
            text="Aktifkan Sisipkan Tanda Tangan Kepala",
            variable=self.enable_kepala_var,
            command=self._on_control_changed
        ).pack(anchor="w", pady=(0, 4))

        row_k1 = ttk.Frame(frame_kepala)
        row_k1.pack(fill="x", pady=2)
        ttk.Label(row_k1, text="Berkas Gambar:").pack(side="left")
        ttk.Button(row_k1, text="Pilih Gambar...", command=self._browse_kepala).pack(side="right")
        ttk.Entry(row_k1, textvariable=self.path_kepala_var, state="readonly").pack(side="left", fill="x", expand=True, padx=4)

        row_k2 = ttk.Frame(frame_kepala)
        row_k2.pack(fill="x", pady=(4, 0))
        ttk.Label(row_k2, text="Lebar Gambar:").pack(side="left")
        self.lbl_width_kepala = ttk.Label(row_k2, text=f"{self.width_kepala_var.get():.1f} cm", width=8, anchor="e")
        self.lbl_width_kepala.pack(side="right")
        self.slider_kepala = ttk.Scale(
            row_k2,
            from_=2.0,
            to=6.5,
            variable=self.width_kepala_var,
            command=lambda val: self._on_slider_changed("kepala", val)
        )
        self.slider_kepala.pack(side="left", fill="x", expand=True, padx=6)

        # B. Tanda Tangan Guru
        frame_guru = ttk.LabelFrame(left_frame, text=" 2. Tanda Tangan Guru / Penyusun ", padding=8)
        frame_guru.pack(fill="x", pady=6)

        ttk.Checkbutton(
            frame_guru,
            text="Aktifkan Sisipkan Tanda Tangan Guru",
            variable=self.enable_guru_var,
            command=self._on_control_changed
        ).pack(anchor="w", pady=(0, 4))

        row_g1 = ttk.Frame(frame_guru)
        row_g1.pack(fill="x", pady=2)
        ttk.Label(row_g1, text="Berkas Gambar:").pack(side="left")
        ttk.Button(row_g1, text="Pilih Gambar...", command=self._browse_guru).pack(side="right")
        ttk.Entry(row_g1, textvariable=self.path_guru_var, state="readonly").pack(side="left", fill="x", expand=True, padx=4)

        row_g2 = ttk.Frame(frame_guru)
        row_g2.pack(fill="x", pady=(4, 0))
        ttk.Label(row_g2, text="Lebar Gambar:").pack(side="left")
        self.lbl_width_guru = ttk.Label(row_g2, text=f"{self.width_guru_var.get():.1f} cm", width=8, anchor="e")
        self.lbl_width_guru.pack(side="right")
        self.slider_guru = ttk.Scale(
            row_g2,
            from_=2.0,
            to=6.5,
            variable=self.width_guru_var,
            command=lambda val: self._on_slider_changed("guru", val)
        )
        self.slider_guru.pack(side="left", fill="x", expand=True, padx=6)

        # C. Perataan & Jarak Spasi
        frame_opt = ttk.LabelFrame(left_frame, text=" 3. Perataan & Spasi Baris ", padding=8)
        frame_opt.pack(fill="x", pady=6)

        row_opt1 = ttk.Frame(frame_opt)
        row_opt1.pack(fill="x", pady=2)
        ttk.Label(row_opt1, text="Perataan:").pack(side="left", padx=(0, 8))
        for align_label, align_val in [("Tengah (Center)", "CENTER"), ("Kiri (Left)", "LEFT"), ("Kanan (Right)", "RIGHT")]:
            ttk.Radiobutton(
                row_opt1,
                text=align_label,
                value=align_val,
                variable=self.alignment_var,
                command=self._on_control_changed
            ).pack(side="left", padx=4)

        # =====================================================================
        # PANEL KANAN: KANVAS SIMULASI REAL-TIME
        # =====================================================================
        right_frame = ttk.LabelFrame(container, text=" Simulasi Tampilan Dokumen Word (Live Preview) ", padding=8)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(right_frame, bg="#ffffff", highlightthickness=1, highlightbackground="#cccccc")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda e: self._update_preview())

        # 3. Tombol Aksi Bawah
        bottom = ttk.Frame(self, padding=(14, 10))
        bottom.pack(fill="x")

        ttk.Button(bottom, text="Reset ke Bawaan", command=self._reset_defaults).pack(side="left")
        ttk.Button(bottom, text="Tutup / Batal", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(
            bottom,
            text="SIMPAN PENGATURAN TANDA TANGAN",
            command=self._save_settings
        ).pack(side="right", ipady=3)

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================
    def _browse_kepala(self):
        f = filedialog.askopenfilename(
            title="Pilih Gambar Tanda Tangan Kepala",
            filetypes=[("Berkas Gambar", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if f:
            self.path_kepala_var.set(os.path.normpath(f))
            self.enable_kepala_var.set(True)
            self._update_preview()

    def _browse_guru(self):
        f = filedialog.askopenfilename(
            title="Pilih Gambar Tanda Tangan Guru",
            filetypes=[("Berkas Gambar", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if f:
            self.path_guru_var.set(os.path.normpath(f))
            self.enable_guru_var.set(True)
            self._update_preview()

    def _on_slider_changed(self, target: str, val: str):
        v = float(val)
        if target == "kepala":
            self.lbl_width_kepala.config(text=f"{v:.1f} cm")
        else:
            self.lbl_width_guru.config(text=f"{v:.1f} cm")
        self._update_preview()

    def _on_control_changed(self):
        self._update_preview()

    # =========================================================================
    # RENDER SIMULASI KANVAS WORD
    # =========================================================================
    def _update_preview(self):
        self.canvas.delete("all")
        self._photo_cache.clear()

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 100 or h < 100:
            w, h = 480, 420

        # Skala konversi: 1 cm di dunia nyata ~ 30 pixel di kanvas layar
        px_per_cm = 32.0

        # Koordinat kolom Kiri (Kepala) dan Kanan (Guru)
        col_w = w / 2.0
        x_kepala_center = col_w * 0.5
        x_guru_center = col_w * 1.5

        # Garis batas vertikal samar pemisah 2 kolom tabel Word
        self.canvas.create_line(col_w, 20, col_w, h - 20, fill="#f0f0f0", dash=(4, 4))

        # --- A. Render Sisi Kiri (Kepala Madrasah) ---
        y = 35
        self.canvas.create_text(x_kepala_center, y, text="Mengetahui,", font=("Segoe UI", 9), fill="#333333")
        y += 18
        self.canvas.create_text(x_kepala_center, y, text="Kepala Madrasah", font=("Segoe UI", 9, "bold"), fill="#111111")
        y += 15

        # Gambar Tanda Tangan Kepala
        k_path = self.path_kepala_var.get().strip()
        k_enabled = self.enable_kepala_var.get()
        k_width_cm = self.width_kepala_var.get()

        k_target_px = int(k_width_cm * px_per_cm)
        y_sig_kepala = y + 35

        if k_enabled and k_path and os.path.isfile(k_path):
            try:
                pil_img = Image.open(k_path)
                aspect = pil_img.height / max(1, pil_img.width)
                k_height_px = max(20, int(k_target_px * aspect))
                resized = pil_img.resize((k_target_px, k_height_px), Image.Resampling.LANCZOS)
                tk_img = ImageTk.PhotoImage(resized)
                self._photo_cache["kepala"] = tk_img

                x_pos = self._calc_align_x(x_kepala_center, col_w * 0.1, col_w * 0.9, k_target_px)
                self.canvas.create_image(x_pos, y_sig_kepala, image=tk_img, anchor="center")
            except Exception:
                self.canvas.create_text(x_kepala_center, y_sig_kepala, text="[Gambar Error]", fill="#cc0000")
        else:
            self.canvas.create_rectangle(
                x_kepala_center - k_target_px // 2, y_sig_kepala - 25,
                x_kepala_center + k_target_px // 2, y_sig_kepala + 25,
                outline="#dddddd", fill="#fafafa", dash=(2, 2)
            )
            desc = "(Tanda Tangan Kepala)" if k_enabled else "(Ruang Tanda Tangan Kosong)"
            self.canvas.create_text(x_kepala_center, y_sig_kepala, text=desc, font=("Segoe UI", 8), fill="#aaaaaa")

        y = y_sig_kepala + 45
        self.canvas.create_text(x_kepala_center, y, text="( Sipulloh, M.Pd )", font=("Segoe UI", 9, "bold", "underline"), fill="#111111")
        y += 18
        self.canvas.create_text(x_kepala_center, y, text="NIP. 197005272007011022", font=("Segoe UI", 9), fill="#333333")

        # --- B. Render Sisi Kanan (Guru / Penyusun) ---
        y_g = 35
        self.canvas.create_text(x_guru_center, y_g, text="Tanggamus, 13 Juli 2026", font=("Segoe UI", 9), fill="#333333")
        y_g += 18
        self.canvas.create_text(x_guru_center, y_g, text="Guru Mata Pelajaran PJOK", font=("Segoe UI", 9, "bold"), fill="#111111")
        y_g += 15

        g_path = self.path_guru_var.get().strip()
        g_enabled = self.enable_guru_var.get()
        g_width_cm = self.width_guru_var.get()

        g_target_px = int(g_width_cm * px_per_cm)
        y_sig_guru = y_g + 35

        if g_enabled and g_path and os.path.isfile(g_path):
            try:
                pil_g = Image.open(g_path)
                aspect_g = pil_g.height / max(1, pil_g.width)
                g_height_px = max(20, int(g_target_px * aspect_g))
                resized_g = pil_g.resize((g_target_px, g_height_px), Image.Resampling.LANCZOS)
                tk_img_g = ImageTk.PhotoImage(resized_g)
                self._photo_cache["guru"] = tk_img_g

                x_pos_g = self._calc_align_x(x_guru_center, col_w + col_w * 0.1, col_w + col_w * 0.9, g_target_px)
                self.canvas.create_image(x_pos_g, y_sig_guru, image=tk_img_g, anchor="center")
            except Exception:
                self.canvas.create_text(x_guru_center, y_sig_guru, text="[Gambar Error]", fill="#cc0000")
        else:
            self.canvas.create_rectangle(
                x_guru_center - g_target_px // 2, y_sig_guru - 25,
                x_guru_center + g_target_px // 2, y_sig_guru + 25,
                outline="#dddddd", fill="#fafafa", dash=(2, 2)
            )
            desc_g = "(Tanda Tangan Guru)" if g_enabled else "(Ruang Tanda Tangan Kosong)"
            self.canvas.create_text(x_guru_center, y_sig_guru, text=desc_g, font=("Segoe UI", 8), fill="#aaaaaa")

        y_g = y_sig_guru + 45
        self.canvas.create_text(x_guru_center, y_g, text="( Dwi Putri Ayu Andari, S.Pd )", font=("Segoe UI", 9, "bold", "underline"), fill="#111111")
        y_g += 18
        self.canvas.create_text(x_guru_center, y_g, text="NIP. 199305312023212036", font=("Segoe UI", 9), fill="#333333")

    def _calc_align_x(self, center_x: float, left_bound: float, right_bound: float, img_w: int) -> float:
        align = self.alignment_var.get().upper()
        if align == "LEFT":
            return left_bound + img_w / 2.0
        elif align == "RIGHT":
            return right_bound - img_w / 2.0
        return center_x

    def _reset_defaults(self):
        self.enable_kepala_var.set(False)
        self.path_kepala_var.set("")
        self.width_kepala_var.set(3.5)
        self.enable_guru_var.set(False)
        self.path_guru_var.set("")
        self.width_guru_var.set(3.5)
        self.alignment_var.set("CENTER")
        self.spacing_var.set(2)
        self.lbl_width_kepala.config(text="3.5 cm")
        self.lbl_width_guru.config(text="3.5 cm")
        self._update_preview()

    def _save_settings(self):
        new_settings = {
            "enabled_kepala": self.enable_kepala_var.get(),
            "kepala_image_path": self.path_kepala_var.get().strip(),
            "kepala_width_cm": round(self.width_kepala_var.get(), 1),
            "enabled_guru": self.enable_guru_var.get(),
            "guru_image_path": self.path_guru_var.get().strip(),
            "guru_width_cm": round(self.width_guru_var.get(), 1),
            "alignment": self.alignment_var.get(),
            "spacing_before_pt": self.spacing_var.get(),
            "spacing_after_pt": self.spacing_var.get(),
        }
        save_signature_settings(new_settings)
        if self.on_save_callback:
            self.on_save_callback(new_settings)
        messagebox.showinfo("Berhasil", "Pengaturan tanda tangan berhasil disimpan!")
        self.destroy()
