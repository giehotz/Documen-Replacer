"""
Unit test untuk manajemen Pustaka Tanda Tangan & Stempel (Signature & Stamp Library).
Menguji:
- Penyimpanan berkas di folder signatures/
- Metadata JSON di config/signature_library.json
- Penambahan, pemfilteran kategori, dan penghapusan item
- Skema pengaturan signature_settings dengan dukungan stempel & lanskap
"""
import unittest
import os
import shutil
import tempfile
from PIL import Image

from core.signature_image_service import (
    load_signature_settings,
    save_signature_settings,
    DEFAULT_SETTINGS,
    resolve_signature_settings_for_orientation,
    load_signature_library,
    save_signature_library,
    add_signature_item,
    delete_signature_item,
    get_signatures_by_category,
    get_signatures_dir,
)


class TestSignatureLibrary(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sig_test_")
        self.lib_path = os.path.join(self.test_dir, "test_library.json")
        self.img_path = os.path.join(self.test_dir, "sample_sig.png")

        # Buat gambar dummy
        img = Image.new("RGBA", (100, 50), color=(0, 0, 255, 128))
        img.save(self.img_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_signature_library_add_and_get(self):
        # Awal: kosong
        lib = load_signature_library(self.lib_path)
        self.assertEqual(lib["items"], [])

        # Tambah item Kepala
        item_k = add_signature_item("Dr. Ahmad Fauzi, M.Pd", "kepala", self.img_path, config_path=self.lib_path)
        self.assertEqual(item_k["name"], "Dr. Ahmad Fauzi, M.Pd")
        self.assertEqual(item_k["category"], "kepala")
        self.assertTrue(os.path.isfile(item_k["path"]))

        # Tambah item Guru
        item_g = add_signature_item("Siti Aminah, S.Pd", "guru", self.img_path, config_path=self.lib_path)
        self.assertEqual(item_g["category"], "guru")

        # Tambah item Stempel
        item_s = add_signature_item("Stempel Resmi MTsN 1", "stempel", self.img_path, config_path=self.lib_path)
        self.assertEqual(item_s["category"], "stempel")

        # Verifikasi filter kategori
        kepala_list = get_signatures_by_category("kepala", config_path=self.lib_path)
        self.assertEqual(len(kepala_list), 1)
        self.assertEqual(kepala_list[0]["id"], item_k["id"])

        guru_list = get_signatures_by_category("guru", config_path=self.lib_path)
        self.assertEqual(len(guru_list), 1)

        stempel_list = get_signatures_by_category("stempel", config_path=self.lib_path)
        self.assertEqual(len(stempel_list), 1)
        self.assertEqual(stempel_list[0]["name"], "Stempel Resmi MTsN 1")

        # Cleanup copied files
        for it in (item_k, item_g, item_s):
            if os.path.isfile(it["path"]):
                try:
                    os.remove(it["path"])
                except Exception:
                    pass

    def test_signature_library_delete(self):
        item = add_signature_item("Test Hapus", "guru", self.img_path, config_path=self.lib_path)
        copied_path = item["path"]
        self.assertTrue(os.path.isfile(copied_path))

        # Hapus item
        ok = delete_signature_item(item["id"], delete_file=True, config_path=self.lib_path)
        self.assertTrue(ok)

        # Pastikan terhapus dari metadata
        guru_items = get_signatures_by_category("guru", config_path=self.lib_path)
        self.assertEqual(len(guru_items), 0)

        # Pastikan file fisik di signatures/ terhapus
        self.assertFalse(os.path.isfile(copied_path))

        # Hapus item yang tidak ada mengembalikan False
        self.assertFalse(delete_signature_item("non_existent_id", config_path=self.lib_path))

    def test_signature_settings_with_stempel(self):
        cfg_path = os.path.join(self.test_dir, "test_signature_settings.json")

        settings = load_signature_settings(cfg_path)
        self.assertIn("enabled_stempel", settings)
        self.assertIn("stempel_image_path", settings)
        self.assertIn("offset_x_stempel_cm", settings)
        self.assertIn("stempel_width_cm", settings)
        self.assertEqual(settings["landscape"]["stempel_width_cm"], 3.5)

        settings["enabled_stempel"] = True
        settings["stempel_image_path"] = "path/to/stempel.png"
        settings["offset_x_stempel_cm"] = -1.8
        save_signature_settings(settings, cfg_path)

        reloaded = load_signature_settings(cfg_path)
        self.assertTrue(reloaded["enabled_stempel"])
        self.assertEqual(reloaded["offset_x_stempel_cm"], -1.8)

    def test_resolve_signature_settings_orientation(self):
        base_cfg = {
            "enabled_kepala": True,
            "kepala_width_cm": 3.5,
            "offset_x_kepala_cm": 0.0,
            "offset_y_kepala_cm": 0.0,
            "enabled_guru": True,
            "guru_width_cm": 3.5,
            "offset_x_guru_cm": 0.0,
            "offset_y_guru_cm": 0.0,
            "enabled_stempel": True,
            "stempel_width_cm": 3.5,
            "offset_x_stempel_cm": -1.5,
            "offset_y_stempel_cm": 0.0,
            "landscape": {
                "kepala_width_cm": 3.8,
                "offset_x_kepala_cm": -2.3,
                "offset_y_kepala_cm": 0.5,
                "guru_width_cm": 3.8,
                "offset_x_guru_cm": -2.3,
                "offset_y_guru_cm": 0.5,
                "stempel_width_cm": 3.6,
                "offset_x_stempel_cm": -3.8,
                "offset_y_stempel_cm": 0.2,
            }
        }

        # Potrait
        pot = resolve_signature_settings_for_orientation(base_cfg, is_landscape=False)
        self.assertEqual(pot["offset_x_kepala_cm"], 0.0)
        self.assertEqual(pot["offset_x_stempel_cm"], -1.5)

        # Lanskap dengan konfigurasi eksplisit
        land = resolve_signature_settings_for_orientation(base_cfg, is_landscape=True)
        self.assertEqual(land["offset_x_kepala_cm"], -2.3)
        self.assertEqual(land["offset_x_stempel_cm"], -3.8)
        self.assertEqual(land["stempel_width_cm"], 3.6)


if __name__ == "__main__":
    unittest.main()
