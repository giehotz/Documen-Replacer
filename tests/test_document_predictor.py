"""
Unit Test untuk Modul Prediksi Dokumen & Generator Aturan Cerdas.
Menguji deteksi struktur, ekstraksi kandidat pada dokumen format berbeda,
agregasi multi-format, dan penggabungan cerdas (smart merge).
"""
import unittest
import os
import shutil
import tempfile

from core.document_predictor import (
    extract_candidates_from_document,
    predict_rules_from_file,
    predict_rules_from_folder,
    smart_merge_rules,
)


class TestDocumentPredictor(unittest.TestCase):
    def setUp(self):
        samples_dir = os.path.join(os.path.dirname(__file__), "samples")
        os.makedirs(samples_dir, exist_ok=True)
        self.doc_bab1 = os.path.join(samples_dir, "sample_bab1.docx")
        self.doc_modul = os.path.join(samples_dir, "sample_modul_ajar.docx")

        if not os.path.exists(self.doc_bab1):
            from tests.generate_samples import create_sample_bab1
            create_sample_bab1(self.doc_bab1)
        if not os.path.exists(self.doc_modul):
            from tests.generate_samples import create_sample_modul_ajar
            create_sample_modul_ajar(self.doc_modul)

        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_extract_candidates_bab1(self):
        """Memastikan kandidat dari BAB 1.docx (tabel 1-kolom, Kepala Sekolah, 20.. /20..) terdeteksi."""
        self.assertTrue(os.path.exists(self.doc_bab1))
        candidates = extract_candidates_from_document(self.doc_bab1)

        self.assertIn("Istilah Jabatan Kepala", candidates)
        self.assertIn("Kepala Sekolah", candidates["Istilah Jabatan Kepala"])

        self.assertIn("Tahun Pelajaran", candidates)
        self.assertIn("20.. /20..", candidates["Tahun Pelajaran"])

        self.assertIn("Titimangsa", candidates)
        self.assertTrue(any("20.." in t for t in candidates["Titimangsa"]))

    def test_extract_candidates_modul_ajar(self):
        """Memastikan kandidat dari Modul Ajar (tabel 3-kolom, Kepala Madrasah, 2025/2026) terdeteksi."""
        self.assertTrue(os.path.exists(self.doc_modul))
        candidates = extract_candidates_from_document(self.doc_modul)

        self.assertIn("Istilah Jabatan Kepala", candidates)
        self.assertIn("Kepala Madrasah", candidates["Istilah Jabatan Kepala"])

        has_tp = "Tahun Pelajaran" in candidates or "Tahun Ajaran" in candidates
        self.assertTrue(has_tp)
        tp_values = candidates.get("Tahun Pelajaran", set()) | candidates.get("Tahun Ajaran", set())
        self.assertIn("2025/2026", tp_values)

        self.assertIn("Nama Madrasah", candidates)
        self.assertTrue(any("MI" in m for m in candidates["Nama Madrasah"]))

    def test_predict_rules_from_file(self):
        """Memastikan predict_rules_from_file menghasilkan aturan terstruktur lengkap."""
        rules = predict_rules_from_file(self.doc_bab1)
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)

        labels = [r["label"] for r in rules]
        self.assertIn("Nama Madrasah", labels)
        self.assertIn("Istilah Jabatan Kepala", labels)
        self.assertIn("Tahun Pelajaran", labels)

        # Cek bahwa old terisi dengan teks konkret yang ditemukan di BAB 1.docx
        tp_rules = [r for r in rules if r["label"] == "Tahun Pelajaran"]
        self.assertTrue(any(r["old"] == "20.. /20.." for r in tp_rules))

        jab_rules = [r for r in rules if r["label"] == "Istilah Jabatan Kepala"]
        self.assertTrue(any(r["old"] == "Kepala Sekolah" for r in jab_rules))

    def test_smart_merge_rules_preserves_user_values(self):
        """Memastikan smart_merge_rules mempertahankan isian Teks Baru milik pengguna."""
        user_rules = [
            {"label": "Nama Madrasah", "old": "", "new": "MIN 1 Bandar Lampung"},
            {"label": "Nama Guru Mata Pelajaran", "old": "", "new": "Budi Santoso, S.Pd"},
            {"label": "NIP Guru Mata Pelajaran", "old": "", "new": "198501012010011005"},
        ]

        predicted = [
            {"label": "Nama Madrasah", "old": "MI ......................................................", "new": "MIN 1 Bandar Lampung"},
            {"label": "Tahun Pelajaran", "old": "2025/2026", "new": "2026/2027"},
            {"label": "Nama Guru Mata Pelajaran", "old": "", "new": "Siti Aminah, S.Pd"},
        ]

        merged = smart_merge_rules(user_rules, predicted)

        # Cek bahwa Teks Baru milik pengguna tetap dipertahankan
        m_map = {r["label"]: r["new"] for r in merged}
        self.assertEqual(m_map["Nama Madrasah"], "MIN 1 Bandar Lampung")
        self.assertEqual(m_map["Nama Guru Mata Pelajaran"], "Budi Santoso, S.Pd")

        # Cek bahwa Teks Lama terisi dari predicted
        old_map = {r["label"]: r["old"] for r in merged}
        self.assertEqual(old_map["Nama Madrasah"], "MI ......................................................")
        self.assertEqual(old_map["Tahun Pelajaran"], "2025/2026")

    def test_predict_rules_from_folder_multi_format(self):
        """Memastikan pemindaian folder mengagregasi seluruh variasi format yang berbeda."""
        # Salin kedua file dengan format berbeda ke folder temporer
        shutil.copy(self.doc_bab1, os.path.join(self.test_dir, "doc1.docx"))
        shutil.copy(self.doc_modul, os.path.join(self.test_dir, "doc2.docx"))

        rules = predict_rules_from_folder(self.test_dir)
        tp_rules = [r for r in rules if r["label"] == "Tahun Pelajaran"]
        old_tp = [r["old"] for r in tp_rules]

        # Harus mencakup kedua variasi format tahun
        self.assertIn("20.. /20..", old_tp)
        self.assertIn("2025/2026", old_tp)

        jab_rules = [r for r in rules if r["label"] == "Istilah Jabatan Kepala"]
        old_jab = [r["old"] for r in jab_rules]
        # Harus mencakup kedua istilah jabatan
        self.assertIn("Kepala Sekolah", old_jab)
        self.assertIn("Kepala Madrasah", old_jab)

    def test_predict_rules_no_hardcoded_pii(self):
        """Memastikan prediksi tanpa defaults tidak menyertakan data pribadi yang di-hardcode."""
        rules = predict_rules_from_file(self.doc_bab1)
        for r in rules:
            self.assertEqual(r.get("new", ""), "", f"Nilai baru harus kosong tanpa defaults: {r}")
            # Pastikan tidak ada string nama pribadi/institusi bawaan lama
            self.assertNotIn("Tanggamus", r.get("new", ""))
            self.assertNotIn("Sipulloh", r.get("new", ""))
            self.assertNotIn("Dwi Putri", r.get("new", ""))

    def test_smart_merge_rules_preserves_multiple_variations(self):
        """Memastikan smart_merge mempertahankan beberapa variasi old dengan label yang sama."""
        user_rules = [
            {"label": "Tahun Pelajaran", "old": "2024/2025", "new": "2026/2027"},
        ]
        predicted = [
            {"label": "Tahun Pelajaran", "old": "2025/2026", "new": ""},
            {"label": "Tahun Pelajaran", "old": "20.. /20..", "new": ""},
        ]
        merged = smart_merge_rules(user_rules, predicted)
        tp_rules = [r for r in merged if r["label"] == "Tahun Pelajaran"]
        # Harus menyimpan semua variasi unik (2024/2025, 2025/2026, 20.. /20..)
        self.assertEqual(len(tp_rules), 3)
        # Dan semuanya harus mewarisi target 'new' yang sama dari pengguna
        for r in tp_rules:
            self.assertEqual(r["new"], "2026/2027")


if __name__ == "__main__":
    unittest.main()
