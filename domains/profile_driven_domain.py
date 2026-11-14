"""
Domain generik berbasis profil deklaratif (ProfileDrivenDomain).
Memungkinkan otomasi jenis dokumen baru hanya dengan berkas *.profile.json (tanpa kode Python baru).
"""
import os
import re
from typing import Dict, Any, List, Optional

from domains.base_domain import BaseDocumentDomain, DetectResult
from domains.profile_loader import DomainProfile
from core.field_dictionary import FieldDictionary, FieldDef
from core.replacement_engine import ReplacementEngine
from core.validation_engine import ReplacementPlanItem
from document.docx_reader import load_document, iter_all_paragraphs
from document.paragraph_processor import get_paragraph_text


class ProfileDrivenDomain(BaseDocumentDomain):
    """
    Domain dokumen yang digerakkan oleh definisi profil JSON (Schema v2).
    Cocok untuk jenis-jenis dokumen sederhana yang berbasis label dan zona.
    """
    def __init__(self, profile: DomainProfile):
        self.profile = profile
        self.domain_id = profile.profile_id
        self.display_name = profile.display_name

        # Konversi data field menjadi objek FieldDef yang valid
        fields_list: List[FieldDef] = []
        for item in profile.fields:
            if isinstance(item, FieldDef):
                fields_list.append(item)
            elif isinstance(item, dict):
                f_def = FieldDef(
                    id=item["id"],
                    category=item["category"],
                    display_label=item.get("display_label", item["category"]),
                    value_type=item.get("value_type", "text"),
                    match_mode=item.get("match_mode", "word_boundary"),
                    priority=int(item.get("priority", 50)),
                    synonyms=[s.strip() for s in item.get("synonyms", []) if s.strip()],
                    exact_only_synonyms=[s.strip() for s in item.get("exact_only_synonyms", []) if s.strip()],
                    never_match=[s.strip() for s in item.get("never_match", []) if s.strip()],
                )
                fields_list.append(f_def)

        self.field_dict = FieldDictionary(
            fields_list=fields_list,
            global_never_match=profile.global_never_match,
            global_ignore_exact=profile.global_ignore_exact
        )
        self.engine = ReplacementEngine(field_dictionary=self.field_dict)

    def detect_score(self, in_path: str) -> DetectResult:
        """Menghitung skor kecocokan berdasarkan auto_detect pada profil."""
        if not os.path.isfile(in_path):
            return DetectResult(score=0.0, reasons=["Berkas tidak ditemukan"])

        auto_detect = self.profile.auto_detect or {}
        strong_pats = auto_detect.get("strong", [])
        weak_pats = auto_detect.get("weak", [])
        negative_pats = auto_detect.get("negative", [])

        if not strong_pats and not weak_pats:
            return DetectResult(score=0.0, reasons=["Profil tidak mendefinisikan auto_detect"])

        try:
            doc = load_document(in_path)
            sample_texts: List[str] = []
            for idx, p in enumerate(iter_all_paragraphs(doc.element.body, doc)):
                if idx >= 30:
                    break
                sample_texts.append(get_paragraph_text(p))
            full_text = "\n".join(sample_texts)
        except Exception as e:
            return DetectResult(score=0.0, reasons=[f"Gagal memuat dokumen: {e}"])

        matched_strong = [pat for pat in strong_pats if re.search(r"\b" + re.escape(pat) + r"\b", full_text, re.IGNORECASE)]
        matched_weak = [pat for pat in weak_pats if re.search(r"\b" + re.escape(pat) + r"\b", full_text, re.IGNORECASE)]
        matched_negative = [pat for pat in negative_pats if re.search(r"\b" + re.escape(pat) + r"\b", full_text, re.IGNORECASE)]

        raw_score = (3.0 * len(matched_strong) + 1.0 * len(matched_weak) - 2.0 * len(matched_negative)) / 9.0
        score = max(0.0, min(1.0, raw_score))

        reasons = []
        if matched_strong:
            reasons.append(f"Cocok indikator utama ({len(matched_strong)})")
        if matched_weak:
            reasons.append(f"Cocok indikator pendukung ({len(matched_weak)})")
        if matched_negative:
            reasons.append(f"Terdeteksi indikator negatif ({len(matched_negative)})")

        return DetectResult(score=score, reasons=reasons)

    def predict_fields(self, in_path: str) -> Dict[str, Any]:
        """Ekstraksi nilai field profil dari dokumen."""
        from core.document_predictor import predict_rules_from_file
        rules = predict_rules_from_file(in_path)
        return {r["label"]: r.get("old", "") for r in rules if r.get("old")}

    def plan_document_changes(
        self,
        in_path: str,
        rel_path: str,
        rules: List[Dict[str, str]],
        mode: str = "GABUNGAN",
        case_sensitive: bool = True,
        **ctx
    ) -> List[ReplacementPlanItem]:
        """Merencanakan perubahan dokumen dengan membubuhkan domain_id."""
        items = self.engine.plan_document_changes(
            in_path=in_path,
            rel_path=rel_path,
            rules=rules,
            mode=mode,
            case_sensitive=case_sensitive
        )
        for it in items:
            if it.target_meta is not None:
                it.target_meta.setdefault("domain_id", self.domain_id)
        return items

    def apply_approved_changes(
        self,
        in_path: str,
        out_path: str,
        approved_items: List[ReplacementPlanItem],
        signature_settings: Optional[Dict[str, Any]] = None,
        **ctx
    ) -> int:
        """Menerapkan perubahan yang disetujui."""
        return self.engine.apply_approved_changes(
            in_path=in_path,
            out_path=out_path,
            approved_items=approved_items,
            signature_settings=signature_settings
        )

    def reload_dictionary(self) -> None:
        """Memuat ulang kamus."""
        self.engine.reload_dictionary()
