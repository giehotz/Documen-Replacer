"""
Unit test untuk profile_loader.py dan profile_driven_domain.py (PRD §6 & §7).
Memastikan berkas profil *.profile.json skema v2 dimuat dengan benar beserta inheritance.
"""
import os
import json
import shutil
import tempfile
import unittest

from domains.profile_loader import load_domain_profile, DomainProfile
from domains.profile_driven_domain import ProfileDrivenDomain
from tests.fixtures.make_sample_docs import create_sample_rpp


class TestProfileLoader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_load_real_rpp_profile(self):
        """Memastikan berkas config/profiles/rpp_modul_ajar.profile.json termuat dengan inheritance."""
        profile_path = os.path.join("config", "profiles", "rpp_modul_ajar.profile.json")
        self.assertTrue(os.path.isfile(profile_path))

        profile: DomainProfile = load_domain_profile(profile_path)
        self.assertEqual(profile.schema_version, 2)
        self.assertEqual(profile.profile_id, "rpp_modul")
        self.assertGreater(len(profile.fields), 0)

        # Pastikan field warisan seperti nama_lembaga dan nama_kepala ada
        field_ids = {f.get("id") for f in profile.fields}
        self.assertIn("nama_lembaga", field_ids)
        self.assertIn("nama_kepala", field_ids)
        self.assertIn("tahun_pelajaran", field_ids)

    def test_reject_unsupported_schema_version(self):
        """Memastikan skema versi bukan 2 ditolak dengan ValueError."""
        bad_profile_file = os.path.join(self.test_dir, "bad_schema.profile.json")
        with open(bad_profile_file, "w", encoding="utf-8") as f:
            json.dump({"schema_version": 99, "profile_id": "invalid"}, f)

        with self.assertRaises(ValueError):
            load_domain_profile(bad_profile_file)

    def test_profile_driven_domain_execution(self):
        """Memastikan ProfileDrivenDomain dapat membaca profil dan mendeteksi skor dokumen."""
        profile_path = os.path.join("config", "profiles", "rpp_modul_ajar.profile.json")
        profile = load_domain_profile(profile_path)
        p_domain = ProfileDrivenDomain(profile)

        sample_doc = os.path.join(self.test_dir, "rpp_sample.docx")
        create_sample_rpp(sample_doc)

        detect_res = p_domain.detect_score(sample_doc)
        self.assertGreater(detect_res.score, 0.4)
        self.assertGreater(len(detect_res.reasons), 0)


if __name__ == "__main__":
    unittest.main()
