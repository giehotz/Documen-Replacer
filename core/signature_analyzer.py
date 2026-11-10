"""
Modul Lapis 4: Signature Analyzer.
Menganalisis dan memproses blok pengesahan/tanda tangan RPP:
- Pemetaan zona (Kepala vs Guru)
- Penelusuran vertikal (ruang kosong, nama terang, NIP)
- Resolusi NIP berdasarkan pewarisan zona
- Deteksi titimangsa (tempat, tanggal)
- Pemeliharaan tanda kurung nama terang
"""
from typing import List, Dict, Optional, Tuple, Any
import re
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell

from core.placeholder_detector import (
    is_pure_placeholder,
    unwrap_parentheses,
    format_with_parentheses,
)
from document.paragraph_processor import (
    get_paragraph_text,
    replace_full_text_keep_style,
    replace_span,
)

# Regex Gelar Akademik
RE_TITLES_PREFIX = re.compile(r"^(drs\.|dra\.|h\.|hj\.|prof\.|dr\.)\s+", re.IGNORECASE)
RE_TITLES_SUFFIX = re.compile(
    r",?\s*(s\.pd|s\.pd\.i|m\.pd|m\.pd\.i|s\.ag|m\.ag|s\.si|m\.si|s\.t|m\.t|s\.kom|m\.kom|s\.sos|s\.e|m\.m|gr\.)(\.|\b)",
    re.IGNORECASE,
)

# Regex Titimangsa (Tempat, Tanggal Bulan Tahun)
MONTHS_ID = r"(?:januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|jan|feb|mar|apr|mei|jun|jul|agu|sep|okt|nov|des)"
RE_TITIMANGSA = re.compile(
    rf"^[A-Za-z\s\.\-]{{2,}},\s*(?:\d{{1,2}}\s+{MONTHS_ID}\s+\d{{2,4}}|\.{{3,}}\s*\d{{2,4}}|[\.\s_-]{{4,}}|\d{{1,2}}\s+{MONTHS_ID}\s+\.{{2,}})",
    re.IGNORECASE,
)

# Regex Label NIP / NUPTK
RE_NIP_LINE = re.compile(r"^\s*(NIP|NUPTK)\.?\s*[:\.]?\s*(.*)$", re.IGNORECASE)


def is_titimangsa_line(text: str) -> bool:
    """Memeriksa apakah sebuah baris teks merupakan baris titimangsa (tempat dan tanggal)."""
    t = text.strip()
    if not t:
        return False
    return bool(RE_TITIMANGSA.match(t))


def is_academic_name(text: str) -> bool:
    """Memeriksa apakah teks memiliki ciri-ciri nama dengan gelar akademik."""
    t = text.strip()
    if not t:
        return False
    # Bersihkan kurung bila ada
    inner, _ = unwrap_parentheses(t)
    return bool(RE_TITLES_PREFIX.search(inner) or RE_TITLES_SUFFIX.search(inner))


def is_paragraph_bold_or_underlined(p: Paragraph) -> bool:
    """Memeriksa apakah sebagian besar run dalam paragraf memiliki format tebal atau bergaris bawah."""
    runs = [r for r in p.runs if r.text.strip()]
    if not runs:
        return False
    has_bold = any(bool(r.bold) for r in runs)
    has_underline = any(bool(r.underline) for r in runs)
    return has_bold or has_underline


def is_signature_table(table: Table) -> bool:
    """
    Mendeteksi apakah tabel merupakan tabel tanda tangan.
    Kriteria: mengandung kata kunci Mengetahui, Kepala, atau Guru/Penyusun.
    """
    full_table_text = ""
    for row in table.rows:
        for cell in row.cells:
            full_table_text += cell.text + " "

    lower_text = full_table_text.lower()
    has_mengetahui = "mengetahui" in lower_text
    has_kepala = "kepala" in lower_text
    has_guru = any(k in lower_text for k in ["guru", "penyusun", "wali kelas", "pendidik"])

    return (has_mengetahui and (has_kepala or has_guru)) or (has_kepala and has_guru)


def classify_zone_role(paragraphs: List[Paragraph]) -> str:
    """
    Menentukan peran kolom/zona: 'KEPALA', 'GURU', atau 'UNKNOWN'.
    """
    for p in paragraphs[:4]:  # Cek 4 baris teratas
        text = get_paragraph_text(p).lower()
        if "kepala" in text or "mengetahui" in text:
            return "KEPALA"
        if any(k in text for k in ["guru", "penyusun", "wali kelas", "pendidik"]):
            return "GURU"
    return "UNKNOWN"


