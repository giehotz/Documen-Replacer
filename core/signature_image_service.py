"""
Layanan Manajemen dan Penyisipan Gambar Tanda Tangan Digital.
Menangani:
- Penyimpanan dan pemuatan konfigurasi tanda tangan (config/signature_settings.json)
- Penyisipan gambar ke paragraf dokumen Word dengan ukuran (Cm) dan perataan presisi.
"""
from typing import Dict, Any, Optional, List
import os
import json
import logging
import time
import shutil
import re
from datetime import datetime
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "enabled_kepala": False,
    "kepala_image_path": "",
    "kepala_name": "",
    "kepala_width_cm": 3.5,
    "offset_x_kepala_cm": 0.0,
    "offset_y_kepala_cm": 0.0,
    "enabled_guru": False,
    "guru_image_path": "",
    "guru_name": "",
    "guru_width_cm": 3.5,
    "offset_x_guru_cm": 0.0,
    "offset_y_guru_cm": 0.0,
    "enabled_stempel": False,
    "stempel_image_path": "",
    "stempel_name": "",
    "stempel_width_cm": 3.5,
    "offset_x_stempel_cm": -1.5,
    "offset_y_stempel_cm": 0.0,
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
        "stempel_width_cm": 3.5,
        "offset_x_stempel_cm": -3.8,
        "offset_y_stempel_cm": 0.0,
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
                "guru_width_cm", "offset_x_guru_cm", "offset_y_guru_cm",
                "stempel_width_cm", "offset_x_stempel_cm", "offset_y_stempel_cm",
            ):
                if k in land_cfg:
                    res[k] = land_cfg[k]
        else:
            # Kompensasi otomatis jika belum dikonfigurasi: kolom lanskap lebih lebar ~4.6cm
            res["offset_x_kepala_cm"] = round(float(res.get("offset_x_kepala_cm", 0.0)) - 2.3, 2)
            res["offset_x_guru_cm"] = round(float(res.get("offset_x_guru_cm", 0.0)) - 2.3, 2)
            res["offset_x_stempel_cm"] = round(float(res.get("offset_x_stempel_cm", -1.5)) - 2.3, 2)
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


def get_signatures_dir() -> str:
    """Mengembalikan direktori penyimpanan berkas tanda tangan fisik di root proyek."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sig_dir = os.path.join(base_dir, "signatures")
    os.makedirs(sig_dir, exist_ok=True)
    return sig_dir


def get_library_config_path() -> str:
    """Mengembalikan path file metadata pustaka tanda tangan."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "config", "signature_library.json")


def load_signature_library(config_path: str = "") -> Dict[str, Any]:
    """Memuat daftar pustaka tanda tangan & stempel tersimpan."""
    if not config_path:
        config_path = get_library_config_path()

    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                    return data
        except Exception as e:
            logger.warning("Gagal membaca signature_library.json: %s", e)

    return {"items": []}


def save_signature_library(library_data: Dict[str, Any], config_path: str = "") -> None:
    """Menyimpan daftar pustaka tanda tangan & stempel ke berkas JSON."""
    if not config_path:
        config_path = get_library_config_path()

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(library_data, f, indent=2, ensure_ascii=False)


