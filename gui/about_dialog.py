"""
Dialog 'Tentang Aplikasi' — Smart RPP & Document Replacer.
Menyediakan informasi versi, kredit pengembang (@giehotz), panduan penggunaan,
dan perjanjian lisensi penggunaan aplikasi dalam format tab terpisah.
"""
import webbrowser
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext

from core.version import APP_NAME, __version__, APP_TITLE, RELEASE_DATE
from gui.ui_helpers import center_window

GITHUB_PROFILE_URL = "https://github.com/giehotz"
DEVELOPER_NAME = "@giehotz"

PANDUAN_TEKS = """================================================================================
Buku Petunjuk Operasional — Smart RPP & Document Replacer v1.1.0
================================================================================

Aplikasi ini dirancang khusus untuk mempermudah tugas administrasi sekolah dan madrasah, 
mulai dari penyusunan perangkat ajar guru hingga penerbitan naskah dinas resmi secara massal.

--------------------------------------------------------------------------------
1. ALUR PENGGANTIAN DOKUMEN & NASKAH DINAS (TAB 1)
--------------------------------------------------------------------------------
Langkah 1: Menentukan Folder
- Folder Asli (Input): Klik 'Pilih Folder...' dan tentukan folder berkas Word (.docx atau .doc).
- Folder Hasil (Output): Folder tujuan default berada di 'Documents/MODUL/Edited/...'. 
  Anda dapat menggantinya sesuai kebutuhan.

Langkah 2: Memilih Jenis Dokumen (Modular Domain)
- Pada bilah pemilih jenis dokumen di bagian atas, pilih kategori naskah yang sesuai:
  * RPP / Modul Ajar: Untuk silabus, RPP kurikulum 2013, modul ajar kurikulum merdeka.
  * Surat Keputusan (SK): Mengganti konsiderans, nomor SK, diktum, dan lampiran.
  * Surat Dinas / Resmi: Mengganti nomor surat, hal, lampiran, dan blok agenda acara.
  * Surat Perintah Tugas (SPT): Penugasan pegawai baik mandiri maupun kolektif.
  * Berita Acara / MOU: Sinkronisasi nomor BA, tanggal terbilang resmi, & isolasi pihak.

Langkah 3: Mengatur Data Penggantian
- Opsi A (Prediksi Otomatis): Klik tombol '🔍 Prediksi dari Dokumen...'. Sistem akan memindai
  dokumen dan otomatis mengenali nama madrasah, kepala, guru, NIP, semester, dan tahun ajaran.
- Opsi B (Isi Manual): Masukkan teks target langsung pada tabel aturan penggantian.
- Opsi C (Muat Profil Preset): Klik 'Muat Profil (.json)' untuk mengisi data instansi Anda secara instan.

Langkah 4: Pratinjau Terpadu & Eksekusi
- Klik tombol 'PROSES SEMUA DOKUMEN SEKARANG'.
- Jendela 'Pratinjau Terpadu' akan menampilkan setiap titik perubahan sebelum berkas disimpan.
- Anda dapat menyetujui, mencentang, atau membatalkan usulan penggantian per item.
- Klik 'LANJUTKAN & SIMPAN PERUBAHAN DOKUMEN' untuk mengeksekusi penyimpanan secara aman.

--------------------------------------------------------------------------------
2. PENATAAN TANDA TANGAN & STEMPEL DIGITAL
--------------------------------------------------------------------------------
- Klik tombol '✍️ Atur Tanda Tangan Digital...' pada Tab 1.
- Muat file gambar tanda tangan Kepala Sekolah/Madrasah, tanda tangan Guru, dan Stempel instansi.
- Gunakan Kanvas Desainer visual interaktif untuk menggeser posisi (Geser X & Y) serta mengubah ukuran.
- Tanda tangan disisipkan dengan teknologi OpenXML 'Behind Text' sehingga teks nama dan NIP tetap
  terbaca tajam di atas gambar tanda tangan tanpa merusak tata letak tabel Word.
- Sistem otomatis mendeteksi orientasi halaman (Potrait vs Lanskap) saat runtime.

--------------------------------------------------------------------------------
3. KONVERSI MASSAL WORD KE PDF (TAB 2)
--------------------------------------------------------------------------------
- Buka Tab '📄 Konversi Word ke PDF'.
- Tentukan Folder Sumber dokumen dan Folder Output PDF.
- Sistem menggunakan Microsoft Word COM asli Windows (dengan fallback otomatis ke LibreOffice Headless)
  sehingga tata letak, margin, font, dan posisi stempel 100% presisi dengan aslinya.
- Klik 'Mulai Konversi PDF'. Antrean berkas akan diproses satu per satu secara stabil.

--------------------------------------------------------------------------------
4. GENERATOR DOKUMEN MASSAL / MAIL MERGE (TAB 3)
--------------------------------------------------------------------------------
- Buka Tab '🖨️ Mail Merge Massal'.
- Pilih Berkas Templat Word yang memuat token dinamis (misal: {{NAMA}}, <<NIP>>, atau [[JABATAN]]).
- Unggah file data tabular sumber berformat CSV atau Microsoft Excel (.xlsx).
- Lakukan pemetaan kolom token, lalu klik 'Buat Semua Dokumen'.
- Puluhan hingga ratusan berkas personal siap cetak (Word & PDF) akan dihasilkan secara otomatis.
================================================================================
"""

