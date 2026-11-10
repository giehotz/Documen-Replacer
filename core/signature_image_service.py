"""
Layanan Manajemen dan Penyisipan Gambar Tanda Tangan Digital.
Menangani:
- Penyimpanan dan pemuatan konfigurasi tanda tangan (config/signature_settings.json)
- Penyisipan gambar ke paragraf dokumen Word dengan ukuran (Cm) dan perataan presisi.
"""
from typing import Dict, Any, Optional
import os
import json
import logging
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "enabled_kepala": False,
    "kepala_image_path": "",
    "kepala_width_cm": 3.5,
    "offset_x_kepala_cm": 0.0,
    "offset_y_kepala_cm": 0.0,
    "enabled_guru": False,
    "guru_image_path": "",
    "guru_width_cm": 3.5,
    "offset_x_guru_cm": 0.0,
    "offset_y_guru_cm": 0.0,
    "alignment": "CENTER",
    "behind_text": True,
    "spacing_before_pt": 2,
    "spacing_after_pt": 2,
    "landscape": {
        "kepala_width_cm": 3.5,
        "offset_x_kepala_cm": -2.3,
        "offset_y_kepala_cm": 0.0,
        "guru_width_cm": 3.5,
        "offset_x_guru_cm": -2.3,
        "offset_y_guru_cm": 0.0,
    },
}


def is_document_landscape(doc) -> bool:
    """Mendeteksi apakah dokumen Word berorientasi lanskap."""
    if not doc or not doc.sections:
        return False
    s = doc.sections[0]
    try:
        from docx.enum.section import WD_ORIENTATION
        return (s.orientation == WD_ORIENTATION.LANDSCAPE) or (s.page_width > s.page_height)
    except Exception:
        return bool(s.page_width and s.page_height and s.page_width > s.page_height)


def resolve_signature_settings_for_orientation(settings: Optional[Dict[str, Any]], is_landscape: bool) -> Dict[str, Any]:
    """
    Mengambil konfigurasi tanda tangan yang sesuai dengan orientasi halaman.
    Jika is_landscape True, menimpa lebar & offset dengan konfigurasi blok 'landscape'.
    """
    if not settings:
        return {}
    res = dict(settings)
    if is_landscape:
        land_cfg = settings.get("landscape")
        if isinstance(land_cfg, dict):
            for k in (
                "kepala_width_cm", "offset_x_kepala_cm", "offset_y_kepala_cm",
                "guru_width_cm", "offset_x_guru_cm", "offset_y_guru_cm"
            ):
                if k in land_cfg:
                    res[k] = land_cfg[k]
        else:
            # Kompensasi otomatis jika belum dikonfigurasi: kolom lanskap lebih lebar ~4.6cm
            res["offset_x_kepala_cm"] = round(float(res.get("offset_x_kepala_cm", 0.0)) - 2.3, 2)
            res["offset_x_guru_cm"] = round(float(res.get("offset_x_guru_cm", 0.0)) - 2.3, 2)
    return res


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
                settings = dict(DEFAULT_SETTINGS)
                # Salin landscape default agar tidak tertimpa kosong
                settings["landscape"] = dict(DEFAULT_SETTINGS["landscape"])
                settings.update(data)
                if isinstance(data.get("landscape"), dict):
                    merged_land = dict(DEFAULT_SETTINGS["landscape"])
                    merged_land.update(data["landscape"])
                    settings["landscape"] = merged_land
                return settings
        except Exception:
            pass

    res = dict(DEFAULT_SETTINGS)
    res["landscape"] = dict(DEFAULT_SETTINGS["landscape"])
    return res


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
    behind_text: bool = True,
    offset_x_cm: float = 0.0,
    offset_y_cm: float = 0.0,
    cell_width_emu: Optional[int] = None,
) -> bool:
    """
    Menyisipkan berkas gambar tanda tangan ke dalam objek Paragraph python-docx.
    Mendukung mode 'Behind Text' (di belakang teks) dengan offset X & Y (geser kanan/kiri/atas/bawah),
    atau mode inline biasa.
    """
    if not image_path or not os.path.isfile(image_path):
        return False

    align_map = {
        "CENTER": WD_ALIGN_PARAGRAPH.CENTER,
        "LEFT": WD_ALIGN_PARAGRAPH.LEFT,
        "RIGHT": WD_ALIGN_PARAGRAPH.RIGHT,
    }

    try:
        if not behind_text:
            paragraph.alignment = align_map.get(alignment.upper(), WD_ALIGN_PARAGRAPH.CENTER)
            paragraph.paragraph_format.space_before = Pt(spacing_before_pt)
            paragraph.paragraph_format.space_after = Pt(spacing_after_pt)

            if paragraph.runs:
                for r in paragraph.runs[1:]:
                    r.text = ""
                run = paragraph.runs[0]
                run.text = ""
            else:
                run = paragraph.add_run()

            run.add_picture(image_path, width=Cm(width_cm))
            return True

        # Mode Behind Text (Di Belakang Teks) via DrawingML wp:anchor
        from docx.oxml import parse_xml
        run = paragraph.add_run()
        inline_shape = run.add_picture(image_path, width=Cm(width_cm))
        inline_elem = inline_shape._inline
        extent = inline_elem.extent
        cx = extent.cx
        cy = extent.cy
        docPr = inline_elem.docPr
        doc_id = docPr.id
        doc_name = docPr.name
        graphic = inline_elem.graphic

        # Hitung posisi horizontal (X) di dalam kolom sel tabel
        cell_w = cell_width_emu if (cell_width_emu and cell_width_emu > 0) else int(8.0 * 360000)
        al_upper = alignment.upper()
        if al_upper == "LEFT":
            base_x = 0
        elif al_upper == "RIGHT":
            base_x = max(0, cell_w - cx)
        else:  # CENTER
            base_x = max(0, int((cell_w - cx) / 2))

        x_emu = int(base_x + offset_x_cm * 360000)

        # Hitung posisi vertikal (Y) relatif terhadap paragraf nama
        # Nilai negatif menaikkan gambar ke atas nama, nilai positif menurunkan
        base_y = -int(cy * 0.85)
        y_emu = int(base_y + offset_y_cm * 360000)

        anchor_xml = f'''<wp:anchor xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                   xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                   xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
                   distT="0" distB="0" distL="0" distR="0"
                   simplePos="0" relativeHeight="251658240"
                   behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1">
            <wp:simplePos x="0" y="0"/>
            <wp:positionH relativeFrom="column">
                <wp:posOffset>{x_emu}</wp:posOffset>
            </wp:positionH>
            <wp:positionV relativeFrom="paragraph">
                <wp:posOffset>{y_emu}</wp:posOffset>
            </wp:positionV>
            <wp:extent cx="{cx}" cy="{cy}"/>
            <wp:effectExtent l="0" t="0" r="0" b="0"/>
            <wp:wrapNone/>
            <wp:docPr id="{doc_id}" name="{doc_name}"/>
            <wp:cNvGraphicFramePr>
                <a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>
            </wp:cNvGraphicFramePr>
        </wp:anchor>'''

        anchor_elem = parse_xml(anchor_xml)
        anchor_elem.append(graphic)

        drawing_elem = inline_elem.getparent()
        drawing_elem.replace(inline_elem, anchor_elem)
        return True
    except Exception as e:
        logger.warning("Gagal menyisipkan gambar tanda tangan '%s': %s", image_path, e, exc_info=True)
        return False
