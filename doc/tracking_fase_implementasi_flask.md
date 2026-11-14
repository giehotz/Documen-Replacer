# Tracking & Checklist Implementasi Flask Web UI & PyWebView Desktop Native

Dokumen ini melacak kemajuan implementasi antarmuka berbasis web lokal (**Flask Web UI**) dan aplikasi desktop native (**PyWebView**) untuk repositori [Smart Document Replacer](file:///d:/Documen-Replacer) berdasarkan rancangan arsitektur [struktur_proyek_flask_smart_document_replacer.md](file:///d:/Documen-Replacer/doc/struktur_proyek_flask_smart_document_replacer.md) dan rencana kerja [rencana_implementasi_flask.md](file:///d:/Documen-Replacer/doc/rencana_implementasi_flask.md).

---

## 📊 Dashboard Kemajuan Proyek

| Fase | Deskripsi | Target File | Status | Kemajuan | Target Selesai |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Fase 1** | **Fondasi Backend Flask & Task State Manager** | `webapp/__init__.py`, `webapp/state_manager.py`, `webapp/native_bridge.py`, `requirements.txt` | *Direncanakan* | 0% | - |
| **Fase 2** | **REST API Blueprints Terpadu** | `webapp/api/*` (System, Replacer, Domains, MailMerge, Tasks, Signatures, Dict, PDF, Reports) | *Direncanakan* | 0% | - |
| **Fase 3** | **Template HTML & Static Assets 100% Offline** | `webapp/templates/*`, `webapp/static/*` (Tailwind bundle, vanilla JS, diff highlighter) | *Direncanakan* | 0% | - |
| **Fase 4** | **Background Task Workers & Titik Masuk Aplikasi** | `webapp/workers/*`, `web_main.py`, `desktop_main.py`, `Jalankan_Web_Replacer.bat` | *Direncanakan* | 0% | - |
| **Fase 5** | **Pengujian Otomatis & Verifikasi Menyeluruh** | `tests/test_webapp_api.py`, `tests/test_webapp_workers.py`, regression suite | *Direncanakan* | 0% | - |

### Metrik Kualitas & Kepatuhan Arsitektur
- **Dampak pada Modul Inti (`core/`, `document/`, `domains/`, `workflows/`, `services/`):** Target `0.0%` (Arsitektur Strangler Fig terbukti).
- **Kompatibilitas GUI Klasik (`gui/`, `main.py`):** Tetap berfungsi 100% tanpa regresi bagi pengguna yang menyukai Tkinter.
- **Kemandirian Offline (Offline-First):** 100% aset statis (CSS, JS, Fonts) tersimpan lokal di `webapp/static/`, tanpa ketergantungan CDN internet luar.
- **Thread Safety & COM Isolation:** Setiap thread konversi PDF Word COM wajib menginisialisasi `pythoncom.CoInitialize()` dan `pythoncom.CoUninitialize()`.
- **Kebijakan Privasi (Zero PII):** Seluruh preset, template, dan contoh data menggunakan data sintetis fiktif (`Budi Santoso, M.Pd`, `198001012005011001`, `Siti Aminah, S.Pd`).

---

## ⏳ Fase 1: Fondasi Backend Flask & Task State Manager (Direncanakan)

Fokus: Menyiapkan dependensi, factory aplikasi Flask, state manager sesi lokal untuk menampung item usulan penggantian dan progres background tasks, serta jembatan dialog folder native OS.

### 1.1. Konfigurasi Lingkungan & Paket
- [ ] **`requirements.txt`**
  - [ ] Tambahkan `flask>=3.0.0`
  - [ ] Tambahkan `pywebview>=5.0.0`
- [ ] **`webapp/__init__.py`**
  - [ ] Factory function `create_app()`
  - [ ] Inisialisasi singleton `UnifiedOrchestrator`, `ReportService`, dan `AppStateManager`
  - [ ] Konfigurasi `JSON_AS_ASCII = False` dan folder template/static
  - [ ] Registrasi Blueprints API

### 1.2. State Manager & Native OS Bridge
- [ ] **`webapp/state_manager.py`**
  - [ ] Penyimpan state sesi lokal (`current_plan_items`, `rules`, `selected_files`)
  - [ ] Pengelola status tugas latar belakang (`task_id`, `status: idle|running|completed|cancelled|error`)
  - [ ] Antrean pesan log real-time (`log_history`)
  - [ ] Flag pembatalan aman (`cancel_requested`)
- [ ] **`webapp/native_bridge.py`**
  - [ ] `pick_folder_native(initial_dir, title)`: Dialog pilih folder native via PyWebView dengan fallback ke Tkinter `askdirectory` tersembunyi
  - [ ] `open_in_file_explorer(path)`: Membuka folder output atau file di Windows File Explorer (`os.startfile` / `explorer.exe`)
  - [ ] `check_conversion_engines()`: Deteksi runtime Word COM dan LibreOffice

---

## ⏳ Fase 2: REST API Blueprints Terpadu (Direncanakan)

Fokus: Membangun endpoint REST API lokal berbasis JSON di `webapp/api/` untuk melayani seluruh kebutuhan komunikasi antara tampilan web dan engine pengolah dokumen.

### 2.1. Endpoints Sistem, Domain & Penggantian Dokumen
- [ ] **`webapp/api/system_routes.py`**
  - [ ] `POST /api/system/browse-folder`: Buka dialog folder OS & hitung saran folder output otomatis
  - [ ] `POST /api/system/open-path`: Buka lokasi file/folder di Windows Explorer
  - [ ] `GET /api/system/engines`: Ambil status ketersediaan MS Word COM dan LibreOffice
- [ ] **`webapp/api/domain_routes.py`**
  - [ ] `GET /api/domains`: Daftar seluruh domain terdaftar (`RPP`, `SK`, `Surat Dinas`, `SPT`, `Berita Acara`)
  - [ ] `POST /api/domains/classify`: Klasifikasi otomatis dokumen via `AutoClassifier`
  - [ ] `GET /api/domains/numbering-presets`: Ambil pola penomoran surat dari `numbering_formats.json`
- [ ] **`webapp/api/replacer_routes.py`**
  - [ ] `POST /api/replacer/predict`: Prediksi nilai lama otomatis dari file sampel dokumen
  - [ ] `POST /api/replacer/plan`: Pemicu analisis dokumen di background thread
  - [ ] `GET /api/replacer/plan-items`: Ambil item usulan perubahan dengan format diff highlight
  - [ ] `POST /api/replacer/apply`: Terapkan item yang disetujui pengguna dan terbitkan laporan JSON
  - [ ] `POST /api/replacer/direct`: Penggantian langsung tanpa pratinjau

### 2.2. Endpoints Mail Merge, Tugas, Kamus, TTD & PDF
- [ ] **`webapp/api/mail_merge_routes.py`**
  - [ ] `POST /api/mail-merge/scan-tokens`: Deteksi token template (`{{...}}`, `<<...>>`)
  - [ ] `POST /api/mail-merge/preview-data`: Baca dan kembalikan sampel baris data CSV/Excel
  - [ ] `POST /api/mail-merge/generate`: Mulai pembuatan batch dokumen massal
- [ ] **`webapp/api/tasks_routes.py`**
  - [ ] `GET /api/tasks/status`: Polling status kemajuan persentase, log terbaru, dan status proses
  - [ ] `GET /api/tasks/events`: Server-Sent Events (SSE) streaming untuk pembaruan instan
  - [ ] `POST /api/tasks/cancel`: Permintaan pembatalan tugas aktif
- [ ] **`webapp/api/signature_routes.py`**
  - [ ] `GET /api/signatures/settings` & `POST /api/signatures/settings`: Kelola pengaturan TTD & stempel
  - [ ] `POST /api/signatures/upload`: Unggah file gambar tanda tangan transparan
- [ ] **`webapp/api/dictionary_routes.py`**
  - [ ] `GET /api/dictionary/fields`: Baca field dan sinonim kamus
  - [ ] `POST /api/dictionary/synonyms`: Tambah atau hapus sinonim kustom pengguna
- [ ] **`webapp/api/pdf_routes.py`**
  - [ ] `POST /api/pdf/scan`: Pindai daftar dokumen Word untuk konversi
  - [ ] `POST /api/pdf/convert`: Mulai batch konversi PDF
- [ ] **`webapp/api/report_routes.py`**
  - [ ] `GET /api/reports/latest`: Ringkasan metrik verifikasi perubahan (`OK`, `PERIKSA`, `SALAH`)
  - [ ] `GET /api/reports/download-json`: Unduh file laporan verifikasi JSON

---

## ⏳ Fase 3: Template HTML & Static Assets 100% Offline (Direncanakan)

Fokus: Menyediakan antarmuka web modern, responsif, dan siap jalan 100% tanpa internet menggunakan bundle CSS/JS lokal.

### 3.1. Aset Statis Lokal (`webapp/static/`)
- [ ] **`webapp/static/css/tailwind.min.css`** (atau bundle CSS mandiri lokal tanpa internet)
- [ ] **`webapp/static/css/app.css`** (Styling penyorotan teks diff, modal, dan lembar kertas kanvas)
- [ ] **`webapp/static/js/app.js`** (Manajemen state navigasi, pemanggilan API `fetch()`, dan SSE/polling task)
- [ ] **`webapp/static/js/replacer.js`** (Tabel pratinjau interaktif, filter keyakinan, centang massal)
- [ ] **`webapp/static/js/mail_merge.js`** (Pratinjau data tabel CSV/Excel dan pemetaan token)
- [ ] **`webapp/static/js/signature_studio.js`** (Studio visual kanvas interaktif tata letak TTD & stempel)

### 3.2. Template Halaman & Modal (`webapp/templates/`)
- [ ] **`webapp/templates/layouts/base.html`** (Sidebar navigasi, indikator mesin, toast notifikasi)
- [ ] **`webapp/templates/pages/dashboard_replacer.html`** (Form input folder, pemilih domain, tabel aturan)
- [ ] **`webapp/templates/pages/mail_merge.html`** (Halaman generator dokumen massal berbasis data)
- [ ] **`webapp/templates/pages/pdf_converter.html`** (Halaman antrean konversi Word ke PDF)
- [ ] **`webapp/templates/pages/signature_studio.html`** (Studio visual drag-and-drop tanda tangan & stempel)
- [ ] **`webapp/templates/pages/dictionary_manager.html`** (Halaman editor kamus istilah & sinonim)
- [ ] **`webapp/templates/pages/verification_report.html`** (Dasbor ringkasan audit perubahan dokumen)
- [ ] **`webapp/templates/partials/modal_preview_diff.html`** (Modal pratinjau teks sebelum vs sesudah)
- [ ] **`webapp/templates/partials/modal_progress.html`** (Modal progress bar real-time & tombol batalkan)

---

## ⏳ Fase 4: Background Task Workers & Titik Masuk Aplikasi (Direncanakan)

Fokus: Mengisolasi pemrosesan dokumen yang memakan waktu lama ke background thread non-blocking serta menyediakan file peluncur aplikasi untuk pengguna akhir.

### 4.1. Background Workers (`webapp/workers/`)
- [ ] **`webapp/workers/task_runner.py`** (Manajer eksekusi thread aman, pelacakan exception, dan emisi progres)
- [ ] **`webapp/workers/replacer_worker.py`** (Eksekusi pemindaian `plan` dan penerapan `apply` dokumen)
- [ ] **`webapp/workers/mail_merge_worker.py`** (Eksekusi batch dokumen massal dengan proteksi rollback)
- [ ] **`webapp/workers/pdf_worker.py`** (Eksekusi konversi PDF dengan inisialisasi `pythoncom.CoInitialize()`)

### 4.2. Titik Masuk Aplikasi (Entrypoints)
- [ ] **`web_main.py`** (Mencari port bebas, meluncurkan server Flask, dan membuka peramban web otomatis)
- [ ] **`desktop_main.py`** (Membungkus Flask ke dalam jendela desktop native PyWebView)
- [ ] **`Jalankan_Web_Replacer.bat`** (Skrip peluncur Windows pintar: coba PyWebView native -> fallback browser)

---

## ⏳ Fase 5: Pengujian Otomatis & Verifikasi Menyeluruh (Direncanakan)

Fokus: Menguji fungsionalitas seluruh endpoint API, thread worker, serta menjamin stabilitas suite regresi global.

### 5.1. Unit & Integration Testing
- [ ] **`tests/test_webapp_api.py`**
  - [ ] Pengujian system routes (browse folder, open path, engine detection)
  - [ ] Pengujian replacer routes (predict, plan, plan-items, apply)
  - [ ] Pengujian domain routes (list domains, classify)
  - [ ] Pengujian mail merge routes (token scan, data preview)
  - [ ] Pengujian signature, dictionary, pdf, dan report routes
- [ ] **`tests/test_webapp_workers.py`**
  - [ ] Pengujian task runner, penanganan pembatalan (*cancellation*), dan error handling
  - [ ] Pengujian isolasi state antar pemanggilan tugas

### 5.2. Verifikasi Regresi Global
- [ ] **177+ Unit Tests Eksisting:** Seluruh tes eksisting (`tests/test_*.py`) tetap lulus 100% tanpa regresi.
- [ ] **Paritas & Non-Destructive Invariant:** Modul `core/`, `document/`, `domains/`, dan `gui/` tetap berfungsi utuh.

---

## 📋 Matriks Kriteria Penerimaan Lintas Fase (DoD Global)

| Aspek Pengujian | Kriteria Keberhasilan | Target Fase | Metode Verifikasi |
| :--- | :--- | :---: | :--- |
| **Bebas Regresi** | 100% tes eksisting hijau tanpa kegagalan | Semua Fase | Eksekusi `unittest discover -s tests` |
| **Kemandirian Offline** | Berjalan sempurna tanpa koneksi internet (0 CDN) | Fase 3 | Uji buka antarmuka tanpa internet |
| **Integritas API** | Semua endpoint JSON merespons dengan status 200 dan format valid | Fase 2, 5 | `tests/test_webapp_api.py` |
| **Thread Safety & COM** | Tidak ada crash RPC/COM saat konversi PDF massal | Fase 4, 5 | `tests/test_webapp_workers.py` |
| **Graceful Fallback** | Otomatis beralih ke mode browser jika PyWebView tidak tersedia | Fase 4 | Uji luncur pada lingkungan non-WebView2 |
| **Kepatuhan Privasi** | Nol kebocoran data pribadi pada UI, log, dan preset (Zero PII) | Semua Fase | Audit data dummy sintetis |

---

> Dokumen ini diperbarui secara berkala setiap kali ada tahapan implementasi Flask yang selesai dikerjakan dan diverifikasi.
