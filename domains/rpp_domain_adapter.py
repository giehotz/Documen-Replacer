"""
Adapter untuk membungkus ReplacementEngine eksisting ke dalam kontrak BaseDocumentDomain.
Menjamin 100% paritas fungsionalitas RPP / Modul Ajar tanpa modifikasi kode legacy.
"""
import os
import re
from typing import Dict, Any, List, Optional

from domains.base_domain import BaseDocumentDomain, DetectResult
from core.replacement_engine import ReplacementEngine
from core.field_dictionary import FieldDictionary
from core.document_predictor import predict_rules_from_file
from core.validation_engine import ReplacementPlanItem, validate_type_safety
from document.docx_reader import load_document, iter_all_paragraphs
from document.paragraph_processor import get_paragraph_text

RPP_STRONG_INDICATORS = [
    r"\bmodul\s+ajar\b",
    r"\brencana\s+pelaksanaan\s+pembelajaran\b",
    r"\brpp\b",
    r"\bcapaian\s+pembelajaran\b",
    r"\btujuan\s+pembelajaran\b",
    r"\balur\s+tujuan\s+pembelajaran\b",
]

RPP_WEAK_INDICATORS = [
    r"\bkompetensi\s+dasar\b",
    r"\balokasi\s+waktu\b",
    r"\bmata\s+pelajaran\b",
    r"\bfase\b",
    r"\bkelas\b",
    r"\btahun\s+pelajaran\b",
    r"\bsemester\b",
]

RPP_NEGATIVE_INDICATORS = [
    r"\bmemutuskan\b",
    r"\bsurat\s+keputusan\b",
    r"\bberita\s+acara\b",
    r"\bsurat\s+perintah\s+tugas\b",
    r"\bpihak\s+kesatu\b",
    r"\bpihak\s+kedua\b",
]


class RPPDomainAdapter(BaseDocumentDomain):
    """
    Adapter domain Perangkat Ajar (RPP / Modul Ajar / Silabus / PROTA / PROMES).
    Mendelegasikan seluruh alur kerja ke ReplacementEngine dan DocumentPredictor.
    """
    domain_id: str = "rpp_modul"
    display_name: str = "Perangkat Ajar (RPP / Modul Ajar)"

    def __init__(
        self,
        replacement_engine: Optional[ReplacementEngine] = None,
        field_dictionary: Optional[FieldDictionary] = None,
        signature_settings: Optional[Dict[str, Any]] = None,
    ):
        if replacement_engine is not None:
            self.engine = replacement_engine
        else:
            dict_obj = field_dictionary or FieldDictionary.load()
            self.engine = ReplacementEngine(field_dictionary=dict_obj)
            if signature_settings:
                self.engine.signature_settings = signature_settings

    def detect_score(self, in_path: str) -> DetectResult:
        """Mengevaluasi kecocokan dokumen terhadap pola RPP/Modul Ajar."""
        if not os.path.isfile(in_path):
            return DetectResult(score=0.0, reasons=["Berkas tidak ditemukan"])

        try:
            doc = load_document(in_path)
            sample_texts: List[str] = []
            for idx, p in enumerate(iter_all_paragraphs(doc.element.body, doc)):
                if idx >= 35:
                    break
                sample_texts.append(get_paragraph_text(p))
            full_text = "\n".join(sample_texts).lower()
        except Exception as e:
            return DetectResult(score=0.0, reasons=[f"Gagal memuat dokumen: {e}"])

        matched_strong = [pat for pat in RPP_STRONG_INDICATORS if re.search(pat, full_text, re.IGNORECASE)]
        matched_weak = [pat for pat in RPP_WEAK_INDICATORS if re.search(pat, full_text, re.IGNORECASE)]
        matched_negative = [pat for pat in RPP_NEGATIVE_INDICATORS if re.search(pat, full_text, re.IGNORECASE)]

        raw_score = (3.0 * len(matched_strong) + 1.0 * len(matched_weak) - 2.0 * len(matched_negative)) / 9.0
        clamped_score = max(0.0, min(1.0, raw_score))

        reasons = []
        if matched_strong:
            reasons.append(f"Indikator kuat RPP ({len(matched_strong)})")
        if matched_weak:
            reasons.append(f"Indikator pendukung ({len(matched_weak)})")
        if matched_negative:
            reasons.append(f"Indikator negatif domain lain ({len(matched_negative)})")

        return DetectResult(score=clamped_score, reasons=reasons)

    def predict_fields(self, in_path: str) -> Dict[str, Any]:
        """Prediksi nilai field dokumen menggunakan predict_rules_from_file."""
        rules = predict_rules_from_file(in_path, field_dictionary=self.engine.dict)
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
        """Merencanakan perubahan dokumen dengan membubuhkan domain_id pada target_meta."""
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
        """Menerapkan perubahan dokumen yang disetujui."""
        sig_cfg = signature_settings or self.engine.signature_settings
        return self.engine.apply_approved_changes(
            in_path=in_path,
            out_path=out_path,
            approved_items=approved_items,
            signature_settings=sig_cfg
        )

    def validate_item(self, item: ReplacementPlanItem) -> bool:
        """Memvalidasi item perubahan dengan proteksi type-safety bawaan."""
        return validate_type_safety(item.category, item.old_text, item.new_text)

    def reload_dictionary(self) -> None:
        """Memuat ulang kamus istilah."""
        self.engine.reload_dictionary()

    def reload_signature_settings(self, settings: Dict[str, Any]) -> None:
        """Memuat ulang konfigurasi tanda tangan."""
        self.engine.signature_settings = settings
