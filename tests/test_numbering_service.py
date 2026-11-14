"""
Unit test untuk Layanan Penomoran Otomatis (NumberingService).
Menguji penomoran berurut, formatting token romawi/tahun, mode dry-run,
rollback saat batal, dan deteksi duplikasi.
"""
import unittest
import os
import shutil
import tempfile
from datetime import datetime
from workflows.numbering_service import NumberingService


class TestNumberingService(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_num_svc_")
        self.storage_file = os.path.join(self.test_dir, "counters.json")
        self.service = NumberingService(storage_path=self.storage_file)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_preview_does_not_increment_counter(self):
        """Mode preview (dry-run) harus menghasilkan nomor tanpa memajukan counter."""
        fmt = "{NO_URUT:03d}/MIN.1/SK/{TAHUN}"
        dt = datetime(2025, 7, 14)

        prev1 = self.service.preview_next_number("sk_keputusan", fmt, ref_date=dt)
        self.assertEqual(prev1, "001/MIN.1/SK/2025")
        self.assertEqual(self.service.get_current_counter("sk_keputusan", 2025), 0)

        prev2 = self.service.preview_next_number("sk_keputusan", fmt, ref_date=dt)
        self.assertEqual(prev2, "001/MIN.1/SK/2025")
        self.assertEqual(self.service.get_current_counter("sk_keputusan", 2025), 0)

    def test_consume_number_increments_and_persists(self):
        """Mode consume harus menyimpan penambahan counter ke disk secara atomik."""
        fmt = "B-{NO_URUT:03d}/Min.01/PP.00/{BULAN_2DIGIT}/{TAHUN}"
        dt = datetime(2025, 7, 14)

        n1 = self.service.consume_number("surat_dinas", fmt, ref_date=dt)
        self.assertEqual(n1, "B-001/Min.01/PP.00/07/2025")
        self.assertEqual(self.service.get_current_counter("surat_dinas", 2025), 1)

        n2 = self.service.consume_number("surat_dinas", fmt, ref_date=dt)
        self.assertEqual(n2, "B-002/Min.01/PP.00/07/2025")
        self.assertEqual(self.service.get_current_counter("surat_dinas", 2025), 2)

        # Verifikasi reload dari storage terpisah
        new_svc = NumberingService(storage_path=self.storage_file)
        self.assertEqual(new_svc.get_current_counter("surat_dinas", 2025), 2)

    def test_rollback_number(self):
        """Rollback harus mengembalikan counter ke nilai sebelumnya bila proses dibatalkan."""
        fmt = "{NO_URUT:03d}/SK/{TAHUN}"
        dt = datetime(2025, 7, 14)

        self.service.consume_number("sk", fmt, ref_date=dt)
        self.service.consume_number("sk", fmt, ref_date=dt)
        self.assertEqual(self.service.get_current_counter("sk", 2025), 2)

        res = self.service.rollback_number("sk", 2025, count=1)
        self.assertTrue(res)
        self.assertEqual(self.service.get_current_counter("sk", 2025), 1)

    def test_manual_start_number(self):
        """Mendukung penomoran dengan nilai awal manual."""
        fmt = "{NO_URUT:04d}/SPT/{TAHUN}"
        dt = datetime(2025, 1, 10)

        n = self.service.consume_number("spt", fmt, ref_date=dt, manual_start=15)
        self.assertEqual(n, "0015/SPT/2025")
        self.assertEqual(self.service.get_current_counter("spt", 2025), 15)

    def test_roman_month_and_extra_variables(self):
        """Mendukung token {BULAN_ROMAWI} dan ekstra variabel kustom."""
        fmt = "B-{NO_URUT:03d}/{KODE_SATKER}/UND/{BULAN_ROMAWI}/{TAHUN}"
        dt = datetime(2025, 11, 20)
        extra = {"KODE_SATKER": "MIN.01"}

        num = self.service.preview_next_number("undangan", fmt, ref_date=dt, extra_vars=extra)
        self.assertEqual(num, "B-001/MIN.01/UND/XI/2025")

    def test_check_duplicate_in_dir(self):
        """Pemeriksaan duplikasi nomor pada folder keluaran."""
        out_dir = os.path.join(self.test_dir, "output")
        os.makedirs(out_dir, exist_ok=True)

        existing_file = os.path.join(out_dir, "Surat_B_005_Min_01.docx")
        with open(existing_file, "w") as f:
            f.write("dummy")

        dups = self.service.check_duplicate_in_dir(out_dir, "B-005/Min.01")
        self.assertEqual(len(dups), 1)
        self.assertIn("Surat_B_005_Min_01.docx", dups[0])

        no_dups = self.service.check_duplicate_in_dir(out_dir, "B-006/Min.01")
        self.assertEqual(len(no_dups), 0)


if __name__ == "__main__":
    unittest.main()
