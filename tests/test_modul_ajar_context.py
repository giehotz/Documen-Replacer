"""
Unit Test: Pengenalan Konteks Tabel Identitas Multi-Paragraf Modul Ajar (BAB 5 & BAB 7).
Memastikan label identitas (Penyusun, Instansi, Tahun Penyusunan, Jenjang Sekolah)
dikenali dengan tepat dan diganti secara presisi tanpa salah sasaran.
"""
import os
import unittest
import docx

from core.replacement_engine import ReplacementEngine


class TestModulAjarContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ReplacementEngine()
        cls.bab5_path = os.path.join(
            "docs", "example", "Modul Ajar BI", "Semester 2", "BAB 5 - MA B Indo Kls 2.docx"
        )
        cls.bab7_path = os.path.join(
            "docs", "example", "Modul Ajar BI", "Semester 2", "BAB 7 - MA B Indo Kls 2.docx"
        )

    def test_bab5_multi_paragraph_table_detection(self):
        """Memastikan tabel multi-paragraf A. IDENTITAS MODUL pada BAB 5 terdeteksi."""
        if not os.path.isfile(self.bab5_path):
            self.skipTest(f"Berkas tidak ditemukan: {self.bab5_path}")

        rules = [
            {"label": "Tahun Ajaran", "new": "2026/2027"},
            {"label": "Nama Madrasah", "new": "MIN 1 Contoh"},
            {"label": "Nama Guru", "new": "Budi Santoso, S.Pd"},
        ]
        items = self.engine.plan_document_changes(self.bab5_path, "BAB 5", rules, mode="GABUNGAN")

        # Harus menemukan usulan untuk Penyusun, Instansi, Tahun Penyusunan, dan Jenjang Sekolah (SD -> SD/MI)
        categories = {it.category for it in items}
        self.assertIn("Nama Guru", categories)
        self.assertIn("Nama Madrasah", categories)
        self.assertIn("Tahun Penyusunan", categories)
        self.assertIn("Jenjang Sekolah", categories)

        # Periksa nilai spesifik yang diusulkan
        instansi_items = [it for it in items if it.category == "Nama Madrasah" and "Tabel Identitas #1" in it.location_info]
        self.assertEqual(len(instansi_items), 1)
        self.assertEqual(instansi_items[0].old_text, "SD ...............................")
        self.assertEqual(instansi_items[0].new_text, "MIN 1 Contoh")

        tahun_items = [it for it in items if it.category == "Tahun Penyusunan"]
        self.assertEqual(len(tahun_items), 1)
        self.assertEqual(tahun_items[0].old_text, "Tahun 20…")
        self.assertEqual(tahun_items[0].new_text, "Tahun 2026/2027")

        jenjang_items = [it for it in items if it.category == "Jenjang Sekolah"]
        self.assertEqual(len(jenjang_items), 1)
        self.assertEqual(jenjang_items[0].old_text, "SD")
        self.assertEqual(jenjang_items[0].new_text, "SD/MI")

    def test_bab7_multi_paragraph_table_detection(self):
        """Memastikan tabel multi-paragraf A. IDENTITAS MODUL pada BAB 7 terdeteksi."""
        if not os.path.isfile(self.bab7_path):
            self.skipTest(f"Berkas tidak ditemukan: {self.bab7_path}")

        rules = [
            {"label": "Tahun Ajaran", "new": "2026/2027"},
            {"label": "Nama Madrasah", "new": "MIN 1 Malang"},
            {"label": "Nama Guru", "new": "Siti Nurhaliza, S.Pd"},
        ]
        items = self.engine.plan_document_changes(self.bab7_path, "BAB 7", rules, mode="GABUNGAN")

        categories = {it.category for it in items}
        self.assertIn("Nama Guru", categories)
        self.assertIn("Nama Madrasah", categories)
        self.assertIn("Tahun Penyusunan", categories)
        self.assertIn("Jenjang Sekolah", categories)
        self.assertEqual(len(items), 4)

    def test_only_tahun_ajaran_rule_replaces_only_tahun(self):
        """
        Sesuai kriteria pengguna:
        Ketika pengguna HANYA memasukkan Tahun Ajaran 2026/2027:
        - Tahun Ajaran / Tahun Penyusunan diisi 2026/2027
        - Penyusun tetap kosong
        - NIP tetap kosong
        - Nama Sekolah tetap kosong
        - Jenjang Sekolah tetap tidak berubah (SD tetap SD)
        """
        if not os.path.isfile(self.bab5_path):
            self.skipTest(f"Berkas tidak ditemukan: {self.bab5_path}")

        rules = [
            {"label": "Tahun Ajaran", "new": "2026/2027"}
        ]
        items = self.engine.plan_document_changes(self.bab5_path, "BAB 5", rules, mode="GABUNGAN")

        # Hanya 2 titik yang boleh diusulkan: Tahun Ajaran di cover (Tabel 0) dan Tahun Penyusunan di modul (Tabel 1)
        self.assertEqual(len(items), 2)
        for it in items:
            self.assertIn(it.category, ("Tahun Ajaran", "Tahun Penyusunan"))

        # Pastikan tidak ada Nama Guru, Nama Madrasah, Jenjang Sekolah, dsb. yang diusulkan
        categories = {it.category for it in items}
        self.assertNotIn("Nama Guru", categories)
        self.assertNotIn("Nama Madrasah", categories)
        self.assertNotIn("Jenjang Sekolah", categories)

    def test_mapel_and_fase_kelas_replacement(self):
        """Memastikan Mata Pelajaran dan Fase / Kelas terdeteksi dan diganti dengan tepat."""
        if not os.path.isfile(self.bab5_path):
            self.skipTest(f"Berkas tidak ditemukan: {self.bab5_path}")

        rules = [
            {"label": "Mata Pelajaran", "new": "IPAS"},
            {"label": "Fase / Kelas", "new": "Fase B / Kelas IV"},
        ]
        items = self.engine.plan_document_changes(self.bab5_path, "BAB 5", rules, mode="GABUNGAN")

        categories = {it.category for it in items}
        self.assertIn("Mata Pelajaran", categories)
        self.assertIn("Fase / Kelas", categories)

        # Di cover (Tabel 0)
        t0_mapel = [it for it in items if it.category == "Mata Pelajaran" and "Tabel Identitas #0" in it.location_info]
        self.assertEqual(len(t0_mapel), 1)
        self.assertEqual(t0_mapel[0].new_text, "IPAS")

        t0_fase = [it for it in items if it.category == "Fase / Kelas" and "Tabel Identitas #0" in it.location_info]
        self.assertEqual(len(t0_fase), 1)
        self.assertEqual(t0_fase[0].new_text, "Fase B / Kelas IV")

        # Di tabel modul (Tabel 1)
        t1_mapel = [it for it in items if it.category == "Mata Pelajaran" and "Tabel Identitas #1" in it.location_info]
        self.assertEqual(len(t1_mapel), 1)
        self.assertEqual(t1_mapel[0].old_text, "Bahasa Indonesia")
        self.assertEqual(t1_mapel[0].new_text, "IPAS")

        t1_fase = [it for it in items if it.category == "Fase / Kelas" and "Tabel Identitas #1" in it.location_info]
        self.assertEqual(len(t1_fase), 1)
        self.assertEqual(t1_fase[0].old_text, "A / II (Dua)")
        self.assertEqual(t1_fase[0].new_text, "Fase B / Kelas IV")


if __name__ == "__main__":
    unittest.main()
