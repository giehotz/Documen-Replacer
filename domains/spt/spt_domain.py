"""
Implementasi BaseDocumentDomain untuk Surat Perintah Tugas (SPTDomain).
Mendukung SPT format tunggal dan SPT format tabel kolektif dengan dataset tabular.
"""
from typing import Dict, Any, List, Optional
import os
import re
from docx import Document

from domains.base_domain import BaseDocumentDomain, DetectResult
from domains.profile_loader import ProfileLoader
from domains.profile_driven_domain import ProfileDrivenDomain
from domains._shared.conflict_resolver import resolve_replacement_overlaps
from domains.spt.pegawai_list_analyzer import analyze_spt_pegawai, plan_collective_spt_items
from core.replacement_engine import ReplacementPlanItem
from document.paragraph_processor import get_paragraph_text


class SPTDomain(BaseDocumentDomain):
    """
    Modul domain untuk pemrosesan Surat Perintah Tugas (SPT) dan SPPD.
    """
    domain_id = "spt_penugasan"
    display_name = "Surat Perintah Tugas (SPT)"

    def __init__(self, profile_path: Optional[str] = None):
        if not profile_path:
            profile_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config", "profiles", "spt_penugasan.profile.json"
            )
        self.profile_path = profile_path
        self.profile_data = ProfileLoader.load_profile(profile_path)
        self._driven_domain = ProfileDrivenDomain(self.profile_data)
        self.field_dict = self._driven_domain.field_dict
        self._last_issues: List[Dict[str, str]] = []

    def detect_score(self, in_path: str) -> DetectResult:
        """Menghitung skor deteksi kecocokan dokumen sebagai SPT."""
        return self._driven_domain.detect_score(in_path)

    def predict_fields(self, in_path: str) -> Dict[str, Any]:
        """Ekstraksi nilai field profil dari naskah SPT."""
        if not os.path.exists(in_path):
            return {}

        results = self._driven_domain.predict_fields(in_path)

        try:
            doc = Document(in_path)

            for idx, p in enumerate(doc.paragraphs[:10]):
                txt = get_paragraph_text(p).strip()
                if not txt:
                    continue

                m_no = re.search(r"^(?:NOMOR|NO)\s*[:\t]\s*(.+)$", txt, re.IGNORECASE)
                if m_no and "nomor_spt" not in results:
                    val = m_no.group(1).strip()
                    results["Nomor SPT"] = val
                    results["nomor_spt"] = val

                m_dasar = re.search(r"^Dasar\s*[:\t]\s*(.+)$", txt, re.IGNORECASE)
                if m_dasar and "dasar_penugasan" not in results:
                    val = m_dasar.group(1).strip()
                    results["Dasar Penugasan"] = val
                    results["dasar_penugasan"] = val

            # Analisis data pegawai
            p_info = analyze_spt_pegawai(doc)
            if p_info["layout_type"] == "single_colon":
                fields = p_info.get("fields", {})
                if "nama" in fields:
                    results["Nama Pegawai"] = fields["nama"]["value"]
                    results["nama_pegawai"] = fields["nama"]["value"]
                if "nip" in fields:
                    results["NIP Pegawai"] = fields["nip"]["value"]
                    results["nip_pegawai"] = fields["nip"]["value"]
                if "jabatan" in fields:
                    results["Jabatan"] = fields["jabatan"]["value"]

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
        datasets: Optional[Dict[str, Any]] = None,
        **ctx
    ) -> List[ReplacementPlanItem]:
        """Merencanakan perubahan pada dokumen SPT termasuk pemetaan dataset kolektif."""
        if not os.path.exists(in_path):
            return []

        doc = Document(in_path)
        items: List[ReplacementPlanItem] = []
        self._last_issues = []

        # 1. Jika terdapat dataset pegawai dan naskah berupa tabel kolektif
        if datasets and "pegawai" in datasets:
            peg_data = datasets["pegawai"]
            p_info = analyze_spt_pegawai(doc)
            if p_info["layout_type"] == "table_kolektif":
                tbl_items, issues = plan_collective_spt_items(doc, in_path, rel_path, peg_data, p_info)
                items.extend(tbl_items)
                self._last_issues.extend(issues)
                # Tandai item jika ada ketidaksesuaian jumlah baris
                if issues:
                    for it in tbl_items:
                        it.target_meta["table_row_mismatch"] = True

        # 2. Rencana dari dictionary engine profil untuk aturan umum (Nomor SPT, Dasar, dll)
        base_items = self._driven_domain.plan_document_changes(
            in_path=in_path,
            rel_path=rel_path,
            rules=rules,
            mode=mode,
            case_sensitive=case_sensitive,
            **ctx
        )
        for it in base_items:
            if it.target_meta is not None:
                it.target_meta.setdefault("domain_id", self.domain_id)

        all_items = items + base_items
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
        """Menerapkan seluruh perubahan yang disetujui pada naskah SPT."""
        return self._driven_domain.apply_approved_changes(
            in_path=in_path,
            out_path=out_path,
            approved_items=approved_items,
            signature_settings=signature_settings,
            **ctx
        )

    def extra_checks(self, item: ReplacementPlanItem, actual_text: str) -> List[Dict[str, str]]:
        """Pemeriksaan tambahan khusus SPT: kesesuaian baris tabel."""
        issues: List[Dict[str, str]] = []
        meta = item.target_meta or {}
        if meta.get("table_row_mismatch"):
            issues.append({
                "code": "JUMLAH_BARIS_TIDAK_SAMA",
                "message": "Jumlah baris tabel SPT di dokumen berbeda dengan jumlah record data yang diberikan."
            })
        return issues

    def reload_dictionary(self) -> None:
        """Memuat ulang profil SPT."""
        self.profile_data = ProfileLoader.load_profile(self.profile_path)
        self._driven_domain = ProfileDrivenDomain(self.profile_data)
        self.field_dict = self._driven_domain.field_dict
