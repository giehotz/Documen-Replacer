"""
Layanan Manajemen dan Penyisipan Gambar Tanda Tangan Digital.
Menangani:
- Penyimpanan dan pemuatan konfigurasi tanda tangan (config/signature_settings.json)
- Penyisipan gambar ke paragraf dokumen Word dengan ukuran (Cm) dan perataan presisi.
"""
from typing import Dict, Any, Optional
import os
import json
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

DEFAULT_SETTINGS: Dict[str, Any] = {
    "enabled_kepala": False,
    "kepala_image_path": "",
    "kepala_width_cm": 3.5,
    "enabled_guru": False,
    "guru_image_path": "",
    "guru_width_cm": 3.5,
    "alignment": "CENTER",
    "spacing_before_pt": 2,
    "spacing_after_pt": 2,
}


def get_default_config_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "config", "signature_settings.json")


def load_signature_settings(config_path: str = "") -> Dict[str, Any]:
    """Memuat pengaturan tanda tangan dari berkas JSON."""
    if not config_path:
        config_path = get_default_config_path()

    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                settings = DEFAULT_SETTINGS.copy()
                settings.update(data)
                return settings
        except Exception:
            pass

    return DEFAULT_SETTINGS.copy()


def save_signature_settings(settings: Dict[str, Any], config_path: str = "") -> None:
    """Menyimpan pengaturan tanda tangan ke berkas JSON."""
    if not config_path:
        config_path = get_default_config_path()

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def insert_signature_picture(
    paragraph,
    image_path: str,
    width_cm: float = 3.5,
    alignment: str = "CENTER",
    spacing_before_pt: int = 2,
    spacing_after_pt: int = 2,
) -> bool:
    """
    Menyisipkan berkas gambar tanda tangan ke dalam objek Paragraph python-docx.
    Mengatur lebar gambar, perataan horizontal, dan spasi sebelum/setelah paragraf.
    """
    if not image_path or not os.path.isfile(image_path):
        return False

    align_map = {
        "CENTER": WD_ALIGN_PARAGRAPH.CENTER,
        "LEFT": WD_ALIGN_PARAGRAPH.LEFT,
        "RIGHT": WD_ALIGN_PARAGRAPH.RIGHT,
    }

    try:
        paragraph.alignment = align_map.get(alignment.upper(), WD_ALIGN_PARAGRAPH.CENTER)
        paragraph.paragraph_format.space_before = Pt(spacing_before_pt)
        paragraph.paragraph_format.space_after = Pt(spacing_after_pt)

        # Bersihkan teks paragraf jika ada
        paragraph.text = ""
        run = paragraph.add_run()
        run.add_picture(image_path, width=Cm(width_cm))
        return True
    except Exception:
        return False
