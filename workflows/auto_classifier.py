"""
Klasifikasi otomatis jenis dokumen berdasarkan skor berbobot, ambang batas, dan penanganan ambigu.
Mencegah salah proses dokumen asing (misal SK masuk ke RPP).
"""
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from domains.domain_registry import DomainRegistry
from domains.base_domain import DetectResult


@dataclass
class DomainCandidate:
    domain_id: str
    display_name: str
    score: float
    reasons: List[str]


@dataclass
class ClassificationResult:
    """Hasil klasifikasi dokumen tunggal."""
    file_path: str
    selected_domain_id: Optional[str]
    selected_domain_name: Optional[str]
    confidence_score: float
    is_ambiguous: bool
    status: str  # 'CONFIRMED' atau 'NEEDS_SELECTION'
    candidates: List[DomainCandidate] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


class AutoClassifier:
    """
    Mesin pengklasifikasi jenis dokumen otomatis multi-domain.
    Menggunakan aturan skor berbobot dan ambang pembeda (PRD §5.2).
    """
    CONFIDENCE_THRESHOLD: float = 0.60
    MARGIN_THRESHOLD: float = 0.20

    def __init__(self, registry: Optional[DomainRegistry] = None):
        self.registry = registry or DomainRegistry.get_instance()

    def classify_document(self, in_path: str) -> ClassificationResult:
        """
        Mengklasifikasikan jenis dokumen untuk sebuah berkas Word.
        Mengembalikan status CONFIRMED jika skor >= 0.60 dan selisih >= 0.20,
        atau NEEDS_SELECTION jika ambigu / tidak memenuhi syarat.
        """
        if not os.path.isfile(in_path):
            return ClassificationResult(
                file_path=in_path,
                selected_domain_id=None,
                selected_domain_name=None,
                confidence_score=0.0,
                is_ambiguous=True,
                status="NEEDS_SELECTION",
                reasons=["Berkas tidak ditemukan"]
            )

        domains = self.registry.list_domains()
        if not domains:
            return ClassificationResult(
                file_path=in_path,
                selected_domain_id=None,
                selected_domain_name=None,
                confidence_score=0.0,
                is_ambiguous=True,
                status="NEEDS_SELECTION",
                reasons=["Tidak ada domain dokumen yang terdaftar"]
            )

        candidates: List[DomainCandidate] = []
        for d in domains:
            try:
                res: DetectResult = d.detect_score(in_path)
                candidates.append(DomainCandidate(
                    domain_id=d.domain_id,
                    display_name=d.display_name,
                    score=res.score,
                    reasons=res.reasons
                ))
            except Exception as e:
                candidates.append(DomainCandidate(
                    domain_id=d.domain_id,
                    display_name=d.display_name,
                    score=0.0,
                    reasons=[f"Evaluasi gagal: {e}"]
                ))

        candidates.sort(key=lambda c: c.score, reverse=True)
        top = candidates[0]
        second_score = candidates[1].score if len(candidates) > 1 else 0.0

        # Aturan keputusan (PRD §5.2)
        score_ok = top.score >= self.CONFIDENCE_THRESHOLD
        margin_ok = (top.score - second_score) >= self.MARGIN_THRESHOLD

        if score_ok and margin_ok:
            return ClassificationResult(
                file_path=in_path,
                selected_domain_id=top.domain_id,
                selected_domain_name=top.display_name,
                confidence_score=top.score,
                is_ambiguous=False,
                status="CONFIRMED",
                candidates=candidates,
                reasons=top.reasons
            )
        else:
            ambiguity_reasons = []
            if not score_ok:
                ambiguity_reasons.append(
                    f"Skor domain tertinggi ({top.display_name}: {top.score:.2f}) di bawah ambang batas minimal ({self.CONFIDENCE_THRESHOLD:.2f})"
                )
            if not margin_ok and len(candidates) > 1 and candidates[1].score > 0.0:
                ambiguity_reasons.append(
                    f"Selisih skor terlalu sempit dengan kandidat kedua ({candidates[1].display_name}: {candidates[1].score:.2f})"
                )

            return ClassificationResult(
                file_path=in_path,
                selected_domain_id=None,
                selected_domain_name=None,
                confidence_score=top.score,
                is_ambiguous=True,
                status="NEEDS_SELECTION",
                candidates=candidates,
                reasons=ambiguity_reasons
            )
