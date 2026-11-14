# Rancangan Struktur Proyek Flask + PyWebView — Smart Document Replacer

Dokumen ini merancang struktur arsitektur proyek berbasis **[Flask](https://flask.palletsprojects.com/) (Web UI Lokal)** dan **[PyWebView](https://pywebview.flowrl.com/) (Desktop Native `.exe`)** untuk repositori [giehotz/Documen-Replacer](https://www.google.com/search?q=https://github.com/giehotz/Documen-Replacer). Desain ini menjaga **100% kompatibilitas** dengan modul inti yang sudah ada (`core/`, `document/`, `services/`, `utils/`, `config/`) tanpa mengubah atau merusak aplikasi Tkinter lama (`main.py`).

## 1. Pohon Berkas Lengkap (File Tree)

Seluruh kode Web UI dan API ditempatkan di dalam paket mandiri `webapp/` serta dua titik masuk baru (`web_main.py` untuk mode browser dan `desktop_main.py` untuk mode aplikasi desktop native):

```text
Documen-Replacer/
├── main.py                                  # [EKSISTING] Mode Klasik Desktop Tkinter (tetap berfungsi)
├── web_main.py                              # [BARU] Mode Web Lokal (jalankan server Flask + buka browser otomatis)
├── desktop_main.py                          # [BARU] Mode Desktop Native (Flask + PyWebView tanpa Chrome/URL bar)
├── build_exe.spec                           # [BARU] Konfigurasi PyInstaller untuk paket menjadi 1 file .exe
├── Jalankan_Smart_RPP_Replacer.bat          # [EKSISTING] Launcher Tkinter
├── Jalankan_Web_Replacer.bat                # [BARU] Launcher Mode Web / PyWebView
├── requirements.txt                         # [UPDATE] Tambah flask>=3.0.0 dan pywebview>=5.0.0
│
├── config/                                  # [EKSISTING + EKSPANSI PROFIL]
│   ├── aliases.json
│   ├── dictionary.default.json
│   ├── signature_settings.example.json
│   └── profiles/                            # [BARU] Profil JSON per jenis dokumen (RPP, SK, Surat Dinas, SPT, BA)
│       ├── profile_registry.json
│       ├── rpp_modul_ajar.profile.json
│       ├── sk_keputusan.profile.json
│       ├── surat_dinas.profile.json
│       └── surat_tugas_spt.profile.json
│
├── core/                                    # [EKSISTING - TIDAK DIUBAH] Mesin penggantian teks, verifikasi, & PDF
├── document/                                # [EKSISTING - TIDAK DIUBAH] Pembaca, penulis, & pemroses XML Word
├── domains/                                 # [BARU] Plugin analyzer spesifik dokumen (SK, Surat, SPT, Berita Acara)
├── services/                                # [EKSISTING - TIDAK DIUBAH] Layanan laporan eksekutif
├── utils/                                   # [EKSISTING - TIDAK DIUBAH] Utilitas platform OS
├── gui/                                     # [EKSISTING - TIDAK DIUBAH] Antarmuka Tkinter lama
│
└── webapp/                                  # [BARU] Paket Utama Aplikasi Flask (Backend API + Frontend UI)
    ├── __init__.py                          # Factory function `create_app()` & registrasi Blueprint
    ├── state_manager.py                     # Penyimpan state sesi lokal (antrean plan_items, progress worker, cancel flag)
    ├── native_bridge.py                     # Jembatan OS lokal: Dialog Pilih Folder native, buka folder hasil, preview file
    │
    ├── api/                                 # Blueprint REST API Lokal (JSON Endpoints)
    │   ├── __init__.py
    │   ├── system_routes.py                 # API dialog pilih folder, buka Explorer, cek status Word COM / LibreOffice
    │   ├── replacer_routes.py               # API prediksi field, scan & plan pratinjau, dan eksekusi apply batch
    │   ├── domain_routes.py                 # API daftar profil dokumen (RPP, SK, Surat, SPT) & preset aturan
    │   ├── dictionary_routes.py             # API CRUD kamus sinonim (`FieldDictionary`)
    │   ├── signature_routes.py              # API upload/kelola gambar TTD & stempel, simpan offset/ukuran kanvas
    │   ├── pdf_routes.py                    # API scan berkas Word, antrean konversi PDF batch, & pembatalan
    │   └── report_routes.py                 # API baca laporan JSON verifikasi (`ChangeReportGenerator`) & unduh ringkasan
    │
    ├── workers/                             # Background Thread Workers (Non-Blocking untuk Flask)
    │   ├── __init__.py
    │   ├── task_runner.py                   # Manajer background thread + Server-Sent Events (SSE) / polling progress
    │   ├── replacer_worker.py               # Worker pemindaian rencana (plan) dan penerapan perubahan (apply/direct)
    │   └── pdf_worker.py                    # Worker konversi Word ke PDF massal dengan `pythoncom.CoInitialize()`
    │
    ├── templates/                           # Template HTML (Jinja2 + Tailwind CSS / Alpine.js atau Vue 3)
    │   ├── layouts/
    │   │   └── base.html                    # Layout utama (Sidebar navigasi, Header status engine, Toast notifikasi)
    │   ├── pages/
    │   │   ├── dashboard_replacer.html      # Halaman Utama: Pilih Profil (RPP/SK/Surat), Input/Output Folder, Tabel Aturan
    │   │   ├── pdf_converter.html           # Halaman Konversi Word ke PDF Massal
    │   │   ├── signature_studio.html        # Halaman Desainer Tanda Tangan & Stempel Interaktif (Drag & Drop Canvas)
    │   │   ├── dictionary_manager.html      # Halaman Manajemen Kamus Field & Sinonim
    │   │   └── verification_report.html     # Halaman Dasbor Laporan Verifikasi Perubahan (Filter OK / PERIKSA / SALAH)
    │   └── partials/
    │       ├── modal_preview_diff.html      # Modal Pratinjau Terpadu (Diff highlight sebelum vs sesudah + filter confidence)
    │       ├── modal_progress.html          # Modal Progress Bar real-time dengan log live & tombol Batal
    │       └── domain_form_cards.html       # Komponen form dinamis sesuai profil dokumen yang dipilih
    │
    └── static/                              # Aset Statis Lokal (Offline-Ready tanpa perlu internet!)
        ├── css/
        │   ├── tailwind.min.css             # Bundle CSS lokal agar aplikasi tetap jalan 100% offline
        │   └── app.css                      # Styling khusus diff highlight ⟦ ⟧ dan kanvas kertas A4/F4
        ├── js/
        │   ├── app.js                       # State utama UI, pemanggilan fetch() ke /api/*, & penanganan SSE progress
        │   ├── preview_table.js             # Logika filter, pencarian, centang massal, dan diff viewer di modal pratinjau
        │   ├── signature_canvas.js          # Logika geser/ubah ukuran TTD Kepala, Guru, & Stempel secara visual
        │   └── pdf_queue.js                 # Logika tabel antrean konversi PDF
        └── img/
            └── logo.png
```

## 2. Spesifikasi Endpoint REST API Lokal (`webapp/api/`)

Seluruh interaksi antara tampilan web dan modul `core/` dihubungkan melalui endpoint JSON lokal berikut:

| Kelompok | Method & Endpoint | Fungsi Utama & Modul Inti yang Dipanggil |
| :--- | :--- | :--- |
| **Sistem & Dialog OS** | `POST /api/system/browse-folder` | Membuka dialog *Pilih Folder* asli Windows (`pywebview` dialog atau `tkinter.filedialog.askdirectory`) dan mengembalikan path absolut (plus saran subfolder otomatis via `resolve_output_subfolder`). |
| | `POST /api/system/open-path` | Membuka folder hasil atau berkas dokumen di Windows Explorer (`utils.platform.open_path`). |
| | `GET /api/system/engines` | Mengecek ketersediaan Microsoft Word COM dan LibreOffice (`PDFConversionManager.get_engine_name`). |
| **Penggantian Dokumen** | `POST /api/replacer/predict` | Memindai sampel dokumen di folder input dan mengembalikan saran nilai lama (`core.document_predictor`). |
| | `POST /api/replacer/plan` | Menjalankan `ReplacementEngine.plan_document_changes()` di background thread dan menyimpan `plan_items` di `state_manager`. |
| | `GET /api/replacer/plan-items` | Mengambil daftar `ReplacementPlanItem` (lengkap dengan teks sebelum/sesudah, lokasi, dan `confidence`) untuk ditampilkan di tabel Pratinjau Web. |
| | `POST /api/replacer/apply` | Menerima daftar ID item yang disetujui pengguna dari web, menjalankan `ReplacementEngine.apply_approved_changes()`, dan membuat laporan verifikasi via `ChangeReportGenerator`. |
| | `POST /api/replacer/direct` | Menjalankan penggantian langsung tanpa pratinjau (`skip_low_confidence`). |
| **Progress & Task** | `GET /api/tasks/status` | Mengembalikan persentase progress (`current`, `total`), baris log terbaru, dan status (`running`, `completed`, `cancelled`, `error`). |
| | `POST /api/tasks/cancel` | Mengatur flag `cancel_requested = True` untuk menghentikan proses batch dengan aman. |
| **Tanda Tangan** | `GET /api/signatures/settings` | Membaca konfigurasi tanda tangan & koleksi gambar (`load_signature_settings`, `load_signature_library`). |
| | `POST /api/signatures/settings` | Menyimpan pengaturan ukuran, posisi offset X/Y, orientasi portrait/landscape (`save_signature_settings`) & memanggil `engine.reload_signature_settings()`. |
| | `POST /api/signatures/upload` | Menyimpan gambar PNG transparan tanda tangan/stempel ke pustaka lokal (`add_signature_item`). |
| **Kamus & Profil** | `GET /api/dictionary/fields` | Mengambil seluruh daftar field dan sinonim (`FieldDictionary.load()`). |
| | `POST /api/dictionary/synonyms` | Menambah/menghapus sinonim pengguna (`add_user_synonym`, `save_user`) & memanggil `engine.reload_dictionary()`. |
| **Konversi PDF** | `POST /api/pdf/scan` | Memindai dokumen `.doc`/`.docx` dan menyiapkan path target (`PDFConversionManager.scan_documents` & `prepare_targets`). |
| | `POST /api/pdf/convert` | Menjalankan `PDFConversionManager.convert_batch()` di background worker thread. |

## 3. Contoh Implementasi Kode Kunci

### 3.1. Factory Flask (`webapp/__init__.py`)
Menginisialisasi satu instance `ReplacementEngine`, `ReportService`, dan `StateManager` yang dapat diakses oleh seluruh route:

```python
from flask import Flask
from core.replacement_engine import ReplacementEngine
from services.report_service import ReportService
from webapp.state_manager import AppStateManager

def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["JSON_AS_ASCII"] = False

    # Inisialisasi layanan inti yang sudah ada tanpa mengubah kodenya
    app.state = AppStateManager()
    app.engine = ReplacementEngine()
    app.report_service = ReportService()

    # Registrasi Blueprint API
    from webapp.api.system_routes import system_bp
    from webapp.api.replacer_routes import replacer_bp
    from webapp.api.signature_routes import signature_bp
    from webapp.api.dictionary_routes import dictionary_bp
    from webapp.api.pdf_routes import pdf_bp
    from webapp.api.report_routes import report_bp

    app.register_blueprint(system_bp, url_prefix="/api/system")
    app.register_blueprint(replacer_bp, url_prefix="/api/replacer")
    app.register_blueprint(signature_bp, url_prefix="/api/signatures")
    app.register_blueprint(dictionary_bp, url_prefix="/api/dictionary")
    app.register_blueprint(pdf_bp, url_prefix="/api/pdf")
    app.register_blueprint(report_bp, url_prefix="/api/reports")

    return app
```

### 3.2. Jembatan Dialog Pilih Folder Native (`webapp/native_bridge.py`)
Memungkinkan tombol di halaman web membuka *File Explorer* asli Windows dan mengembalikan path folder penuh (mis. `D:\Dokumen Madrasah\SK 2026`):

```python
import tkinter as tk
from tkinter import filedialog
from typing import Optional

def pick_folder_native(initial_dir: str = "", title: str = "Pilih Folder") -> Optional[str]:
    """
    Membuka dialog pilih folder bawaan OS di atas jendela browser/PyWebView.
    """
    # 1. Jika berjalan di dalam PyWebView, gunakan dialog native PyWebView
    try:
        import webview
        if webview.windows:
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=initial_dir or ""
            )
            if result and len(result) > 0:
                return result[0]
            return None
    except Exception:
        pass

    # 2. Fallback jika dibuka lewat browser biasa (Chrome/Edge): gunakan dialog Tk tersembunyi
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        folder = filedialog.askdirectory(initialdir=initial_dir or None, title=title)
        return folder if folder else None
    finally:
        root.destroy()
```

### 3.3. Titik Masuk Mode Browser (`web_main.py`)
Digunakan saat pengembangan atau jika pengguna ingin membuka lewat browser Chrome/Edge:

```python
import socket
import threading
import webbrowser
from webapp import create_app

def find_free_port(default_port: int = 5050) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", default_port)) != 0:
            return default_port
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def main():
    app = create_app()
    port = find_free_port(5050)
    url = f"http://127.0.0.1:{port}"

    # Buka browser otomatis setelah server siap
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"Smart Document Replacer berjalan di {url}")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)

if __name__ == "__main__":
    main()
```

### 3.4. Titik Masuk Mode Desktop Native (`desktop_main.py`)
Membungkus aplikasi Flask menjadi aplikasi desktop mandiri tanpa bar URL browser, siap di-compile menjadi `.exe` tunggal dengan PyInstaller:

```python
import ctypes
import webview
from webapp import create_app

def main():
    # Aktifkan ketajaman layar HiDPI di Windows
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = create_app()
    window = webview.create_window(
        title="Smart Document Replacer & PDF Converter",
        url=app,
        width=1320,
        height=840,
        min_size=(1024, 680),
        text_select=True,
    )
    webview.start(debug=False)

if __name__ == "__main__":
    main()
```

## 4. Alur Eksekusi Data dari Web UI ke Modul `core/`

1. **Pilih Folder & Profil Dokumen:**
   Pengguna memilih profil dokumen di UI Web (`RPP/Modul Ajar`, `Surat Keputusan (SK)`, `Surat Dinas`, atau `Otomatis`) lalu menekan tombol **Pilih Folder Input**. Frontend memanggil `POST /api/system/browse-folder`, menampilkan path folder asli, dan otomatis mengisi saran path Folder Output.
2. **Pemindaian & Pratinjau (`Plan`):**
   Saat pengguna menekan **Pindai & Pratinjau**, `replacer_worker.py` memproses dokumen di *background thread* sambil mengirim progres real-time ke UI. Setiap `ReplacementPlanItem` diberi ID unik (`item_0001`, dst.) dan disimpan di `app.state.current_plan_items`.
3. **Review Interaktif di Browser:**
   Browser menampilkan tabel perubahan dengan penyorotan perbedaan teks (*diff highlight* warna merah untuk teks lama dan hijau untuk teks baru), filter berdasarkan tingkat keyakinan (`HIGH`, `MEDIUM`, `LOW`), dan filter per berkas atau kategori.
4. **Penerapan & Verifikasi (`Apply`):**
   Pengguna menekan **Terapkan Perubahan**. Browser mengirimkan array ID item yang dicentang ke `POST /api/replacer/apply`. Server memperbarui properti `item.is_approved` di memori, memanggil `app.engine.apply_approved_changes()`, menghasilkan laporan verifikasi lewat `ChangeReportGenerator`, dan langsung menampilkan dasbor ringkasan hasil (`OK`, `PERIKSA`, `SALAH`) beserta opsi satu klik **Ekspor Hasil ke PDF**.
