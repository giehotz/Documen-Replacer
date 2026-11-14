# 🚀 Smart RPP & Document Replacer

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(x64)-0078D6.svg)](https://microsoft.com/windows)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release: v1.1.0](https://img.shields.io/badge/release-v1.1.0-blue.svg)](CHANGELOG.md)
[![Tests Status](https://img.shields.io/badge/tests-177%2B%20passing-brightgreen.svg)](tests/)
[![Code Style: Clean](https://img.shields.io/badge/architecture-modular-success.svg)](core/)

**Smart RPP & Document Replacer** adalah aplikasi desktop modern berbasis Python untuk mengotomasi pengeditan dokumen administrasi sekolah/madrasah dan perangkat pembelajaran guru (RPP, Modul Ajar, Surat Keputusan, Surat Dinas, SPT Penugasan, Berita Acara, serta generator massal Batch Mail Merge berformat `.docx` maupun `.doc` lawas) dengan modul terintegrasi untuk konversi massal berkas Microsoft Word ke PDF.

Aplikasi dilengkapi mesin pengenal konteks cerdas (*Context-Aware Engine*), sistem kamus sinonim field terstruktur (*Field Dictionary*), pemilih domain naskah otomatis (*AutoClassifier*), generator massal *Mail Merge*, desainer posisi tanda tangan digital tingkat lanjut (*Behind Text* untuk dokumen Potrait & Lanskap), dialog pratinjau interaktif, generator prediksi aturan otomatis, dan mesin konversi PDF massal berpresisi tinggi.

---

## 📑 Daftar Isi
1. [Fitur Unggulan](#-fitur-unggulan)
2. [Persyaratan Sistem (Prerequisites)](#-persyaratan-sistem-prerequisites)
3. [Daftar Library & Dependensi](#-daftar-library--dependensi)
4. [Panduan Instalasi & Persiapan](#-panduan-instalasi--persiapan)
5. [Tutorial & Alur Penggunaan Aplikasi](#-tutorial--alur-penggunaan-aplikasi)
   - [A. Menjalankan Aplikasi](#a-menjalankan-aplikasi)
   - [B. Alur Tab 1: Penggantian RPP & Tanda Tangan Digital](#b-alur-tab-1-penggantian-rpp--tanda-tangan-digital)
   - [C. Alur Tab 2: Konversi Massal Word ke PDF](#c-alur-tab-2-konversi-massal-word-ke-pdf)
   - [D. Alur Tab 3: Generator Dokumen Massal (Mail Merge)](#d-alur-tab-3-generator-dokumen-massal-mail-merge)
6. [Struktur Direktori Proyek](#-struktur-direktori-proyek)
7. [Pengujian & Verifikasi (Test Suite)](#-pengujian--verifikasi-test-suite)
8. [Tips & Pemecahan Masalah (Troubleshooting)](#-tips--pemecahan-masalah-troubleshooting)
9. [Catatan Perubahan (Changelog)](CHANGELOG.md)

---

## ✨ Fitur Unggulan

### 📝 Tab 1: Penggantian Data RPP & Tanda Tangan Digital
* **Dukungan Penuh Berkas .docx & .doc (Transparan):** Menerima berkas Word modern (`.docx`) dan biner lawas (`.doc`) secara otomatis tanpa perlu konversi manual oleh pengguna.
* **Kamus Field & Sinonim Kustom (Field Dictionary):** Menggunakan basis schema v2 terstandarisasi (`config/dictionary.default.json`) dengan dialog interaktif **`📖 Kelola Kamus...`** sehingga pengguna dapat menambah variasi istilah lokal sekolah/madrasah sendiri (disimpan aman di profil pengguna `%APPDATA%\SmartRPPReplacer\dictionary.user.json`).
* **Prediksi Cerdas dari Dokumen (Rule Predictor):** Opsi **`🔍 Prediksi dari Dokumen...`** untuk memindai 1 berkas contoh atau seluruh folder dokumen input, mengekstrak format placeholder konkret, dan menyiapkan tabel aturan penggantian secara instan tanpa hardcoded data pribadi.
* **Deteksi Label Tak Dikenal (Unknown Labels Dialog):** Pasca-prediksi, sistem otomatis mendeteksi label baru yang belum terdaftar di kamus dan menawarkan dialog untuk memetakannya ke field yang sesuai hanya dengan satu klik.
* **Validasi Lunak Interaktif & Badge Status:** Indikator badge `✔` (cocok) atau `?` (tak dikenal) di samping pilihan label, serta peringatan format lembut (*soft warning*) jika format NIP, tahun ajaran, atau semester tidak sesuai standar tanpa memblokir proses.
* **Deteksi Konteks Otomatis (Context-Aware):** Anda tidak wajib mengetahui teks lama di dokumen. Sistem cerdas otomatis mengenali target nama sekolah, kepala madrasah, guru mata pelajaran, NIP, semester, tahun ajaran, dan titimangsa meskipun berwujud titik-titik `..........`, garis bawah `__________`, tanda kurung `(...)`, atau nama guru lama.
* **4 Mode Pencarian Fleksibel:**
  1. *Gabungan (Disarankan):* Mencocokkan teks persis (*exact match*) terlebih dahulu, lalu melengkapi dengan deteksi cerdas otomatis.
  2. *Pencarian Persis Saja (Exact Match):* Hanya mengganti teks lama yang cocok 100%.
  3. *Otomatis Cerdas Murni:* Mengabaikan teks lama dan otomatis mengisi seluruh struktur identitas dan tanda tangan.
  4. *Hanya Sisipkan Tanda Tangan Digital:* Menjaga teks dokumen 100% utuh tanpa perubahan kata, hanya menyisipkan gambar tanda tangan di atas nama terang.
* **Desainer Tanda Tangan Digital Presisi (Signature Designer):**
  - **Di Belakang Teks (Behind Text):** Menggunakan DrawingML OpenXML (`wp:anchor`) sehingga teks nama, gelar, dan NIP tetap terbaca tajam di depan tanda tangan tanpa merusak tata letak atau mendorong baris tabel ke bawah.
  - **Profil Ganda (Potrait & Lanskap):** Dokumen sekolah memiliki format beragam (RPP biasanya Potrait, sedangkan Silabus/Promes/Prota adalah Lanskap). Aplikasi menyediakan profil ukuran dan pergeseran terpisah untuk masing-masing orientasi dengan **deteksi orientasi otomatis saat runtime**.
  - **Kontrol Geser Fleksibel:** Slider Geser X (horizontal) diperluas hingga rentang **`-8.0 cm s.d. +8.0 cm`** dan slider Geser Y (vertikal) **`-5.0 cm s.d. +5.0 cm`**.
  - **Kanvas Simulasi Real-Time:** Pratinjau visual langsung yang responsif terhadap pergerakan slider.
* **Jendela Pratinjau Terpadu (Interactive Preview):** Memeriksa setiap titik perubahan sebelum berkas disimpan ke komputer, lengkap dengan status keyakinan (High/Medium/Low) dan kotak centang persetujuan per item.
* **Opsi Ekspor Otomatis ke PDF:** Opsi sekali centang `[x] Langsung ekspor hasil edit ke format PDF setelah selesai`.

### 📄 Tab 2: Konversi Massal Word ke PDF (Batch PDF Converter)
* **Presisi Tata Letak 100% (Microsoft Word COM Automation):** Menggunakan mesin rendering Word asli Windows melalui COM automation thread-safe (`pythoncom.CoInitialize()`), menjamin tata letak, margin, gambar tanda tangan, dan tabel di PDF identik dengan berkas Word aslinya.
* **Fallback Otomatis (LibreOffice Headless):** Jika komputer tidak memiliki lisensi Microsoft Word, sistem otomatis mengalihkan proses ke LibreOffice tanpa menyebabkan crash.
* **Pemindaian Dokumen Massal:** Memindai puluhan hingga ratusan berkas `.doc` dan `.docx` secara rekursif ke seluruh subfolder.
* **Pemfilteran Cerdas:** Otomatis mengabaikan berkas sementara Microsoft Word (`~$*`) dan berkas tersembunyi.
* **Preservasi Struktur Folder & Anti-Benturan Nama:**
  - Opsi mempertahankan struktur subfolder di folder output.
  - Penomoran otomatis nama berkas jika terjadi duplikasi nama di folder yang sama (mis. `RPP (2).pdf`).
  - Opsi lewati berkas jika PDF sudah ada sebelumnya.
* **Antarmuka Interaktif & Anti-Freeze:** Daftar antrean dokumen berbasis tabel dengan indikator status berwarna (*Menunggu, Memproses, Berhasil, Gagal, Dilewati*), bilah progres persentase, dan kontrol *Cancel* yang aman.

### 🗂️ Modul Multi-Domain & Generator Dokumen Massal (Mail Merge)
* **Ekspansi Multi-Domain Terpadu:** Mendukung pemrosesan otomatis berbagai ragam naskah dinas madrasah/sekolah:
  - **Surat Keputusan (SK):** Otomasi nomor SK, konsiderans menimbang/mengingat, diktum memutuskan, dan sinkronisasi lampiran SK.
  - **Surat Dinas / Resmi:** Penggantian nomor surat, sifat, lampiran, perihal, tujuan, serta penyesuaian blok waktu & agenda acara.
  - **Surat Perintah Tugas (SPT):** Penggantian nomor tugas, dasar surat perintah, serta pembaharuan daftar pegawai penugasan baik personal maupun kolektif.
  - **Berita Acara / MOU:** Isolasi ketat pihak kesatu & kedua, serta sinkronisasi otomatis tanggal numerik ke format terbilang resmi Bahasa Indonesia.
* **Klasifikasi Dokumen Otomatis (AutoClassifier):** Sistem cerdas menganalisis struktur naskah dan secara otomatis memilih profil domain dokumen tanpa konfigurasi rumit.
* **Generator Dokumen Massal (Batch Mail Merge):** Membuat puluhan hingga ratusan berkas Word dan PDF siap cetak berbasis templat token (`{{TAG}}`, `<<TAG>>`, `[[TAG]]`) yang diintegrasikan langsung dengan data tabel CSV atau Microsoft Excel (`.xlsx`).
* **Layanan Penomoran Surat Otomatis (Numbering Service):** Penghitung penomoran surat berurutan terstruktur dengan dukungan format dinamis, bulan Romawi (`{BULAN_ROMAWI}`), dan pembatalan (*rollback*) aman jika terjadi kegagalan.

---

## 💻 Persyaratan Sistem (Prerequisites)

| Komponen | Persyaratan Minimum | Rekomendasi |
| :--- | :--- | :--- |
| **Sistem Operasi** | Windows 10 (versi 1809+) 64-bit | Windows 11 (64-bit) |
| **Versi Python** | **Python 3.10** | **Python 3.11, 3.12, atau 3.13** |
| **Microsoft Office** | Tidak Wajib *(bisa pakai LibreOffice)* | **Microsoft Office Word 2016 / 2019 / 2021 / 365** |
| **Arsitektur CPU** | x64 (64-bit) | x64 (64-bit) |
| **RAM** | Minimal 2 GB | 4 GB atau lebih |

> [!NOTE]
> Pastikan saat menginstal Python di Windows, Anda mencentang opsi **"Add python.exe to PATH"**.

---

## 📦 Daftar Library & Dependensi

Dependensi proyek telah dipin pada berkas [`requirements.txt`](requirements.txt):

```text
python-docx>=1.1.0,<2.0.0
Pillow>=10.0.0,<12.0.0
pywin32>=306; sys_platform == 'win32'
```

### Rincian Fungsi Tiap Pustaka:
1. **`python-docx`**: Membaca, memanipulasi elemen XML OpenXML, tabel, header, footer, dan menyimpan dokumen Word `.docx` secara atomik.
2. **`Pillow` (PIL)**: Memuat berkas gambar tanda tangan (PNG/JPG), menghitung aspek rasio, melakukan *resampling*, dan merender simulasi visual kanvas.
3. **`pywin32`**: Menghubungkan otomasi Microsoft Word COM (`win32com.client` & `pythoncom`) untuk mengekspor dokumen Word ke PDF dengan presisi 100%.
4. **`tkinter` & `ttk`**: Pustaka bawaan resmi Python untuk antarmuka grafis desktop (GUI).

---

## 🛠 Panduan Instalasi & Persiapan

Ikuti langkah-langkah mudah berikut untuk memasang aplikasi dari awal:

### 1. Unduh / Clone Repository
Buka PowerShell atau Command Prompt, lalu clone repository ini:
```powershell
git clone https://github.com/giehotz/Documen-Replacer.git
cd Documen-Replacer
```

### 2. Buat Lingkungan Virtual (Virtual Environment)
Disarankan menggunakan virtual environment agar dependensi terisolasi rapi:
```powershell
# Membuat virtual environment bernama .venv
python -m venv .venv

# Mengaktifkan virtual environment di Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# (Atau jika menggunakan Command Prompt CMD):
# .venv\Scripts\activate.bat
```

### 3. Pasang Pustaka Dependensi
Jalankan perintah pip untuk memasang seluruh kebutuhan pustaka:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 📖 Tutorial & Alur Penggunaan Aplikasi

### A. Menjalankan Aplikasi

Anda dapat menjalankan aplikasi dengan salah satu dari dua cara berikut:
1. **Cara Cepat:** Klik dua kali pada berkas:
   ```text
   Jalankan_Smart_RPP_Replacer.bat
   ```
2. **Melalui Terminal / Konsol:**
   ```powershell
   python main.py
   ```

Antarmuka utama akan terbuka dengan dua tab navigasi di bagian atas:
* **Tab 1: 📝 Penggantian Data RPP & Tanda Tangan**
* **Tab 2: 📄 Konversi Word ke PDF**

---

### B. Alur Tab 1: Penggantian RPP & Tanda Tangan Digital

```text
[Pilih Folder Input/Output] ➔ [Isi Aturan Teks Baru / Muat Profil .json] ➔ [Atur Tanda Tangan Digital] ➔ [Klik Proses] ➔ [Pratinjau & Simpan]
```

1. **Tentukan Lokasi Dokumen:**
   - **Folder Asli (Input):** Klik tombol **Pilih Folder...** dan pilih folder yang memuat dokumen Word RPP asli Anda (contoh: folder `docs/06_Kelas 6/Tahun Pelajaran 2020-2021`).
   - **Folder Hasil (Output):** Otomatis disiapkan oleh sistem ke folder `Documents/MODUL/Edited/<Nama_Subfolder>`. Anda dapat mengubahnya kapan saja.
   - **Opsi Pencarian:**
     - `[✓] Peka huruf besar/kecil`: Mengaktifkan sensitivitas huruf kapital.
     - `[✓] Sertakan subfolder`: Memproses seluruh folder turunan.
     - `[✓] Tampilkan pratinjau`: Memunculkan dialog konfirmasi sebelum berkas disimpan.
     - `[✓] Langsung ekspor ke PDF setelah selesai`: Otomatis mengonversi dokumen hasil edit ke format PDF setelah proses selesai.

2. **Isi Aturan Penggantian Data:**
   - Masukkan nilai target pada kolom **Teks Baru (Target Isian)** (misalnya: *Nama Sekolah, Nama Kepala Madrasah, NIP Kepala, Nama Guru Penyusun, NIP Guru, Semester, Tahun Ajaran, Titimangsa*).
   - Kolom *Teks Lama* bersifat **opsional** (boleh dikosongkan). Mesin cerdas otomatis mencocokkan struktur tabel identitas dan tabel tanda tangan.
   - Anda juga dapat mengeklik tombol **Muat Profil (.json)** untuk mengisi seluruh kolom secara instan dari profil sekolah yang sudah disimpan.

3. **Atur Tanda Tangan Digital (Opsional):**
   - Klik tombol **`✍ Atur Tanda Tangan Digital...`**.
   - Pilih tab **`📄 Dokumen Potrait (RPP)`** atau **`📑 Dokumen Lanskap (Silabus / Promes)`**.
   - Centang *Aktifkan Tanda Tangan*, pilih berkas gambar tanda tangan berformat PNG transparan.
   - Sesuaikan slider **Lebar (cm)**, **Geser X (horizontal)**, dan **Geser Y (vertikal)**.
   - Pastikan opsi `[✓] Posisi Di Belakang Teks (Behind Text)` tercentang.
   - Amati simulasi live preview di kanvas kanan, lalu klik **SIMPAN PENGATURAN TANDA TANGAN**.

4. **Eksekusi & Pratinjau:**
   - Klik tombol **PROSES SEMUA DOKUMEN SEKARANG**.
   - Pada jendela **Pratinjau Terpadu**:
     * Tinjau daftar titik yang ditemukan (Kategori, Teks Lama, Teks Baru, Tingkat Keyakinan).
     * Hilangkan centang jika ada titik tertentu yang tidak ingin diubah.
     * Klik **LANJUTKAN & SIMPAN PERUBAHAN DOKUMEN**.
   - Setelah selesai, dialog **Laporan Hasil** akan muncul dan folder output otomatis terbuka.

---

### C. Alur Tab 2: Konversi Massal Word ke PDF

Tab ini digunakan untuk mengonversi kumpulan dokumen Word (`.doc` dan `.docx`) apa saja menjadi dokumen PDF secara massal:

```text
[Pilih Folder Sumber Word] ➔ [Klik Pindai Dokumen] ➔ [Atur Opsi Subfolder & Timpa] ➔ [Klik Mulai Konversi PDF] ➔ [Buka Folder PDF]
```

1. **Pilih Folder:**
   - Klik tab **`📄 Konversi Word ke PDF`**.
   - Pada kolom *Folder Sumber (Word)*, klik **Pilih Folder...** dan tentukan folder berkas Word Anda.
   - Kolom *Folder Tujuan (PDF)* otomatis disesuaikan ke subfolder `PDF`. Anda bebas mengubahnya.

2. **Pindai Dokumen:**
   - Klik tombol **`🔍 Pindai Dokumen`**.
   - Sistem akan memindai folder (termasuk subfolder jika dicentang), menyaring berkas sementara `~$`, dan menampilkan seluruh antrean pada tabel.
   - Tabel menampilkan *Nama Dokumen, Subfolder Asal, Ukuran Berkas, dan Status*.

3. **Tentukan Opsi:**
   - `[✓] Sertakan subfolder (rekursif)`: Memindai hingga folder terdalam.
   - `[✓] Pertahankan struktur subfolder di output`: Membuat struktur hierarki folder yang sama di folder PDF.
   - `[✓] Lewati jika berkas PDF sudah ada`: Menghemat waktu dengan tidak mengonversi ulang berkas yang sudah pernah dibuat.
   - `[✓] Buka folder tujuan setelah selesai`: Otomatis membuka Windows Explorer saat selesai.

4. **Mulai Konversi:**
   - Klik tombol **`▶ MULAI KONVERSI PDF`**.
   - Konversi berjalan di latar belakang tanpa membuat antarmuka membeku (*no freeze*).
   - Bilah progres dan badge status per baris tabel akan diperbarui secara *real-time*.
   - Jika perlu membatalkan di tengah jalan, cukup klik tombol **`⏹ Batalkan`**.

5. **Hasil:**
   - Setelah selesai, dialog ringkasan akan muncul (*Total, Berhasil, Gagal, Dilewati*).
   - Klik **`📁 Buka Folder PDF`** untuk langsung melihat berkas PDF Anda.

---

## 📂 Struktur Direktori Proyek

```text
Documen-Replacer/
│
├── core/                                   # Mesin Pengolahan Inti (Backend)
│   ├── pdf_converter/                      # Modul Konverter Word ke PDF
│   │   ├── __init__.py
│   │   ├── base.py                         # Kelas abstrak BasePdfConverter
│   │   ├── word_com_engine.py              # Mesin MS Word COM Automation (Thread-Safe)
│   │   ├── libreoffice_engine.py           # Mesin Fallback LibreOffice Headless
│   │   └── conversion_manager.py           # Scanner berkas, path resolver, batch worker
│   ├── doc_compat_service.py               # Jembatan kompatibilitas format .doc & .docx
│   ├── document_predictor.py               # Generator prediksi aturan dari contoh & scanner unknown labels
│   ├── exact_matcher.py                    # Pencocokan pola persis regex
│   ├── field_dictionary.py                 # Engine Kamus Field & sinonim pengguna (schema v2)
│   ├── label_recognizer.py                 # Pengenal label kategori & alias (bridge FieldDictionary)
│   ├── placeholder_detector.py             # Detektor placeholder titik-titik & garis bawah
│   ├── replacement_engine.py               # Mesin penggantian data RPP modular
│   ├── signature_analyzer.py               # Analisis zona tanda tangan tabel & tabulasi
│   ├── signature_image_service.py          # Layanan penyisipan gambar TTD & orientasi
│   ├── similarity_matcher.py               # Pencocokan fuzzy berbasis SequenceMatcher
│   └── validation_engine.py                # Validasi type-safety & evaluasi keyakinan
│
├── gui/                                    # Antarmuka Pengguna Desktop (Tkinter)
│   ├── app.py                              # Jendela utama dengan ttk.Notebook (Tab 1 & 2)
│   ├── dictionary_dialog.py                # Dialog Pengelola Kamus & Dialog Unknown Labels
│   ├── pdf_converter_view.py               # Tampilan Tab Konversi Word ke PDF
│   ├── replacement_view.py                 # Tampilan Aturan Penggantian Data, Combobox & Badges
│   ├── preview_view.py                     # Dialog Pratinjau Terpadu Interaktif
│   ├── report_view.py                      # Dialog Laporan Eksekutif Hasil Penggantian
│   └── signature_designer_dialog.py        # Dialog Desainer Posisi TTD Potrait & Lanskap
│
├── document/                               # Utilitas Manipulasi Berkas Word
│   ├── docx_reader.py                      # Pembaca dokumen Word OpenXML (.docx & .doc)
│   ├── docx_writer.py                      # Penyimpan dokumen atomik (anti-corrupt)
│   └── paragraph_processor.py              # Manipulasi teks run tanpa merusak gambar
│
├── services/                               # Layanan Pendukung
│   └── report_service.py                   # Generator laporan eksekutif (TXT & JSON)
│
├── config/                                 # Berkas Konfigurasi & Preset
│   ├── dictionary.default.json             # Kamus standar 10 field RPP (schema v2)
│   ├── dictionary.user.example.json        # Template sinonim tambahan kustom pengguna
│   ├── aliases.json                        # Kamus alias kategori (legacy fallback)
│   ├── signature_settings.example.json     # Template konfigurasi tanda tangan netral
│   └── preset_example.json                 # Contoh template profil penggantian data
│
├── docs/                                   # Dokumentasi Teknis & Rancangan
│   └── fiturtambahan/                      # Spesifikasi fitur lanjutan & PySide6 roadmap
│
├── tests/                                  # Unit Test Suite Otomatis (98 Tests, 4 Skipped)
│   ├── test_anti_blind_replacement.py     # 3 tests pencegahan penggantian buta placeholder tanpa label
│   ├── test_change_verifier.py            # 4 tests verifikasi kepatuhan, laporan JSON & deteksi anomali
│   ├── test_dictionary_corpus.py          # 13 tests korpus kamus lengkap, variasi kurung & anti-overwrite
│   ├── test_doc_compat.py                 # 6 tests dukungan format .doc & konversi transparan
│   ├── test_document_predictor.py         # 7 tests prediksi dokumen & smart merge
│   ├── test_field_dictionary.py           # 10 tests FieldDictionary, dialog & validasi lunak
│   ├── test_modul_ajar_context.py         # 3 tests pengenalan konteks Modul Ajar & multi-paragraf
│   ├── test_overlapping_proposals.py      # 2 tests pencegahan konflik usulan tumpang tindih
│   ├── test_pdf_converter.py              # 9 tests pemindai berkas & konversi Word ke PDF batch
│   ├── test_signature_library.py          # 4 tests pustaka tanda tangan & persistensi profil
│   ├── test_signature_multi_image.py      # 2 tests dukungan multi-gambar TTD & stempel
│   ├── test_signature_prediction.py       # 3 tests prediksi dan resolusi slot tanda tangan tabel
│   ├── test_smart_engine.py               # 25 tests mesin penggantian, TTD, & orientasi
│   └── test_year_replacement.py           # 7 tests golden cases penggantian tahun ajaran
│
├── Jalankan_Smart_RPP_Replacer.bat        # Launcher sekali klik Windows
├── main.py                                # Entry point utama aplikasi
├── requirements.txt                       # Daftar pin dependensi pip
└── README.md                              # Dokumentasi panduan ini
```

---

## 🧪 Pengujian & Verifikasi (Test Suite)

Aplikasi memiliki **178 unit test otomatis** (dengan 11 pengujian di-skip pada lingkungan tanpa display GUI Tkinter) dengan cakupan menyeluruh untuk menjamin keandalan kode sebelum digunakan pada berkas penting.

Untuk menjalankan seluruh unit test suite:
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Hasil uji yang diharapkan:
```text
Ran 178 tests in ~90s
OK (skipped=11)
```

### Rincian Cakupan Pengujian:
* **Korpus Kamus Lengkap & Variasi Tanda Kurung:** Resolusi 10 field standar dengan variasi tanda kurung `()`, `[]`, `{}`, instruksi template `[... Anda]`, deteksi placeholder tanda tangan `(__________________________)`, pola titimangsa titik-titik, dan proteksi label campuran berbahaya agar tidak tertimpa.
* **Kamus Field & Sinonim:** Resolusi 10 field standar, proteksi kata jebakan (*never_match*), benturan sinonim pengguna, persistensi user dictionary, dan validasi nilai lunak (*soft warning*).
* **Anti-Blind Replacement & Isolasi Konteks:** Memastikan placeholder generik (`_____`) tidak diganti secara buta jika bukan bagian dari label field yang bersangkutan.
* **Verifikasi Perubahan & Laporan Audit:** Laporan verifikasi JSON berstruktur lengkap dengan ringkasan eksekutif, deteksi anomali tahun awalan ganda, dan hashing integritas dokumen.
* **Kompatibilitas Dokumen .doc & .docx:** Konversi transparan format lama Word 97-2003 (.doc) ke (.docx) via Word COM / LibreOffice, pembacaan instan via `load_document`, dan penyimpanan kembali.
* **Prediksi Dokumen:** Analisis tabel identitas (1-kolom, 2-kolom, 3-kolom), deteksi format placeholder konkret, penggabungan variasi unik (*smart merge*), dan pengumpulan label tak dikenal (*unknown labels*).
* **Penggantian Teks:** Exact match, fuzzy matching, case sensitivity, pengenalan label, preservasi style bold/italic/underline pada run Word.
* **Tanda Tangan Digital & Multi-Gambar:** Penyisipan gambar *behind text*, offset X/Y potrait vs lanskap, persistensi pengaturan JSON, penyisipan terpisah tanda tangan kepala/guru dan stempel madrasah, serta eliminasi double-counting.
* **Keamanan Dokumen:** Penyimpanan atomik berkas (`tempfile.mkstemp` + `os.replace`), pengabaian berkas sementara `~$`, dan proteksi type-safety.
* **Konverter PDF:** Pemindaian berkas, filter ekstensi, preservasi struktur subfolder, penomoran benturan nama, serta konversi riil dokumen `.docx` ke `.pdf` valid dengan header `%PDF`.

---

## 💡 Tips & Pemecahan Masalah (Troubleshooting)

| Masalah | Penyebab | Solusi |
| :--- | :--- | :--- |
| **Aplikasi tidak mau terbuka saat klik file `.bat`** | Python belum terdaftar di PATH Windows | Buka installer Python, pilih *Modify*, lalu pastikan opsi *"Add Python to environment variables"* dicentang. |
| **Error `No module named 'win32com'`** | Pustaka `pywin32` belum terpasang | Jalankan perintah `pip install pywin32` di terminal/PowerShell. |
| **Gagal membuka atau menimpa berkas Word** | Berkas sedang terbuka di Microsoft Word | Tutup dokumen Word tersebut di Microsoft Word terlebih dahulu, lalu ulangi proses. |
| **Tanda tangan sedikit miring / bergeser di dokumen Lanskap** | Nilai offset X belum disesuaikan | Buka tombol *Atur Tanda Tangan Digital*, pilih tab *Dokumen Lanskap*, lalu klik tombol *Sesuaikan Otomatis Lanskap* atau geser slider Geser X. |
| **Konversi PDF lambat** | Mengonversi ratusan dokumen sekaligus | Aplikasi menggunakan satu instans Word aktif secara berurutan agar stabil dan hemat memori. Harap tunggu hingga seluruh berkas selesai diproses. |

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah lisensi **MIT License**. Bebas digunakan, dimodifikasi, dan didistribusikan untuk keperluan pendidikan maupun personal.
