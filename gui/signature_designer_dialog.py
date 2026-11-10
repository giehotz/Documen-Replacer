"""
Komponen GUI: Jendela Desain & Pengatur Tanda Tangan Digital (Signature Designer).
Menyediakan:
- Kontrol slider ukuran (cm), pemilihan berkas gambar, perataan, dan spasi
- Pemisahan profil konfigurasi antara Dokumen Potrait (RPP) dan Dokumen Lanskap (Silabus/Promes)
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
        self.title("Pengatur Tanda Tangan Digital & Presisi Penempatan (Potrait & Lanskap)")
        self.geometry("1040x720")
        self.minsize(940, 640)
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
        self.current_orientation = "PORTRAIT"

        # Pengaturan Bersama (Gambar, Status Aktif, Alignment, Behind Text)
        self.enable_kepala_var = tk.BooleanVar(value=self.settings.get("enabled_kepala", False))
        self.path_kepala_var = tk.StringVar(value=self.settings.get("kepala_image_path", ""))
        self.enable_guru_var = tk.BooleanVar(value=self.settings.get("enabled_guru", False))
        self.path_guru_var = tk.StringVar(value=self.settings.get("guru_image_path", ""))

        self.alignment_var = tk.StringVar(value=self.settings.get("alignment", "CENTER"))
        self.behind_text_var = tk.BooleanVar(value=bool(self.settings.get("behind_text", True)))
        self.spacing_var = tk.IntVar(value=int(self.settings.get("spacing_before_pt", 2)))

        # Profil Geometri Potrait (Root Settings)
        self.portrait_geo = {
            "width_kepala": float(self.settings.get("kepala_width_cm", 3.5)),
            "offx_kepala": float(self.settings.get("offset_x_kepala_cm", 0.0)),
            "offy_kepala": float(self.settings.get("offset_y_kepala_cm", 0.0)),
            "width_guru": float(self.settings.get("guru_width_cm", 3.5)),
            "offx_guru": float(self.settings.get("offset_x_guru_cm", 0.0)),
            "offy_guru": float(self.settings.get("offset_y_guru_cm", 0.0)),
        }

        # Profil Geometri Lanskap (Sub-dict 'landscape')
        land_cfg = self.settings.get("landscape")
        if isinstance(land_cfg, dict):
            self.landscape_geo = {
                "width_kepala": float(land_cfg.get("kepala_width_cm", self.portrait_geo["width_kepala"])),
                "offx_kepala": float(land_cfg.get("offset_x_kepala_cm", round(self.portrait_geo["offx_kepala"] - 2.3, 1))),
                "offy_kepala": float(land_cfg.get("offset_y_kepala_cm", self.portrait_geo["offy_kepala"])),
                "width_guru": float(land_cfg.get("guru_width_cm", self.portrait_geo["width_guru"])),
                "offx_guru": float(land_cfg.get("offset_x_guru_cm", round(self.portrait_geo["offx_guru"] - 2.3, 1))),
                "offy_guru": float(land_cfg.get("offset_y_guru_cm", self.portrait_geo["offy_guru"])),
            }
        else:
            self.landscape_geo = {
                "width_kepala": self.portrait_geo["width_kepala"],
                "offx_kepala": round(self.portrait_geo["offx_kepala"] - 2.3, 1),
                "offy_kepala": self.portrait_geo["offy_kepala"],
                "width_guru": self.portrait_geo["width_guru"],
                "offx_guru": round(self.portrait_geo["offx_guru"] - 2.3, 1),
                "offy_guru": self.portrait_geo["offy_guru"],
            }

        # Variabel aktif yang terikat langsung ke slider GUI
        self.width_kepala_var = tk.DoubleVar(value=self.portrait_geo["width_kepala"])
        self.offx_kepala_var = tk.DoubleVar(value=self.portrait_geo["offx_kepala"])
        self.offy_kepala_var = tk.DoubleVar(value=self.portrait_geo["offy_kepala"])

        self.width_guru_var = tk.DoubleVar(value=self.portrait_geo["width_guru"])
        self.offx_guru_var = tk.DoubleVar(value=self.portrait_geo["offx_guru"])
        self.offy_guru_var = tk.DoubleVar(value=self.portrait_geo["offy_guru"])

    def _build_ui(self):
        # 1. Header
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Pengatur Posisi & Ukuran Tanda Tangan Digital (Potrait & Lanskap)",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Tersedia profil terpisah untuk Dokumen Potrait (RPP) dan Dokumen Lanskap (Silabus/Promes). Sistem otomatis mendeteksi orientasi berkas saat memproses.",
            foreground="#555555"
        ).pack(anchor="w", pady=(2, 0))

        # 2. Main Container (Split: Kiri Kontrol, Kanan Kanvas)
        container = ttk.Frame(self, padding=(12, 4))
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=4, minsize=420)
        container.columnconfigure(1, weight=5, minsize=440)
        container.rowconfigure(0, weight=1)

        # =====================================================================
        # PANEL KIRI: KONTROL PENGATURAN
        # =====================================================================
        left_frame = ttk.Frame(container)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Tab Pemilih Orientasi Halaman
        tab_frame = ttk.LabelFrame(left_frame, text=" Pilih Profil Orientasi yang Sedang Diatur ", padding=6)
        tab_frame.pack(fill="x", pady=(0, 6))

        tab_row = ttk.Frame(tab_frame)
        tab_row.pack(fill="x", pady=2)

        self.btn_tab_portrait = tk.Button(
            tab_row,
            text="📄 Dokumen Potrait (RPP)",
            font=("Segoe UI", 9, "bold"),
            bg="#0066cc",
            fg="#ffffff",
            relief="groove",
            command=lambda: self._switch_orientation("PORTRAIT")
        )
        self.btn_tab_portrait.pack(side="left", fill="x", expand=True, padx=(0, 3), ipady=3)

        self.btn_tab_landscape = tk.Button(
            tab_row,
            text="📑 Dokumen Lanskap (Silabus / Promes)",
            font=("Segoe UI", 9),
            bg="#f0f0f0",
            fg="#222222",
            relief="groove",
            command=lambda: self._switch_orientation("LANDSCAPE")
        )
        self.btn_tab_landscape.pack(side="left", fill="x", expand=True, padx=(3, 0), ipady=3)

        # Bilah Alat Khusus Lanskap (Pintasan Cepat)
        self.frame_land_tools = ttk.Frame(left_frame, padding=(4, 2))
        ttk.Button(
            self.frame_land_tools,
            text="📋 Salin dari Potrait",
            command=self._copy_from_portrait
        ).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ttk.Button(
            self.frame_land_tools,
            text="⚡ Sesuaikan Otomatis Lanskap",
            command=self._auto_compensate_landscape
        ).pack(side="left", fill="x", expand=True, padx=(2, 0))

        # A. Tanda Tangan Kepala Madrasah
        self.frame_kepala = ttk.LabelFrame(left_frame, text=" 1. Tanda Tangan Kepala Madrasah/Sekolah ", padding=8)
        self.frame_kepala.pack(fill="x", pady=(0, 5))

        ttk.Checkbutton(
            self.frame_kepala,
            text="Aktifkan Sisipkan Tanda Tangan Kepala",
            variable=self.enable_kepala_var,
            command=self._on_control_changed
        ).pack(anchor="w", pady=(0, 2))

        row_k1 = ttk.Frame(self.frame_kepala)
        row_k1.pack(fill="x", pady=2)
        ttk.Label(row_k1, text="Berkas:").pack(side="left")
        ttk.Button(row_k1, text="Pilih Gambar...", command=self._browse_kepala).pack(side="right")
        ttk.Entry(row_k1, textvariable=self.path_kepala_var, state="readonly").pack(side="left", fill="x", expand=True, padx=4)

        row_k2 = ttk.Frame(self.frame_kepala)
        row_k2.pack(fill="x", pady=1)
        ttk.Label(row_k2, text="Lebar:").pack(side="left")
        self.lbl_width_kepala = ttk.Label(row_k2, text=f"{self.width_kepala_var.get():.1f} cm", width=8, anchor="e")
        self.lbl_width_kepala.pack(side="right")
        self.slider_kepala = ttk.Scale(
            row_k2,
            from_=2.0,
            to=6.5,
            variable=self.width_kepala_var,
            command=lambda val: self._on_slider_changed("kepala", "width", val)
        )
        self.slider_kepala.pack(side="left", fill="x", expand=True, padx=6)

        row_k3 = ttk.Frame(self.frame_kepala)
        row_k3.pack(fill="x", pady=1)
        ttk.Label(row_k3, text="Geser X (◄ ►):").pack(side="left")
        self.lbl_offx_kepala = ttk.Label(row_k3, text=self._fmt_offset(self.offx_kepala_var.get()), width=8, anchor="e")
        self.lbl_offx_kepala.pack(side="right")
        ttk.Scale(
            row_k3,
            from_=-8.0,
            to=8.0,
            variable=self.offx_kepala_var,
            command=lambda val: self._on_slider_changed("kepala", "offx", val)
        ).pack(side="left", fill="x", expand=True, padx=6)

        row_k4 = ttk.Frame(self.frame_kepala)
        row_k4.pack(fill="x", pady=1)
        ttk.Label(row_k4, text="Geser Y (▲ ▼):").pack(side="left")
        self.lbl_offy_kepala = ttk.Label(row_k4, text=self._fmt_offset(self.offy_kepala_var.get()), width=8, anchor="e")
        self.lbl_offy_kepala.pack(side="right")
        ttk.Scale(
            row_k4,
            from_=-5.0,
            to=5.0,
            variable=self.offy_kepala_var,
            command=lambda val: self._on_slider_changed("kepala", "offy", val)
        ).pack(side="left", fill="x", expand=True, padx=6)

        # B. Tanda Tangan Guru
        frame_guru = ttk.LabelFrame(left_frame, text=" 2. Tanda Tangan Guru / Penyusun ", padding=8)
        frame_guru.pack(fill="x", pady=5)

        ttk.Checkbutton(
            frame_guru,
            text="Aktifkan Sisipkan Tanda Tangan Guru",
            variable=self.enable_guru_var,
            command=self._on_control_changed
        ).pack(anchor="w", pady=(0, 2))

        row_g1 = ttk.Frame(frame_guru)
        row_g1.pack(fill="x", pady=2)
        ttk.Label(row_g1, text="Berkas:").pack(side="left")
        ttk.Button(row_g1, text="Pilih Gambar...", command=self._browse_guru).pack(side="right")
        ttk.Entry(row_g1, textvariable=self.path_guru_var, state="readonly").pack(side="left", fill="x", expand=True, padx=4)

        row_g2 = ttk.Frame(frame_guru)
        row_g2.pack(fill="x", pady=1)
        ttk.Label(row_g2, text="Lebar:").pack(side="left")
        self.lbl_width_guru = ttk.Label(row_g2, text=f"{self.width_guru_var.get():.1f} cm", width=8, anchor="e")
        self.lbl_width_guru.pack(side="right")
        self.slider_guru = ttk.Scale(
            row_g2,
            from_=2.0,
            to=6.5,
            variable=self.width_guru_var,
            command=lambda val: self._on_slider_changed("guru", "width", val)
        )
        self.slider_guru.pack(side="left", fill="x", expand=True, padx=6)

        row_g3 = ttk.Frame(frame_guru)
        row_g3.pack(fill="x", pady=1)
        ttk.Label(row_g3, text="Geser X (◄ ►):").pack(side="left")
        self.lbl_offx_guru = ttk.Label(row_g3, text=self._fmt_offset(self.offx_guru_var.get()), width=8, anchor="e")
        self.lbl_offx_guru.pack(side="right")
        ttk.Scale(
            row_g3,
            from_=-8.0,
            to=8.0,
            variable=self.offx_guru_var,
            command=lambda val: self._on_slider_changed("guru", "offx", val)
        ).pack(side="left", fill="x", expand=True, padx=6)

        row_g4 = ttk.Frame(frame_guru)
        row_g4.pack(fill="x", pady=1)
        ttk.Label(row_g4, text="Geser Y (▲ ▼):").pack(side="left")
        self.lbl_offy_guru = ttk.Label(row_g4, text=self._fmt_offset(self.offy_guru_var.get()), width=8, anchor="e")
        self.lbl_offy_guru.pack(side="right")
        ttk.Scale(
            row_g4,
            from_=-5.0,
            to=5.0,
            variable=self.offy_guru_var,
            command=lambda val: self._on_slider_changed("guru", "offy", val)
        ).pack(side="left", fill="x", expand=True, padx=6)

        # C. Perataan & Posisi Layer
        frame_opt = ttk.LabelFrame(left_frame, text=" 3. Posisi Tanda Tangan & Perataan ", padding=8)
        frame_opt.pack(fill="x", pady=5)

        row_opt1 = ttk.Frame(frame_opt)
        row_opt1.pack(fill="x", pady=1)
        ttk.Label(row_opt1, text="Perataan:").pack(side="left", padx=(0, 8))
        for align_label, align_val in [("Tengah", "CENTER"), ("Kiri", "LEFT"), ("Kanan", "RIGHT")]:
            ttk.Radiobutton(
                row_opt1,
                text=align_label,
                value=align_val,
                variable=self.alignment_var,
                command=self._on_control_changed
            ).pack(side="left", padx=4)

        row_opt2 = ttk.Frame(frame_opt)
        row_opt2.pack(fill="x", pady=(4, 1))
        ttk.Checkbutton(
            row_opt2,
            text="Posisi Di Belakang Teks (Behind Text - Teks Nama Tetap Jelas)",
            variable=self.behind_text_var,
            command=self._on_control_changed
        ).pack(side="left")

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

    @staticmethod
    def _fmt_offset(v: float) -> str:
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.1f} cm"

    # =========================================================================
    # EVENT HANDLERS & ORIENTATION SWITCHING
    # =========================================================================
    def _switch_orientation(self, target_mode: str):
        if target_mode == self.current_orientation:
            return

        # 1. Simpan nilai aktif saat ini ke dictionary profil
        active_dict = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
        active_dict["width_kepala"] = round(self.width_kepala_var.get(), 1)
        active_dict["offx_kepala"] = round(self.offx_kepala_var.get(), 1)
        active_dict["offy_kepala"] = round(self.offy_kepala_var.get(), 1)
        active_dict["width_guru"] = round(self.width_guru_var.get(), 1)
        active_dict["offx_guru"] = round(self.offx_guru_var.get(), 1)
        active_dict["offy_guru"] = round(self.offy_guru_var.get(), 1)

        # 2. Beralih mode orientasi
        self.current_orientation = target_mode
        new_dict = self.portrait_geo if target_mode == "PORTRAIT" else self.landscape_geo

        # 3. Muat nilai profil ke variabel Tk
        self.width_kepala_var.set(new_dict["width_kepala"])
        self.offx_kepala_var.set(new_dict["offx_kepala"])
        self.offy_kepala_var.set(new_dict["offy_kepala"])
        self.width_guru_var.set(new_dict["width_guru"])
        self.offx_guru_var.set(new_dict["offx_guru"])
        self.offy_guru_var.set(new_dict["offy_guru"])

        # 4. Perbarui label slider
        self.lbl_width_kepala.config(text=f"{new_dict['width_kepala']:.1f} cm")
        self.lbl_offx_kepala.config(text=self._fmt_offset(new_dict['offx_kepala']))
        self.lbl_offy_kepala.config(text=self._fmt_offset(new_dict['offy_kepala']))
        self.lbl_width_guru.config(text=f"{new_dict['width_guru']:.1f} cm")
        self.lbl_offx_guru.config(text=self._fmt_offset(new_dict['offx_guru']))
        self.lbl_offy_guru.config(text=self._fmt_offset(new_dict['offy_guru']))

        # 5. Perbarui gaya tombol tab
        if target_mode == "PORTRAIT":
            self.btn_tab_portrait.config(bg="#0066cc", fg="#ffffff", font=("Segoe UI", 9, "bold"))
            self.btn_tab_landscape.config(bg="#f0f0f0", fg="#222222", font=("Segoe UI", 9))
            self.frame_land_tools.pack_forget()
        else:
            self.btn_tab_landscape.config(bg="#0066cc", fg="#ffffff", font=("Segoe UI", 9, "bold"))
            self.btn_tab_portrait.config(bg="#f0f0f0", fg="#222222", font=("Segoe UI", 9))
            self.frame_land_tools.pack(fill="x", pady=(0, 6), before=self.frame_kepala)

        self._update_preview()

    def _copy_from_portrait(self):
        """Menyalin nilai konfigurasi potrait ke lanskap."""
        self.landscape_geo["width_kepala"] = self.portrait_geo["width_kepala"]
        self.landscape_geo["offx_kepala"] = self.portrait_geo["offx_kepala"]
        self.landscape_geo["offy_kepala"] = self.portrait_geo["offy_kepala"]
        self.landscape_geo["width_guru"] = self.portrait_geo["width_guru"]
        self.landscape_geo["offx_guru"] = self.portrait_geo["offx_guru"]
        self.landscape_geo["offy_guru"] = self.portrait_geo["offy_guru"]

        if self.current_orientation == "LANDSCAPE":
            self._switch_orientation("PORTRAIT")
            self._switch_orientation("LANDSCAPE")

    def _auto_compensate_landscape(self):
        """Menghitung kompensasi otomatis untuk kolom tabel lanskap yang lebih lebar."""
        self.landscape_geo["width_kepala"] = self.portrait_geo["width_kepala"]
        self.landscape_geo["offx_kepala"] = round(self.portrait_geo["offx_kepala"] - 2.3, 1)
        self.landscape_geo["offy_kepala"] = self.portrait_geo["offy_kepala"]
        self.landscape_geo["width_guru"] = self.portrait_geo["width_guru"]
        self.landscape_geo["offx_guru"] = round(self.portrait_geo["offx_guru"] - 2.3, 1)
        self.landscape_geo["offy_guru"] = self.portrait_geo["offy_guru"]

        if self.current_orientation == "LANDSCAPE":
            self._switch_orientation("PORTRAIT")
            self._switch_orientation("LANDSCAPE")

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

    def _on_slider_changed(self, target: str, param: str, val: str):
        v = float(val)
        if target == "kepala":
            if param == "width":
                self.lbl_width_kepala.config(text=f"{v:.1f} cm")
            elif param == "offx":
                self.lbl_offx_kepala.config(text=self._fmt_offset(v))
            elif param == "offy":
                self.lbl_offy_kepala.config(text=self._fmt_offset(v))
        else:
            if param == "width":
                self.lbl_width_guru.config(text=f"{v:.1f} cm")
            elif param == "offx":
                self.lbl_offx_guru.config(text=self._fmt_offset(v))
            elif param == "offy":
                self.lbl_offy_guru.config(text=self._fmt_offset(v))
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
            w, h = 500, 450

        # Skala konversi: 1 cm di dunia nyata ~ 28 pixel di kanvas layar
        px_per_cm = 28.0
        is_land = (self.current_orientation == "LANDSCAPE")

        # Indikator mode orientasi aktif di kanvas
        mode_text = "Simulasi: 📑 Dokumen Lanskap (Lebar Kolom ~13.1 cm)" if is_land else "Simulasi: 📄 Dokumen Potrait (Lebar Kolom ~8.5 cm)"
        mode_color = "#0055aa" if is_land else "#555555"
        self.canvas.create_text(w / 2, 14, text=mode_text, font=("Segoe UI", 9, "bold"), fill=mode_color)

        # Koordinat kolom Kiri (Kepala) dan Kanan (Guru)
        col_w = w / 2.0
        x_kepala_center = col_w * 0.5
        x_guru_center = col_w * 1.5

        # Garis batas vertikal samar pemisah 2 kolom tabel Word
        self.canvas.create_line(col_w, 28, col_w, h - 15, fill="#eeeeee", dash=(4, 4))

        # Y anchor dasar baris Nama Terang
        y_name_k = 195
        y_name_g = 195

        # Pergeseran dasar jika orientasi Lanskap (kolom Word lebih lebar ~4.6cm -> centering geser ke kanan ~2.3cm)
        base_shift_px = int(2.3 * px_per_cm) if is_land else 0

        # Hitung posisi gambar Kepala
        k_path = self.path_kepala_var.get().strip()
        k_enabled = self.enable_kepala_var.get()
        k_width_cm = self.width_kepala_var.get()
        k_target_px = int(k_width_cm * px_per_cm)
        base_x_k = self._calc_align_x(x_kepala_center, col_w * 0.1, col_w * 0.9, k_target_px)
        x_img_k = base_x_k + base_shift_px + int(self.offx_kepala_var.get() * px_per_cm)
        y_img_k = (y_name_k - 35) + int(self.offy_kepala_var.get() * px_per_cm)

        # Hitung posisi gambar Guru
        g_path = self.path_guru_var.get().strip()
        g_enabled = self.enable_guru_var.get()
        g_width_cm = self.width_guru_var.get()
        g_target_px = int(g_width_cm * px_per_cm)
        base_x_g = self._calc_align_x(x_guru_center, col_w + col_w * 0.1, col_w + col_w * 0.9, g_target_px)
        x_img_g = base_x_g + base_shift_px + int(self.offx_guru_var.get() * px_per_cm)
        y_img_g = (y_name_g - 35) + int(self.offy_guru_var.get() * px_per_cm)

        behind = self.behind_text_var.get()

        def draw_images():
            # Gambar TTD Kepala
            if k_enabled and k_path and os.path.isfile(k_path):
                try:
                    pil_img = Image.open(k_path)
                    aspect = pil_img.height / max(1, pil_img.width)
                    k_height_px = max(20, int(k_target_px * aspect))
                    resized = pil_img.resize((k_target_px, k_height_px), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(resized)
                    self._photo_cache["kepala"] = tk_img
                    self.canvas.create_image(x_img_k, y_img_k, image=tk_img, anchor="center")
                except Exception:
                    self.canvas.create_text(x_img_k, y_img_k, text="[Gambar Error]", fill="#cc0000")
            else:
                self.canvas.create_rectangle(
                    x_img_k - k_target_px // 2, y_img_k - 25,
                    x_img_k + k_target_px // 2, y_img_k + 25,
                    outline="#dddddd", fill="#fafafa", dash=(2, 2)
                )
                desc = "(Tanda Tangan Kepala)" if k_enabled else "(Ruang TTD Kosong)"
                self.canvas.create_text(x_img_k, y_img_k, text=desc, font=("Segoe UI", 8), fill="#aaaaaa")

            # Gambar TTD Guru
            if g_enabled and g_path and os.path.isfile(g_path):
                try:
                    pil_g = Image.open(g_path)
                    aspect_g = pil_g.height / max(1, pil_g.width)
                    g_height_px = max(20, int(g_target_px * aspect_g))
                    resized_g = pil_g.resize((g_target_px, g_height_px), Image.Resampling.LANCZOS)
                    tk_img_g = ImageTk.PhotoImage(resized_g)
                    self._photo_cache["guru"] = tk_img_g
                    self.canvas.create_image(x_img_g, y_img_g, image=tk_img_g, anchor="center")
                except Exception:
                    self.canvas.create_text(x_img_g, y_img_g, text="[Gambar Error]", fill="#cc0000")
            else:
                self.canvas.create_rectangle(
                    x_img_g - g_target_px // 2, y_img_g - 25,
                    x_img_g + g_target_px // 2, y_img_g + 25,
                    outline="#dddddd", fill="#fafafa", dash=(2, 2)
                )
                desc_g = "(Tanda Tangan Guru)" if g_enabled else "(Ruang TTD Kosong)"
                self.canvas.create_text(x_img_g, y_img_g, text=desc_g, font=("Segoe UI", 8), fill="#aaaaaa")

        def draw_texts():
            # Teks Kepala
            self.canvas.create_text(x_kepala_center, 48, text="Mengetahui,", font=("Segoe UI", 9), fill="#333333")
            self.canvas.create_text(x_kepala_center, 68, text="Kepala Madrasah", font=("Segoe UI", 9, "bold"), fill="#111111")
            self.canvas.create_text(x_kepala_center, y_name_k, text="( Nama Kepala Madrasah, M.Pd )", font=("Segoe UI", 9, "bold", "underline"), fill="#111111")
            self.canvas.create_text(x_kepala_center, y_name_k + 20, text="NIP. 197001012000011001", font=("Segoe UI", 9), fill="#333333")

            # Teks Guru
            self.canvas.create_text(x_guru_center, 48, text="Kota Contoh, 10 Juli 2026", font=("Segoe UI", 9), fill="#333333")
            self.canvas.create_text(x_guru_center, 68, text="Guru Mata Pelajaran", font=("Segoe UI", 9, "bold"), fill="#111111")
            self.canvas.create_text(x_guru_center, y_name_g, text="( Nama Guru Penyusun, S.Pd )", font=("Segoe UI", 9, "bold", "underline"), fill="#111111")
            self.canvas.create_text(x_guru_center, y_name_g + 20, text="NIP. 199001012020012002", font=("Segoe UI", 9), fill="#333333")

        # Jika Behind Text aktif, gambar ditaruh di layer belakang (digambar duluan)
        if behind:
            draw_images()
            draw_texts()
        else:
            draw_texts()
            draw_images()

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
        self.enable_guru_var.set(False)
        self.path_guru_var.set("")
        self.alignment_var.set("CENTER")
        self.behind_text_var.set(True)
        self.spacing_var.set(2)

        self.portrait_geo = {
            "width_kepala": 3.5, "offx_kepala": 0.0, "offy_kepala": 0.0,
            "width_guru": 3.5, "offx_guru": 0.0, "offy_guru": 0.0
        }
        self.landscape_geo = {
            "width_kepala": 3.5, "offx_kepala": -2.3, "offy_kepala": 0.0,
            "width_guru": 3.5, "offx_guru": -2.3, "offy_guru": 0.0
        }

        active = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
        self.width_kepala_var.set(active["width_kepala"])
        self.offx_kepala_var.set(active["offx_kepala"])
        self.offy_kepala_var.set(active["offy_kepala"])
        self.width_guru_var.set(active["width_guru"])
        self.offx_guru_var.set(active["offx_guru"])
        self.offy_guru_var.set(active["offy_guru"])

        self.lbl_width_kepala.config(text=f"{active['width_kepala']:.1f} cm")
        self.lbl_offx_kepala.config(text=self._fmt_offset(active["offx_kepala"]))
        self.lbl_offy_kepala.config(text=self._fmt_offset(active["offy_kepala"]))
        self.lbl_width_guru.config(text=f"{active['width_guru']:.1f} cm")
        self.lbl_offx_guru.config(text=self._fmt_offset(active["offx_guru"]))
        self.lbl_offy_guru.config(text=self._fmt_offset(active["offy_guru"]))

        self._update_preview()

    def _save_settings(self):
        # 1. Pastikan nilai aktif saat ini tersimpan ke profil yang relevan
        active_dict = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
        active_dict["width_kepala"] = round(self.width_kepala_var.get(), 1)
        active_dict["offx_kepala"] = round(self.offx_kepala_var.get(), 1)
        active_dict["offy_kepala"] = round(self.offy_kepala_var.get(), 1)
        active_dict["width_guru"] = round(self.width_guru_var.get(), 1)
        active_dict["offx_guru"] = round(self.offx_guru_var.get(), 1)
        active_dict["offy_guru"] = round(self.offy_guru_var.get(), 1)

        new_settings = dict(self.settings)
        new_settings.update({
            "enabled_kepala": self.enable_kepala_var.get(),
            "kepala_image_path": self.path_kepala_var.get().strip(),
            "kepala_width_cm": self.portrait_geo["width_kepala"],
            "offset_x_kepala_cm": self.portrait_geo["offx_kepala"],
            "offset_y_kepala_cm": self.portrait_geo["offy_kepala"],
            "enabled_guru": self.enable_guru_var.get(),
            "guru_image_path": self.path_guru_var.get().strip(),
            "guru_width_cm": self.portrait_geo["width_guru"],
            "offset_x_guru_cm": self.portrait_geo["offx_guru"],
            "offset_y_guru_cm": self.portrait_geo["offy_guru"],
            "alignment": self.alignment_var.get(),
            "behind_text": self.behind_text_var.get(),
            "spacing_before_pt": 2,
            "spacing_after_pt": 2,
            "landscape": {
                "kepala_width_cm": self.landscape_geo["width_kepala"],
                "offset_x_kepala_cm": self.landscape_geo["offx_kepala"],
                "offset_y_kepala_cm": self.landscape_geo["offy_kepala"],
                "guru_width_cm": self.landscape_geo["width_guru"],
                "offset_x_guru_cm": self.landscape_geo["offx_guru"],
                "offset_y_guru_cm": self.landscape_geo["offy_guru"],
            }
        })
        save_signature_settings(new_settings)
        if self.on_save_callback:
            self.on_save_callback(new_settings)
        messagebox.showinfo("Berhasil", "Pengaturan tanda tangan Potrait & Lanskap berhasil disimpan!")
        self.destroy()
