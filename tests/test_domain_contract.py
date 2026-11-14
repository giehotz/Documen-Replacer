"""
Uji Kontrak Domain & Uji Paritas 100% RPP Adapter:
Memastikan UnifiedOrchestrator dengan RPPDomainAdapter menghasilkan rencana
dan hasil dokumen yang identik persis dengan ReplacementEngine asli (PRD §5.1 & §7).
"""
import os
import shutil
import tempfile
import unittest
from docx import Document

from core.replacement_engine import ReplacementEngine
from core.field_dictionary import FieldDictionary
from core.change_verifier import ChangeReportGenerator
from workflows.unified_orchestrator import UnifiedOrchestrator
from domains.domain_registry import DomainRegistry
from domains.rpp_domain_adapter import RPPDomainAdapter
from tests.fixtures.make_sample_docs import create_sample_rpp


class TestDomainContractAndParity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dict = FieldDictionary.load()
        self.legacy_engine = ReplacementEngine(field_dictionary=self.dict)

        # Setup registry dan orchestrator
        self.registry = DomainRegistry(auto_register_defaults=False)
        self.rpp_adapter = RPPDomainAdapter(field_dictionary=self.dict)
        self.registry.register(self.rpp_adapter)
        self.orchestrator = UnifiedOrchestrator(
            registry=self.registry,
            default_domain_id="rpp_modul",
            field_dictionary=self.dict
        )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_domain_contract_attributes_and_stamping(self):
        """Memastikan BaseDocumentDomain terpenuhi dan setiap item rencana membawa target_meta['domain_id']."""
        sample_path = os.path.join(self.test_dir, "contract_sample.docx")
        create_sample_rpp(sample_path)

        rules = [
            {"label": "Nama Madrasah", "old": "MIN 1 Contoh", "new": "MIN 2 Model"},
            {"label": "Tahun Pelajaran", "old": "2025/2026", "new": "2026/2027"}
        ]

        items = self.orchestrator.plan_document_changes(
            in_path=sample_path,
            rel_path="contract_sample.docx",
            rules=rules,
            mode="GABUNGAN"
        )

        self.assertGreater(len(items), 0)
        for it in items:
            self.assertIn("domain_id", it.target_meta)
            self.assertEqual(it.target_meta["domain_id"], "rpp_modul")

    def test_parity_plan_and_apply_between_orchestrator_and_legacy_engine(self):
        """Uji Paritas: Hasil rencana dan penerapan dokumen antara UnifiedOrchestrator dan ReplacementEngine harus identik."""
        doc_legacy = os.path.join(self.test_dir, "doc_legacy.docx")
        doc_orch = os.path.join(self.test_dir, "doc_orch.docx")
        create_sample_rpp(doc_legacy)
        shutil.copyfile(doc_legacy, doc_orch)

        rules = [
            {"label": "Nama Madrasah", "old": "MIN 1 Contoh", "new": "MIN 2 Model"},
            {"label": "Tahun Pelajaran", "old": "2025/2026", "new": "2026/2027"},
            {"label": "Nama Kepala", "old": "Budi Santoso, M.Pd", "new": "Ahmad Dahlan, M.Pd"},
            {"label": "Nama Guru", "old": "Siti Aminah, S.Pd", "new": "Fatimah, S.Pd"}
        ]

        # 1. Rencana perubahan
        plan_legacy = self.legacy_engine.plan_document_changes(doc_legacy, "doc.docx", rules, mode="GABUNGAN")
        plan_orch = self.orchestrator.plan_document_changes(doc_orch, "doc.docx", rules, mode="GABUNGAN")

        self.assertEqual(len(plan_legacy), len(plan_orch))
        for l_it, o_it in zip(plan_legacy, plan_orch):
            self.assertEqual(l_it.category, o_it.category)
            self.assertEqual(l_it.old_text, o_it.old_text)
            self.assertEqual(l_it.new_text, o_it.new_text)
            self.assertEqual(l_it.target_type, o_it.target_type)

        # 2. Penerapan perubahan
        out_leg_dir = os.path.join(self.test_dir, "leg_out")
        os.makedirs(out_leg_dir, exist_ok=True)
        out_legacy = os.path.join(out_leg_dir, "doc.docx")

        out_orch_dir = os.path.join(self.test_dir, "orch_out")
        os.makedirs(out_orch_dir, exist_ok=True)
        out_orch = os.path.join(out_orch_dir, "doc.docx")

        changes_legacy = self.legacy_engine.apply_approved_changes(doc_legacy, out_legacy, plan_legacy)
        changes_orch = self.orchestrator.apply_approved_changes(doc_orch, out_orch, plan_orch)

        self.assertEqual(changes_legacy, changes_orch)

        # 3. Bandingkan seluruh teks paragraf dokumen hasil
        d_leg = Document(out_legacy)
        d_orc = Document(out_orch)

        paras_leg = [p.text for p in d_leg.paragraphs]
        paras_orc = [p.text for p in d_orc.paragraphs]
        self.assertEqual(paras_leg, paras_orc)

        # 4. Verifikasi laporan perubahan ChangeReportGenerator: paritas verdict 100%
        verifier = ChangeReportGenerator()
        _, rep_leg = verifier.generate_report(
            output_dir=out_leg_dir,
            input_dir=self.test_dir,
            plan_items=plan_legacy,
            rules=rules,
            mode="GABUNGAN"
        )
        _, rep_orc = verifier.generate_report(
            output_dir=out_orch_dir,
            input_dir=self.test_dir,
            plan_items=plan_orch,
            rules=rules,
            mode="GABUNGAN"
        )
        self.assertEqual(rep_leg["ringkasan"]["verdict"], rep_orc["ringkasan"]["verdict"])


if __name__ == "__main__":
    unittest.main()
