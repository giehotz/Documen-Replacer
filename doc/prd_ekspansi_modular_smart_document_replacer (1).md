# Product Requirements Document (PRD): Ekspansi Modular Smart Document Replacer (Multi-Domain Word Automation)

> **Status dokumen:** Revisi 1 · 14 November 2026. Bagian yang diperbaiki atau ditambah ditandai **[Catatan Revisi Rn]** dan dirangkum di **§12**. Baseline kode yang dirujuk: cabang `main`, commit `dbb7c34`.

## 1. Ringkasan Eksekutif & Visi Produk

Saat ini, **Smart RPP Replacer** ([giehotz/Documen-Replacer](https://github.com/giehotz/Documen-Replacer)) telah memiliki fondasi mesin pemrosesan dokumen Word (`.docx` & `.doc`), pengenalan label cerdas berbasis kamus (`FieldDictionary`), deteksi blok tanda tangan, pratinjau interaktif, verifikasi kualitas perubahan (`ChangeReportGenerator`), serta konversi massal ke PDF (`WordComConverter` & `LibreOfficeConverter`). Namun, aturan deteksi struktur dan kamus istilahnya masih terikat erat (*tightly coupled*) pada domain perangkat pembelajaran guru (**RPP, Modul Ajar, Silabus, PROTA, PROMES**).

Dokumen PRD ini merancang **arsitektur ekspansi modular berbasis Domain Profile & Plugin Pipeline** untuk memperluas jangkauan aplikasi menjadi **Universal Madrasah/School Administrative Document Automation**—mencakup **Surat Keputusan (SK), Surat Dinas/Resmi, Surat Tugas (SPT), Berita Acara, Piagam/Sertifikat, dan MOU/SPK**—**tanpa mengubah atau merusak kode sumber yang sudah ada** (*Open-Closed Principle*: terbuka untuk ekstensi, tertutup untuk modifikasi destruktif).

> **[Catatan Revisi R1: baseline]** Direktori `domains/`, `workflows/`, dan `config/profiles/` **belum ada** di repo; seluruh isinya masih rencana. Yang sudah ada dan menjadi pijakan: `ReplacementPlanItem` (`core/validation_engine.py`), `ChangeReportGenerator` (`core/change_verifier.py`), `ReportService` (`services/report_service.py`), dan `FieldDictionary` skema v2 yang dapat memuat berkas mana pun lewat `FieldDictionary.load(default_path=...)`. Fakta terakhir dipakai di §6.

## 2. Prinsip Desain Non-Intrusif (Zero-Breaking Architecture)

Agar kode yang sudah berjalan di `core/`, `document/`, `gui/`, dan `services/` tetap utuh dan stabil:

1. **Pola *Strangler Fig* & *Adapter/Facade*:**
   - Seluruh modul asli (`core/replacement_engine.py`, `document/paragraph_processor.py`, `core/field_dictionary.py`, dll.) dipertahankan apa adanya sebagai **Core Engine & Legacy RPP Provider**.
   - Penambahan fitur dilakukan melalui paket baru yang berdiri sendiri (`domains/`, `engines/`, `workflows/`, `config/profiles/`).
2. **Isolasi Kamus & Aturan Per Jenis Dokumen (*Domain Profile*):**
   - Setiap jenis dokumen (RPP/Modul Ajar, SK, Surat Dinas, Surat Tugas, Berita Acara) memiliki profil JSON dan *analyzer* spesifiknya sendiri, sehingga kata kunci pada SK (mis. *"Menimbang"*, *"Mengingat"*, *"MEMUTUSKAN"*, *"Ditetapkan di"*) tidak mencemari atau bentrok dengan kamus RPP.
3. **Pemanfaatan Kembali Infrastruktur Inti (*Reuse Existing Primitives*):**
   - Primitif manipulasi XML Word di `document/` (`load_document`, `save_document`, `iter_all_paragraphs`, `replace_span`, `replace_full_text_keep_style`) dan struktur `ReplacementPlanItem` di `core/validation_engine.py` tetap menjadi kontrak data tunggal (*Single Data Contract*) antara semua domain baru dan GUI Pratinjau Terpadu (`IntegratedPreviewDialog`).
4. **Pengecualian terkontrol atas "tidak mengubah kode lama"** *(Catatan Revisi R2)*: selama ekspansi, kode eksisting hanya boleh disentuh untuk tiga hal: (a) perbaikan bug yang diungkap tes domain baru; (b) **satu titik penyambungan** di `gui/app.py` (`self.engine = UnifiedOrchestrator(...)`, lihat §5.1); (c) *hook* opsional yang tidak mengubah perilaku bawaan. Perubahan lain memerlukan keputusan eksplisit yang dicatat di §12. Tanpa batas ini klaim "0% perubahan" di §7 tidak dapat diverifikasi.
5. **Kontrak berlaku sampai ke verifikasi** *(Catatan Revisi R2)*: memakai `ReplacementPlanItem` saja belum cukup. Item domain juga harus memakai `target_type` dan kunci `target_meta` yang dikenali `ChangeReportGenerator`; bila tidak, laporan perubahan tidak dapat membaca teks "sesudah" dengan benar (lihat §5.1).

## 3. Cakupan Ekspansi Domain Dokumen Baru

| Kode Profil | Kategori Dokumen | Karakteristik Struktur Khusus di MS Word | Kebutuhan Otomasi Utama |
| :--- | :--- | :--- | :--- |
| **`DOM-01`** | **Perangkat Ajar (Eksisting)** (RPP, Modul Ajar, PROTA, PROMES) | Tabel Identitas, Paragraf Inline (`Label : ...`), Blok TTD 2 Kolom (Kepala & Guru). | Penggantian identitas guru, kepala, mapel, kelas/fase, tahun ajaran, titimangsa, & TTD. |
| **`DOM-02`** | **Surat Keputusan (SK)** (SK Pembagian Tugas, SK Panitia, SK Bendahara, SK Kelulusan) | Judul & Nomor SK di tengah, konsiderans (`Menimbang:`, `Mengingat:`, `Memperhatikan:`), diktum (`MEMUTUSKAN: Menetapkan: KESATU...`), blok penetapan (`Ditetapkan di ...`, `Pada tanggal ...`), Tembusan, dan **Tabel Lampiran SK**. | Pembaruan Nomor SK, Tentang/Judul SK, Tahun Anggaran/Pelajaran, Isi Diktum, Tanggal Penetapan, Pejabat Penandatangan, serta *Mail-Merge/Batch Update* Tabel Lampiran SK. |
| **`DOM-03`** | **Surat Dinas / Surat Resmi** (Undangan, Permohonan, Pemberitahuan, Pengantar) | Kop Surat (Header/Body), Nomor, Lampiran, Perihal/Hal, Tujuan (`Kepada Yth.`), Pembuka, Blok Acara (`Hari/Tanggal`, `Waktu`, `Tempat`, `Acara`), Penutup, TTD Tunggal/Ganda + Stempel. | Penggantian Nomor Surat otomatis/berurut, Tanggal Surat, Tujuan Surat, Detail Waktu/Tempat Acara, dan Penandatangan. |
| **`DOM-04`** | **Surat Perintah Tugas (SPT) & SPPD** | Dasar Surat, Daftar Pegawai yang Ditugaskan (Format Paragraf Bernomor atau Tabel Pegawai: Nama, NIP, Pangkat/Gol, Jabatan), Tujuan Tugas, Tanggal Berangkat/Kembali. | Penggantian Dasar SPT, Data Pegawai (tunggal maupun tabel multi-pegawai), Lokasi & Waktu Penugasan. |
| **`DOM-05`** | **Berita Acara & Pakta Integritas / MOU** | Narasi pembuka hari/tanggal terbilang (`Pada hari ini ... tanggal ... bulan ... tahun ...`), Pihak Pertama (`PIHAK KESATU`), Pihak Kedua (`PIHAK KEDUA`), Saksi-saksi, Blok TTD Multi-Pihak. | Pembaruan tanggal terbilang & angka, identitas Pihak Kesatu & Kedua (Nama, NIP, Jabatan, Instansi), dan Saksi. |
| **`DOM-06`** | **Mail Merge / Generator Dokumen Massal (CSV/Excel ke Word)** | Dokumen template dengan token dinamis (`{{NAMA}}`, `{{NIP}}`, `<<JABATAN>>`) atau tabel daftar nama. | Menghasilkan puluhan/ratusan dokumen Word & PDF individual (1 baris Excel/CSV = 1 file SK/Surat/Sertifikat) dalam satu kali klik. |

## 4. Struktur Direktori Baru (File Tree Spesifik)

Berikut adalah rancangan pohon berkas (*file tree*) lengkap. Berkas bertanda `[EKSISTING - TIDAK DIUBAH]` tetap berada di posisinya, sedangkan berkas bertanda `[BARU]` adalah modul ekspansi yang bersifat *plug-and-play*:

```text
Documen-Replacer/
├── main.py                                  # [EKSISTING] Titik masuk aplikasi
├── Jalankan_Smart_RPP_Replacer.bat          # [EKSISTING] Launcher Windows
├── requirements.txt                         # [EKSISTING] Dependensi pustaka
│
├── config/                                  # Konfigurasi & Kamus
│   ├── aliases.json                         # [EKSISTING - TIDAK DIUBAH]
│   ├── dictionary.default.json              # [EKSISTING - TIDAK DIUBAH]
│   ├── signature_settings.example.json      # [EKSISTING - TIDAK DIUBAH]
│   │
│   ├── profiles/                            # [BARU] Definisi Profil Domain Dokumen (JSON)
│   │   ├── profile_registry.json            # [BARU] Daftar seluruh profil aktif & metadata UI
│   │   ├── rpp_modul_ajar.profile.json      # [BARU] Wrapper profil perangkat ajar (merujuk kamus lama)
│   │   ├── sk_keputusan.profile.json        # [BARU] Kamus label, pola regex konsiderans/diktum, & aturan SK
│   │   ├── surat_dinas.profile.json         # [BARU] Kamus atribut surat resmi (Nomor, Hal, Lampiran, Yth, Acara)
│   │   ├── surat_tugas_spt.profile.json     # [BARU] Kamus atribut SPT/SPPD & skema tabel pegawai
│   │   └── berita_acara_mou.profile.json    # [BARU] Kamus atribut Berita Acara, Pihak 1, Pihak 2, & Saksi
│   │
│   └── templates/                           # [BARU] Preset isian cepat & pola penomoran surat
│       ├── numbering_formats.json           # [BARU] Format nomor surat otomatis (mis: B-{no}/Kk.08.06/PP.00/{bln}/{thn})
│       └── presets_madrasah.example.json    # [BARU] Contoh data instansi FIKTIF (Kop, Kepala, alamat, kode satker). Data asli disimpan di folder pengguna, bukan di repo
│
├── document/                                # Lapisan Primitif I/O & XML Word
│   ├── __init__.py                          # [EKSISTING - TIDAK DIUBAH]
│   ├── docx_reader.py                       # [EKSISTING - TIDAK DIUBAH]
│   ├── docx_writer.py                       # [EKSISTING - TIDAK DIUBAH]
│   ├── header_footer_processor.py           # [EKSISTING - TIDAK DIUBAH]
│   ├── paragraph_processor.py               # [EKSISTING - TIDAK DIUBAH]
│   ├── table_processor.py                   # [EKSISTING - TIDAK DIUBAH]
│   │
│   └── extensions/                          # [BARU] Ekstensi Manipulasi Elemen Dokumen Lanjutan
│       ├── __init__.py                      # [BARU]
│       ├── kop_surat_processor.py           # [BARU] Pemindai & pengganti Kop Surat (Header maupun Tabel Baris Pertama)
│       ├── block_section_processor.py       # [BARU] Pemroses blok struktural (Menimbang/Mengingat/Diktum KESATU-KELIMA)
│       ├── attachment_table_processor.py    # [BARU] Pemroses Tabel Lampiran SK & Tabel Daftar Pegawai SPT
│       └── token_template_processor.py      # [BARU] Pemroses placeholder kurawal/sudut ({{FIELD}}, <<FIELD>>) lintas run
│
├── core/                                    # Mesin Inti Eksisting
│   ├── __init__.py                          # [EKSISTING - TIDAK DIUBAH]
│   ├── replacement_engine.py                # [EKSISTING - TIDAK DIUBAH]
│   ├── field_dictionary.py                  # [EKSISTING - TIDAK DIUBAH]
│   ├── label_recognizer.py                  # [EKSISTING - TIDAK DIUBAH]
│   ├── placeholder_detector.py              # [EKSISTING - TIDAK DIUBAH]
│   ├── exact_matcher.py                     # [EKSISTING - TIDAK DIUBAH]
│   ├── similarity_matcher.py                # [EKSISTING - TIDAK DIUBAH]
│   ├── signature_analyzer.py                # [EKSISTING - TIDAK DIUBAH]
│   ├── signature_image_service.py           # [EKSISTING - TIDAK DIUBAH]
│   ├── document_predictor.py                # [EKSISTING - TIDAK DIUBAH]
│   ├── validation_engine.py                 # [EKSISTING - TIDAK DIUBAH]
│   ├── change_verifier.py                   # [EKSISTING - TIDAK DIUBAH]
│   ├── doc_compat_service.py                # [EKSISTING - TIDAK DIUBAH]
│   └── pdf_converter/                       # [EKSISTING - TIDAK DIUBAH]
│
├── domains/                                 # [BARU] Lapisan Strategi & Analyzer Spesifik Jenis Dokumen
│   ├── __init__.py                          # [BARU]
│   ├── base_domain.py                       # [BARU] Abstract Base Class `BaseDocumentDomain` (Kontrak Plugin)
│   ├── domain_registry.py                   # [BARU] Registrasi & Auto-Detector jenis dokumen otomatis
│   ├── rpp_domain_adapter.py                # [BARU] Adapter yang membungkus `core.replacement_engine.ReplacementEngine`
│   ├── profile_loader.py                    # [BARU] Memuat *.profile.json: menggabungkan `inherit`, membaca zones/sync/auto_detect
│   ├── profile_driven_domain.py             # [BARU] Domain generik berbasis profil (label + zona) untuk jenis dokumen sederhana
│   │
│   ├── _shared/                             # [BARU] Pembantu bersama antar-domain
│   │   ├── __init__.py                      # [BARU]
│   │   ├── conflict_resolver.py             # [BARU] Menggabung/membuang usulan yang beririsan, termasuk lintas zona
│   │   └── validators.py                    # [BARU] Validator jenis nilai baru (doc_number, date_id, multiline_title)
│   │
│   ├── sk/                                  # [BARU] Paket Domain Surat Keputusan (SK)
│   │   ├── __init__.py                      # [BARU]
│   │   ├── sk_domain.py                     # [BARU] Orkestrator perencanaan & penerapan perubahan dokumen SK
│   │   ├── sk_header_analyzer.py            # [BARU] Detektor blok "SURAT KEPUTUSAN...", "NOMOR : ...", "TENTANG"
│   │   ├── diktum_analyzer.py               # [BARU] Detektor blok Menimbang, Mengingat, Memperhatikan, & KESATU..DST
│   │   ├── penetapan_signature_analyzer.py  # [BARU] Detektor blok "Ditetapkan di : ...", "Pada tanggal : ..."
│   │   └── lampiran_sk_analyzer.py          # [BARU] Detektor header Lampiran SK ("LAMPIRAN KEPUTUSAN...", Nomor, Tanggal)
│   │
│   ├── surat_dinas/                         # [BARU] Paket Domain Surat Resmi / Undangan / Pengantar
│   │   ├── __init__.py                      # [BARU]
│   │   ├── surat_domain.py                  # [BARU] Orkestrator perubahan Surat Dinas
│   │   ├── meta_surat_analyzer.py           # [BARU] Detektor blok Nomor, Sifat, Lampiran, Hal/Perihal, & Tujuan Yth.
│   │   └── agenda_block_analyzer.py         # [BARU] Detektor blok Hari/Tanggal, Waktu/Pukul, Tempat, & Acara
│   │
│   ├── spt/                                 # [BARU] Paket Domain Surat Perintah Tugas (SPT)
│   │   ├── __init__.py                      # [BARU]
│   │   ├── spt_domain.py                    # [BARU] Orkestrator perubahan SPT
│   │   └── pegawai_list_analyzer.py         # [BARU] Detektor daftar/tabel pegawai yang ditugaskan (Nama, NIP, Jabatan)
│   │
│   └── berita_acara/                        # [BARU] Paket Domain Berita Acara & MOU
│       ├── __init__.py                      # [BARU]
│       ├── ba_domain.py                     # [BARU] Orkestrator perubahan Berita Acara
│       ├── pihak_analyzer.py                # [BARU] Detektor blok PIHAK KESATU, PIHAK KEDUA, dan Saksi
│       └── tanggal_terbilang_helper.py      # [BARU] Konverter tanggal ke teks terbilang Indonesia otomatis
│
├── workflows/                               # [BARU] Orkestrator Alur Kerja Lintas Domain
│   ├── __init__.py                          # [BARU]
│   ├── unified_orchestrator.py              # [BARU] Facade pengganti-langsung `ReplacementEngine` di gui/app.py (API identik, §5.1)
│   ├── auto_classifier.py                   # [BARU] Klasifikasi jenis dokumen: skor berbobot + ambang + penanganan ambigu (§5.2)
│   ├── numbering_service.py                 # [BARU] Nomor surat/SK berurut; penghitung tersimpan di folder pengguna, aman untuk dry-run/batal
│   └── batch_mail_merge.py                  # [BARU] Mesin Mail-Merge dari tabel CSV/Excel ke dokumen Word & PDF
│
├── gui/                                     # Antarmuka Pengguna (Tkinter)
│   ├── app.py                               # [EKSISTING - Satu baris: self.engine = UnifiedOrchestrator(...) di balik feature flag + hook tab/selector opsional]
│   ├── replacement_view.py                  # [EKSISTING - TIDAK DIUBAH]
│   ├── preview_view.py                      # [EKSISTING - TIDAK DIUBAH, langsung kompatibel!]
│   ├── report_view.py                       # [EKSISTING - TIDAK DIUBAH, langsung kompatibel!]
│   ├── pdf_converter_view.py                # [EKSISTING - TIDAK DIUBAH]
│   ├── dictionary_dialog.py                 # [EKSISTING - TIDAK DIUBAH]
│   ├── signature_designer_dialog.py         # [EKSISTING - TIDAK DIUBAH]
│   │
│   └── modules/                             # [BARU] Komponen GUI Modular untuk Ekspansi Dokumen
│       ├── __init__.py                      # [BARU]
│       ├── domain_selector_bar.py           # [BARU] Pilihan jenis dokumen: [Otomatis | RPP/Modul | SK | Surat Dinas | SPT | Berita Acara]
│       ├── sk_editor_panel.py               # [BARU] Form terstruktur khusus SK (Nomor SK, Tentang, Diktum, Tgl Penetapan, Lampiran)
│       ├── surat_editor_panel.py            # [BARU] Form khusus Surat Dinas (Nomor, Hal, Tujuan Yth, Hari/Tgl, Waktu, Tempat)
│       └── mail_merge_view.py               # [BARU] Tab/Panel generator dokumen massal berbasis CSV/Excel
│
└── tests/                                   # Suite Pengujian
    ├── [ seluruh test_*.py eksisting ]      # [EKSISTING - TIDAK DIUBAH]
    ├── test_sk_domain.py                    # [BARU] Unit test deteksi & penggantian SK + Lampiran SK
    ├── test_surat_dinas_domain.py           # [BARU] Unit test deteksi & penggantian Surat Dinas/Undangan
    ├── test_spt_domain.py                   # [BARU] Unit test deteksi & penggantian Surat Tugas
    ├── test_auto_classifier.py              # [BARU] Unit test klasifikasi otomatis jenis dokumen
    ├── test_batch_mail_merge.py             # [BARU] Unit test generasi dokumen massal dari data tabular
    ├── test_ba_domain.py                    # [BARU] Berita Acara: PIHAK KESATU vs KEDUA tidak tertukar
    ├── test_tanggal_terbilang.py            # [BARU] Uji berbasis properti: angka <-> terbilang untuk 2000-2099
    ├── test_numbering_service.py            # [BARU] Penomoran berurut, dry-run, batal, duplikat
    ├── test_token_template.py               # [BARU] Token {{FIELD}} / <<FIELD>> terpecah di banyak run
    ├── test_profile_loader.py               # [BARU] Profil = berkas kamus v2 yang sah; inherit; skema tak dikenal ditolak
    ├── test_domain_contract.py              # [BARU] Item domain kompatibel dgn pratinjau & laporan; uji paritas RPP
    └── fixtures/
        └── make_sample_docs.py              # [BARU] Pembuat dokumen uji sintetis (python-docx); tanpa data nyata
```

> **[Catatan Revisi R12: perubahan pada struktur direktori]**
> - Ditambah `domains/profile_loader.py` dan `domains/profile_driven_domain.py`: tanpa keduanya janji "tambah JSON tanpa menulis kode Python" (§6) tidak punya pelaksana.
> - Ditambah `domains/_shared/` untuk pemecah konflik usulan lintas zona dan validator jenis nilai baru.
> - `presets_madrasah.json` menjadi `presets_madrasah.example.json` berisi data **fiktif**. Data instansi asli (kepala, alamat, kode satker) bersifat identitas dan disimpan di folder pengguna, bukan di repo (pelajaran dari riwayat repo sebelumnya).
> - Ditambah berkas uji yang belum ada dan `tests/fixtures/make_sample_docs.py`. Fixture dibuat dengan `python-docx`, bukan dokumen nyata, karena folder `docs/` tidak ikut repo dan tes yang bergantung padanya gagal di mesin lain.

## 5. Cara Kerja & Alur Arsitektur Baru (How It Works)

### 5.1. Kontrak Abstraksi Tunggal (`domains/base_domain.py`)

> **[Catatan Revisi R3: kontrak berbasis path]** Draf awal menerima objek `Document` pada `plan_changes`/`apply_changes`. Mesin yang berjalan bekerja berbasis **path**: `ReplacementEngine.plan_document_changes(in_path, rel_path, rules, mode, case_sensitive)` memuat dokumen sendiri, dan `apply_approved_changes(in_path, out_path, approved_items, signature_settings)` memuat ulang dari disk (alur *rencana → pratinjau → terapkan*). Kontrak domain disamakan dengan itu agar (1) `UnifiedOrchestrator` dapat menggantikan `ReplacementEngine` di `gui/app.py` tanpa mengubah pemanggilnya, dan (2) tidak ada objek `Document` yang dibagi antara tahap rencana dan penerapan.

Seluruh domain dokumen baru mengimplementasikan antarmuka standar `BaseDocumentDomain` yang menghasilkan objek **`ReplacementPlanItem`** yang **identik** dengan yang digunakan oleh `core/replacement_engine.py`:

```python
@dataclass(frozen=True)
class DetectResult:
    score: float                 # 0.0 - 1.0
    reasons: List[str]           # indikator yang cocok (ditampilkan saat klasifikasi ambigu)

class BaseDocumentDomain(ABC):
    domain_id: str               # contoh: "sk_keputusan", "surat_dinas", "rpp_modul"
    display_name: str            # contoh: "Surat Keputusan (SK)"

    @abstractmethod
    def detect_score(self, in_path: str) -> DetectResult: ...

    @abstractmethod
    def predict_fields(self, in_path: str) -> Dict[str, Any]:
        """Nilai saat ini di dokumen (untuk fitur 'Prediksi dari Dokumen')."""

    @abstractmethod
    def plan_document_changes(
        self, in_path: str, rel_path: str, rules: List[Dict[str, str]],
        mode: str = "GABUNGAN", case_sensitive: bool = True, **ctx
    ) -> List[ReplacementPlanItem]:
        """Setiap item WAJIB berisi target_meta["domain_id"] = self.domain_id."""

    @abstractmethod
    def apply_approved_changes(
        self, in_path: str, out_path: str, approved_items: List[ReplacementPlanItem],
        signature_settings: Optional[Dict[str, Any]] = None, **ctx
    ) -> int:
        """Menerapkan item yang disetujui; simpan lewat document.docx_writer.save_document."""

    # --- opsional (ada implementasi bawaan) ---
    def validate_item(self, item: ReplacementPlanItem) -> bool: return True
    def extra_checks(self, item: ReplacementPlanItem, actual_text: str) -> List[Dict[str, str]]: return []
    def reload_dictionary(self) -> None: ...
```

**Aturan kontrak** *(diuji oleh `tests/test_domain_contract.py`)*:

1. **Jenis target yang dikenali.** `ChangeReportGenerator._extract_actual_text` hanya tahu cara membaca hasil untuk jenis berikut; di luar daftar ini ia jatuh ke pencarian paragraf pertama yang memuat `new_text`, yang tidak andal.

   | `target_type` | Kunci `target_meta` yang wajib |
   | :--- | :--- |
   | `EXACT` | `para_idx` atau `all_para_idx` |
   | `PARAGRAPH_SPAN`, `TAB_LINE` | `para_idx` (+ `start`, `end` untuk `PARAGRAPH_SPAN`) |
   | `TABLE_CELL`, `TABLE_CELL_SPAN`, `TABLE_CELL_PARA`, `INSERT_SIGNATURE_TABLE` | `table_idx`, `row_idx`, `col_idx`, `para_idx` |
   | `HEADER_FOOTER` | `sec_idx`, `hf_attr`, `para_idx` |

   Domain **v1 dibatasi pada "ganti teks di tempat"**. Operasi struktur (hapus/duplikasi baris tabel, tambah paragraf diktum) baru boleh pada Fase 3 dan harus disertai `extra_checks`, karena laporan belum memahaminya.
2. **Penanda domain.** Setiap item membawa `target_meta["domain_id"]`. `ReplacementPlanItem` tidak diubah; `UnifiedOrchestrator` memakai penanda ini untuk meneruskan item yang disetujui ke domain yang benar, dan item tanpa penanda dianggap RPP.
3. **`UnifiedOrchestrator` adalah pengganti langsung `ReplacementEngine`.** Ia menyediakan nama dan tanda tangan metode yang kini dipanggil `gui/app.py`: `plan_document_changes`, `apply_approved_changes`, `process_file`, `reload_dictionary`, `reload_signature_settings`. Penyambungan di `app.py` cukup satu baris dan dapat dimatikan lewat *feature flag*.
4. **Validasi tipe.** `validate_type_safety` memeriksa *substring* nama kategori (`NIP`, `Nama`, `Titimangsa`, `Tahun`). Kategori baru (`Nomor SK`, `Tanggal Penetapan`, ...) tidak tercakup, maka orchestrator memanggil `domain.validate_item()` sebelum item masuk pratinjau; item yang ditolak diberi keyakinan `NONE`.
5. **Jenis nilai baru tanpa mengubah `FieldDictionary`.** `doc_number`, `multiline_title`, dan `date_id` tidak dikenal `FieldDictionary.validate_value`; jenis yang tak dikenal **lolos tanpa peringatan** (bukan galat; sudah diuji). Validasinya ditaruh di domain (`domains/_shared/validators.py`) dan disalurkan ke laporan lewat `extra_checks`.

Dengan kontrak di atas:
- **Dialog Pratinjau Terpadu (`gui/preview_view.py`)** bekerja tanpa perubahan karena hanya membaca `ReplacementPlanItem`.
- **Laporan Perubahan JSON (`core/change_verifier.py` & `services/report_service.py`)** dapat memverifikasi item domain baru selama aturan 1 dipenuhi. Pemeriksaan khusus domain (mis. `SINKRON_ANTAR_ZONA`, `TANGGAL_TERBILANG_TIDAK_SINKRON`) masuk lewat `extra_checks`; untuk itu `ChangeReportGenerator.generate_report(...)` diberi **satu parameter opsional** `extra_checks=None` (pengecualian 4c: bila `None`, perilakunya tidak berubah).
- **Mesin Konversi PDF (`core/pdf_converter/`)** langsung dapat mengekspor hasil SK dan Surat Dinas ke PDF.

### 5.2. Klasifikasi Dokumen Otomatis (`workflows/auto_classifier.py`)

> **[Catatan Revisi R4: klasifikasi]** Draf awal (a) mengarahkan dokumen yang tidak cocok ke RPP secara bawaan, dan (b) memakai kata kunci tunggal yang saling tumpang tindih: `KESATU` ada di diktum SK sekaligus di `PIHAK KESATU` pada Berita Acara, dan `Nomor :` ada di hampir semua surat. Akibatnya SK dapat salah masuk Berita Acara, dan dokumen yang tak dikenal (piagam, surat keterangan) diproses kamus RPP yang bisa mengganti isian yang tidak semestinya. Diganti dengan skor berbobot, ambang, dan penanganan ambigu.

Ketika pengguna memilih mode **"Deteksi Otomatis (Semua Dokumen)"** pada sebuah folder yang berisi campuran file RPP, SK, dan Surat Undangan:
1. `AutoClassifier` membaca **30 paragraf pertama, seluruh tabel, header (kop), dan isi kotak teks**, lalu menghitung skor tiap domain dari indikator pada profil (`auto_detect`, §6): `skor = (3·kuat + 1·lemah − 2·negatif) / 9`, dibatasi 0..1. Pencocokan berbatas-kata dan, untuk judul, hanya pada awal paragraf.
2. Indikator awal (dikalibrasi ulang dengan korpus uji):

   | Domain | Kuat (bobot 3) | Lemah (bobot 1) | Negatif (bobot −2) |
   | :--- | :--- | :--- | :--- |
   | `DOM-01` RPP/Modul | `Modul Ajar`, `Rencana Pelaksanaan Pembelajaran`, `Capaian Pembelajaran`, `Tujuan Pembelajaran` | `Kompetensi Dasar`, `Alokasi Waktu`, `Mata Pelajaran`, `Fase` | `MEMUTUSKAN` |
   | `DOM-02` SK | `SURAT KEPUTUSAN`, `KEPUTUSAN KEPALA`, `MEMUTUSKAN` | `Menimbang`, `Mengingat`, `Menetapkan`, paragraf berawalan `KESATU`, `Ditetapkan di` | `PIHAK KESATU`, `BERITA ACARA` |
   | `DOM-03` Surat Dinas | `Kepada Yth`, `Perihal` / `Hal` | `Nomor`, `Lampiran`, `Sifat`, `Hormat kami`, `Wassalam` | `MEMUTUSKAN`, `Menugaskan` |
   | `DOM-04` SPT | `SURAT PERINTAH TUGAS`, `SURAT TUGAS`, `Menugaskan kepada` | `Pangkat/Gol`, `Berangkat`, `SPPD` | `MEMUTUSKAN` |
   | `DOM-05` Berita Acara/MOU | `BERITA ACARA`, `PIHAK KESATU` **dan** `PIHAK KEDUA`, `PAKTA INTEGRITAS` | `Pada hari ini`, `Saksi` | `MEMUTUSKAN` |

3. **Keputusan:** domain dengan skor tertinggi dipilih bila skor ≥ 0,6 **dan** selisihnya dengan peringkat kedua ≥ 0,2.
4. **Bila tidak memenuhi** (tidak dikenali atau ambigu): dokumen ditandai **"Perlu dipilih"**. GUI meminta pengguna memilih domain, satu kali per kelompok berkas serupa, dan **tidak** diam-diam memakai RPP. Tersedia **"Mode aman"** yang hanya menjalankan pencocokan teks persis (`EXACT`) tanpa deteksi berbasis label.
5. Hasil klasifikasi (domain, skor, alasan) dicatat di laporan agar pengguna dapat memeriksa mengapa suatu dokumen diproses sebagai domain tertentu.

### 5.3. Cara Kerja Spesifik pada Domain Baru

#### A. Domain Surat Keputusan (`domains/sk/`)
Dokumen SK memiliki tantangan unik yang berbeda dari RPP karena satu dokumen SK sering memuat **satu nilai yang sama di beberapa zona struktural berbeda** (di Judul SK, di Diktum, dan di Header Lampiran SK):
1. **`sk_header_analyzer.py`:** Mengenali pola judul terpusat di bawah kata `NOMOR : ...` dan setelah kata `TENTANG` (yang biasanya berada pada paragraf terpisah tanpa tanda titik dua `:`).
2. **`diktum_analyzer.py`:** Mengenali tabel tanpa garis (*borderless table*) atau paragraf bertabulasi pada bagian `Menimbang :`, `Mengingat :`, `Memperhatikan :`, serta diktum `KESATU :`, `KEDUA :`, dst.
3. **`penetapan_signature_analyzer.py`:** Mengenali zona penetapan SK yang menggunakan frasa:
   - `Ditetapkan di : [Tempat]`
   - `Pada tanggal : [Tanggal]`
   (Berbeda dengan RPP yang menggunakan format satu baris `Kota Agung, 14 November 2026`).
4. **`lampiran_sk_analyzer.py`:** Mendeteksi blok pojok kanan atas pada halaman lampiran (`Lampiran Keputusan Kepala ...`, `Nomor : ...`, `Tanggal : ...`) dan secara otomatis menyinkronkan Nomor SK, Judul Tentang SK, serta Tanggal Penetapan dari halaman utama SK ke seluruh halaman Lampiran SK!

> **[Catatan Revisi R5: sinkronisasi antar-zona]** Nilai yang sama (Nomor, Tentang, Tanggal) muncul di beberapa zona, sehingga satu paragraf dapat menerima lebih dari satu usulan. Aturannya: (1) nilai **sumber** diambil dari `source_zone` pada bagian `sync` profil (§6) lalu disalin ke `target_zones`; (2) usulan lintas zona yang rentangnya beririsan pada paragraf yang sama digabung, atau yang kalah dibuang oleh `domains/_shared/conflict_resolver.py`, bukan dibiarkan bertumpuk; (3) setelah penerapan, nilai di semua zona dibandingkan lagi dan perbedaan dilaporkan sebagai `SINKRON_ANTAR_ZONA`. Catatan lain: kamus RPP bawaan sudah memuat frasa `Ditetapkan di` (untuk Titimangsa). Itu tidak bentrok selama SK memakai kamus profilnya sendiri, tetapi itulah alasan SK tidak boleh jatuh ke domain RPP (§5.2).

#### B. Domain Surat Dinas & Undangan (`domains/surat_dinas/`)
1. **`meta_surat_analyzer.py`:** Mengenali blok atribut surat di kiri atas (`Nomor`, `Sifat`, `Lampiran`, `Hal`/`Perihal`) baik yang ditulis menggunakan tabulasi (`Nomor \t: ...`) maupun tabel 2/3 kolom, serta blok tujuan surat (`Kepada Yth. ... di Tempat`).
2. **`agenda_block_analyzer.py`:** Mengenali blok waktu/tempat kegiatan (`Hari, Tanggal`, `Waktu`/`Pukul`, `Tempat`, `Acara`) di tengah isi surat tanpa salah mengganti teks tanggal surat di bagian atas.
3. **Penomoran Otomatis (`workflows/numbering_service.py`):** Mendukung token variabel seperti `{NO_URUT:03d}`, `{BULAN_ROMAWI}`, dan `{TAHUN}` sehingga saat memproses 20 surat sekaligus di dalam folder, nomor surat dapat diisi otomatis berurutan (`001`, `002`, ..., `020`).

> **[Catatan Revisi R6: kop surat & penomoran]**
> - **Kop surat** sering berupa kotak teks, gambar, atau *content control*, bukan paragraf biasa. `iter_all_paragraphs` menelusuri semua `w:p` (termasuk isi kotak teks), sedangkan `doc.paragraphs` tidak. `kop_surat_processor` harus memakai **satu cara penelusuran yang sama** untuk rencana, penerapan, dan verifikasi, serta menghindari penghitungan ganda pada `mc:AlternateContent` (cabang *Choice* dan *Fallback* memuat teks yang sama). Fixture uji untuk ketiganya wajib ada.
> - **Penomoran berurut harus tahan batal dan *dry-run*.** Penghitung disimpan per jenis + tahun di folder pengguna (bukan di repo) dan ditulis secara atomik. Pratinjau hanya **menampilkan** nomor yang *akan* dipakai (mis. `001`-`020`) tanpa mengonsumsinya; nomor dikonsumsi saat penerapan berhasil dan dikembalikan bila proses dibatalkan. Nomor yang sudah ada di folder hasil diberi peringatan duplikat. Pengguna dapat menetapkan nomor awal secara manual.

#### C. Domain Surat Tugas / SPT (`domains/spt/`)
1. **`pegawai_list_analyzer.py`:** Mengenali dua variasi tata letak SPT yang umum di madrasah/sekolah:
   - **SPT Tunggal (Format Titik Dua):** `Nama : ...`, `NIP : ...`, `Pangkat/Gol. Ruang : ...`, `Jabatan : ...`.
   - **SPT Kolektif (Format Tabel):** Tabel dengan kolom `No | Nama / NIP | Pangkat / Gol | Jabatan | Keterangan`.

> **[Catatan Revisi R7: data multi-pegawai]** Format aturan saat ini `{"label","old","new"}` per baris tidak dapat menampung daftar pegawai. Ditambahkan jalur data terpisah yang **kompatibel mundur**: `plan_document_changes(..., datasets={"pegawai": [{"nama": "...", "nip": "...", "pangkat_gol": "...", "jabatan": "..."}, ...]})`. Aturan label biasa tetap lewat `rules`. Untuk SPT kolektif, jumlah baris tabel dibandingkan dengan jumlah record dan selisihnya dilaporkan (`JUMLAH_BARIS_TIDAK_SAMA`). Fase 3 dimulai dengan **mengisi baris yang sudah ada**; menambah/menghapus baris adalah operasi struktur (§5.1 aturan 1) dan menyusul setelah laporan perubahan memahaminya.

#### D. Domain Berita Acara & Tanggal Terbilang (`domains/berita_acara/`)
1. **`tanggal_terbilang_helper.py`:** Ketika pengguna memasukkan tanggal `2026-11-14`, helper secara otomatis membangkitkan teks kalimat pembuka Berita Acara:
   > *"Pada hari ini **Sabtu** tanggal **Empat Belas** bulan **November** tahun **Dua Ribu Dua Puluh Enam** (14-11-2026)..."*
   dan mengganti span hari, tanggal, bulan, serta tahun terbilang secara presisi.
2. **`pihak_analyzer.py`:** Membedakan atribut `Nama`, `NIP`, dan `Jabatan` milik **PIHAK KESATU** dan **PIHAK KEDUA** berdasarkan zona urutan paragraf (`anchor-based zone scoping`), sehingga `Nama` Pihak Kesatu dan `Nama` Pihak Kedua tidak tertukar meskipun memiliki label teks yang sama-sama bertuliskan `Nama : ...`.

> **[Catatan Revisi R8: tanggal terbilang]** Angka dan terbilang harus **selalu sinkron**. Uji berbasis properti: untuk setiap tanggal 2000-2099, `terbilang → angka` kembali ke tanggal semula; nama hari dihitung dari tanggal (bukan diketik pengguna); kapitalisasi (`Empat Belas` vs `empat belas`) dapat diatur di profil. Ketidaksinkronan setelah penerapan dilaporkan sebagai `TANGGAL_TERBILANG_TIDAK_SINKRON`. Karena teks terbilang dapat terpecah di banyak *run*, penggantian memakai `replace_span` yang sudah ada.

#### E. Mail Merge / Generator Massal (`workflows/batch_mail_merge.py`, DOM-06)

> **[Catatan Revisi R9: bagian baru]** DOM-06 ada di tabel §3 tetapi belum dijelaskan cara kerjanya. Berbeda dari domain lain (mengganti nilai pada dokumen **yang sudah terisi**), mail merge **membuat banyak dokumen dari satu templat**, sehingga kebutuhannya lain:

1. **Templat & token.** `{{NAMA}}`, `<<JABATAN>>`, dan `{{NIP}}` dapat terpecah di beberapa *run*; `token_template_processor.py` menggabungkan dan menggantinya dengan mempertahankan gaya run pertama. Token yang tidak punya kolom data dilaporkan, tidak dibiarkan tertinggal di dokumen.
2. **Sumber data.** CSV (UTF-8 dengan/tanpa BOM; pemisah `,` atau `;` dideteksi) dan Excel `.xlsx` (memerlukan `openpyxl`, **dependensi opsional** yang diimpor saat dibutuhkan dengan pesan jelas bila belum terpasang). Baris pertama adalah nama kolom.
3. **Pratinjau & validasi sebelum menghasilkan.** Tampilkan 3-5 baris pertama sebagai dokumen contoh; validasi semua baris (kolom wajib kosong, NIP tak lazim, token tanpa kolom) dan tampilkan ringkasan galat **sebelum** satu berkas pun ditulis.
4. **Penamaan berkas.** Pola nama dari kolom (mis. `SK_{NAMA}_{NO}`) wajib disanitasi: buang karakter terlarang Windows, batasi panjang, cegah *path traversal* (`..`, `\`, `/`), dan beri akhiran `_2`, `_3` untuk nama kembar.
5. **Hasil.** Satu baris = satu `.docx` (opsional + `.pdf` lewat modul konversi yang ada) di folder hasil; kemajuan dan tombol batal mengikuti pola *thread + queue* GUI yang sudah ada; ringkasan berhasil/gagal per baris ditulis ke `_laporan/`.
6. **Privasi.** Data CSV/Excel memuat nama dan NIP: tidak pernah disalin ke repo, log memakai mode anonim, dan berkas contoh hanya berisi data fiktif.

## 6. Spesifikasi Skema Profil Domain (`config/profiles/*.profile.json`)

> **[Catatan Revisi R10: skema profil diselaraskan dengan kamus v2]** Draf awal memakai kunci sendiri (`synonyms` datar, tipe `year_range_or_single`, serta `Tanggal`/`TA`/`TP` sebagai sinonim biasa). Itu akan mengulang masalah yang sudah diselesaikan pada `FieldDictionary` v2: sinonim pendek dan umum (`TP`, `Tanggal`, `Nomor`) harus berupa `exact_only_synonyms`, dan label berbahaya harus masuk `never_match`/`global_never_match`, kalau tidak teks yang salah ikut tertimpa (mis. `Tanggal Lahir`, `Nomor Rekening`). Skema di bawah memakai **kunci yang sama dengan `FieldDictionary` v2 pada tingkat akar**. Akibatnya penting: **berkas profil sekaligus berkas kamus yang sah.** `FieldDictionary.load(default_path="config/profiles/sk_keputusan.profile.json")` langsung memuatnya, sedangkan kunci tambahan (`zones`, `sync`, `auto_detect`, `inherit`) diabaikan pemuat kamus dan dibaca oleh `profile_loader.py`. *(Sudah diuji: contoh di bawah termuat tanpa galat, `validate_integrity()` kosong, `Nomor Rekening` dan `Tanggal Lahir` tidak dikenali, dan `TP`/`Tanggal` hanya cocok sebagai label tunggal.)*

Agar penambahan jenis dokumen baru di masa depan (misalnya Surat Keterangan Aktif Sekolah, Surat Pindah/Mutasi, atau SPJ BOS) dapat dilakukan **cukup dengan menambah file JSON** untuk dokumen yang strukturnya sederhana, setiap profil domain mengikuti skema deklaratif berikut:

```json
{
  "schema_version": 2,
  "profile_id": "sk_keputusan",
  "display_name": "Surat Keputusan (SK)",
  "description": "Profil untuk SK Kepala Madrasah/Sekolah, SK Panitia, dan SK Pembagian Tugas",
  "inherit": {
    "from": "config/dictionary.default.json",
    "fields": ["nama_lembaga", "jabatan_kepala", "nama_kepala", "nip_kepala"]
  },
  "auto_detect": {
    "strong": ["SURAT KEPUTUSAN", "KEPUTUSAN KEPALA", "MEMUTUSKAN"],
    "weak": ["Menimbang", "Mengingat", "Menetapkan", "KESATU", "Ditetapkan di"],
    "negative": ["PIHAK KESATU", "BERITA ACARA"]
  },
  "global_never_match": ["nomor rekening", "nomor telepon", "tanggal lahir", "tempat lahir"],
  "global_ignore_exact": [],
  "fields": [
    {
      "id": "nomor_sk", "category": "Nomor SK", "display_label": "Nomor SK", "value_type": "doc_number",
      "match_mode": "word_boundary", "priority": 50,
      "synonyms": ["nomor sk", "nomor keputusan", "no sk"],
      "exact_only_synonyms": ["nomor", "no"],
      "never_match": ["nomor induk pegawai", "nomor surat"]
    },
    {
      "id": "tentang_sk", "category": "Tentang SK", "display_label": "Tentang / Judul SK", "value_type": "multiline_title",
      "match_mode": "word_boundary", "priority": 50,
      "synonyms": ["tentang sk", "judul sk"],
      "exact_only_synonyms": ["tentang"],
      "never_match": []
    },
    {
      "id": "tahun_anggaran", "category": "Tahun Anggaran", "display_label": "Tahun Anggaran", "value_type": "year_single",
      "match_mode": "word_boundary", "priority": 50,
      "synonyms": ["tahun anggaran"],
      "exact_only_synonyms": [],
      "never_match": ["tahun lahir"]
    },
    {
      "id": "tahun_pelajaran", "category": "Tahun Ajaran", "display_label": "Tahun Pelajaran", "value_type": "year_range",
      "match_mode": "word_boundary", "priority": 50,
      "synonyms": ["tahun pelajaran", "tahun ajaran"],
      "exact_only_synonyms": ["ta", "tp"],
      "never_match": ["output"]
    },
    {
      "id": "tempat_penetapan", "category": "Tempat Penetapan", "display_label": "Tempat Penetapan", "value_type": "text",
      "match_mode": "word_boundary", "priority": 50,
      "synonyms": ["ditetapkan di", "dikeluarkan di"],
      "exact_only_synonyms": [],
      "never_match": []
    },
    {
      "id": "tanggal_penetapan", "category": "Tanggal Penetapan", "display_label": "Tanggal Penetapan", "value_type": "date_id",
      "match_mode": "word_boundary", "priority": 50,
      "synonyms": ["pada tanggal", "tanggal penetapan", "ditetapkan pada tanggal"],
      "exact_only_synonyms": ["tanggal"],
      "never_match": ["tanggal lahir", "tanggal masuk"]
    }
  ],
  "zones": [
    {"zone_id": "judul_sk", "start_anchor": "NOMOR", "end_anchor": "TENTANG", "max_paragraphs": 8,
     "fields": ["nomor_sk", "tentang_sk"]},
    {"zone_id": "penetapan_sk", "anchors": ["Ditetapkan di", "Pada tanggal"], "max_paragraphs": 15,
     "fields": ["tempat_penetapan", "tanggal_penetapan", "jabatan_kepala", "nama_kepala", "nip_kepala"]},
    {"zone_id": "lampiran_header", "anchors": ["LAMPIRAN KEPUTUSAN", "Lampiran SK"], "repeat": true,
     "label_map": {"Nomor": "nomor_sk", "Tanggal": "tanggal_penetapan", "Tentang": "tentang_sk"}}
  ],
  "sync": [
    {"field": "nomor_sk", "source_zone": "judul_sk", "target_zones": ["lampiran_header"]},
    {"field": "tentang_sk", "source_zone": "judul_sk", "target_zones": ["lampiran_header"]},
    {"field": "tanggal_penetapan", "source_zone": "penetapan_sk", "target_zones": ["lampiran_header"]}
  ]
}
```

**Catatan skema**

| Kunci | Fungsi |
| :--- | :--- |
| `schema_version` | Versi skema profil (`2`). Versi tak dikenal → profil ditolak dengan pesan yang jelas |
| `inherit` | Memakai ulang field dari kamus lain (mis. `nama_kepala`, `nip_kepala`) agar **kategori dan perlindungannya sama** dengan RPP. Digabung oleh `profile_loader.py`; tidak dikenal oleh `FieldDictionary` |
| `auto_detect` | Indikator `strong` / `weak` / `negative` untuk `AutoClassifier` (§5.2) |
| `fields[]` | Persis skema `FieldDictionary` v2: `id`, `category`, `display_label`, `value_type`, `match_mode`, `priority`, `synonyms`, `exact_only_synonyms`, `never_match` |
| `zones[]` | Wilayah dokumen: `start_anchor`/`end_anchor` atau `anchors`; `max_paragraphs` (batas agar zona tidak "bocor" ke bagian lain); `fields`; `repeat` (zona muncul di banyak halaman, mis. header lampiran); `label_map` (label di dokumen → id field) |
| `sync[]` | Salin nilai dari `source_zone` ke `target_zones` (§5.3-A) |

**Jenis nilai.** Jenis yang sudah ada (`text`, `person_name`, `nip`, `year_single`, `year_range`, `date_place`, `semester`, `role_title`) divalidasi oleh `FieldDictionary`. Jenis baru `doc_number`, `multiline_title`, dan `date_id` divalidasi oleh `domains/_shared/validators.py` (§5.1 aturan 5). `year_range_or_single` pada draf awal dipecah menjadi dua field (`tahun_anggaran` = `year_single`, `tahun_pelajaran` = `year_range`) agar format hasil tidak ambigu (`2026` vs `2026/2027`).

**Batas "tanpa kode Python baru".** Berlaku untuk dokumen yang strukturnya cukup digambarkan dengan **label + zona** (Surat Keterangan, SPJ sederhana), dilayani `ProfileDrivenDomain`. Struktur yang butuh logika (diktum bertingkat, PIHAK KESATU/KEDUA, tabel pegawai) tetap memerlukan analyzer Python. Profil tidak boleh berkembang menjadi bahasa pemrograman: bila butuh kondisi atau perulangan, tulis analyzer.

## 7. Integrasi Bertahap Tanpa Mengubah Kode Eksisting (Migration & Rollout Plan)

> **[Catatan Revisi R11: urutan fase]** Pada draf awal seluruh `document/extensions/*` ada di Fase 3, padahal SK dan Surat Dinas (Fase 2) membutuhkan `kop_surat_processor`, `block_section_processor`, dan `attachment_table_processor`. `auto_classifier.py` dan `numbering_service.py` tidak masuk fase mana pun, `token_template_processor.py` hanya dipakai Mail Merge, dan "0% perubahan" belum punya cara pembuktian. Tabel di bawah memperbaiki urutan dan menambah **Kriteria Selesai** yang dapat diuji.

| Tahap | Fokus Pengembangan | File yang Ditambahkan | Dampak pada Kode Eksisting (`core/`, `document/`, `gui/`) | Kriteria Selesai (DoD) |
| :--- | :--- | :--- | :--- | :--- |
| **Fase 1: Fondasi & Adapter** | Kontrak `BaseDocumentDomain`, `DomainRegistry`, `RPPDomainAdapter`, `UnifiedOrchestrator`, klasifikasi dasar, pemuat profil. | `domains/base_domain.py`, `domain_registry.py`, `rpp_domain_adapter.py`, `profile_loader.py`, `profile_driven_domain.py`, `domains/_shared/*`, `workflows/unified_orchestrator.py`, `workflows/auto_classifier.py`, `config/profiles/profile_registry.json`, `rpp_modul_ajar.profile.json`, `tests/fixtures/make_sample_docs.py`, `test_domain_contract.py`, `test_profile_loader.py`, `test_auto_classifier.py` | **0%.** `gui/app.py` belum disentuh; orchestrator diuji lewat tes. | Semua tes eksisting hijau. **Uji paritas:** `UnifiedOrchestrator` dengan hanya domain RPP menghasilkan rencana dan hasil yang identik dengan `ReplacementEngine` pada korpus RPP sintetis. |
| **Fase 2: Domain SK & Surat Dinas** | Analyzer SK (Nomor, Tentang, Konsiderans, Diktum, Penetapan, Lampiran) dan Surat Dinas (Nomor, Hal, Tujuan, Blok Acara); penomoran. | `domains/sk/*`, `domains/surat_dinas/*`, `config/profiles/sk_keputusan.profile.json`, `surat_dinas.profile.json`, `document/extensions/kop_surat_processor.py`, `block_section_processor.py`, `attachment_table_processor.py` (baca + sinkron header lampiran), `workflows/numbering_service.py`, `config/templates/numbering_formats.json`, `presets_madrasah.example.json`, `test_sk_domain.py`, `test_surat_dinas_domain.py`, `test_numbering_service.py` | Tidak ada perubahan logika `core/` dan `document/`. **Satu baris** di `gui/app.py` (di balik *feature flag*, mati secara bawaan) dan satu parameter opsional `extra_checks` pada `ChangeReportGenerator` (§5.1). | Korpus SK dan Surat Dinas lulus dengan **0 butir `SALAH`** di laporan perubahan; `SINKRON_ANTAR_ZONA` = 0; tanggal surat tidak tertukar dengan tanggal acara; fixture kotak teks dan `AlternateContent` lulus. |
| **Fase 3: Domain SPT & Berita Acara** | Zona multi-pihak (`PIHAK KESATU` vs `PIHAK KEDUA`), tanggal terbilang, tabel daftar pegawai SPT (isi baris yang ada dahulu). | `domains/spt/*`, `domains/berita_acara/*`, `tanggal_terbilang_helper.py`, perluasan `attachment_table_processor.py`, `test_spt_domain.py`, `test_ba_domain.py`, `test_tanggal_terbilang.py` | **0%** pada kode lama. | Pihak Kesatu/Kedua tidak tertukar; angka dan terbilang sinkron untuk semua tanggal 2000-2099; jumlah baris SPT = jumlah record data. |
| **Fase 4: Integrasi UI Modular & Mail Merge** | Bar pemilih jenis dokumen (`domain_selector_bar.py`), panel editor SK/Surat, tab Mail Merge CSV/Excel. | `gui/modules/*`, `workflows/batch_mail_merge.py`, `document/extensions/token_template_processor.py`, `test_batch_mail_merge.py`, `test_token_template.py` | Registrasi komponen baru di `gui/app.py`; view eksisting tidak diubah. | Pratinjau dan validasi seluruh baris sebelum menulis; penamaan berkas aman; membatalkan di tengah proses tidak meninggalkan berkas setengah jadi. |

## 8. Kriteria Penerimaan Lintas Domain

> **[Catatan Revisi R13: bagian baru §8-§11]** PRD awal belum memuat kriteria penerimaan, risiko, batasan cakupan, dan pertanyaan terbuka. Ditambahkan secara ringkas agar tiap fase punya ukuran selesai yang sama.

| Aspek | Kriteria | Cara menguji |
| :--- | :--- | :--- |
| Regresi | Seluruh tes eksisting hijau pada setiap fase | CI |
| Paritas RPP | Orchestrator dengan domain RPP identik dengan `ReplacementEngine` | `test_domain_contract.py` |
| Kebenaran hasil | **0 butir `SALAH`** di Laporan Perubahan pada korpus sintetis tiap domain | `ChangeReportGenerator` |
| Klasifikasi | ≥ 95% benar pada 100 dokumen sintetis (20 per domain), dan **0 salah-arah diam-diam**: kasus ragu harus berstatus "Perlu dipilih" | `test_auto_classifier.py` |
| Konsistensi SK | Nomor, Tentang, dan Tanggal identik di judul, diktum, dan lampiran | bendera `SINKRON_ANTAR_ZONA` |
| Privasi | Tidak ada nama/NIP/identitas instansi asli di repo, fixture, dan contoh | pemindaian pola + tinjauan |
| Kinerja | Belum ada angka dasar. Waktu per dokumen dan per batch 100 dokumen diukur pada akhir Fase 2, lalu target ditetapkan | benchmark |

## 9. Risiko & Mitigasi

| # | Risiko | Mitigasi |
| :--- | :--- | :--- |
| 1 | Dokumen salah klasifikasi lalu diproses kamus yang keliru | Skor berbobot + ambang + status "Perlu dipilih"; tanpa fallback diam-diam ke RPP (§5.2) |
| 2 | Kop/judul berada di kotak teks, `AlternateContent`, atau *content control* sehingga tak terbaca atau terganti ganda | Satu cara penelusuran untuk rencana/penerapan/verifikasi; fixture uji khusus (§5.3-B) |
| 3 | Nilai yang sama di banyak zona menimbulkan usulan bertumpuk | `conflict_resolver` bersama + bendera `SINKRON_ANTAR_ZONA` (§5.3-A) |
| 4 | Data pribadi bocor lewat presets, CSV, atau profil | Hanya contoh fiktif di repo; data asli di folder pengguna; `.gitignore`; mode anonim pada log dan laporan |
| 5 | Profil JSON tumbuh menjadi "bahasa pemrograman" | Dibatasi pada label + zona; logika kompleks tetap analyzer Python; `schema_version` (§6) |
| 6 | Nomor surat terpakai padahal proses dibatalkan | Nomor dikonsumsi saat penerapan berhasil, dikembalikan bila batal; pratinjau tidak mengonsumsi (§5.3-B) |
| 7 | Dependensi baru (`openpyxl`) memberatkan pemasangan | Opsional, diimpor saat dibutuhkan, pesan jelas bila belum ada |
| 8 | Regresi pada alur RPP yang sudah stabil | Uji paritas, *feature flag* mati secara bawaan, titik penyambungan hanya satu |
| 9 | Dokumen `.doc` lama pada domain baru | Memakai `doc_compat_service` yang sudah ada; hasil akhir `.docx` secara bawaan |

## 10. Di Luar Cakupan (Non-Goals)

- OCR atau pembacaan dokumen hasil pindai/PDF sebagai masukan.
- Tanda tangan elektronik tersertifikasi atau verifikasi keabsahan dokumen.
- Penyusunan isi naratif dokumen oleh AI; yang diotomasi hanya penggantian dan pengisian data yang sudah ditentukan pengguna.
- Penyimpanan/sinkronisasi cloud, arsip surat masuk-keluar, atau manajemen disposisi.
- Editor templat visual; templat tetap dibuat pengguna di MS Word.

## 11. Pertanyaan Terbuka

1. Apakah satu folder boleh berisi campuran domain pada rilis pertama, atau cukup satu domain per proses (lebih sederhana dan lebih aman)?
2. Format nomor surat/SK resmi apa yang berlaku untuk madrasah pengguna (kode klasifikasi, kode satker)? Ini menentukan isi `numbering_formats.json`.
3. Prioritas sumber data Mail Merge: CSV saja dulu, atau Excel `.xlsx` sejak awal?
4. Apakah Lampiran SK perlu *mail merge* per baris (mis. satu daftar tugas per guru), atau cukup sinkronisasi header?
5. Apakah stempel/gambar kop perlu diganti otomatis, atau hanya teks?

## 12. Riwayat Revisi

| Kode | Bagian | Perubahan | Alasan |
| :--- | :--- | :--- | :--- |
| (kecil) | Judul, §1, §4 | Tautan GitHub yang rusak diperbaiki; salah ketik `└──presets...` | Kerapian |
| R1 | §1 | Catatan baseline: apa yang sudah ada dan yang masih rencana | Menghindari asumsi keliru tentang kondisi repo |
| R2 | §2 | Pengecualian terkontrol atas "tidak mengubah kode lama" + kontrak sampai ke verifikasi | Klaim "0% perubahan" tak dapat diuji tanpa batas yang jelas |
| R3 | §5.1 | Kontrak diubah dari berbasis `Document` menjadi berbasis path, disamakan dengan `ReplacementEngine`; ditambah aturan jenis target, penanda domain, orchestrator pengganti-langsung, validasi tipe, jenis nilai baru | Mesin nyata bekerja dengan path; tanpa ini orchestrator tidak bisa menggantikan engine dan laporan tidak dapat membaca hasil domain |
| R4 | §5.2 | Klasifikasi: kata kunci tunggal diganti skor berbobot + ambang + "Perlu dipilih"; fallback otomatis ke RPP dihapus | `KESATU` ambigu antara SK dan Berita Acara; dokumen tak dikenal tidak boleh diproses kamus RPP |
| R5 | §5.3-A | Aturan sinkronisasi antar-zona | Satu nilai di banyak zona rawan usulan bertumpuk |
| R6 | §5.3-B | Kop dalam kotak teks/`AlternateContent`; penomoran tahan batal dan dry-run | Kasus nyata kop surat; nomor tidak boleh terpakai sia-sia |
| R7 | §5.3-C | Jalur `datasets` untuk multi-pegawai | Format aturan `{label, old, new}` tidak dapat menampung daftar |
| R8 | §5.3-D | Uji properti dan bendera sinkron untuk tanggal terbilang | Angka dan terbilang harus selalu sama |
| R9 | §5.3-E | Cara kerja Mail Merge (token, sumber data, validasi, penamaan aman, privasi) | DOM-06 belum dijelaskan sama sekali |
| R10 | §6 | Skema profil diselaraskan dengan `FieldDictionary` v2; berkas profil = berkas kamus yang sah; jenis nilai; batas klaim "tanpa kode Python" | Skema awal akan mengulang bug sinonim pendek (`TP`, `Tanggal`, `Nomor`) yang sudah diselesaikan |
| R11 | §7 | Urutan fase diperbaiki + kolom Kriteria Selesai | Ketergantungan terbalik (Fase 2 butuh berkas Fase 3); beberapa berkas tak masuk fase mana pun |
| R12 | §4 | `profile_loader`, `profile_driven_domain`, `_shared/`, tes tambahan, fixture; presets menjadi contoh fiktif | Janji "cukup tambah JSON" tidak punya pelaksana; hindari data instansi asli di repo |
| R13 | §8-§11 | Kriteria penerimaan, risiko, non-goals, pertanyaan terbuka | Kelengkapan PRD |
