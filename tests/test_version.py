"""
Unit Test: Verifikasi integritas versi dan metadata rilis v1.1.0.
"""
import unittest
from core.version import __version__, APP_NAME, APP_TITLE, RELEASE_DATE


class TestVersionIntegrity(unittest.TestCase):
    def test_version_value(self):
        """Memastikan nomor versi kanonik adalah 1.1.0."""
        self.assertEqual(__version__, "1.1.0")

    def test_app_name_and_title(self):
        """Memastikan nama aplikasi dan format judul jendela konsisten."""
        self.assertEqual(APP_NAME, "Smart RPP & Document Replacer")
        self.assertEqual(APP_TITLE, "Smart RPP & Document Replacer v1.1.0")
        self.assertIn("1.1.0", APP_TITLE)

    def test_release_date_format(self):
        """Memastikan format tanggal rilis sesuai ISO 8601 (YYYY-MM-DD)."""
        self.assertEqual(RELEASE_DATE, "2026-11-14")


if __name__ == "__main__":
    unittest.main()
