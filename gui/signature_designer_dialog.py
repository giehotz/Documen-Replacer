"""
Komponen GUI: Jendela Desain & Pengatur Tanda Tangan Digital (Signature Designer).
Menyediakan:
- Kontrol slider ukuran (cm), pemilihan berkas gambar, perataan, dan spasi
- Interaksi Drag-and-Drop langsung pada kanvas pratinjau (geser posisi & tarik sudut untuk ubah ukuran)
- Pemisahan profil konfigurasi antara Dokumen Potrait (RPP) dan Dokumen Lanskap (Silabus/Promes)
- Pustaka Tanda Tangan & Stempel Bernama (Named Signature Library di folder signatures/)
- Dukungan 3 slot gambar terpisah: Tanda Tangan Kepala, Tanda Tangan Guru, dan Stempel Resmi Sekolah
- Fitur Inspeksi & Prediksi Tata Letak Dokumen Sampel (Signature Placement Prediction)
- Simulasi visual Kanvas real-time blok tanda tangan Microsoft Word
- Penyimpanan pengaturan permanen ke config/signature_settings.json
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Any, Optional, List
from PIL import Image, ImageTk

from core.signature_image_service import (
    load_signature_settings,
    save_signature_settings,
    DEFAULT_SETTINGS,
    load_signature_library,
    add_signature_item,
    delete_signature_item,
    get_signatures_by_category,
    predict_signature_layout,
)


class SignatureDesignerDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, on_save_callback=None):
        super().__init__(parent)
        self.title("Pengatur Tanda Tangan Digital, Stempel & Presisi Penempatan (Potrait & Lanskap)")
        self.geometry("1100x750")
        self.minsize(980, 680)
        self.transient(parent)
        self.grab_set()

        self.on_save_callback = on_save_callback
        self.settings: Dict[str, Any] = load_signature_settings()

        # Cache untuk referensi objek PhotoImage Tkinter agar tidak di-garbage collect
        self._photo_cache = {}

        self._init_variables()
        self._build_ui()
        self._refresh_library_comboboxes()
        self._update_preview()

    def _init_variables(self):
        self.current_orientation = "PORTRAIT"

        # Variabel Drag & Drop Interaktif Kanvas
        self._selected_target = None   # 'kepala' | 'guru' | 'stempel' | None
        self._drag_mode = None         # 'move' | 'resize' | None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_start_offx = 0.0
        self._drag_start_offy = 0.0
        self._drag_start_width = 3.5
        self._element_boxes = {}

        # 1. Tanda Tangan Kepala
        self.enable_kepala_var = tk.BooleanVar(value=self.settings.get("enabled_kepala", False))
        self.path_kepala_var = tk.StringVar(value=self.settings.get("kepala_image_path", ""))
        self.name_kepala_var = tk.StringVar(value=self.settings.get("kepala_name", ""))

        # 2. Tanda Tangan Guru
        self.enable_guru_var = tk.BooleanVar(value=self.settings.get("enabled_guru", False))
        self.path_guru_var = tk.StringVar(value=self.settings.get("guru_image_path", ""))
        self.name_guru_var = tk.StringVar(value=self.settings.get("guru_name", ""))

        # 3. Stempel Resmi Sekolah / Madrasah
        self.enable_stempel_var = tk.BooleanVar(value=self.settings.get("enabled_stempel", False))
        self.path_stempel_var = tk.StringVar(value=self.settings.get("stempel_image_path", ""))
        self.name_stempel_var = tk.StringVar(value=self.settings.get("stempel_name", ""))

        # Pengaturan Umum
        self.alignment_var = tk.StringVar(value=self.settings.get("alignment", "CENTER"))
        self.behind_text_var = tk.BooleanVar(value=bool(self.settings.get("behind_text", True)))
        self.spacing_var = tk.IntVar(value=int(self.settings.get("spacing_before_pt", 2)))

        # Profil Geometri Potrait
        self.portrait_geo = {
            "width_kepala": float(self.settings.get("kepala_width_cm", 3.5)),
            "offx_kepala": float(self.settings.get("offset_x_kepala_cm", 0.0)),
            "offy_kepala": float(self.settings.get("offset_y_kepala_cm", 0.0)),
            "width_guru": float(self.settings.get("guru_width_cm", 3.5)),
            "offx_guru": float(self.settings.get("offset_x_guru_cm", 0.0)),
            "offy_guru": float(self.settings.get("offset_y_guru_cm", 0.0)),
            "width_stempel": float(self.settings.get("stempel_width_cm", 3.5)),
            "offx_stempel": float(self.settings.get("offset_x_stempel_cm", -1.5)),
            "offy_stempel": float(self.settings.get("offset_y_stempel_cm", 0.0)),
        }

        # Profil Geometri Lanskap
        land_cfg = self.settings.get("landscape")
        if isinstance(land_cfg, dict):
            self.landscape_geo = {
                "width_kepala": float(land_cfg.get("kepala_width_cm", self.portrait_geo["width_kepala"])),
                "offx_kepala": float(land_cfg.get("offset_x_kepala_cm", round(self.portrait_geo["offx_kepala"] - 2.3, 1))),
                "offy_kepala": float(land_cfg.get("offset_y_kepala_cm", self.portrait_geo["offy_kepala"])),
                "width_guru": float(land_cfg.get("guru_width_cm", self.portrait_geo["width_guru"])),
                "offx_guru": float(land_cfg.get("offset_x_guru_cm", round(self.portrait_geo["offx_guru"] - 2.3, 1))),
                "offy_guru": float(land_cfg.get("offset_y_guru_cm", self.portrait_geo["offy_guru"])),
                "width_stempel": float(land_cfg.get("stempel_width_cm", self.portrait_geo["width_stempel"])),
                "offx_stempel": float(land_cfg.get("offset_x_stempel_cm", round(self.portrait_geo["offx_stempel"] - 2.3, 1))),
                "offy_stempel": float(land_cfg.get("offset_y_stempel_cm", self.portrait_geo["offy_stempel"])),
            }
        else:
            self.landscape_geo = {
                "width_kepala": self.portrait_geo["width_kepala"],
                "offx_kepala": round(self.portrait_geo["offx_kepala"] - 2.3, 1),
                "offy_kepala": self.portrait_geo["offy_kepala"],
                "width_guru": self.portrait_geo["width_guru"],
                "offx_guru": round(self.portrait_geo["offx_guru"] - 2.3, 1),
                "offy_guru": self.portrait_geo["offy_guru"],
                "width_stempel": self.portrait_geo["width_stempel"],
                "offx_stempel": round(self.portrait_geo["offx_stempel"] - 2.3, 1),
                "offy_stempel": self.portrait_geo["offy_stempel"],
            }

        # Variabel aktif yang terikat ke slider GUI
        self.width_kepala_var = tk.DoubleVar(value=self.portrait_geo["width_kepala"])
        self.offx_kepala_var = tk.DoubleVar(value=self.portrait_geo["offx_kepala"])
        self.offy_kepala_var = tk.DoubleVar(value=self.portrait_geo["offy_kepala"])

        self.width_guru_var = tk.DoubleVar(value=self.portrait_geo["width_guru"])
        self.offx_guru_var = tk.DoubleVar(value=self.portrait_geo["offx_guru"])
        self.offy_guru_var = tk.DoubleVar(value=self.portrait_geo["offy_guru"])

        self.width_stempel_var = tk.DoubleVar(value=self.portrait_geo["width_stempel"])
        self.offx_stempel_var = tk.DoubleVar(value=self.portrait_geo["offx_stempel"])
        self.offy_stempel_var = tk.DoubleVar(value=self.portrait_geo["offy_stempel"])

    def _build_ui(self):
        # 1. Header
        header = ttk.Frame(self, padding=(14, 8))
        header.pack(fill="x")

        head_left = ttk.Frame(header)
        head_left.pack(side="left", fill="x", expand=True)

        ttk.Label(
            head_left,
            text="Pengatur Posisi, Ukuran Tanda Tangan & Stempel Resmi (Potrait & Lanskap)",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        ttk.Label(
            head_left,
            text="Tanda tangan & stempel dapat digeser (drag) atau ditarik sudutnya langsung pada pratinjau dokumen, atau menggunakan slider presisi.",
            foreground="#555555"
        ).pack(anchor="w", pady=(2, 0))

        head_right = ttk.Frame(header)
        head_right.pack(side="right")
        ttk.Button(
            head_right,
            text="🔍 Uji & Deteksi Dokumen Sampel...",
            command=self._test_sample_document
        ).pack(side="right", padx=(6, 0))

        # 2. Main Container (Split: Kiri Kontrol Ber-scroll, Kanan Kanvas)
        container = ttk.Frame(self, padding=(12, 4))
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=4, minsize=460)
        container.columnconfigure(1, weight=5, minsize=460)
        container.rowconfigure(0, weight=1)

        # =====================================================================
        # PANEL KIRI: KONTROL DENGAN SCROLLBAR
        # =====================================================================
        left_container = ttk.Frame(container)
        left_container.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_container.rowconfigure(0, weight=1)
        left_container.columnconfigure(0, weight=1)

        scroll_canvas = tk.Canvas(left_container, highlightthickness=0)
        v_scroll = ttk.Scrollbar(left_container, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=v_scroll.set)

        scroll_canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        left_frame = ttk.Frame(scroll_canvas)
        canvas_window = scroll_canvas.create_window((0, 0), window=left_frame, anchor="nw")

        def _on_frame_configure(event):
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))

        def _on_canvas_configure(event):
            scroll_canvas.itemconfig(canvas_window, width=event.width)

        left_frame.bind("<Configure>", _on_frame_configure)
        scroll_canvas.bind("<Configure>", _on_canvas_configure)

        # Tab Pemilih Orientasi Halaman
        tab_frame = ttk.LabelFrame(left_frame, text=" Profil Orientasi Aktif ", padding=5)
        tab_frame.pack(fill="x", pady=(0, 4))

        tab_row = ttk.Frame(tab_frame)
        tab_row.pack(fill="x", pady=1)

        self.btn_tab_portrait = tk.Button(
            tab_row,
            text="📄 Dokumen Potrait (RPP)",
            font=("Segoe UI", 9, "bold"),
            bg="#0066cc",
            fg="#ffffff",
            relief="groove",
            command=lambda: self._switch_orientation("PORTRAIT")
        )
        self.btn_tab_portrait.pack(side="left", fill="x", expand=True, padx=(0, 2), ipady=3)

        self.btn_tab_landscape = tk.Button(
            tab_row,
            text="📑 Dokumen Lanskap (Silabus / Promes)",
            font=("Segoe UI", 9),
            bg="#f0f0f0",
            fg="#222222",
            relief="groove",
            command=lambda: self._switch_orientation("LANDSCAPE")
        )
        self.btn_tab_landscape.pack(side="left", fill="x", expand=True, padx=(2, 0), ipady=3)

        # Bilah Alat Khusus Lanskap
        self.frame_land_tools = ttk.Frame(left_frame, padding=(2, 2))
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

        # =====================================================================
        # SEKSI 1: TANDA TANGAN KEPALA MADRASAH
        # =====================================================================
        self.frame_kepala = ttk.LabelFrame(left_frame, text=" 1. Tanda Tangan Kepala Madrasah / Sekolah ", padding=6)
        self.frame_kepala.pack(fill="x", pady=(0, 4))

        ttk.Checkbutton(
            self.frame_kepala,
            text="Aktifkan Sisipkan Tanda Tangan Kepala",
            variable=self.enable_kepala_var,
            command=self._on_control_changed
        ).pack(anchor="w", pady=(0, 2))

        # Pilihan Pustaka
        row_k_lib = ttk.Frame(self.frame_kepala)
        row_k_lib.pack(fill="x", pady=2)
        ttk.Label(row_k_lib, text="Pustaka Simpanan:").pack(side="left")
        self.cb_kepala = ttk.Combobox(row_k_lib, state="readonly", width=22)
        self.cb_kepala.pack(side="left", fill="x", expand=True, padx=(4, 4))
        self.cb_kepala.bind("<<ComboboxSelected>>", lambda e: self._on_library_selected("kepala"))
        ttk.Button(row_k_lib, text="+ Tambah", width=8, command=lambda: self._add_signature_dialog("kepala")).pack(side="left", padx=2)
        ttk.Button(row_k_lib, text="🗑 Hapus", width=7, command=lambda: self._delete_signature_dialog("kepala")).pack(side="left", padx=2)

        # Berkas Fisik
        row_k1 = ttk.Frame(self.frame_kepala)
        row_k1.pack(fill="x", pady=2)
        ttk.Label(row_k1, text="Berkas:").pack(side="left")
        ttk.Button(row_k1, text="Pilih Berkas Lain...", command=self._browse_kepala).pack(side="right")
        ttk.Entry(row_k1, textvariable=self.path_kepala_var, state="readonly").pack(side="left", fill="x", expand=True, padx=4)

        # Sliders Kepala
        self._build_slider_row(self.frame_kepala, "Lebar:", "kepala", "width", self.width_kepala_var, 2.0, 6.5)
        self._build_slider_row(self.frame_kepala, "Geser X (◄ ►):", "kepala", "offx", self.offx_kepala_var, -8.0, 8.0)
        self._build_slider_row(self.frame_kepala, "Geser Y (▲ ▼):", "kepala", "offy", self.offy_kepala_var, -5.0, 5.0)

        # =====================================================================
        # SEKSI 2: TANDA TANGAN GURU / PENYUSUN
        # =====================================================================
        frame_guru = ttk.LabelFrame(left_frame, text=" 2. Tanda Tangan Guru / Penyusun ", padding=6)
        frame_guru.pack(fill="x", pady=4)

        ttk.Checkbutton(
            frame_guru,
            text="Aktifkan Sisipkan Tanda Tangan Guru",
            variable=self.enable_guru_var,
            command=self._on_control_changed
        ).pack(anchor="w", pady=(0, 2))

        # Pilihan Pustaka
        row_g_lib = ttk.Frame(frame_guru)
        row_g_lib.pack(fill="x", pady=2)
        ttk.Label(row_g_lib, text="Pustaka Simpanan:").pack(side="left")
        self.cb_guru = ttk.Combobox(row_g_lib, state="readonly", width=22)
        self.cb_guru.pack(side="left", fill="x", expand=True, padx=(4, 4))
        self.cb_guru.bind("<<ComboboxSelected>>", lambda e: self._on_library_selected("guru"))
        ttk.Button(row_g_lib, text="+ Tambah", width=8, command=lambda: self._add_signature_dialog("guru")).pack(side="left", padx=2)
        ttk.Button(row_g_lib, text="🗑 Hapus", width=7, command=lambda: self._delete_signature_dialog("guru")).pack(side="left", padx=2)

        # Berkas Fisik
        row_g1 = ttk.Frame(frame_guru)
        row_g1.pack(fill="x", pady=2)
        ttk.Label(row_g1, text="Berkas:").pack(side="left")
        ttk.Button(row_g1, text="Pilih Berkas Lain...", command=self._browse_guru).pack(side="right")
        ttk.Entry(row_g1, textvariable=self.path_guru_var, state="readonly").pack(side="left", fill="x", expand=True, padx=4)

        # Sliders Guru
        self._build_slider_row(frame_guru, "Lebar:", "guru", "width", self.width_guru_var, 2.0, 6.5)
        self._build_slider_row(frame_guru, "Geser X (◄ ►):", "guru", "offx", self.offx_guru_var, -8.0, 8.0)
        self._build_slider_row(frame_guru, "Geser Y (▲ ▼):", "guru", "offy", self.offy_guru_var, -5.0, 5.0)

        # =====================================================================
        # SEKSI 3: STEMPEL RESMI SEKOLAH / MADRASAH
        # =====================================================================
        frame_stempel = ttk.LabelFrame(left_frame, text=" 3. Stempel Resmi Sekolah / Madrasah (Zona Kepala) ", padding=6)
        frame_stempel.pack(fill="x", pady=4)

        ttk.Checkbutton(
            frame_stempel,
            text="Aktifkan Sisipkan Stempel Resmi",
            variable=self.enable_stempel_var,
            command=self._on_control_changed
        ).pack(anchor="w", pady=(0, 2))

        # Pilihan Pustaka
        row_s_lib = ttk.Frame(frame_stempel)
        row_s_lib.pack(fill="x", pady=2)
        ttk.Label(row_s_lib, text="Pustaka Simpanan:").pack(side="left")
        self.cb_stempel = ttk.Combobox(row_s_lib, state="readonly", width=22)
        self.cb_stempel.pack(side="left", fill="x", expand=True, padx=(4, 4))
        self.cb_stempel.bind("<<ComboboxSelected>>", lambda e: self._on_library_selected("stempel"))
        ttk.Button(row_s_lib, text="+ Tambah", width=8, command=lambda: self._add_signature_dialog("stempel")).pack(side="left", padx=2)
        ttk.Button(row_s_lib, text="🗑 Hapus", width=7, command=lambda: self._delete_signature_dialog("stempel")).pack(side="left", padx=2)

        # Berkas Fisik
        row_s1 = ttk.Frame(frame_stempel)
        row_s1.pack(fill="x", pady=2)
        ttk.Label(row_s1, text="Berkas:").pack(side="left")
        ttk.Button(row_s1, text="Pilih Berkas Lain...", command=self._browse_stempel).pack(side="right")
        ttk.Entry(row_s1, textvariable=self.path_stempel_var, state="readonly").pack(side="left", fill="x", expand=True, padx=4)

        # Sliders Stempel
        self._build_slider_row(frame_stempel, "Lebar:", "stempel", "width", self.width_stempel_var, 2.0, 6.5)
        self._build_slider_row(frame_stempel, "Geser X (◄ ►):", "stempel", "offx", self.offx_stempel_var, -8.0, 8.0)
        self._build_slider_row(frame_stempel, "Geser Y (▲ ▼):", "stempel", "offy", self.offy_stempel_var, -5.0, 5.0)

        # =====================================================================
        # SEKSI 4: PERATAAN & POSISI LAYER
        # =====================================================================
        frame_opt = ttk.LabelFrame(left_frame, text=" 4. Posisi Tanda Tangan & Perataan ", padding=6)
        frame_opt.pack(fill="x", pady=4)

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
        row_opt2.pack(fill="x", pady=(3, 1))
        ttk.Checkbutton(
            row_opt2,
            text="Posisi Di Belakang Teks (Behind Text - Teks Nama Tetap Terbaca)",
            variable=self.behind_text_var,
            command=self._on_control_changed
        ).pack(side="left")

        # =====================================================================
        # PANEL KANAN: KANVAS SIMULASI DENGAN DUKUNGAN DRAG-AND-DROP
        # =====================================================================
        right_frame = ttk.LabelFrame(container, text=" Simulasi Dokumen Word (Live Preview & Drag-and-Drop) ", padding=8)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(right_frame, bg="#ffffff", highlightthickness=1, highlightbackground="#cccccc")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Event Bindings Drag and Drop & Resize di Kanvas
        self.canvas.bind("<Configure>", lambda e: self._update_preview())
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)

        ttk.Label(
            right_frame,
            text="💡 Tips: Klik & seret (drag) gambar untuk menggeser posisi. Tarik kotak biru di sudut kanan-bawah atau Scroll Mouse untuk mengubah ukuran.",
            font=("Segoe UI", 8),
            foreground="#555555"
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # 3. Tombol Aksi Bawah
        bottom = ttk.Frame(self, padding=(14, 8))
        bottom.pack(fill="x")

        ttk.Button(bottom, text="Reset ke Bawaan", command=self._reset_defaults).pack(side="left")
        ttk.Button(bottom, text="Tutup / Batal", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(
            bottom,
            text="SIMPAN PENGATURAN TANDA TANGAN & STEMPEL",
            command=self._save_settings
        ).pack(side="right", ipady=3)

    def _build_slider_row(self, parent, label_text, target, param, var, from_, to_):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=label_text, width=12, anchor="w").pack(side="left")

        lbl_val = ttk.Label(row, text=f"{var.get():.1f} cm" if param == "width" else self._fmt_offset(var.get()), width=8, anchor="e")
        lbl_val.pack(side="right")

        attr_name = f"lbl_{param}_{target}"
        setattr(self, attr_name, lbl_val)

        ttk.Scale(
            row,
            from_=from_,
            to=to_,
            variable=var,
            command=lambda val: self._on_slider_changed(target, param, val)
        ).pack(side="left", fill="x", expand=True, padx=4)

    @staticmethod
    def _fmt_offset(v: float) -> str:
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.1f} cm"

    # =========================================================================
    # INTERAKSI DRAG & DROP SERTA RESIZE DI KANVAS
    # =========================================================================
    def _on_canvas_press(self, event):
        x, y = event.x, event.y

        # 1. Cek apakah klik pada sudut resize handle dari elemen yang sedang dipilih
        if self._selected_target:
            info = self._element_boxes.get(self._selected_target)
            if info and info["enabled"]:
                hx, hy = info["handle"]
                if abs(x - hx) <= 8 and abs(y - hy) <= 8:
                    self._drag_mode = "resize"
                    self._drag_start_x = x
                    self._drag_start_y = y
                    self._drag_start_width = getattr(self, f"width_{self._selected_target}_var").get()
                    return

        # 2. Cek apakah klik di dalam bounding box gambar
        # Urutan prioritas: target terpilih dulu, stempel (karena kecil/menimpa), kepala, guru
        candidates = []
        if self._selected_target:
            candidates.append(self._selected_target)
        for cat in ("stempel", "kepala", "guru"):
            if cat not in candidates:
                candidates.append(cat)

        clicked_target = None
        for cat in candidates:
            info = self._element_boxes.get(cat)
            if not info or not info["enabled"]:
                continue
            bx1, by1, bx2, by2 = info["bbox"]
            if bx1 <= x <= bx2 and by1 <= y <= by2:
                clicked_target = cat
                break

        if clicked_target:
            self._selected_target = clicked_target
            self._drag_mode = "move"
            self._drag_start_x = x
            self._drag_start_y = y
            self._drag_start_offx = getattr(self, f"offx_{clicked_target}_var").get()
            self._drag_start_offy = getattr(self, f"offy_{clicked_target}_var").get()
        else:
            self._selected_target = None
            self._drag_mode = None

        self._update_preview()

    def _on_canvas_drag(self, event):
        if not self._selected_target or not self._drag_mode:
            return

        tgt = self._selected_target
        px_per_cm = 28.0

        if self._drag_mode == "move":
            dx_px = event.x - self._drag_start_x
            dy_px = event.y - self._drag_start_y

            new_offx = round(self._drag_start_offx + (dx_px / px_per_cm), 1)
            new_offy = round(self._drag_start_offy + (dy_px / px_per_cm), 1)

            # Batasi dalam rentang slider [-8.0, 8.0] dan [-5.0, 5.0]
            new_offx = max(-8.0, min(8.0, new_offx))
            new_offy = max(-5.0, min(5.0, new_offy))

            getattr(self, f"offx_{tgt}_var").set(new_offx)
            getattr(self, f"offy_{tgt}_var").set(new_offy)

            lbl_x = getattr(self, f"lbl_offx_{tgt}", None)
            if lbl_x:
                lbl_x.config(text=self._fmt_offset(new_offx))
            lbl_y = getattr(self, f"lbl_offy_{tgt}", None)
            if lbl_y:
                lbl_y.config(text=self._fmt_offset(new_offy))

            active_geo = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
            active_geo[f"offx_{tgt}"] = new_offx
            active_geo[f"offy_{tgt}"] = new_offy

            self._update_preview()

        elif self._drag_mode == "resize":
            dx_px = event.x - self._drag_start_x
            new_w = round(self._drag_start_width + (dx_px * 2.0 / px_per_cm), 1)
            new_w = max(2.0, min(6.5, new_w))

            getattr(self, f"width_{tgt}_var").set(new_w)
            lbl_w = getattr(self, f"lbl_width_{tgt}", None)
            if lbl_w:
                lbl_w.config(text=f"{new_w:.1f} cm")

            active_geo = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
            active_geo[f"width_{tgt}"] = new_w

            self._update_preview()

    def _on_canvas_release(self, event):
        self._drag_mode = None
        self._update_preview()

    def _on_canvas_motion(self, event):
        x, y = event.x, event.y
        # Hover di handle resize
        if self._selected_target:
            info = self._element_boxes.get(self._selected_target)
            if info and info["enabled"]:
                hx, hy = info["handle"]
                if abs(x - hx) <= 8 and abs(y - hy) <= 8:
                    self.canvas.config(cursor="size_nw_se")
                    return

        # Hover di gambar
        for cat in ("stempel", "kepala", "guru"):
            info = self._element_boxes.get(cat)
            if info and info["enabled"]:
                bx1, by1, bx2, by2 = info["bbox"]
                if bx1 <= x <= bx2 and by1 <= y <= by2:
                    self.canvas.config(cursor="fleur")
                    return

        self.canvas.config(cursor="")

    def _on_canvas_mousewheel(self, event):
        """Scroll mouse untuk memperbesar / memperkecil elemen yang sedang aktif."""
        if not self._selected_target:
            return
        tgt = self._selected_target
        delta = 0.1 if event.delta > 0 else -0.1
        cur_w = getattr(self, f"width_{tgt}_var").get()
        new_w = round(max(2.0, min(6.5, cur_w + delta)), 1)

        getattr(self, f"width_{tgt}_var").set(new_w)
        lbl_w = getattr(self, f"lbl_width_{tgt}", None)
        if lbl_w:
            lbl_w.config(text=f"{new_w:.1f} cm")

        active_geo = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
        active_geo[f"width_{tgt}"] = new_w
        self._update_preview()

    # =========================================================================
    # PUSTAKA TANDA TANGAN & STEMPEL (LIBRARY MANAGEMENT)
    # =========================================================================
    def _refresh_library_comboboxes(self):
        """Memuat ulang daftar item pustaka ke dalam Combobox masing-masing kategori."""
        lib = load_signature_library()
        items = lib.get("items", [])

        # 1. Kepala
        items_k = [it for it in items if it.get("category") == "kepala"]
        vals_k = ["[Pilih dari Pustaka...]"] + [f"{it.get('name')} | {it.get('filename')}" for it in items_k]
        self._lib_items_kepala = items_k
        self.cb_kepala["values"] = vals_k

        cur_p_k = self.path_kepala_var.get()
        idx_k = 0
        for i, it in enumerate(items_k, 1):
            if it.get("path") == cur_p_k or it.get("name") == self.name_kepala_var.get():
                idx_k = i
                break
        self.cb_kepala.current(idx_k)

        # 2. Guru
        items_g = [it for it in items if it.get("category") == "guru"]
        vals_g = ["[Pilih dari Pustaka...]"] + [f"{it.get('name')} | {it.get('filename')}" for it in items_g]
        self._lib_items_guru = items_g
        self.cb_guru["values"] = vals_g

        cur_p_g = self.path_guru_var.get()
        idx_g = 0
        for i, it in enumerate(items_g, 1):
            if it.get("path") == cur_p_g or it.get("name") == self.name_guru_var.get():
                idx_g = i
                break
        self.cb_guru.current(idx_g)

        # 3. Stempel
        items_s = [it for it in items if it.get("category") == "stempel"]
        vals_s = ["[Pilih dari Pustaka...]"] + [f"{it.get('name')} | {it.get('filename')}" for it in items_s]
        self._lib_items_stempel = items_s
        self.cb_stempel["values"] = vals_s

        cur_p_s = self.path_stempel_var.get()
        idx_s = 0
        for i, it in enumerate(items_s, 1):
            if it.get("path") == cur_p_s or it.get("name") == self.name_stempel_var.get():
                idx_s = i
                break
        self.cb_stempel.current(idx_s)

    def _on_library_selected(self, category: str):
        if category == "kepala":
            idx = self.cb_kepala.current()
            if idx > 0 and idx <= len(self._lib_items_kepala):
                target = self._lib_items_kepala[idx - 1]
                self.path_kepala_var.set(target.get("path", ""))
                self.name_kepala_var.set(target.get("name", ""))
                self.enable_kepala_var.set(True)
        elif category == "guru":
            idx = self.cb_guru.current()
            if idx > 0 and idx <= len(self._lib_items_guru):
                target = self._lib_items_guru[idx - 1]
                self.path_guru_var.set(target.get("path", ""))
                self.name_guru_var.set(target.get("name", ""))
                self.enable_guru_var.set(True)
        elif category == "stempel":
            idx = self.cb_stempel.current()
            if idx > 0 and idx <= len(self._lib_items_stempel):
                target = self._lib_items_stempel[idx - 1]
                self.path_stempel_var.set(target.get("path", ""))
                self.name_stempel_var.set(target.get("name", ""))
                self.enable_stempel_var.set(True)

        self._selected_target = category
        self._update_preview()

    def _add_signature_dialog(self, category: str):
        """Dialog modal untuk menambah tanda tangan / stempel baru ke pustaka."""
        cat_title = {
            "kepala": "Tanda Tangan Kepala",
            "guru": "Tanda Tangan Guru",
            "stempel": "Stempel Resmi Sekolah/Madrasah"
        }.get(category, "Tanda Tangan")

        dlg = tk.Toplevel(self)
        dlg.title(f"Tambah {cat_title} ke Pustaka")
        dlg.geometry("480x210")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=f"Nama Personil / Keterangan {cat_title}:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        name_var = tk.StringVar()
        ent_name = ttk.Entry(frame, textvariable=name_var)
        ent_name.pack(fill="x", pady=(0, 8))
        ent_name.focus_set()

        ttk.Label(frame, text="Berkas Gambar (PNG / JPG / BMP):", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        file_row = ttk.Frame(frame)
        file_row.pack(fill="x", pady=(0, 12))

        file_var = tk.StringVar()
        ttk.Entry(file_row, textvariable=file_var, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 4))

        def _pick_file():
            f = filedialog.askopenfilename(
                parent=dlg,
                title=f"Pilih Gambar {cat_title}",
                filetypes=[("Berkas Gambar", "*.png;*.jpg;*.jpeg;*.bmp")]
            )
            if f:
                file_var.set(os.path.normpath(f))
                if not name_var.get().strip():
                    base = os.path.splitext(os.path.basename(f))[0]
                    name_var.set(base.replace("_", " ").title())

        ttk.Button(file_row, text="Pilih Gambar...", command=_pick_file).pack(side="right")

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", pady=(6, 0))

        def _save_new():
            nm = name_var.get().strip()
            fp = file_var.get().strip()
            if not nm:
                messagebox.showwarning("Peringatan", "Nama tidak boleh kosong!", parent=dlg)
                return
            if not fp or not os.path.isfile(fp):
                messagebox.showwarning("Peringatan", "Silakan pilih berkas gambar yang valid!", parent=dlg)
                return

            try:
                item = add_signature_item(nm, category, fp)
                dlg.destroy()
                self._refresh_library_comboboxes()

                if category == "kepala":
                    self.path_kepala_var.set(item["path"])
                    self.name_kepala_var.set(item["name"])
                    self.enable_kepala_var.set(True)
                elif category == "guru":
                    self.path_guru_var.set(item["path"])
                    self.name_guru_var.set(item["name"])
                    self.enable_guru_var.set(True)
                elif category == "stempel":
                    self.path_stempel_var.set(item["path"])
                    self.name_stempel_var.set(item["name"])
                    self.enable_stempel_var.set(True)

                self._selected_target = category
                self._refresh_library_comboboxes()
                self._update_preview()
                messagebox.showinfo("Berhasil", f"'{nm}' berhasil disimpan ke folder signatures/!", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menambahkan tanda tangan: {e}", parent=dlg)

        ttk.Button(btn_row, text="Batal", command=dlg.destroy).pack(side="right", padx=(4, 0))
        ttk.Button(btn_row, text="Simpan ke Pustaka", command=_save_new).pack(side="right")

    def _delete_signature_dialog(self, category: str):
        """Menghapus item tanda tangan/stempel yang sedang dipilih di combobox dari pustaka."""
        cb = self.cb_kepala if category == "kepala" else (self.cb_guru if category == "guru" else self.cb_stempel)
        idx = cb.current()
        items = self._lib_items_kepala if category == "kepala" else (self._lib_items_guru if category == "guru" else self._lib_items_stempel)

        if idx <= 0 or idx > len(items):
            messagebox.showinfo("Info", "Pilih terlebih dahulu entri tanda tangan yang ingin dihapus pada daftar simpanan.", parent=self)
            return

        target = items[idx - 1]
        t_name = target.get("name", "Item")
        if not messagebox.askyesno(
            "Konfirmasi Hapus",
            f"Apakah Anda yakin ingin menghapus '{t_name}' dari pustaka tanda tangan?\n(Berkas fisik di folder signatures/ juga akan dibersihkan)",
            parent=self
        ):
            return

        success = delete_signature_item(target.get("id", ""))
        if success:
            if category == "kepala" and self.path_kepala_var.get() == target.get("path"):
                self.path_kepala_var.set("")
                self.name_kepala_var.set("")
            elif category == "guru" and self.path_guru_var.get() == target.get("path"):
                self.path_guru_var.set("")
                self.name_guru_var.set("")
            elif category == "stempel" and self.path_stempel_var.get() == target.get("path"):
                self.path_stempel_var.set("")
                self.name_stempel_var.set("")

            if self._selected_target == category:
                self._selected_target = None

            self._refresh_library_comboboxes()
            self._update_preview()
            messagebox.showinfo("Berhasil", f"'{t_name}' berhasil dihapus.", parent=self)

    # =========================================================================
    # FITUR INSPEKSI & PREDIKSI GEOMETRI DOKUMEN SAMPEL
    # =========================================================================
    def _test_sample_document(self):
        """Membuka file dialog dan menganalisis letak tanda tangan pada dokumen docx sampel."""
        f = filedialog.askopenfilename(
            title="Pilih Dokumen Word (.docx) Sampel untuk Pengujian Letak Tanda Tangan",
            filetypes=[("Dokumen Word", "*.docx")]
        )
        if not f:
            return

        try:
            res = predict_signature_layout(f)
        except Exception as e:
            messagebox.showerror("Error Analisis", f"Gagal menganalisis dokumen: {e}", parent=self)
            return

        res_dlg = tk.Toplevel(self)
        res_dlg.title("Hasil Prediksi & Deteksi Letak Tanda Tangan Dokumen")
        res_dlg.geometry("520x460")
        res_dlg.transient(self)
        res_dlg.grab_set()

        f_cont = ttk.Frame(res_dlg, padding=14)
        f_cont.pack(fill="both", expand=True)

        ttk.Label(f_cont, text="🔍 Hasil Analisis Tata Letak Dokumen", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(f_cont, text=f"Berkas: {res['file_name']}", foreground="#555555").pack(anchor="w", pady=(2, 8))

        info_box = tk.Text(f_cont, height=14, wrap="word", font=("Consolas", 9), bg="#fcfcfc", relief="solid", bd=1)
        info_box.pack(fill="both", expand=True, pady=4)

        recs = res["recommended_offsets"]
        det_names = res.get("detected_names", {})

        report_lines = [
            f"► Orientasi Halaman     : {res['orientation_label'].upper()}",
            f"► Dimensi Kertas        : {res['page_width_cm']} x {res['page_height_cm']} cm",
            f"► Lebar Area Cetak      : {res['printable_width_cm']} cm",
            f"► Tipe Wadah Pengesahan : {res['container_type']}",
        ]
        if res.get("col_widths_cm"):
            cols_str = ", ".join(f"Kolom #{i+1}: {w} cm" for i, w in enumerate(res["col_widths_cm"]))
            report_lines.append(f"► Lebar Kolom Nyata     : {cols_str}")

        if det_names:
            report_lines.append("")
            report_lines.append("► Teks Nama Terdeteksi  :")
            if "kepala" in det_names:
                report_lines.append(f"   - Kepala : {det_names['kepala']}")
            if "guru" in det_names:
                report_lines.append(f"   - Guru   : {det_names['guru']}")

        report_lines.extend([
            "",
            "★ REKOMENDASI GEOMETRI OPTIMAL:",
            f"   - Lebar Tanda Tangan/Stempel : {recs['kepala_width_cm']} cm",
            f"   - Geser X TTD Kepala        : {recs['offset_x_kepala_cm']} cm",
            f"   - Geser X TTD Guru          : {recs['offset_x_guru_cm']} cm",
            f"   - Geser X Stempel Resmi     : {recs['offset_x_stempel_cm']} cm",
            f"   - Geser Y (Vertikal)        : 0.0 cm",
        ])

        info_box.insert("1.0", "\n".join(report_lines))
        info_box.configure(state="disabled")

        btn_row = ttk.Frame(f_cont)
        btn_row.pack(fill="x", pady=(10, 0))

        def _apply_recommendations():
            target_mode = "LANDSCAPE" if res["is_landscape"] else "PORTRAIT"
            self._switch_orientation(target_mode)

            self.width_kepala_var.set(recs["kepala_width_cm"])
            self.offx_kepala_var.set(recs["offset_x_kepala_cm"])
            self.offy_kepala_var.set(recs["offset_y_kepala_cm"])

            self.width_guru_var.set(recs["guru_width_cm"])
            self.offx_guru_var.set(recs["offset_x_guru_cm"])
            self.offy_guru_var.set(recs["offset_y_guru_cm"])

            self.width_stempel_var.set(recs["stempel_width_cm"])
            self.offx_stempel_var.set(recs["offset_x_stempel_cm"])
            self.offy_stempel_var.set(recs["offset_y_stempel_cm"])

            self.lbl_width_kepala.config(text=f"{recs['kepala_width_cm']:.1f} cm")
            self.lbl_offx_kepala.config(text=self._fmt_offset(recs['offset_x_kepala_cm']))
            self.lbl_offy_kepala.config(text=self._fmt_offset(recs['offset_y_kepala_cm']))

            self.lbl_width_guru.config(text=f"{recs['guru_width_cm']:.1f} cm")
            self.lbl_offx_guru.config(text=self._fmt_offset(recs['offset_x_guru_cm']))
            self.lbl_offy_guru.config(text=self._fmt_offset(recs['offset_y_guru_cm']))

            self.lbl_width_stempel.config(text=f"{recs['stempel_width_cm']:.1f} cm")
            self.lbl_offx_stempel.config(text=self._fmt_offset(recs['offset_x_stempel_cm']))
            self.lbl_offy_stempel.config(text=self._fmt_offset(recs['offset_y_stempel_cm']))

            self._update_preview()
            res_dlg.destroy()
            messagebox.showinfo("Terapkan Sukses", f"Rekomendasi geometri untuk profil {target_mode} telah diterapkan ke slider!", parent=self)

        ttk.Button(btn_row, text="Tutup", command=res_dlg.destroy).pack(side="right", padx=(4, 0))
        ttk.Button(btn_row, text="TERAPKAN REKOMENDASI GEOMETRI INI", command=_apply_recommendations).pack(side="right")

    # =========================================================================
    # EVENT HANDLERS & ORIENTATION SWITCHING
    # =========================================================================
    def _switch_orientation(self, target_mode: str):
        if target_mode == self.current_orientation:
            return

        active_dict = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
        active_dict["width_kepala"] = round(self.width_kepala_var.get(), 1)
        active_dict["offx_kepala"] = round(self.offx_kepala_var.get(), 1)
        active_dict["offy_kepala"] = round(self.offy_kepala_var.get(), 1)
        active_dict["width_guru"] = round(self.width_guru_var.get(), 1)
        active_dict["offx_guru"] = round(self.offx_guru_var.get(), 1)
        active_dict["offy_guru"] = round(self.offy_guru_var.get(), 1)
        active_dict["width_stempel"] = round(self.width_stempel_var.get(), 1)
        active_dict["offx_stempel"] = round(self.offx_stempel_var.get(), 1)
        active_dict["offy_stempel"] = round(self.offy_stempel_var.get(), 1)

        self.current_orientation = target_mode
        new_dict = self.portrait_geo if target_mode == "PORTRAIT" else self.landscape_geo

        self.width_kepala_var.set(new_dict["width_kepala"])
        self.offx_kepala_var.set(new_dict["offx_kepala"])
        self.offy_kepala_var.set(new_dict["offy_kepala"])
        self.width_guru_var.set(new_dict["width_guru"])
        self.offx_guru_var.set(new_dict["offx_guru"])
        self.offy_guru_var.set(new_dict["offy_guru"])
        self.width_stempel_var.set(new_dict["width_stempel"])
        self.offx_stempel_var.set(new_dict["offx_stempel"])
        self.offy_stempel_var.set(new_dict["offy_stempel"])

        self.lbl_width_kepala.config(text=f"{new_dict['width_kepala']:.1f} cm")
        self.lbl_offx_kepala.config(text=self._fmt_offset(new_dict['offx_kepala']))
        self.lbl_offy_kepala.config(text=self._fmt_offset(new_dict['offy_kepala']))
        self.lbl_width_guru.config(text=f"{new_dict['width_guru']:.1f} cm")
        self.lbl_offx_guru.config(text=self._fmt_offset(new_dict['offx_guru']))
        self.lbl_offy_guru.config(text=self._fmt_offset(new_dict['offy_guru']))
        self.lbl_width_stempel.config(text=f"{new_dict['width_stempel']:.1f} cm")
        self.lbl_offx_stempel.config(text=self._fmt_offset(new_dict['offx_stempel']))
        self.lbl_offy_stempel.config(text=self._fmt_offset(new_dict['offy_stempel']))

        if target_mode == "PORTRAIT":
            self.btn_tab_portrait.config(bg="#0066cc", fg="#ffffff", font=("Segoe UI", 9, "bold"))
            self.btn_tab_landscape.config(bg="#f0f0f0", fg="#222222", font=("Segoe UI", 9))
            self.frame_land_tools.pack_forget()
        else:
            self.btn_tab_landscape.config(bg="#0066cc", fg="#ffffff", font=("Segoe UI", 9, "bold"))
            self.btn_tab_portrait.config(bg="#f0f0f0", fg="#222222", font=("Segoe UI", 9))
            self.frame_land_tools.pack(fill="x", pady=(0, 4), before=self.frame_kepala)

        self._update_preview()

    def _copy_from_portrait(self):
        """Menyalin nilai konfigurasi potrait ke lanskap."""
        for k in ("width_kepala", "offx_kepala", "offy_kepala", "width_guru", "offx_guru", "offy_guru", "width_stempel", "offx_stempel", "offy_stempel"):
            self.landscape_geo[k] = self.portrait_geo[k]

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
        self.landscape_geo["width_stempel"] = self.portrait_geo["width_stempel"]
        self.landscape_geo["offx_stempel"] = round(self.portrait_geo["offx_stempel"] - 2.3, 1)
        self.landscape_geo["offy_stempel"] = self.portrait_geo["offy_stempel"]

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
            self._selected_target = "kepala"
            self._update_preview()

    def _browse_guru(self):
        f = filedialog.askopenfilename(
            title="Pilih Gambar Tanda Tangan Guru",
            filetypes=[("Berkas Gambar", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if f:
            self.path_guru_var.set(os.path.normpath(f))
            self.enable_guru_var.set(True)
            self._selected_target = "guru"
            self._update_preview()

    def _browse_stempel(self):
        f = filedialog.askopenfilename(
            title="Pilih Gambar Stempel Resmi Sekolah",
            filetypes=[("Berkas Gambar", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if f:
            self.path_stempel_var.set(os.path.normpath(f))
            self.enable_stempel_var.set(True)
            self._selected_target = "stempel"
            self._update_preview()

    def _on_slider_changed(self, target: str, param: str, val: str):
        v = float(val)
        lbl = getattr(self, f"lbl_{param}_{target}", None)
        if lbl:
            lbl.config(text=f"{v:.1f} cm" if param == "width" else self._fmt_offset(v))

        active_geo = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
        active_geo[f"{param}_{target}"] = v

        self._selected_target = target
        self._update_preview()

    def _on_control_changed(self):
        self._update_preview()

    # =========================================================================
    # RENDER SIMULASI KANVAS WORD (LIVE PREVIEW & DRAG-AND-DROP HANDLES)
    # =========================================================================
    def _update_preview(self):
        self.canvas.delete("all")
        self._photo_cache.clear()
        self._element_boxes.clear()

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 100 or h < 100:
            w, h = 500, 480

        px_per_cm = 28.0
        is_land = (self.current_orientation == "LANDSCAPE")

        mode_text = "Simulasi: 📑 Dokumen Lanskap (Lebar Kolom ~13.1 cm)" if is_land else "Simulasi: 📄 Dokumen Potrait (Lebar Kolom ~8.5 cm)"
        mode_color = "#0055aa" if is_land else "#555555"
        self.canvas.create_text(w / 2, 14, text=mode_text, font=("Segoe UI", 9, "bold"), fill=mode_color)

        col_w = w / 2.0
        x_kepala_center = col_w * 0.5
        x_guru_center = col_w * 1.5

        # Garis pemisah kolom tabel
        self.canvas.create_line(col_w, 28, col_w, h - 15, fill="#eeeeee", dash=(4, 4))

        y_name_k = 205
        y_name_g = 205
        base_shift_px = int(2.3 * px_per_cm) if is_land else 0

        # 1. Hitung Geometri TTD Kepala
        k_path = self.path_kepala_var.get().strip()
        k_enabled = self.enable_kepala_var.get()
        k_width_cm = self.width_kepala_var.get()
        k_target_px = int(k_width_cm * px_per_cm)
        base_x_k = self._calc_align_x(x_kepala_center, col_w * 0.1, col_w * 0.9, k_target_px)
        x_img_k = base_x_k + base_shift_px + int(self.offx_kepala_var.get() * px_per_cm)
        y_img_k = (y_name_k - 35) + int(self.offy_kepala_var.get() * px_per_cm)

        k_aspect = 0.5
        if k_enabled and k_path and os.path.isfile(k_path):
            try:
                with Image.open(k_path) as im:
                    k_aspect = im.height / max(1, im.width)
            except Exception:
                pass
        k_height_px = max(24, int(k_target_px * k_aspect))
        box_k = (x_img_k - k_target_px // 2, y_img_k - k_height_px // 2, x_img_k + k_target_px // 2, y_img_k + k_height_px // 2)
        self._element_boxes["kepala"] = {
            "enabled": k_enabled,
            "bbox": box_k,
            "center": (x_img_k, y_img_k),
            "handle": (box_k[2], box_k[3]),
            "width_cm": k_width_cm,
            "color": "#0078d7",
            "title": "TTD Kepala"
        }

        # 2. Hitung Geometri Stempel Resmi (Zona Kepala)
        s_path = self.path_stempel_var.get().strip()
        s_enabled = self.enable_stempel_var.get()
        s_width_cm = self.width_stempel_var.get()
        s_target_px = int(s_width_cm * px_per_cm)
        base_x_s = self._calc_align_x(x_kepala_center, col_w * 0.1, col_w * 0.9, s_target_px)
        x_img_s = base_x_s + base_shift_px + int(self.offx_stempel_var.get() * px_per_cm)
        y_img_s = (y_name_k - 35) + int(self.offy_stempel_var.get() * px_per_cm)

        s_aspect = 1.0
        if s_enabled and s_path and os.path.isfile(s_path):
            try:
                with Image.open(s_path) as im:
                    s_aspect = im.height / max(1, im.width)
            except Exception:
                pass
        s_height_px = max(24, int(s_target_px * s_aspect))
        box_s = (x_img_s - s_target_px // 2, y_img_s - s_height_px // 2, x_img_s + s_target_px // 2, y_img_s + s_height_px // 2)
        self._element_boxes["stempel"] = {
            "enabled": s_enabled,
            "bbox": box_s,
            "center": (x_img_s, y_img_s),
            "handle": (box_s[2], box_s[3]),
            "width_cm": s_width_cm,
            "color": "#9933cc",
            "title": "Stempel Resmi"
        }

        # 3. Hitung Geometri TTD Guru
        g_path = self.path_guru_var.get().strip()
        g_enabled = self.enable_guru_var.get()
        g_width_cm = self.width_guru_var.get()
        g_target_px = int(g_width_cm * px_per_cm)
        base_x_g = self._calc_align_x(x_guru_center, col_w + col_w * 0.1, col_w + col_w * 0.9, g_target_px)
        x_img_g = base_x_g + base_shift_px + int(self.offx_guru_var.get() * px_per_cm)
        y_img_g = (y_name_g - 35) + int(self.offy_guru_var.get() * px_per_cm)

        g_aspect = 0.5
        if g_enabled and g_path and os.path.isfile(g_path):
            try:
                with Image.open(g_path) as im:
                    g_aspect = im.height / max(1, im.width)
            except Exception:
                pass
        g_height_px = max(24, int(g_target_px * g_aspect))
        box_g = (x_img_g - g_target_px // 2, y_img_g - g_height_px // 2, x_img_g + g_target_px // 2, y_img_g + g_height_px // 2)
        self._element_boxes["guru"] = {
            "enabled": g_enabled,
            "bbox": box_g,
            "center": (x_img_g, y_img_g),
            "handle": (box_g[2], box_g[3]),
            "width_cm": g_width_cm,
            "color": "#2e7d32",
            "title": "TTD Guru"
        }

        behind = self.behind_text_var.get()

        def draw_images():
            # A. Gambar TTD Kepala
            if k_enabled and k_path and os.path.isfile(k_path):
                try:
                    pil_img = Image.open(k_path)
                    resized = pil_img.resize((k_target_px, k_height_px), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(resized)
                    self._photo_cache["kepala"] = tk_img
                    self.canvas.create_image(x_img_k, y_img_k, image=tk_img, anchor="center")
                except Exception:
                    self.canvas.create_text(x_img_k, y_img_k, text="[Gambar Error]", fill="#cc0000")
            elif k_enabled:
                self.canvas.create_rectangle(
                    box_k[0], box_k[1], box_k[2], box_k[3],
                    outline="#dddddd", fill="#fafafa", dash=(2, 2)
                )
                self.canvas.create_text(x_img_k, y_img_k, text="(TTD Kepala)", font=("Segoe UI", 8), fill="#aaaaaa")

            # B. Gambar Stempel Resmi Sekolah
            if s_enabled and s_path and os.path.isfile(s_path):
                try:
                    pil_s = Image.open(s_path)
                    resized_s = pil_s.resize((s_target_px, s_height_px), Image.Resampling.LANCZOS)
                    tk_s = ImageTk.PhotoImage(resized_s)
                    self._photo_cache["stempel"] = tk_s
                    self.canvas.create_image(x_img_s, y_img_s, image=tk_s, anchor="center")
                except Exception:
                    self.canvas.create_text(x_img_s, y_img_s, text="[Stempel Error]", fill="#cc0000")
            elif s_enabled:
                r = s_target_px // 2
                self.canvas.create_oval(
                    x_img_s - r, y_img_s - r,
                    x_img_s + r, y_img_s + r,
                    outline="#8833aa", fill="#f9f0fc", dash=(3, 3), width=2
                )
                self.canvas.create_text(x_img_s, y_img_s, text="[ Stempel Resmi ]", font=("Segoe UI", 8, "bold"), fill="#8833aa")

            # C. Gambar TTD Guru
            if g_enabled and g_path and os.path.isfile(g_path):
                try:
                    pil_g = Image.open(g_path)
                    resized_g = pil_g.resize((g_target_px, g_height_px), Image.Resampling.LANCZOS)
                    tk_img_g = ImageTk.PhotoImage(resized_g)
                    self._photo_cache["guru"] = tk_img_g
                    self.canvas.create_image(x_img_g, y_img_g, image=tk_img_g, anchor="center")
                except Exception:
                    self.canvas.create_text(x_img_g, y_img_g, text="[Gambar Error]", fill="#cc0000")
            elif g_enabled:
                self.canvas.create_rectangle(
                    box_g[0], box_g[1], box_g[2], box_g[3],
                    outline="#dddddd", fill="#fafafa", dash=(2, 2)
                )
                self.canvas.create_text(x_img_g, y_img_g, text="(TTD Guru)", font=("Segoe UI", 8), fill="#aaaaaa")

        def draw_texts():
            # Teks Kepala
            self.canvas.create_text(x_kepala_center, 48, text="Mengetahui,", font=("Segoe UI", 9), fill="#333333")
            self.canvas.create_text(x_kepala_center, 68, text="Kepala Madrasah", font=("Segoe UI", 9, "bold"), fill="#111111")
            name_k_disp = self.name_kepala_var.get().strip() or "Nama Kepala Madrasah, M.Pd"
            self.canvas.create_text(x_kepala_center, y_name_k, text=f"( {name_k_disp} )", font=("Segoe UI", 9, "bold", "underline"), fill="#111111")
            self.canvas.create_text(x_kepala_center, y_name_k + 20, text="NIP. 197001012000011001", font=("Segoe UI", 9), fill="#333333")

            # Teks Guru
            self.canvas.create_text(x_guru_center, 48, text="Kota Contoh, 10 Juli 2026", font=("Segoe UI", 9), fill="#333333")
            self.canvas.create_text(x_guru_center, 68, text="Guru Mata Pelajaran", font=("Segoe UI", 9, "bold"), fill="#111111")
            name_g_disp = self.name_guru_var.get().strip() or "Nama Guru Penyusun, S.Pd"
            self.canvas.create_text(x_guru_center, y_name_g, text=f"( {name_g_disp} )", font=("Segoe UI", 9, "bold", "underline"), fill="#111111")
            self.canvas.create_text(x_guru_center, y_name_g + 20, text="NIP. 199001012020012002", font=("Segoe UI", 9), fill="#333333")

        def draw_selection_handles():
            # Gambarkan Bounding Box interaktif & Handle Resize untuk elemen yang sedang dipilih/aktif
            if not self._selected_target:
                return

            info = self._element_boxes.get(self._selected_target)
            if not info or not info["enabled"]:
                return

            bx1, by1, bx2, by2 = info["bbox"]
            clr = info["color"]

            # Garis putus-putus penanda seleksi
            self.canvas.create_rectangle(bx1 - 2, by1 - 2, bx2 + 2, by2 + 2, outline=clr, dash=(4, 3), width=2)

            # 4 Sudut titik penanda
            h_rad = 3
            for cx, cy in [(bx1 - 2, by1 - 2), (bx2 + 2, by1 - 2), (bx1 - 2, by2 + 2)]:
                self.canvas.create_rectangle(cx - h_rad, cy - h_rad, cx + h_rad, cy + h_rad, outline=clr, fill="#ffffff", width=1)

            # Titik sudut kanan-bawah utama untuk Resize Drag
            hx, hy = info["handle"]
            self.canvas.create_rectangle(hx - 2, hy - 2, hx + 6, hy + 6, outline="#ffffff", fill=clr, width=1)

            # Badge info ukuran & geser
            self.canvas.create_rectangle(bx1 - 2, by1 - 20, bx1 + 130, by1 - 3, fill=clr, outline=clr)
            badge_text = f"{info['title']}: {info['width_cm']:.1f}cm"
            self.canvas.create_text(bx1 + 4, by1 - 12, text=badge_text, font=("Segoe UI", 8, "bold"), fill="#ffffff", anchor="w")

        if behind:
            draw_images()
            draw_texts()
        else:
            draw_texts()
            draw_images()

        draw_selection_handles()

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
        self.name_kepala_var.set("")
        self.enable_guru_var.set(False)
        self.path_guru_var.set("")
        self.name_guru_var.set("")
        self.enable_stempel_var.set(False)
        self.path_stempel_var.set("")
        self.name_stempel_var.set("")
        self.alignment_var.set("CENTER")
        self.behind_text_var.set(True)
        self.spacing_var.set(2)

        self.portrait_geo = {
            "width_kepala": 3.5, "offx_kepala": 0.0, "offy_kepala": 0.0,
            "width_guru": 3.5, "offx_guru": 0.0, "offy_guru": 0.0,
            "width_stempel": 3.5, "offx_stempel": -1.5, "offy_stempel": 0.0,
        }
        self.landscape_geo = {
            "width_kepala": 3.5, "offx_kepala": -2.3, "offy_kepala": 0.0,
            "width_guru": 3.5, "offx_guru": -2.3, "offy_guru": 0.0,
            "width_stempel": 3.5, "offx_stempel": -3.8, "offy_stempel": 0.0,
        }

        active = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
        self.width_kepala_var.set(active["width_kepala"])
        self.offx_kepala_var.set(active["offx_kepala"])
        self.offy_kepala_var.set(active["offy_kepala"])
        self.width_guru_var.set(active["width_guru"])
        self.offx_guru_var.set(active["offx_guru"])
        self.offy_guru_var.set(active["offy_guru"])
        self.width_stempel_var.set(active["width_stempel"])
        self.offx_stempel_var.set(active["offx_stempel"])
        self.offy_stempel_var.set(active["offy_stempel"])

        self.lbl_width_kepala.config(text=f"{active['width_kepala']:.1f} cm")
        self.lbl_offx_kepala.config(text=self._fmt_offset(active["offx_kepala"]))
        self.lbl_offy_kepala.config(text=self._fmt_offset(active["offy_kepala"]))
        self.lbl_width_guru.config(text=f"{active['width_guru']:.1f} cm")
        self.lbl_offx_guru.config(text=self._fmt_offset(active["offx_guru"]))
        self.lbl_offy_guru.config(text=self._fmt_offset(active["offy_guru"]))
        self.lbl_width_stempel.config(text=f"{active['width_stempel']:.1f} cm")
        self.lbl_offx_stempel.config(text=self._fmt_offset(active["offx_stempel"]))
        self.lbl_offy_stempel.config(text=self._fmt_offset(active["offy_stempel"]))

        self._selected_target = None
        self._refresh_library_comboboxes()
        self._update_preview()

    def _save_settings(self):
        active_dict = self.portrait_geo if self.current_orientation == "PORTRAIT" else self.landscape_geo
        active_dict["width_kepala"] = round(self.width_kepala_var.get(), 1)
        active_dict["offx_kepala"] = round(self.offx_kepala_var.get(), 1)
        active_dict["offy_kepala"] = round(self.offy_kepala_var.get(), 1)
        active_dict["width_guru"] = round(self.width_guru_var.get(), 1)
        active_dict["offx_guru"] = round(self.offx_guru_var.get(), 1)
        active_dict["offy_guru"] = round(self.offy_guru_var.get(), 1)
        active_dict["width_stempel"] = round(self.width_stempel_var.get(), 1)
        active_dict["offx_stempel"] = round(self.offx_stempel_var.get(), 1)
        active_dict["offy_stempel"] = round(self.offy_stempel_var.get(), 1)

        new_settings = dict(self.settings)
        new_settings.update({
            "enabled_kepala": self.enable_kepala_var.get(),
            "kepala_image_path": self.path_kepala_var.get().strip(),
            "kepala_name": self.name_kepala_var.get().strip(),
            "kepala_width_cm": self.portrait_geo["width_kepala"],
            "offset_x_kepala_cm": self.portrait_geo["offx_kepala"],
            "offset_y_kepala_cm": self.portrait_geo["offy_kepala"],

            "enabled_guru": self.enable_guru_var.get(),
            "guru_image_path": self.path_guru_var.get().strip(),
            "guru_name": self.name_guru_var.get().strip(),
            "guru_width_cm": self.portrait_geo["width_guru"],
            "offset_x_guru_cm": self.portrait_geo["offx_guru"],
            "offset_y_guru_cm": self.portrait_geo["offy_guru"],

            "enabled_stempel": self.enable_stempel_var.get(),
            "stempel_image_path": self.path_stempel_var.get().strip(),
            "stempel_name": self.name_stempel_var.get().strip(),
            "stempel_width_cm": self.portrait_geo["width_stempel"],
            "offset_x_stempel_cm": self.portrait_geo["offx_stempel"],
            "offset_y_stempel_cm": self.portrait_geo["offy_stempel"],

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
                "stempel_width_cm": self.landscape_geo["width_stempel"],
                "offset_x_stempel_cm": self.landscape_geo["offx_stempel"],
                "offset_y_stempel_cm": self.landscape_geo["offy_stempel"],
            }
        })

        save_signature_settings(new_settings)
        if self.on_save_callback:
            try:
                self.on_save_callback(new_settings)
            except Exception as e:
                pass

        messagebox.showinfo("Berhasil", "Pengaturan tanda tangan & stempel Potrait/Lanskap berhasil disimpan!")
        self.destroy()
