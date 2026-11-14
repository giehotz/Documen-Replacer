"""
Implementasi BaseDocumentDomain untuk Surat Dinas dan Surat Undangan.
Menggabungkan profil skema v2, penganalisis metadata surat (Nomor, Hal, Tujuan),
dan pemroses blok agenda acara dengan jaminan tanggal surat tidak tertukar tanggal acara.
"""
from typing import Dict, Any, List, Optional
import os
import re
from docx import Document

from domains.base_domain import BaseDocumentDomain, DetectResult
from domains.profile_loader import ProfileLoader
from domains.profile_driven_domain import ProfileDrivenDomain
from domains._shared.conflict_resolver import resolve_replacement_overlaps
from domains.surat_dinas.meta_surat_analyzer import analyze_meta_surat
from domains.surat_dinas.agenda_block_analyzer import analyze_agenda_block
from core.replacement_engine import ReplacementPlanItem
from document.paragraph_processor import get_paragraph_text


class SuratDinasDomain(BaseDocumentDomain):
    """
    Modul domain untuk pemrosesan Surat Dinas dan Surat Undangan Resmi.
    """
    domain_id = "surat_dinas"
    display_name = "Surat Dinas / Undangan"

    def __init__(self, profile_path: Optional[str] = None):
        if not profile_path:
            profile_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config", "profiles", "surat_dinas.profile.json"
            )
        self.profile_path = profile_path
        self.profile_data = ProfileLoader.load_profile(profile_path)
        self._driven_domain = ProfileDrivenDomain(self.profile_data)
        self.field_dict = self._driven_domain.field_dict

    def detect_score(self, in_path: str) -> DetectResult:
        """Menghitung skor deteksi kecocokan dokumen sebagai Surat Dinas."""
        return self._driven_domain.detect_score(in_path)

    def predict_fields(self, in_path: str) -> Dict[str, Any]:
        """Ekstraksi nilai field profil dari naskah Surat Dinas."""
        if not os.path.exists(in_path):
            return {}

        results = self._driven_domain.predict_fields(in_path)

        try:
            doc = Document(in_path)
            # 1. Analisis metadata surat
            meta_info = analyze_meta_surat(doc)
            if "nomor_surat" in meta_info:
                results["Nomor Surat"] = meta_info["nomor_surat"]["value"]
                results["nomor_surat"] = meta_info["nomor_surat"]["value"]
            if "sifat_surat" in meta_info:
                results["Sifat Surat"] = meta_info["sifat_surat"]["value"]
                results["sifat_surat"] = meta_info["sifat_surat"]["value"]
            if "lampiran_surat" in meta_info:
                results["Lampiran"] = meta_info["lampiran_surat"]["value"]
                results["lampiran_surat"] = meta_info["lampiran_surat"]["value"]
            if "hal_surat" in meta_info:
                results["Hal / Perihal"] = meta_info["hal_surat"]["value"]
                results["hal_surat"] = meta_info["hal_surat"]["value"]
            if "tujuan_surat" in meta_info:
                results["Kepada Yth"] = meta_info["tujuan_surat"]["value"]
                results["tujuan_surat"] = meta_info["tujuan_surat"]["value"]

            # 2. Analisis blok agenda kegiatan
            agenda_info = analyze_agenda_block(doc)
            if "hari_tanggal_acara" in agenda_info:
                results["Hari, Tanggal Kegiatan"] = agenda_info["hari_tanggal_acara"]["value"]
                results["hari_tanggal_acara"] = agenda_info["hari_tanggal_acara"]["value"]
            if "waktu_acara" in agenda_info:
                results["Pukul / Waktu Kegiatan"] = agenda_info["waktu_acara"]["value"]
                results["waktu_acara"] = agenda_info["waktu_acara"]["value"]
            if "tempat_acara" in agenda_info:
                results["Tempat Kegiatan"] = agenda_info["tempat_acara"]["value"]
                results["tempat_acara"] = agenda_info["tempat_acara"]["value"]
            if "acara_kegiatan" in agenda_info:
                results["Acara Kegiatan"] = agenda_info["acara_kegiatan"]["value"]
                results["acara_kegiatan"] = agenda_info["acara_kegiatan"]["value"]
        except Exception:
            pass

        return results

    def plan_document_changes(
        self,
        in_path: str,
        rel_path: str,
        rules: List[Dict[str, str]],
        mode: str = "GABUNGAN",
        case_sensitive: bool = True,
        **ctx
    ) -> List[ReplacementPlanItem]:
        """Merencanakan perubahan pada dokumen Surat Dinas / Undangan."""
        if not os.path.exists(in_path):
            return []

        doc = Document(in_path)

        # 1. Rencana dari dictionary engine profil
        base_items = self._driven_domain.plan_document_changes(
            in_path=in_path,
            rel_path=rel_path,
            rules=rules,
            mode=mode,
            case_sensitive=case_sensitive,
            **ctx
        )

        # 2. Pastikan domain_id tertempel pada setiap item
        for it in base_items:
            if it.target_meta is not None:
                it.target_meta.setdefault("domain_id", self.domain_id)

        # 3. Selesaikan potensi konflik tumpang tindih
        resolved_items = resolve_replacement_overlaps(base_items)
        return resolved_items

    def apply_approved_changes(
        self,
        in_path: str,
        out_path: str,
        approved_items: List[ReplacementPlanItem],
        signature_settings: Optional[Dict[str, Any]] = None,
        **ctx
    ) -> int:
        """Menerapkan seluruh perubahan yang disetujui pada naskah Surat Dinas."""
        return self._driven_domain.apply_approved_changes(
            in_path=in_path,
            out_path=out_path,
            approved_items=approved_items,
            signature_settings=signature_settings,
            **ctx
        )

    def extra_checks(self, item: ReplacementPlanItem, actual_text: str) -> List[Dict[str, str]]:
        """Pemeriksaan tambahan khusus Surat Dinas."""
        issues: List[Dict[str, str]] = []
        # Perlindungan anti-tertukar tanggal acara dan tanggal surat
        if "acara" in (item.category or "").lower():
            if "ditetapkan" in actual_text.lower():
                issues.append({
                    "code": "TANGGAL_ACARA_TERTUKAR_TANGGAL_SURAT",
                    "message": "Tanggal agenda acara terindikasi diterapkan pada blok titimangsa/tanggal surat."
                })
        return issues

    def reload_dictionary(self) -> None:
        """Memuat ulang profil dan kamus Surat Dinas."""
        self.profile_data = ProfileLoader.load_profile(self.profile_path)
        self._driven_domain = ProfileDrivenDomain(self.profile_data)
        self.field_dict = self._driven_domain.field_dict
