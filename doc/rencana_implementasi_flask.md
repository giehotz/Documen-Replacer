# Rencana Implementasi Flask Web UI & PyWebView — Smart Document Replacer

## 📌 Deskripsi & Tujuan

Mengimplementasikan antarmuka berbasis web modern (**Flask Web UI**) dan aplikasi desktop native tanpa bilah browser (**PyWebView**) untuk Smart Document Replacer berdasarkan spesifikasi arsitektur di [doc/struktur_proyek_flask_smart_document_replacer.md](file:///d:/Documen-Replacer/doc/struktur_proyek_flask_smart_document_replacer.md).

Tujuan implementasi ini:
1. **Modernisasi Antarmuka:** Menyediakan antarmuka web modern, responsif, dan interaktif (tabel pratinjau diff highlight sebelum/sesudah, studio tanda tangan visual, dasbor verifikasi).
2. **Pola Non-Intrusif (*Strangler Fig*):** Menjaga modul `core/`, `document/`, `domains/`, `workflows/`, dan aplikasi desktop Tkinter lama (`main.py`) **100% utuh tanpa modifikasi destruktif**.
3. **100% Offline-First:** Seluruh pustaka CSS dan JavaScript disimpan secara lokal di `webapp/static/` tanpa ketergantungan CDN internet, sehingga dapat berjalan di madrasah/sekolah tanpa jaringan internet.
4. **Dua Mode Eksekusi:**
   - **Mode Web Browser:** `web_main.py` (menjalankan server lokal Flask dan membuka peramban standar sistem).
   - **Mode Desktop Native:** `desktop_main.py` (menjalankan Flask dibungkus jendela aplikasi native desktop via PyWebView yang siap dikompilasi menjadi satu file `.exe` mandiri).

---

## ⚠️ User Review Required

> [!IMPORTANT]
> **Dependensi Tambahan pada `requirements.txt`:**
> Implementasi ini membutuhkan penambahan paket:
> - `flask>=3.0.0` (Backend web server & REST API)
> - `pywebview>=5.0.0` (Jendela desktop native Webview2 di Windows)
> 
> PyWebView memanfaatkan runtime **Microsoft Edge WebView2** yang sudah terpasang secara bawaan di Windows 10 dan Windows 11. Jika PyWebView belum terpasang atau mengalami kendala platform, aplikasi otomatis melakukan graceful fallback ke mode Web Browser standar (`web_main.py`).

> [!NOTE]
> **Pemisahan Jalur Antarmuka:**
> Pengguna tetap dapat menjalankan antarmuka klasik Tkinter kapan pun melalui `python main.py` atau `Jalankan_Smart_RPP_Replacer.bat`. File peluncur baru `Jalankan_Web_Replacer.bat` disediakan untuk mode web/PyWebView.

---

## 🏗️ Diagram Arsitektur Sistem

```mermaid
flowchart TD
    subgraph Client Layer [Frontend / UI Layer]
        PWV[Desktop Window PyWebView]
        BRW[Web Browser Chrome/Edge]
        UI[Offline UI Templates & Static Assets\nTailwind / Vanilla JS / Canvas]
        PWV --> UI
        BRW --> UI
    end

    subgraph Entrypoints [Titik Masuk Aplikasi]
        WM[web_main.py\nBrowser Auto-Launch]
        DM[desktop_main.py\nNative Window PyWebView]
        TK[main.py\nLegacy Tkinter Desktop]
    end

    subgraph WebApp [Paket webapp/]
        APP[Flask App Factory\ncreate_app]
        STATE[AppStateManager\nPlan Items, Tasks & Progress]
        BRIDGE[NativeBridge\nWindows Folder Dialog & Explorer]
        
        subgraph API Blueprints [REST API Endpoints]
            API_SYS[/api/system]
            API_REP[/api/replacer]
            API_DOM[/api/domains]
            API_MM[/api/mail-merge]
            API_PDF[/api/pdf]
            API_SIG[/api/signatures]
            API_DIC[/api/dictionary]
            API_REP2[/api/reports]
            API_TSK[/api/tasks]
        end
        
        subgraph Workers [Background Task Workers]
            W_REP[ReplacerWorker\nPlan & Apply]
            W_MM[MailMergeWorker\nBatch CSV/Excel]
            W_PDF[PdfWorker\npythoncom CoInitialize]
        end
    end

    subgraph ExistingCore [Modul Inti Eksisting - 0% Perubahan]
        ORCH[workflows/unified_orchestrator.py]
        DOM_REG[domains/domain_registry.py]
        AUTO_CLS[workflows/auto_classifier.py]
        B_MM[workflows/batch_mail_merge.py]
        NUMB[workflows/numbering_service.py]
        CHG_REP[core/change_verifier.py]
        PDF_MGR[core/pdf_converter/conversion_manager.py]
        DICT[core/field_dictionary.py]
        SIG_SVC[core/signature_image_service.py]
    end

    WM --> APP
    DM --> APP
    UI <--> |HTTP / JSON & SSE| API Blueprints
    
    APP --> API Blueprints
    APP --> STATE
    API_SYS --> BRIDGE
    API_REP --> W_REP
    API_MM --> W_MM
    API_PDF --> W_PDF
    
    W_REP --> STATE
    W_MM --> STATE
    W_PDF --> STATE
    API_TSK --> STATE
    
    W_REP --> ORCH
    W_REP --> CHG_REP
    W_MM --> B_MM
    W_PDF --> PDF_MGR
    API_DOM --> DOM_REG
    API_DOM --> NUMB
    API_DIC --> DICT
    API_SIG --> SIG_SVC
```

---

## 📋 Tahapan Rencana Implementasi

Proses implementasi dibagi menjadi **5 Fase Terstruktur**:

### Fase 1: Fondasi Backend Flask & Task State Manager
- [ ] Update `requirements.txt` menambahkan `flask>=3.0.0` dan `pywebview>=5.0.0`.
- [ ] Buat modul `webapp/__init__.py` (Factory function `create_app()` yang menginisialisasi `UnifiedOrchestrator`, `ReportService`, dan `AppStateManager`).
- [ ] Buat modul `webapp/state_manager.py` (Menyimpan sesi aktif, item rencana penggantian `current_plan_items`, status progres tugas latar belakang, antrean log pesan, dan flag pembatalan).
- [ ] Buat modul `webapp/native_bridge.py` (Dialog pilih folder native Windows via PyWebView dengan fallback ke Tkinter `askdirectory` tersembunyi, serta membuka direktori di File Explorer via `os.startfile`).

### Fase 2: REST API Blueprints Terpadu (`webapp/api/`)
- [ ] `webapp/api/system_routes.py`:
  - `POST /api/system/browse-folder`: Dialog pilih folder native & kalkulasi otomatis saran folder output.
  - `POST /api/system/open-path`: Buka folder/berkas di Windows Explorer.
  - `GET /api/system/engines`: Status deteksi Word COM dan LibreOffice.
- [ ] `webapp/api/replacer_routes.py`:
  - `POST /api/replacer/predict`: Auto-fill prediksi teks lama dari dokumen sampel.
  - `POST /api/replacer/plan`: Pemicu pemindaian dokumen (background thread).
  - `GET /api/replacer/plan-items`: Mengambil daftar usulan perubahan lengkap dengan teks sebelum/sesudah, kategori, confidence, dan diff highlight HTML.
  - `POST /api/replacer/apply`: Menerapkan perubahan yang disetujui pengguna dan menghasilkan laporan JSON verifikasi.
- [ ] `webapp/api/domain_routes.py`:
  - `GET /api/domains`: Daftar seluruh domain terdaftar (`RPP`, `SK`, `Surat Dinas`, `SPT`, `Berita Acara`).
  - `POST /api/domains/classify`: Klasifikasi otomatis berkas menggunakan `AutoClassifier`.
  - `GET /api/domains/numbering-presets`: Format penomoran surat otomatis dari `numbering_formats.json`.
- [ ] `webapp/api/mail_merge_routes.py`:
  - `POST /api/mail-merge/scan-tokens`: Pindai token dinamis (`{{...}}`, `<<...>>`) pada templat Word.
  - `POST /api/mail-merge/preview-data`: Baca dan kembalikan 5 baris pertama CSV / Excel.
  - `POST /api/mail-merge/generate`: Pemicu pembuatan dokumen massal berulir dengan proteksi pembatalan.
- [ ] `webapp/api/tasks_routes.py`:
  - `GET /api/tasks/status`: Polling status kemajuan tugas (`progress`, `message`, `status`, `logs`).
  - `GET /api/tasks/events`: Server-Sent Events (SSE) streaming untuk progress bar instan.
  - `POST /api/tasks/cancel`: Permintaan pembatalan tugas aktif.
- [ ] `webapp/api/signature_routes.py`:
  - `GET /api/signatures/settings` & `POST /api/signatures/settings`: Baca/simpan konfigurasi 3 tanda tangan & stempel.
  - `POST /api/signatures/upload`: Unggah file gambar PNG transparan tanda tangan.
- [ ] `webapp/api/dictionary_routes.py`:
  - `GET /api/dictionary/fields`: Ambil kamus istilah dan sinonim.
  - `POST /api/dictionary/synonyms`: Tambah/hapus sinonim kustom pengguna.
- [ ] `webapp/api/pdf_routes.py`:
  - `POST /api/pdf/scan`: Pindai dokumen sumber Word untuk konversi PDF.
  - `POST /api/pdf/convert`: Mulai konversi batch PDF di background thread.
- [ ] `webapp/api/report_routes.py`:
  - `GET /api/reports/latest`: Baca ringkasan laporan verifikasi terakhir (`OK`, `PERIKSA`, `SALAH`).
  - `GET /api/reports/download-json`: Unduh berkas laporan JSON lengkap.

### Fase 3: Template HTML & Static Assets 100% Offline
- [ ] `webapp/static/`:
  - Menyediakan bundle CSS lokal (Tailwind/modern styling) tanpa butuh internet.
  - Menyediakan skrip JavaScript modular murni (Vanilla/Alpine-compatible) untuk AJAX/fetch dan interaktivitas:
    - `static/js/app.js`: Inisialisasi status, tab switching, penanganan dialog folder dan SSE/polling.
    - `static/js/replacer.js`: Tabel pratinjau diff, filter keyakinan, centang massal, eksekusi.
    - `static/js/mail_merge.js`: Unggah data, pemetaan kolom token, generator batch.
    - `static/js/signature_studio.js`: Kanvas interaktif tata letak tanda tangan & stempel.
- [ ] `webapp/templates/`:
  - `layouts/base.html`: Kerangka navigasi sidebar, status bar engine, dan container modal.
  - `pages/dashboard_replacer.html`: Halaman utama penggantian dokumen dan bilah pemilih domain.
  - `pages/mail_merge.html`: Halaman generator Mail Merge massal CSV/Excel ke Word.
  - `pages/pdf_converter.html`: Halaman antrean konversi Word ke PDF massal.
  - `pages/signature_studio.html`: Studio visual penempatan tanda tangan dan stempel.
  - `pages/dictionary_manager.html`: Pengelola sinonim kamus istilah.
  - `pages/verification_report.html`: Dasbor analitik verifikasi perubahan naskah.

### Fase 4: Background Task Workers & Titik Masuk Aplikasi
- [ ] `webapp/workers/`:
  - `replacer_worker.py`: Background thread untuk pemindaian dan penerapan perubahan dokumen melalui `UnifiedOrchestrator`.
  - `mail_merge_worker.py`: Background thread untuk generator batch Mail Merge melalui `BatchMailMerge`.
  - `pdf_worker.py`: Background thread untuk konversi PDF dengan inisialisasi COM `pythoncom.CoInitialize()`.
- [ ] Titik Masuk (Entrypoints):
  - `web_main.py`: Menemukan port bebas (default 5050), membuka browser otomatis lewat `webbrowser.open()`, dan menjalankan Flask server berulir.
  - `desktop_main.py`: Inisialisasi PyWebView native window dengan dukungan HiDPI Windows.
  - `Jalankan_Web_Replacer.bat`: Launcher ganda cerdas (mencoba mode desktop PyWebView, dan jika tidak tersedia otomatis beralih ke mode browser).

### Fase 5: Pengujian Otomatis & Verifikasi Menyeluruh
- [ ] `tests/test_webapp_api.py`: Pengujian seluruh endpoint API Flask menggunakan `app.test_client()`:
  - System routes (browse folder, engine status).
  - Replacer routes (predict, plan, plan-items, apply).
  - Domain routes (list domains, classify).
  - Mail merge routes (token scan, data preview).
  - Signature, Dictionary, and PDF routes.
- [ ] `tests/test_webapp_workers.py`: Pengujian task runner, cancellation flag, dan thread safety.
- [ ] Pengujian Regresi Global: Memastikan 177 unit test eksisting tetap berjalan hijau (100% pass).

---

## 🔍 Rencana Verifikasi

### Pengujian Otomatis
```powershell
# 1. Jalankan unit test khusus WebApp API & Workers
python -m unittest tests/test_webapp_api.py
python -m unittest tests/test_webapp_workers.py

# 2. Jalankan seluruh suite regresi global (177+ tes)
python -m unittest discover -s tests -p "test_*.py"
```

### Verifikasi Manual
1. **Mode Browser:**
   - Jalankan `python web_main.py`.
   - Browser terbuka otomatis ke `http://127.0.0.1:5050`.
   - Klik tombol **Pilih Folder Asli**, verifikasi dialog explorer Windows muncul dan mengembalikan path folder.
   - Pilih jenis dokumen, lakukan pemindaian, buka modal pratinjau, dan terapkan perubahan.
2. **Mode Desktop PyWebView (jika terpasang):**
   - Jalankan `python desktop_main.py`.
   - Jendela native muncul tanpa address bar browser.
3. **Mode Klasik Tkinter:**
   - Jalankan `python main.py`.
   - Pastikan GUI Tkinter lama tetap berfungsi normal 100%.