def process_signature_zone(
    paragraphs: List[Paragraph],
    role: str,
    target_values: Dict[str, str],
    signature_settings: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Memproses daftar paragraf dalam satu zona tanda tangan (Kepala atau Guru).
    target_values: dict kategori -> teks baru
    signature_settings: opsi pengaturan gambar tanda tangan digital
    """
    changes = 0
    num_p = len(paragraphs)
    if num_p == 0:
        return 0

    # 1. Cek Titimangsa di baris atas (biasanya di zona Guru)
    new_titimangsa = target_values.get("Titimangsa", "").strip()
    if new_titimangsa:
        for i in range(min(3, num_p)):
            p = paragraphs[i]
            t = get_paragraph_text(p).strip()
            if is_titimangsa_line(t):
                replace_full_text_keep_style(p, new_titimangsa)
                changes += 1
                break

    # 2. Cari Role Anchor
    anchor_idx = -1
    for i in range(num_p):
        t = get_paragraph_text(paragraphs[i]).lower()
        if role == "KEPALA" and ("kepala" in t or "mengetahui" in t):
            anchor_idx = i
        elif role == "GURU" and any(k in t for k in ["guru", "penyusun", "wali kelas", "pendidik"]):
            anchor_idx = i

    start_scan = anchor_idx + 1 if anchor_idx != -1 else 0

    # 3. Cari baris NIP terlebih dahulu untuk referensi posisi nama
    nip_idx = -1
    for i in range(start_scan, num_p):
        t = get_paragraph_text(paragraphs[i]).strip()
        if RE_NIP_LINE.match(t):
            nip_idx = i
            break

    # 4. Cari target Nama Terang
    target_name_key = "Nama Kepala" if role == "KEPALA" else "Nama Guru"
    new_name = target_values.get(target_name_key, "").strip()

    name_idx = -1
    for i in range(start_scan, num_p):
        if i == nip_idx:
            continue
        p = paragraphs[i]
        t = get_paragraph_text(p).strip()
        if not t:
            continue  # Lewati baris kosong / ruang tanda tangan

        # Kriteria calon nama:
        is_placeholder = is_pure_placeholder(t)
        is_title = is_academic_name(t)
        is_bold_under = is_paragraph_bold_or_underlined(p)
        is_above_nip = (nip_idx != -1 and i == nip_idx - 1)

        if is_placeholder or is_title or is_bold_under or is_above_nip:
            name_idx = i
            if new_name:
                # Periksa apakah teks asli dibungkus kurung
                _, had_parens = unwrap_parentheses(t)
                formatted_name = format_with_parentheses(new_name, had_parens)
                replace_full_text_keep_style(p, formatted_name)
                changes += 1
            break

    # 4.5 Sisipkan Gambar Tanda Tangan Digital jika dikonfigurasi
    if signature_settings and name_idx != -1:
        is_kepala = (role == "KEPALA")
        enabled = signature_settings.get("enabled_kepala" if is_kepala else "enabled_guru", False)
        img_path = signature_settings.get("kepala_image_path" if is_kepala else "guru_image_path", "")
        if enabled and img_path and os.path.isfile(img_path):
            try:
                from core.signature_image_service import insert_signature_picture
                width_cm = float(signature_settings.get("kepala_width_cm" if is_kepala else "guru_width_cm", 3.5))
                align = signature_settings.get("alignment", "CENTER")
                sp_b = int(signature_settings.get("spacing_before_pt", 2))
                sp_a = int(signature_settings.get("spacing_after_pt", 2))

                # Gunakan paragraf kosong tepat sebelum nama jika ada, atau sisipkan paragraf baru
                p_img = None
                for empty_i in range(start_scan, name_idx):
                    if not get_paragraph_text(paragraphs[empty_i]).strip():
                        p_img = paragraphs[empty_i]
                        break

                if p_img is None:
                    p_img = paragraphs[name_idx].insert_paragraph_before()

                if insert_signature_picture(p_img, img_path, width_cm, align, sp_b, sp_a):
                    changes += 1
            except Exception:
                pass

    # 5. Proses baris NIP
    target_nip_key = "NIP Kepala" if role == "KEPALA" else "NIP Guru"
    new_nip = target_values.get(target_nip_key, "").strip()

    if new_nip and nip_idx != -1:
        p = paragraphs[nip_idx]
        t = get_paragraph_text(p)
        m = RE_NIP_LINE.match(t)
        if m:
            prefix = m.group(1)  # NIP atau NUPTK
            formatted_nip = f"{prefix}. {new_nip}"
            replace_full_text_keep_style(p, formatted_nip)
            changes += 1

    return changes


def process_table_signatures(
    table: Table,
    target_values: Dict[str, str],
    signature_settings: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Memproses blok tanda tangan dalam format tabel (tabel borderless).
    Mengelompokkan paragraf per kolom sel.
    """
    if not is_signature_table(table):
        return 0

    num_cols = len(table.columns)
    changes = 0

    # Kumpulkan paragraf untuk tiap kolom
    col_paragraphs: Dict[int, List[Paragraph]] = {c: [] for c in range(num_cols)}
    for row in table.rows:
        for c_idx, cell in enumerate(row.cells):
            col_paragraphs[c_idx].extend(cell.paragraphs)

    for c_idx in range(num_cols):
        paras = col_paragraphs[c_idx]
        role = classify_zone_role(paras)
        if role == "UNKNOWN":
            # Jika kolom 0 dan 1: fallback zona kiri=KEPALA, zona kanan=GURU
            if num_cols >= 2:
                role = "KEPALA" if c_idx == 0 else "GURU"

        if role in ("KEPALA", "GURU"):
            changes += process_signature_zone(paras, role, target_values, signature_settings)

    return changes


def process_tab_separated_signature_block(
    paragraphs: List[Paragraph],
    target_values: Dict[str, str],
) -> int:
    """
    Memproses tanda tangan yang ditulis dalam paragraf bertabulasi (\t\t).
    Mengidentifikasi blok baris yang konsisten memiliki tab.
    """
    tab_lines_indices = []
    for idx, p in enumerate(paragraphs):
        t = get_paragraph_text(p)
        if "\t" in t:
            tab_lines_indices.append(idx)

    if not tab_lines_indices:
        return 0

    # Kelompokkan baris bertab yang berurutan
    blocks: List[List[int]] = []
    current_block: List[int] = []

    for idx in tab_lines_indices:
        if not current_block or idx == current_block[-1] + 1:
            current_block.append(idx)
        else:
            if len(current_block) >= 3:
                blocks.append(current_block)
            current_block = [idx]
    if len(current_block) >= 3:
        blocks.append(current_block)

    total_changes = 0
    for block in blocks:
        # Cek apakah blok ini mengandung Mengetahui / Kepala / Guru
        block_text = " ".join(get_paragraph_text(paragraphs[i]) for i in block).lower()
        if not (("mengetahui" in block_text or "kepala" in block_text) and "guru" in block_text):
            continue

        # Pecah tiap baris menjadi bagian kiri dan kanan berdasarkan tab
        for i in block:
            p = paragraphs[i]
            t = get_paragraph_text(p)
            parts = re.split(r"\t+", t)
            if len(parts) >= 2:
                left_part = parts[0].strip()
                right_part = parts[-1].strip()
                changed = False

                # Cek titimangsa di sisi kanan
                new_titi = target_values.get("Titimangsa", "").strip()
                if new_titi and is_titimangsa_line(right_part):
                    right_part = new_titi
                    changed = True

                # Cek nama kepala di sisi kiri
                new_kepala = target_values.get("Nama Kepala", "").strip()
                if new_kepala and (is_pure_placeholder(left_part) or is_academic_name(left_part)):
                    _, had_p = unwrap_parentheses(left_part)
                    left_part = format_with_parentheses(new_kepala, had_p)
                    changed = True

                # Cek nama guru di sisi kanan
                new_guru = target_values.get("Nama Guru", "").strip()
                if new_guru and (is_pure_placeholder(right_part) or is_academic_name(right_part)):
                    _, had_p = unwrap_parentheses(right_part)
                    right_part = format_with_parentheses(new_guru, had_p)
                    changed = True

                # Cek NIP kepala di sisi kiri
                new_nip_k = target_values.get("NIP Kepala", "").strip()
                if new_nip_k and RE_NIP_LINE.match(left_part):
                    left_part = f"NIP. {new_nip_k}"
                    changed = True

                # Cek NIP guru di sisi kanan
                new_nip_g = target_values.get("NIP Guru", "").strip()
                if new_nip_g and RE_NIP_LINE.match(right_part):
                    right_part = f"NIP. {new_nip_g}"
                    changed = True

                if changed:
                    # Gabungkan kembali dengan \t\t\t
                    new_line = f"{left_part}\t\t\t\t{right_part}"
                    replace_full_text_keep_style(p, new_line)
                    total_changes += 1

    return total_changes