PERJANJIAN_TEKS = """================================================================================
Perjanjian Penggunaan & Lisensi Perangkat Lunak
================================================================================

1. PRIVASI DATA & KEAMANAN LOKAL (100% OFFLINE)
Aplikasi Smart RPP & Document Replacer memproses seluruh berkas dokumen Word (.docx, .doc),
gambar tanda tangan, stempel instansi, serta basis data tabular secara LOKAL di komputer Anda.
Tidak ada data pribadi, NIP, nomor SK, stempel, atau berkas apa pun yang dikirim atau diunggah
ke peladen (server) pihak ketiga maupun internet.

2. KEABSAHAN & TANGGUNG JAWAB DOKUMEN
Aplikasi ini disediakan sebagai alat bantu otomatisasi pengolahan kata dan dokumen administratif.
Pengguna bertanggung jawab penuh atas:
- Ketelitian dan kebenaran data yang dimasukkan (Nama, NIP, Nomor Surat, Tanggal, dan Konsiderans).
- Memeriksa kembali isi dokumen hasil keluaran sebelum ditandatangani, distempel, dan diedarkan.
- Penggunaan gambar tanda tangan dan stempel digital sesuai dengan kewenangan dan ketentuan
  hukum yang berlaku di satuan pendidikan masing-masing.

3. KETENTUAN INTEGRITAS DOKUMEN
Aplikasi secara default menyimpan hasil perubahan ke folder keluaran (Output) yang terpisah dari
folder sumber (Input). Pengguna disarankan untuk selalu mempertahankan berkas cadangan (backup)
dokumen asli sebelum melakukan pemrosesan massal.

--------------------------------------------------------------------------------
LISENSI PERANGKAT LUNAK (MIT LICENSE)
--------------------------------------------------------------------------------
MIT License

Copyright (c) 2026 Giehotz & Kontributor Smart RPP Replacer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
================================================================================
"""


