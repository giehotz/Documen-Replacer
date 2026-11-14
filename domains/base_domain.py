"""
Kontrak abstraksi tunggal untuk plugin domain dokumen (BaseDocumentDomain).
Memastikan seluruh domain menghasilkan ReplacementPlanItem yang seragam dan kompatibel
dengan dialog pratinjau, ChangeReportGenerator, serta pipeline konversi.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from core.validation_engine import ReplacementPlanItem


@dataclass(frozen=True)
class DetectResult:
    """Hasil evaluasi kecocokan dokumen terhadap suatu domain."""
    score: float                 # Rentang 0.0 - 1.0
    reasons: List[str] = field(default_factory=list)  # Daftar indikator yang cocok


class BaseDocumentDomain(ABC):
    """
    Antarmuka dasar untuk semua modul domain dokumen.
    Setiap domain (RPP, SK, Surat Dinas, SPT, Berita Acara, dll.) wajib mewarisi kelas ini.
    """
    domain_id: str = "base"
    display_name: str = "Base Document Domain"

    @abstractmethod
    def detect_score(self, in_path: str) -> DetectResult:
        """
        Menghitung tingkat kecocokan dokumen terhadap karakteristik domain ini.
        Mengembalikan skor 0.0 hingga 1.0 serta daftar alasan/indikator kecocokan.
        """
        pass

    @abstractmethod
    def predict_fields(self, in_path: str) -> Dict[str, Any]:
        """
        Mengekstrak nilai field saat ini yang terdeteksi di dokumen
        (digunakan oleh fitur 'Prediksi dari Dokumen' pada GUI).
        """
        pass

    @abstractmethod
    def plan_document_changes(
        self,
        in_path: str,
        rel_path: str,
        rules: List[Dict[str, str]],
        mode: str = "GABUNGAN",
        case_sensitive: bool = True,
        **ctx
    ) -> List[ReplacementPlanItem]:
        """
        Menghasilkan daftar usulan perubahan (ReplacementPlanItem).
        Setiap item yang dihasilkan WAJIB mencantumkan target_meta['domain_id'] = self.domain_id.
        """
        pass

    @abstractmethod
    def apply_approved_changes(
        self,
        in_path: str,
        out_path: str,
        approved_items: List[ReplacementPlanItem],
        signature_settings: Optional[Dict[str, Any]] = None,
        **ctx
    ) -> int:
        """
        Menerapkan usulan perubahan yang disetujui pengguna ke berkas target dan menyimpannya.
        Mengembalikan jumlah perubahan yang berhasil diterapkan.
        """
        pass

    def validate_item(self, item: ReplacementPlanItem) -> bool:
        """
        Validasi khusus domain sebelum item masuk ke pratinjau.
        Default: mengembalikan True.
        """
        return True

    def extra_checks(self, item: ReplacementPlanItem, actual_text: str) -> List[Dict[str, str]]:
        """
        Pemeriksaan semantik tambahan khusus domain untuk disertakan dalam laporan verifikasi.
        Mengembalikan list bendera, misal: [{"kode": "SINKRON_ANTAR_ZONA", "pesan": "..."}].
        """
        return []

    def reload_dictionary(self) -> None:
        """Memuat ulang kamus atau konfigurasi jika terjadi perubahan berkas kamus."""
        pass
