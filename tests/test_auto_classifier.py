"""
Unit test untuk workflows/auto_classifier.py (PRD §5.2 & §7).
Memastikan klasifikasi dokumen berbasis skor berbobot, ambang batas, dan penanganan status ambigu.
"""
import os
import shutil
import tempfile
import unittest
from docx import Document

from workflows.auto_classifier import AutoClassifier
from domains.domain_registry import DomainRegistry
from domains.rpp_domain_adapter import RPPDomainAdapter
from tests.fixtures.make_sample_docs import (
    create_sample_rpp,
    create_sample_sk,
    create_sample_surat_dinas,
    create_sample_spt,
    create_sample_berita_acara,
)
from domains.sk.sk_domain import SKDomain
from domains.surat_dinas.surat_dinas_domain import SuratDinasDomain
from domains.spt.spt_domain import SPTDomain
from domains.berita_acara.berita_acara_domain import BeritaAcaraDomain


class TestAutoClassifier(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.registry = DomainRegistry(auto_register_defaults=False)
        self.registry.register(RPPDomainAdapter())
        self.classifier = AutoClassifier(registry=self.registry)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_classify_rpp_confirmed(self):
        """Memastikan dokumen RPP sintetis diklasifikasikan sebagai rpp_modul dengan status CONFIRMED."""
        rpp_path = os.path.join(self.test_dir, "sample_rpp.docx")
        create_sample_rpp(rpp_path)

        res = self.classifier.classify_document(rpp_path)
        self.assertEqual(res.status, "CONFIRMED")
        self.assertEqual(res.selected_domain_id, "rpp_modul")
        self.assertFalse(res.is_ambiguous)
        self.assertGreaterEqual(res.confidence_score, 0.60)

    def test_sk_document_not_falsely_classified_as_rpp(self):
        """
        Memastikan dokumen SK yang memuat indikator negatif RPP (MEMUTUSKAN, SURAT KEPUTUSAN)
        TIDAK salah-arah diam-diam ke RPP, melainkan berstatus NEEDS_SELECTION bila domain SK belum didaftarkan.
        """
        sk_path = os.path.join(self.test_dir, "sample_sk.docx")
        create_sample_sk(sk_path)

        res = self.classifier.classify_document(sk_path)
        self.assertEqual(res.status, "NEEDS_SELECTION")
        self.assertIsNone(res.selected_domain_id)
        self.assertTrue(res.is_ambiguous)

    def test_classify_sk_confirmed_when_domain_registered(self):
        """Memastikan dokumen SK terklasifikasi sebagai sk_keputusan saat SKDomain didaftarkan."""
        self.registry.register(SKDomain())
        sk_path = os.path.join(self.test_dir, "sample_sk.docx")
        create_sample_sk(sk_path)

        res = self.classifier.classify_document(sk_path)
        self.assertEqual(res.status, "CONFIRMED")
        self.assertEqual(res.selected_domain_id, "sk_keputusan")
        self.assertGreaterEqual(res.confidence_score, 0.60)

    def test_classify_surat_dinas_confirmed(self):
        """Memastikan dokumen Surat Dinas terklasifikasi sebagai surat_dinas."""
        self.registry.register(SuratDinasDomain())
        surat_path = os.path.join(self.test_dir, "sample_surat.docx")
        create_sample_surat_dinas(surat_path)

        res = self.classifier.classify_document(surat_path)
        self.assertEqual(res.status, "CONFIRMED")
        self.assertEqual(res.selected_domain_id, "surat_dinas")
        self.assertGreaterEqual(res.confidence_score, 0.60)

    def test_classify_spt_confirmed(self):
        """Memastikan dokumen SPT terklasifikasi sebagai spt_penugasan."""
        self.registry.register(SPTDomain())
        spt_path = os.path.join(self.test_dir, "sample_spt.docx")
        create_sample_spt(spt_path)

        res = self.classifier.classify_document(spt_path)
        self.assertEqual(res.status, "CONFIRMED")
        self.assertEqual(res.selected_domain_id, "spt_penugasan")
        self.assertGreaterEqual(res.confidence_score, 0.60)

    def test_classify_berita_acara_confirmed(self):
        """Memastikan dokumen Berita Acara terklasifikasi sebagai berita_acara."""
        self.registry.register(BeritaAcaraDomain())
        ba_path = os.path.join(self.test_dir, "sample_ba.docx")
        create_sample_berita_acara(ba_path)

        res = self.classifier.classify_document(ba_path)
        self.assertEqual(res.status, "CONFIRMED")
        self.assertEqual(res.selected_domain_id, "berita_acara")
        self.assertGreaterEqual(res.confidence_score, 0.60)

    def test_empty_or_unrecognized_document_needs_selection(self):
        """Dokumen kosong atau tanpa kata kunci khas harus ditandai NEEDS_SELECTION."""
        blank_path = os.path.join(self.test_dir, "blank.docx")
        doc = Document()
        doc.add_paragraph("Catatan Acak Tanpa Kata Kunci Pembelajaran Maupun Administrasi")
        doc.save(blank_path)

        res = self.classifier.classify_document(blank_path)
        self.assertEqual(res.status, "NEEDS_SELECTION")
        self.assertIsNone(res.selected_domain_id)
        self.assertTrue(res.is_ambiguous)


if __name__ == "__main__":
    unittest.main()