def add_signature_item(name: str, category: str, src_path: str, config_path: str = "") -> Dict[str, Any]:
    """
    Menambahkan tanda tangan atau stempel baru ke pustaka.
    Menyalin berkas gambar ke folder 'signatures/' dengan nama unik dan aman.
    """
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Nama tanda tangan / instansi tidak boleh kosong.")
    if not src_path or not os.path.isfile(src_path):
        raise FileNotFoundError(f"Berkas gambar sumber tidak ditemukan: {src_path}")

    cat = category.strip().lower()
    if cat not in ("kepala", "guru", "stempel"):
        cat = "kepala"

    sig_dir = get_signatures_dir()
    _, ext = os.path.splitext(src_path)
    if not ext:
        ext = ".png"

    # Sanitasi nama berkas
    slug = re.sub(r"[^\w\-]", "_", clean_name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")[:40] or "sig"
    ts = int(time.time() * 1000)
    dest_filename = f"{cat}_{slug}_{ts}{ext.lower()}"
    dest_path = os.path.join(sig_dir, dest_filename)

    shutil.copy2(src_path, dest_path)

    item = {
        "id": f"sig_{cat}_{ts}",
        "name": clean_name,
        "category": cat,
        "filename": dest_filename,
        "path": dest_path,
        "created_at": datetime.now().isoformat(timespec="seconds")
    }

    lib = load_signature_library(config_path)
    lib.setdefault("items", []).append(item)
    save_signature_library(lib, config_path)
    return item


def delete_signature_item(item_id: str, delete_file: bool = True, config_path: str = "") -> bool:
    """Menghapus item tanda tangan dari pustaka dan menghapus berkas fisiknya jika berada di signatures/."""
    lib = load_signature_library(config_path)
    items = lib.get("items", [])
    target = None
    new_items = []
    for it in items:
        if it.get("id") == item_id:
            target = it
        else:
            new_items.append(it)

    if not target:
        return False

    lib["items"] = new_items
    save_signature_library(lib, config_path)

    if delete_file:
        file_p = target.get("path", "")
        sig_dir = os.path.abspath(get_signatures_dir())
        if file_p and os.path.isfile(file_p):
            abs_p = os.path.abspath(file_p)
            if abs_p.startswith(sig_dir):
                try:
                    os.remove(abs_p)
                except Exception as e:
                    logger.warning("Gagal menghapus berkas gambar tanda tangan '%s': %s", abs_p, e)

    return True


def get_signatures_by_category(category: str, config_path: str = "") -> List[Dict[str, Any]]:
    """Mengambil daftar tanda tangan/stempel terfilter berdasarkan kategori ('kepala', 'guru', 'stempel')."""
    lib = load_signature_library(config_path)
    cat = category.strip().lower()
    return [it for it in lib.get("items", []) if it.get("category") == cat]


def predict_signature_layout(doc_path: str) -> Dict[str, Any]:
    """
    Menganalisis dokumen Word sampel untuk memprediksi tata letak tanda tangan:
    - Orientasi halaman (Potrait vs Lanskap)
    - Dimensi halaman dan lebar margin
    - Keberadaan dan geometri tabel tanda tangan (lebar kolom nyata dalam Cm)
    - Jarak vertikal dan nama yang terdeteksi
    - Rekomendasi Offset X, Offset Y, dan Lebar optimal
    """
    from document.docx_reader import load_document, iter_tables
    from core.signature_analyzer import (
        is_signature_table,
        classify_zone_role,
        KEPALA_ROLE_KEYWORDS,
        GURU_ROLE_KEYWORDS,
        RE_NIP_LINE,
    )
    from document.paragraph_processor import get_paragraph_text

    if not os.path.isfile(doc_path):
        raise FileNotFoundError(f"Dokumen tidak ditemukan: {doc_path}")

    doc = load_document(doc_path)
    is_land = is_document_landscape(doc)

    # 1. Dimensi Halaman
    page_w_cm = 29.7 if is_land else 21.0
    page_h_cm = 21.0 if is_land else 29.7
    margin_l_cm = 2.54
    margin_r_cm = 2.54

    if doc.sections:
        sec = doc.sections[0]
        if sec.page_width:
            page_w_cm = round(sec.page_width / 360000.0, 2)
        if sec.page_height:
            page_h_cm = round(sec.page_height / 360000.0, 2)
        if sec.left_margin:
            margin_l_cm = round(sec.left_margin / 360000.0, 2)
        if sec.right_margin:
            margin_r_cm = round(sec.right_margin / 360000.0, 2)

    printable_w_cm = max(10.0, round(page_w_cm - margin_l_cm - margin_r_cm, 2))

    res: Dict[str, Any] = {
        "file_name": os.path.basename(doc_path),
        "is_landscape": is_land,
        "orientation_label": "Lanskap" if is_land else "Potrait",
        "page_width_cm": page_w_cm,
        "page_height_cm": page_h_cm,
        "printable_width_cm": printable_w_cm,
        "container_type": "NOT_FOUND",
        "detected_names": {},
        "col_widths_cm": [],
        "recommended_offsets": {
            "kepala_width_cm": 3.5,
            "offset_x_kepala_cm": -2.3 if is_land else 0.0,
            "offset_y_kepala_cm": 0.0,
            "guru_width_cm": 3.5,
            "offset_x_guru_cm": -2.3 if is_land else 0.0,
            "offset_y_guru_cm": 0.0,
            "stempel_width_cm": 3.5,
            "offset_x_stempel_cm": -3.8 if is_land else -1.5,
            "offset_y_stempel_cm": 0.0,
        }
    }

    # 2. Cari Tabel Tanda Tangan
    found_table = None
    table_idx = -1
    for t_i, tbl in enumerate(iter_tables(doc)):
        if is_signature_table(tbl):
            found_table = tbl
            table_idx = t_i
            break

    if found_table:
        res["container_type"] = "TABLE"
        res["table_index"] = table_idx
        num_cols = len(found_table.columns)
        res["num_columns"] = num_cols

        col_widths = []
        for c_i in range(num_cols):
            w_emu = None
            for row in found_table.rows:
                if c_i < len(row.cells) and row.cells[c_i].width:
                    w_emu = row.cells[c_i].width
                    break
            c_w = round(w_emu / 360000.0, 2) if w_emu else round(printable_w_cm / max(1, num_cols), 2)
            col_widths.append(c_w)
        res["col_widths_cm"] = col_widths

        # Analisis isi per kolom
        for c_i in range(num_cols):
            paras = []
            for row in found_table.rows:
                if c_i < len(row.cells):
                    paras.extend(row.cells[c_i].paragraphs)

            role = classify_zone_role(paras)
            if role == "UNKNOWN" and num_cols >= 2:
                role = "KEPALA" if c_i == 0 else "GURU"

            if role in ("KEPALA", "GURU"):
                role_key = "kepala" if role == "KEPALA" else "guru"
                # Cari nama terang
                detected_name = ""
                for p in paras:
                    txt = get_paragraph_text(p).strip()
                    if txt and not any(k in txt.lower() for k in KEPALA_ROLE_KEYWORDS + GURU_ROLE_KEYWORDS) and not RE_NIP_LINE.match(txt):
                        detected_name = txt
                        break
                if detected_name:
                    res["detected_names"][role_key] = detected_name

        # Rekomendasi lebar optimal
        avg_col_w = sum(col_widths) / max(1, len(col_widths))
        opt_w = min(4.0, max(2.5, round(avg_col_w * 0.45, 1)))
        res["recommended_offsets"]["kepala_width_cm"] = opt_w
        res["recommended_offsets"]["guru_width_cm"] = opt_w
        res["recommended_offsets"]["stempel_width_cm"] = opt_w
    else:
        # 3. Cek Paragraf Tabulasi
        from core.signature_analyzer import process_tab_separated_signature_block
        tab_paras = [p for p in doc.paragraphs if "\t" in get_paragraph_text(p)]
        if len(tab_paras) >= 3:
            res["container_type"] = "TAB_PARAGRAPHS"
            half_w = round(printable_w_cm / 2.0, 2)
            res["col_widths_cm"] = [half_w, half_w]

    return res


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
