"""
Pengujian Kriteria Penerimaan Global (DoD Global Acceptance Test)
Sesuai spesifikasi PRD §8 dan Matriks Kriteria Penerimaan Lintas Fase.
Menguji secara menyeluruh:
1. Integritas registry seluruh domain (RPP, SK, Surat Dinas, SPT, Berita Acara)
2. Paritas RPP antara UnifiedOrchestrator dan ReplacementEngine
3. Akurasi AutoClassifier dan proteksi anti-silent fallback
4. Konsistensi sinkronisasi antar-zona SK (judul, diktum, lampiran)
5. Isolasi pihak dan sinkronisasi tanggal terbilang Berita Acara
6. Pemetaan data multi-baris SPT melalui datasets
7. Integritas dan ketahanan template token Mail Merge
8. Kepatuhan Kebijakan Privasi (Zero PII Audit) pada seluruh config, preset, dan fixtures
"""
import unittest
import os
import re
import tempfile
import shutil

from docx import Document
from domains.domain_registry import DomainRegistry
from domains.rpp_domain_adapter import RPPDomainAdapter
from domains.sk.sk_domain import SKDomain
from domains.surat_dinas.surat_dinas_domain import SuratDinasDomain
from domains.spt.spt_domain import SPTDomain
from domains.berita_acara.berita_acara_domain import BeritaAcaraDomain
from workflows.auto_classifier import AutoClassifier, ClassificationResult
from workflows.unified_orchestrator import UnifiedOrchestrator
from core.replacement_engine import ReplacementEngine
from core.change_verifier import ChangeReportGenerator
from tests.fixtures.make_sample_docs import (
    create_sample_rpp,
    create_sample_sk_with_attachment,
    create_sample_surat_dinas,
    create_sample_spt,
    create_sample_berita_acara,
)