class AboutDialog(tk.Toplevel):
    """
    Jendela dialog modular Tentang Aplikasi dengan navigasi tab:
    1. Tentang & Pengembang
    2. Cara Penggunaan
    3. Perjanjian & Lisensi
    """

    def __init__(self, parent: tk.Tk, initial_tab: int = 0):
        super().__init__(parent)
        self.title(f"Tentang {APP_NAME}")
        self.geometry("780x560")
        self.minsize(680, 480)
        self.transient(parent)
        self.grab_set()

        self._center_window(parent)
        self._build_ui(initial_tab)

    def _center_window(self, parent: tk.Tk):
        """Memposisikan jendela dialog tepat di tengah jendela induk."""
        center_window(self, parent, 780, 560)

    def _build_ui(self, initial_tab: int):
        # 1. Header Frame
        header_frame = ttk.Frame(self, padding=(16, 12, 16, 8))
        header_frame.pack(fill="x")

        title_lbl = ttk.Label(
            header_frame,
            text=f"🚀 {APP_NAME}",
            font=("Segoe UI", 14, "bold"),
            foreground="#1e3a8a",
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ttk.Label(
            header_frame,
            text=f"Versi {__version__} ({RELEASE_DATE}) • Solusi Cerdas Otomasi Dokumen Madrasah & Sekolah",
            font=("Segoe UI", 9),
            foreground="#4b5563",
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # 2. Main Notebook Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=6)

        # Tab 1: Tentang & Pengembang
        self.tab_about = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_about, text=" ℹ️ Tentang & Pengembang ")
        self._build_tab_about(self.tab_about)

        # Tab 2: Cara Penggunaan
        self.tab_guide = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_guide, text=" 📖 Cara Penggunaan ")
        self._build_tab_guide(self.tab_guide)

        # Tab 3: Perjanjian & Lisensi
        self.tab_terms = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_terms, text=" ⚖️ Perjanjian & Lisensi ")
        self._build_tab_terms(self.tab_terms)

        # Pilih tab awal
        if 0 <= initial_tab < 3:
            self.notebook.select(initial_tab)

        # 3. Bottom Action Bar
        bottom_frame = ttk.Frame(self, padding=(12, 8, 12, 10))
        bottom_frame.pack(fill="x")

        close_btn = ttk.Button(bottom_frame, text="Tutup", width=12, command=self.destroy)
        close_btn.pack(side="right")

    def _build_tab_about(self, parent: ttk.Frame):
        """Membangun konten Tab 1: Tentang & Pengembang."""
        # Kartu Deskripsi
        desc_frame = ttk.LabelFrame(parent, text=" Ringkasan Aplikasi ", padding=12)
        desc_frame.pack(fill="x", pady=(0, 10))

        desc_text = (
            f"{APP_NAME} adalah aplikasi desktop modern berbasis Python untuk "
            "mengotomasi pengeditan dokumen perangkat ajar (RPP, Modul Ajar, Silabus, Promes/Prota) "
            "dan berbagai format naskah dinas madrasah/sekolah (Surat Keputusan, Surat Dinas, "
            "Surat Perintah Tugas, dan Berita Acara / MOU), dilengkapi mesin konversi massal Word ke PDF "
            "serta generator dokumen massal (Batch Mail Merge)."
        )
        ttk.Label(desc_frame, text=desc_text, wraplength=710, justify="left").pack(anchor="w")

        # Kartu Pengembang & Kredit
        dev_frame = ttk.LabelFrame(parent, text=" Kredit & Pengembang ", padding=12)
        dev_frame.pack(fill="x", pady=(0, 10))

        dev_grid = ttk.Frame(dev_frame)
        dev_grid.pack(fill="x")

        ttk.Label(dev_grid, text="Pengembang Utama:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=4)
        author_lbl = ttk.Label(dev_grid, text=DEVELOPER_NAME, font=("Segoe UI", 10, "bold"), foreground="#0f766e")
        author_lbl.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(dev_grid, text="Profil GitHub:", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", pady=4)

        # Link yang bisa diklik langsung membuka browser
        self.link_lbl = tk.Label(
            dev_grid,
            text=GITHUB_PROFILE_URL,
            font=("Segoe UI", 9, "underline"),
            fg="#0284c7",
            cursor="hand2",
        )
        self.link_lbl.grid(row=1, column=1, sticky="w", padx=8, pady=4)
        self.link_lbl.bind("<Button-1>", lambda e: self._open_github())

        # Fitur Utama Ringkas
        feat_frame = ttk.LabelFrame(parent, text=" Keunggulan Sistem ", padding=12)
        feat_frame.pack(fill="both", expand=True)

        features = [
            "✔ Context-Aware Engine — mengenali titik-titik (....), garis bawah (____), dan nama lama secara cerdas.",
            "✔ Desainer Tanda Tangan 'Behind Text' — posisi presisi dengan profil terpisah Potrait & Lanskap.",
            "✔ Multi-Domain Expansion — mendukung modul RPP, SK, Surat Dinas, SPT, dan Berita Acara.",
            "✔ Batch Mail Merge — hasilkan ratusan dokumen Word/PDF dari data CSV atau Microsoft Excel.",
            "✔ 100% Offline & Aman — seluruh dokumen diproses lokal tanpa telemetri atau pengunggahan data.",
        ]
        for f in features:
            ttk.Label(feat_frame, text=f, justify="left").pack(anchor="w", pady=2)

    def _build_tab_guide(self, parent: ttk.Frame):
        """Membangun konten Tab 2: Panduan Penggunaan."""
        st = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            font=("Consolas", 9),
            background="#f8fafc",
            foreground="#1e293b",
            relief="flat",
            padx=10,
            pady=10,
        )
        st.pack(fill="both", expand=True)
        st.insert(tk.END, PANDUAN_TEKS)
        st.configure(state="disabled")

    def _build_tab_terms(self, parent: ttk.Frame):
        """Membangun konten Tab 3: Perjanjian & Lisensi."""
        st = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            font=("Consolas", 9),
            background="#f8fafc",
            foreground="#1e293b",
            relief="flat",
            padx=10,
            pady=10,
        )
        st.pack(fill="both", expand=True)
        st.insert(tk.END, PERJANJIAN_TEKS)
        st.configure(state="disabled")

    def _open_github(self):
        """Membuka tautan profil GitHub pengembang di peramban bawaan sistem."""
        try:
            webbrowser.open_new_tab(GITHUB_PROFILE_URL)
        except Exception:
            pass
