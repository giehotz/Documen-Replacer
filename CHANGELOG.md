# Catatan Perubahan (Changelog) — Smart RPP & Document Replacer

Semua perubahan penting pada proyek **Smart RPP & Document Replacer** ([giehotz/Documen-Replacer](https://github.com/giehotz/Documen-Replacer)) didokumentasikan dalam berkas ini. Format penulisan mengacu pada standar [Keep a Changelog](https://keepachangelog.com/id/1.1.0/) dan [Semantic Versioning](https://semver.org/lang/id/).

---

## [v1.1.0] - 2026-11-14

### 📊 Ringkasan Statistik Rilis (`v1.0.0` → `v1.1.0`)
| Parameter Rilis | Detail |
| :--- | :--- |
| **Nama Aplikasi** | Smart RPP & Document Replacer |
| **Nomor Versi Baru** | `v1.1.0` (Minor Release — Multi-Domain & Audit Stabilization) |
| **Versi Sebelumnya** | `v1.0.0` |
| **Tanggal Rilis** | 14 November 2026 |
| **Total Push / Commit** | 5 push pada siklus `v1.1.0` (Total 21 commit sejak inisiasi repositori) |

### 🚀 Added (Fitur Baru)
- **Ekspansi Modular Multi-Domain (Fase 1–4):** Memperluas dukungan otomasi dokumen di luar perangkat ajar (RPP/Modul Ajar) untuk menangani dokumen administrasi sekolah/madrasah meliputi **Surat Keputusan (SK)**, **Surat Dinas/Resmi**, **Surat Perintah Tugas (SPT)**, dan **Berita Acara / MOU** lengkap dengan klasifikasi jenis dokumen otomatis (`AutoClassifier`) dan pemilih profil dokumen di antarmuka pengguna (`09ef5a4`).
- **Generator Dokumen Massal (Batch Mail-Merge):** Menambahkan fitur pembuatan dokumen Word dan PDF secara massal berbasis data tabular (CSV/Excel) serta layanan penomoran surat berurutan otomatis (`09ef5a4`).
- **Log Prediksi Langsung & Dialog Ringkasan Prediksi:** Menambahkan tampilan log *real-time* dan jendela ringkasan interaktif saat aplikasi memindai serta memprediksi aturan isian dari dokumen sumber (`b05f0ba`).
- **Dukungan Run Hyperlink pada Pemroses Paragraf:** Menambahkan kemampuan membaca dan mengganti teks yang berada di dalam elemen tautan (`<w:hyperlink>`) pada dokumen Word tanpa merusak struktur XML paragraf (`dbb7c34`).
- **Dokumentasi Arsitektur Web (Flask + PyWebView):** Menyediakan cetak biru arsitektur antarmuka web lokal berbasis Flask dan pembungkus aplikasi desktop native PyWebView beserta dokumentasi pelacakan fase implementasi (`9e7948a`).

### 🔄 Changed (Perubahan)
- **Konsistensi Pembacaan Teks Paragraf:** Menyeragamkan penggunaan fungsi `get_paragraph_text` di seluruh alur perencanaan dan penerapan perubahan agar perhitungan posisi karakter (`span`) selalu presisi baik pada teks biasa maupun teks ber-hyperlink (`dbb7c34`).

### 🐛 Fixed (Perbaikan Bug)
- **Perbaikan Paket Audit Bug Inti:** Memperbaiki 5 bug kritis dan tinggi hasil audit, mencakup penambahan impor `ttk` pada `main.py`, penyelarasan ruang indeks paragraf antara pencocokan eksak (`iter_all_paragraphs`) dan paragraf inline (`doc.paragraphs`), pelestarian elemen gambar tanda tangan/stempel (`w:drawing`/`w:pict`) saat mengganti teks run pertama, pemrosesan tanda tangan bertabulasi (`TAB_LINE`) agar menghormati persetujuan per-item, serta dukungan penuh seluruh jenis Header/Footer halaman pertama dan genap (`b05f0ba`).
- **Keamanan Thread GUI & Validasi Kamus:** Memastikan pembacaan aturan dari komponen Tkinter hanya dilakukan di *main thread* sebelum *worker thread* berjalan serta mencegah `ValueError` saat memvalidasi format tahun ajaran yang memuat karakter *wildcard* (`b05f0ba`).
- **Pelindung Layar Headless pada Pengujian GUI:** Menambahkan pengecekan ketersediaan layar (*headless display guard*) pada unit test berbasis Tkinter agar rangkaian pengujian otomatis tidak gagal saat dijalankan di lingkungan tanpa layar/CI (`e11f250`).

---

## [v1.0.0] - 2026-11-13

### 📊 Ringkasan Statistik Rilis Awal (`Initial` → `v1.0.0`)
| Parameter Rilis | Detail |
| :--- | :--- |
| **Nomor Versi** | `v1.0.0` (Initial Stable Release) |
| **Tanggal Rilis** | 10 – 13 November 2026 |
| **Total Push / Commit** | 16 push (`d781316` s.d. `7285956`) |

### 🚀 Added (Fitur Baru)
- **Mesin Penggantian Cerdas Berlapis & Tabel Identitas Kontekstual:** Membangun mesin penggantian dokumen Word (`.docx`) dengan pencocokan eksak, pengenalan label/alias, deteksi placeholder titik-titik/garis bawah, pemindaian tabel identitas kontekstual, serta proteksi *anti-blind replacement* (`d781316`, `e2762a6`, `a4f4b57`).
- **Dukungan Format Lawas `.doc` & Prediktor Aturan Otomatis:** Menambahkan layanan kompatibilitas transparan untuk membuka serta menyimpan berkas Word 97–2003 (`.doc`) melalui Microsoft Word COM / LibreOffice, disertai fitur prediksi otomatis nilai lama dari dokumen (`00ae2a8`).
- **Konverter Massal Word ke PDF:** Mengintegrasikan modul konversi batch `.doc`/`.docx` ke `.pdf` dengan mesin ganda (*Microsoft Word COM Automation* dan *LibreOffice Headless fallback*) beserta antrean progres dan fitur pembatalan (`6a59968`).
- **Desainer Tanda Tangan & Stempel Digital Interaktif:** Menyediakan kanvas visual *drag-and-drop* dan *resize* untuk mengatur posisi tanda tangan Kepala Sekolah/Madrasah, Guru, serta stempel digital dengan profil otomatis untuk halaman *Portrait* maupun *Landscape* (`4b264e8`, `b7f0a56`, `d66a936`).
- **Kamus Field Terstruktur & Field Kustom Dinamis:** Menambahkan manajemen kamus sinonim (`FieldDictionary`) dengan normalisasi teks, aturan pengecualian (*never-match*), dukungan bidang *Mata Pelajaran* & *Fase/Kelas*, serta penambahan field kustom secara dinamis (`c0eaa88`, `c16ee6f`, `7285956`).
- **Laporan Verifikasi Perubahan JSON (`ChangeVerifier`):** Menghasilkan laporan audit perubahan pasca-eksekusi berformat JSON yang memeriksa ketepatan mekanis dan semantik hasil penggantian teks (`b6e9564`).

### 🐛 Fixed (Perbaikan Bug)
- **Resolusi Usulan Tumpang Tindih & Pola Tahun Ajaran:** Menyelesaikan benturan antar-usulan perubahan yang menyasar rentang teks yang sama pada satu paragraf serta menyempurnakan deteksi placeholder rentang tahun ajaran agar tidak menyisakan awalan tahun ganda (`b6e9564`).
- **Perbaikan Impor Modul Sistem:** Memperbaiki kesalahan impor modul `os` pada pengelola dialog kamus (`c0eaa88`).

### 🗑️ Removed (Dihapus)
- **Pembersihan Berkas Keluaran dari Pelacakan Git:** Menghentikan pelacakan folder hasil pengujian lokal (`Hasil_Edit_RPP_Kelas6`) dari repositori Git (`e667c02`).