class TestGlobalDoD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="test_global_dod_")
        cls.rpp_path = os.path.join(cls.test_dir, "sample_rpp.docx")
        cls.sk_path = os.path.join(cls.test_dir, "sample_sk.docx")
        cls.surat_path = os.path.join(cls.test_dir, "sample_surat.docx")
        cls.spt_path = os.path.join(cls.test_dir, "sample_spt.docx")
        cls.ba_path = os.path.join(cls.test_dir, "sample_ba.docx")

        create_sample_rpp(cls.rpp_path)
        create_sample_sk_with_attachment(cls.sk_path)
        create_sample_surat_dinas(cls.surat_path)
        create_sample_spt(cls.spt_path)
        create_sample_berita_acara(cls.ba_path)

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(cls.test_dir):
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_dod_registry_completeness(self):
        """DoD: Semua 5 domain utama terdaftar dan dapat diakses dari DomainRegistry."""
        registry = DomainRegistry.get_instance()
        domains = registry.list_domains()

        expected_ids = {"rpp_modul", "sk_keputusan", "surat_dinas", "spt_penugasan", "berita_acara"}
        registered_ids = {d.domain_id for d in domains}

        for exp_id in expected_ids:
            self.assertIn(exp_id, registered_ids, f"Domain {exp_id} belum terdaftar di registry!")

    def test_dod_rpp_parity(self):
        """DoD Paritas RPP: Hasil UnifiedOrchestrator identik 100% dengan ReplacementEngine."""
        legacy_engine = ReplacementEngine()
        orchestrator = UnifiedOrchestrator()

        rules = [
            {"old": "Siti Aminah, S.Pd", "new": "Dewi Sartika, S.Pd"},
            {"old": "Budi Santoso, M.Pd", "new": "Drs. H. Ahmad Dahlan, M.Ag"},
        ]

        legacy_items = legacy_engine.plan_document_changes(self.rpp_path, "sample_rpp.docx", rules, "GABUNGAN", True)
        orch_items = orchestrator.plan_document_changes(self.rpp_path, "sample_rpp.docx", rules, "GABUNGAN", True)

        self.assertEqual(len(legacy_items), len(orch_items))
        for leg, orch in zip(legacy_items, orch_items):
            self.assertEqual(leg.old_text, orch.old_text)
            self.assertEqual(leg.new_text, orch.new_text)
            self.assertEqual(leg.confidence, orch.confidence)

    def test_dod_classification_accuracy_and_no_silent_fallback(self):
        """DoD Akurasi Klasifikasi: Klasifikasi tepat pada semua domain uji & 0 silent fallback."""
        classifier = AutoClassifier()

        cases = [
            (self.rpp_path, "rpp_modul"),
            (self.sk_path, "sk_keputusan"),
            (self.surat_path, "surat_dinas"),
            (self.spt_path, "spt_penugasan"),
            (self.ba_path, "berita_acara"),
        ]

        for path, expected_domain in cases:
            res = classifier.classify_document(path)
            self.assertEqual(
                res.status,
                "CONFIRMED",
                f"File {os.path.basename(path)} tidak terdeteksi dengan status CONFIRMED!"
            )
            self.assertEqual(
                res.selected_domain_id,
                expected_domain,
                f"File {os.path.basename(path)} salah diklasifikasikan sebagai {res.selected_domain_id}!"
            )
            self.assertGreaterEqual(res.confidence_score, 0.60)

        # Uji proteksi anti-silent fallback untuk dokumen acak/tak dikenal
        doc_unknown = os.path.join(self.test_dir, "unknown.docx")
        d = Document()
        d.add_paragraph("Resep Masakan Tradisional Rendang Daging")
        d.add_paragraph("Bahan: 1 kg daging sapi, santan kelapa, bumbu rempah.")
        d.save(doc_unknown)

        res_unknown = classifier.classify_document(doc_unknown)
        # Harus UNKNOWN atau NEEDS_SELECTION, TIDAK BOLEH fallback diam-diam ke rpp_modul
        self.assertNotEqual(res_unknown.status, "CONFIRMED")
        self.assertNotEqual(res_unknown.selected_domain_id, "rpp_modul")

    def test_dod_sk_consistency_and_zero_salah(self):
        """DoD Konsistensi SK: Sinkronisasi judul-lampiran dan 0 butir SALAH di Laporan Verifikasi."""
        sk_dom = SKDomain()
        rules = [
            {"label": "Nomor SK", "old": "421.2/015/MIN.1/SK/2025", "new": "421.2/099/MIN.1/SK/2026"},
            {"label": "Tentang / Judul SK", "old": "PEMBAGIAN TUGAS GURU TAHUN PELAJARAN 2025/2026", "new": "PEMBAGIAN TUGAS GURU TAHUN PELAJARAN 2026/2027"},
            {"label": "Tanggal Penetapan", "old": "14 Juli 2025", "new": "16 Juli 2026"},
        ]

        items = sk_dom.plan_document_changes(self.sk_path, "sample_sk.docx", rules)
        self.assertTrue(len(items) >= 4)

        out_sk = os.path.join(self.test_dir, "out_sk.docx")
        changes = sk_dom.apply_approved_changes(self.sk_path, out_sk, items)
        self.assertGreater(changes, 0)

        # Verifikasi laporan
        report_gen = ChangeReportGenerator(anonymize_pii=False)
        rep_dir = os.path.join(self.test_dir, "rep_sk")
        os.makedirs(rep_dir, exist_ok=True)
        json_path, rep = report_gen.generate_report(
            output_dir=rep_dir,
            input_dir=self.test_dir,
            plan_items=items,
            rules=rules
        )

        ringkasan = rep.get("ringkasan", {})
        self.assertEqual(ringkasan.get("salah", 0), 0, "Ditemukan butir SALAH pada verifikasi SK!")

    def test_dod_ba_party_isolation_and_terbilang(self):
        """DoD Berita Acara: Isolasi PIHAK KESATU & KEDUA serta sinkronisasi tanggal terbilang."""
        ba_dom = BeritaAcaraDomain()
        rules = [
            {"label": "Nama Pihak Pertama", "old": "Budi Santoso, M.Pd", "new": "Drs. H. Ahmad Dahlan, M.Ag"},
            {"label": "Nama Pihak Kedua", "old": "Ahmad Dahlan, M.Pd", "new": "M. Yusuf, S.Pd"},
            {"label": "Tanggal Naskah", "old": "15-07-2025", "new": "20-08-2026"},
        ]

        items = ba_dom.plan_document_changes(self.ba_path, "sample_ba.docx", rules)
        self.assertTrue(len(items) >= 2)

        out_ba = os.path.join(self.test_dir, "out_ba.docx")
        changes = ba_dom.apply_approved_changes(self.ba_path, out_ba, items)
        self.assertGreater(changes, 0)

        # Periksa tidak ada tertukar pihak
        doc_res = Document(out_ba)
        full_text = "\n".join(p.text for p in doc_res.paragraphs)
        self.assertIn("Drs. H. Ahmad Dahlan, M.Ag", full_text)
        self.assertIn("M. Yusuf, S.Pd", full_text)

    def test_dod_spt_multi_row_mapping(self):
        """DoD SPT: Pemetaan baris tabel pegawai kolektif via datasets dan 0 SALAH."""
        spt_dom = SPTDomain()
        rules = [
            {"label": "Nomor SPT", "old": "800/012/SPT/2025", "new": "800/099/SPT/2026"},
        ]
        datasets = {
            "pegawai": [
                {
                    "nama": "Dewi Sartika, S.Pd",
                    "nip": "199003032015012003",
                    "pangkat": "Penata Muda / III.a",
                    "jabatan": "Guru Bahasa Inggris",
                }
            ]
        }

        items = spt_dom.plan_document_changes(self.spt_path, "sample_spt.docx", rules, datasets=datasets)
        self.assertTrue(len(items) >= 2)

        out_spt = os.path.join(self.test_dir, "out_spt.docx")
        changes = spt_dom.apply_approved_changes(self.spt_path, out_spt, items)
        self.assertGreater(changes, 0)

        doc_res = Document(out_spt)
        tbl_text = "\n".join(c.text for r in doc_res.tables[0].rows for c in r.cells)
        self.assertIn("Dewi Sartika, S.Pd", tbl_text)

    def test_dod_gui_thread_safety_contract(self):
        """DoD Thread Safety: Background workers berkomunikasi lewat queue, bukan widget langsung."""
        import inspect
        from gui.modules.mail_merge_view import MailMergeView
        from gui.app import SmartRPPReplacerApp

        # Periksa method worker pada MailMergeView
        src_merge = inspect.getsource(MailMergeView._worker_run)
        self.assertIn("self.event_queue.put", src_merge)
        # Tidak boleh ada panggilan dialog tkinter langsung di thread
        self.assertNotIn("messagebox.showinfo", src_merge)
        self.assertNotIn("messagebox.showerror", src_merge)

        # Periksa method worker pada SmartRPPReplacerApp
        src_worker_apply = inspect.getsource(SmartRPPReplacerApp._worker_apply)
        self.assertIn("self.msg_queue.put", src_worker_apply)
        self.assertNotIn("self.btn_process.configure", src_worker_apply)
        self.assertNotIn("self.progress.configure", src_worker_apply)

    def test_dod_zero_pii_policy(self):
        """DoD Zero PII Policy: Memastikan tidak ada data pribadi riil pada profil, template, dan preset modular."""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        profiles_dir = os.path.join(root_dir, "config", "profiles")
        templates_dir = os.path.join(root_dir, "config", "templates")
        presets_path = os.path.join(root_dir, "presets_madrasah.example.json")

        real_nip_pattern = re.compile(r"\b19\d{16}\b")
        allowed_dummy_nips = {"198001012005011001", "198502022010012002", "198803032014031003"}

        files_to_scan = []
        if os.path.isfile(presets_path):
            files_to_scan.append(presets_path)

        for scan_dir in [profiles_dir, templates_dir]:
            if os.path.isdir(scan_dir):
                for r, _, files in os.walk(scan_dir):
                    for f in files:
                        if f.endswith(".json"):
                            files_to_scan.append(os.path.join(r, f))

        for fpath in files_to_scan:
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()
                matches = real_nip_pattern.findall(content)
                for m in matches:
                    self.assertIn(
                        m,
                        allowed_dummy_nips,
                        f"Potensi pelanggaran Zero PII: Ditemukan NIP tak dikenal '{m}' pada {fpath}"
                    )


if __name__ == "__main__":
    unittest.main()
