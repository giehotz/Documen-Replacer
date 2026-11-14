"""
Unit test berbasis properti untuk tanggal_terbilang_helper.py (PRD §5.3-D & §7).
Menguji konversi angka <-> terbilang untuk seluruh 36.525 tanggal dari rentang tahun 2000 hingga 2099.
"""
import unittest
import datetime
from domains.berita_acara.tanggal_terbilang_helper import (
    format_date_to_words,
    parse_date_string,
    parse_terbilang_sentence,
    verify_terbilang_sync,
    DAY_WORDS_MAP,
    MONTH_WORDS_MAP,
    YEAR_WORDS_MAP,
)


class TestTanggalTerbilang(unittest.TestCase):
    def test_property_all_dates_roundtrip_2000_to_2099(self):
        """
        Pengujian properti: untuk setiap tanggal dari 2000-01-01 s.d 2099-12-31,
        hasil terbilang harus dapat direkonstruksi 100% kembali ke tanggal semula tanpa cacat.
        """
        start_date = datetime.date(2000, 1, 1)
        end_date = datetime.date(2099, 12, 31)

        curr = start_date
        tested_count = 0

        while curr <= end_date:
            comp = format_date_to_words(curr, capitalize=True)

            d_val = DAY_WORDS_MAP.get(comp["tanggal"].lower())
            m_val = MONTH_WORDS_MAP.get(comp["bulan"].lower())
            y_val = YEAR_WORDS_MAP.get(comp["tahun"].lower())

            self.assertEqual(d_val, curr.day, f"Gagal pada hari: {curr}")
            self.assertEqual(m_val, curr.month, f"Gagal pada bulan: {curr}")
            self.assertEqual(y_val, curr.year, f"Gagal pada tahun: {curr}")

            # Rekonstruksi tanggal utuh
            reconstructed = datetime.date(y_val, m_val, d_val)
            self.assertEqual(reconstructed, curr)

            tested_count += 1
            curr += datetime.timedelta(days=1)

        self.assertEqual(tested_count, 36525)

    def test_sentence_formatting_and_parsing(self):
        """Format kalimat pembuka Berita Acara dan parsing balik."""
        dt = datetime.date(2026, 11, 14)
        info = format_date_to_words(dt, capitalize=True)

        expected_sentence = "Pada hari ini Sabtu tanggal Empat Belas bulan November tahun Dua Ribu Dua Puluh Enam (14-11-2026)"
        self.assertEqual(info["kalimat_lengkap"], expected_sentence)

        # Parsing dari kalimat lengkap
        parsed_dt = parse_terbilang_sentence(expected_sentence)
        self.assertEqual(parsed_dt, dt)

        # Parsing tanpa kurung angka
        sentence_without_paren = "Pada hari ini Sabtu tanggal Empat Belas bulan November tahun Dua Ribu Dua Puluh Enam."
        parsed_dt_words_only = parse_terbilang_sentence(sentence_without_paren)
        self.assertEqual(parsed_dt_words_only, dt)

    def test_parse_date_string_formats(self):
        """Mengenali berbagai format tanggal masukan."""
        expected = datetime.date(2026, 11, 14)

        self.assertEqual(parse_date_string("2026-11-14"), expected)
        self.assertEqual(parse_date_string("14-11-2026"), expected)
        self.assertEqual(parse_date_string("14/11/2026"), expected)
        self.assertEqual(parse_date_string("14 November 2026"), expected)

    def test_verify_terbilang_sync(self):
        """Memverifikasi sinkronisasi antara kalimat naskah dan tanggal acuan."""
        dt = datetime.date(2026, 11, 14)
        valid_text = "Pada hari ini Sabtu tanggal Empat Belas bulan November tahun Dua Ribu Dua Puluh Enam (14-11-2026)"
        invalid_text = "Pada hari ini Senin tanggal Empat Belas bulan November tahun Dua Ribu Dua Puluh Enam (14-11-2026)"

        self.assertTrue(verify_terbilang_sync(valid_text, dt))
        self.assertFalse(verify_terbilang_sync(invalid_text, dt))


if __name__ == "__main__":
    unittest.main()
