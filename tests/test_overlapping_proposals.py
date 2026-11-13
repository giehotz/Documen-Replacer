"""
Unit test untuk memastikan resolusi konflik usulan tumpang tindih
(Overlapping Proposals Resolution) berjalan dengan benar.
"""
import unittest
from core.validation_engine import ReplacementPlanItem, ConfidenceLevel
from core.replacement_engine import ReplacementEngine


class TestOverlappingProposals(unittest.TestCase):
    def setUp(self):
        self.engine = ReplacementEngine()

    def test_exact_wins_over_overlapping_span(self):
        """Aturan EXACT dengan teks eksplisit dari user mengalahkan usulan PARAGRAPH_SPAN generik."""
        items = [
            ReplacementPlanItem(
                doc_path="doc1.docx",
                rel_path="doc1.docx",
                category="Pencocokan Persis",
                old_text="20.... / 20....",
                new_text="2026/2027",
                confidence=ConfidenceLevel.HIGH,
                location_info="Paragraf #1",
                target_type="EXACT",
                target_meta={
                    "para_idx": 1,
                    "start": 18,
                    "end": 33,
                    "original_text": "Tahun Pelajaran : 20.... / 20....",
                }
            ),
            ReplacementPlanItem(
                doc_path="doc1.docx",
                rel_path="doc1.docx",
                category="Tahun Ajaran",
                old_text="....",
                new_text="2026/2027",
                confidence=ConfidenceLevel.HIGH,
                location_info="Paragraf #1 (Inline)",
                target_type="PARAGRAPH_SPAN",
                target_meta={
                    "para_idx": 1,
                    "start": 20,
                    "end": 24,
                    "original_text": "Tahun Pelajaran : 20.... / 20....",
                }
            )
        ]

        resolved = self.engine._deduplicate_and_resolve_overlaps(items)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].target_type, "EXACT")
        self.assertEqual(resolved[0].old_text, "20.... / 20....")

    def test_disjoint_proposals_in_same_paragraph_both_preserved(self):
        """Dua usulan pada paragraf yang sama tetapi tidak beririsan harus sama-sama dipertahankan."""
        items = [
            ReplacementPlanItem(
                doc_path="doc1.docx",
                rel_path="doc1.docx",
                category="Pencocokan Persis",
                old_text="Semester 1",
                new_text="Semester 2",
                confidence=ConfidenceLevel.HIGH,
                location_info="Paragraf #2",
                target_type="EXACT",
                target_meta={
                    "para_idx": 2,
                    "start": 0,
                    "end": 10,
                    "original_text": "Semester 1 / Tahun 2025",
                }
            ),
            ReplacementPlanItem(
                doc_path="doc1.docx",
                rel_path="doc1.docx",
                category="Tahun Ajaran",
                old_text="2025",
                new_text="2026",
                confidence=ConfidenceLevel.HIGH,
                location_info="Paragraf #2",
                target_type="EXACT",
                target_meta={
                    "para_idx": 2,
                    "start": 19,
                    "end": 23,
                    "original_text": "Semester 1 / Tahun 2025",
                }
            )
        ]

        resolved = self.engine._deduplicate_and_resolve_overlaps(items)
        self.assertEqual(len(resolved), 2)


if __name__ == "__main__":
    unittest.main()
