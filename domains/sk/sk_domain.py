"""
Implementasi BaseDocumentDomain untuk Surat Keputusan (SK).
Menggabungkan profil skema v2, penganalisis struktur SK (header, diktum, penetapan),
dan sinkronisasi otomatis ke seluruh header lampiran.
"""
from typing import Dict, Any, List, Optional
import os
import re
from docx import Document

from domains.base_domain import BaseDocumentDomain, DetectResult
from domains.profile_loader import ProfileLoader
from domains.profile_driven_domain import ProfileDrivenDomain
from domains._shared.conflict_resolver import resolve_replacement_overlaps
from domains.sk.sk_header_analyzer import analyze_sk_header
from domains.sk.diktum_analyzer import analyze_diktums
from domains.sk.penetapan_signature_analyzer import analyze_penetapan_and_signature
from domains.sk.lampiran_sk_analyzer import plan_attachment_sync_items
from core.replacement_engine import ReplacementPlanItem, ReplacementEngine
from document.paragraph_processor import get_paragraph_text, replace_span, replace_full_text_keep_style
from document.docx_writer import save_document


class SKDomain(BaseDocumentDomain):
    """
    Modul domain untuk pemrosesan Surat Keputusan (SK).
    """
    domain_id = "sk_keputusan"
    display_name = "Surat Keputusan (SK)"

    def __init__(self, profile_path: Optional[str] = None):
        if not profile_path:
            profile_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config", "profiles", "sk_keputusan.profile.json"
            )
        self.profile_path = profile_path
        self.profile_data = ProfileLoader.load_profile(profile_path)
        self._driven_domain = ProfileDrivenDomain(self.profile_data)
        self.field_dict = self._driven_domain.field_dict

    def detect_score(self, in_path: str) -> DetectResult:
        """Menghitung skor deteksi kecocokan dokumen sebagai SK."""
        return self._driven_domain.detect_score(in_path)

    def predict_fields(self, in_path: str) -> Dict[str, Any]:
        """Ekstraksi nilai field profil dari naskah SK."""
        if not os.path.exists(in_path):
            return {}

        results = self._driven_domain.predict_fields(in_path)

        try:
            doc = Document(in_path)
            # Analisis header SK
            hdr_info = analyze_sk_header(doc)
            if "nomor_sk" in hdr_info:
                results["Nomor SK"] = hdr_info["nomor_sk"]["value"]
                results["nomor_sk"] = hdr_info["nomor_sk"]["value"]
            if "tentang_sk" in hdr_info:
                results["Tentang / Judul SK"] = hdr_info["tentang_sk"]["value"]
                results["tentang_sk"] = hdr_info["tentang_sk"]["value"]

            # Analisis penetapan dan tanda tangan
            pen_info = analyze_penetapan_and_signature(doc)
            if "tempat_penetapan" in pen_info:
                results["Tempat Penetapan"] = pen_info["tempat_penetapan"]["value"]
                results["tempat_penetapan"] = pen_info["tempat_penetapan"]["value"]
            if "tanggal_penetapan" in pen_info:
                results["Tanggal Penetapan"] = pen_info["tanggal_penetapan"]["value"]
                results["tanggal_penetapan"] = pen_info["tanggal_penetapan"]["value"]
            if "nama_kepala" in pen_info:
                results["Nama Kepala"] = pen_info["nama_kepala"]["value"]
                results["nama_kepala"] = pen_info["nama_kepala"]["value"]
            if "nip_kepala" in pen_info:
                results["NIP Kepala"] = pen_info["nip_kepala"]["value"]
                results["nip_kepala"] = pen_info["nip_kepala"]["value"]
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
        """Merencanakan perubahan pada dokumen SK termasuk sinkronisasi lampiran."""
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

        # 2. Buat mapping rules: label/id -> new_value
        rules_map: Dict[str, str] = {}
        for r in rules:
            lbl = r.get("label", "").strip()
            new_v = r.get("new", "").strip()
            if lbl and new_v:
                rules_map[lbl] = new_v
                # Petakan juga id field jika cocok
                fields_src = getattr(self.profile_data, "fields", [])
                for f in fields_src:
                    f_lbl = f.get("display_label", "") if isinstance(f, dict) else getattr(f, "display_label", "")
                    f_id = f.get("id", "") if isinstance(f, dict) else getattr(f, "id", "")
                    if f_lbl.lower() == lbl.lower() or f_id.lower() == lbl.lower():
                        rules_map[f_id] = new_v

        # 3. Rencana sinkronisasi lampiran SK
        sync_items = plan_attachment_sync_items(doc, in_path, rel_path, rules_map)

        all_items = base_items + sync_items

        # Beri penanda domain_id
        for it in all_items:
            if it.target_meta is not None:
                it.target_meta.setdefault("domain_id", self.domain_id)

        # 4. Selesaikan konflik tumpang tindih
        resolved_items = resolve_replacement_overlaps(all_items)
        return resolved_items

    def apply_approved_changes(
        self,
        in_path: str,
        out_path: str,
        approved_items: List[ReplacementPlanItem],
        signature_settings: Optional[Dict[str, Any]] = None,
        **ctx
    ) -> int:
        """Menerapkan seluruh perubahan yang disetujui pada dokumen SK."""
        return self._driven_domain.apply_approved_changes(
            in_path=in_path,
            out_path=out_path,
            approved_items=approved_items,
            signature_settings=signature_settings,
            **ctx
        )

    def extra_checks(self, item: ReplacementPlanItem, actual_text: str) -> List[Dict[str, str]]:
        """Pemeriksaan tambahan khusus SK: sinkronisasi antar-zona."""
        issues: List[Dict[str, str]] = []
        meta = item.target_meta or {}

        # Periksa apakah ini item sinkronisasi lampiran
        if "sync_field" in meta:
            if item.new_text not in actual_text:
                issues.append({
                    "code": "SINKRON_ANTAR_ZONA",
                    "message": f"Field '{meta.get('sync_field')}' pada lampiran tidak sinkron dengan nilai SK utama ({item.new_text})."
                })

        return issues

    def reload_dictionary(self) -> None:
        """Memuat ulang profil dan kamus SK."""
        self.profile_data = ProfileLoader.load_profile(self.profile_path)
        self._driven_domain = ProfileDrivenDomain(self.profile_data)
        self.field_dict = self._driven_domain.field_dict
