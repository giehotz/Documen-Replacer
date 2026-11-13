"""
Modul Prediksi Dokumen & Generator Aturan Cerdas.
Membaca dokumen Word (.docx / .doc) contoh atau folder dokumen, mendeteksi struktur & format unik,
mengekstrak teks lama / placeholder yang ada, dan menyarankan daftar aturan penggantian data.
"""
from typing import Dict, List, Set, Optional, Tuple, Any
import os
import re
import logging

from core.label_recognizer import load_aliases, match_category
from core.placeholder_detector import extract_label_and_placeholder, is_pure_placeholder
from core.signature_analyzer import (
    is_signature_table,
    classify_zone_role,
    is_titimangsa_line,
    is_academic_name,
    is_paragraph_bold_or_underlined,
    KEPALA_ROLE_KEYWORDS,
    GURU_ROLE_KEYWORDS,
    RE_NIP_LINE,
)
from document.docx_reader import load_document
from document.paragraph_processor import get_paragraph_text

logger = logging.getLogger(__name__)

# Pola Tahun Ajaran: 2025/2026, 2020-2021, 20.. /20.., dll.
RE_YEAR_PATTERN = re.compile(
    r"(?:^|[^\w])(20(?:\d{2}|\.\.)\s*[/–-]\s*20(?:\d{2}|\.\.))(?=[^\w]|$)",
    re.IGNORECASE
)

# Pemetaan kategori internal ke label standar profil GUI
CATEGORY_TO_LABEL = {
    "Nama Madrasah": "Nama Madrasah",
    "Istilah Jabatan Kepala": "Istilah Jabatan Kepala",
    "Tahun Ajaran": "Tahun Pelajaran",
    "Tahun Pelajaran": "Tahun Pelajaran",
    "Semester": "Semester",
    "Nama Kepala": "Nama Kepala Madrasah",
    "NIP Kepala": "NIP Kepala Madrasah",
    "Nama Guru": "Nama Guru Mata Pelajaran",
    "NIP Guru": "NIP Guru Mata Pelajaran",
    "Titimangsa": "Titimangsa (Tempat, Tanggal)",
    "Mata Pelajaran": "Mata Pelajaran",
    "Fase / Kelas": "Fase / Kelas",
}


def extract_candidates_from_document(docx_path: str, aliases: Optional[Dict[str, List[str]]] = None) -> Dict[str, Set[str]]:
    """
    Memindai satu dokumen Word dan mengekstrak semua teks lama / placeholder konkret
    yang ditemukan untuk setiap kategori relevan.
    """
    if aliases is None:
        aliases = load_aliases()

    doc = load_document(docx_path)
    candidates: Dict[str, Set[str]] = {}

    def add_candidate(cat: str, val: str):
        v = val.strip()
        if v:
            candidates.setdefault(cat, set()).add(v)

    # 1. Pemindaian Seluruh Tabel
    for t_idx, table in enumerate(doc.tables):
        if is_signature_table(table):
            num_cols = len(table.columns)
            for c_idx in range(num_cols):
                col_paras = []
                for row in table.rows:
                    if c_idx < len(row.cells):
                        col_paras.extend(row.cells[c_idx].paragraphs)

                role = classify_zone_role(col_paras)
                if role == "UNKNOWN" and num_cols >= 2:
                    role = "KEPALA" if c_idx == 0 else "GURU"

                is_k = (role == "KEPALA")

                # Cek Titimangsa di bagian atas zona Guru
                if not is_k:
                    for i in range(min(4, len(col_paras))):
                        t = get_paragraph_text(col_paras[i]).strip()
                        if is_titimangsa_line(t):
                            add_candidate("Titimangsa", t)
                            break

                anchor_idx = -1
                for i, p in enumerate(col_paras):
                    txt = get_paragraph_text(p).lower()
                    if is_k and any(k in txt for k in KEPALA_ROLE_KEYWORDS):
                        anchor_idx = i
                        if "kepala sekolah" in txt:
                            add_candidate("Istilah Jabatan Kepala", "Kepala Sekolah")
                        elif "kepala madrasah" in txt:
                            add_candidate("Istilah Jabatan Kepala", "Kepala Madrasah")
                    elif not is_k and any(k in txt for k in GURU_ROLE_KEYWORDS):
                        anchor_idx = i

                start_scan = anchor_idx + 1 if anchor_idx != -1 else 0
                nip_idx = -1
                for i in range(start_scan, len(col_paras)):
                    t = get_paragraph_text(col_paras[i]).strip()
                    m_nip = RE_NIP_LINE.match(t)
                    if m_nip:
                        nip_idx = i
                        add_candidate("NIP Kepala" if is_k else "NIP Guru", t)
                        break

                for i in range(start_scan, len(col_paras)):
                    if i == nip_idx:
                        continue
                    p = col_paras[i]
                    t = get_paragraph_text(p).strip()
                    if not t:
                        continue
                    if is_pure_placeholder(t) or is_academic_name(t) or is_paragraph_bold_or_underlined(p) or (nip_idx != -1 and i == nip_idx - 1):
                        add_candidate("Nama Kepala" if is_k else "Nama Guru", t)
                        break
        else:
            # Tabel Identitas (1-kolom, 2-kolom, 3-kolom)
            for row in table.rows:
                cells = row.cells
                num_c = len(cells)
                if num_c == 1:
                    for p in cells[0].paragraphs:
                        text = get_paragraph_text(p)
                        extracted = extract_label_and_placeholder(text)
                        if extracted:
                            lbl_pfx, pl, _, _ = extracted
                            cat = match_category(lbl_pfx, aliases)
                            if cat:
                                add_candidate(cat, pl)
                        m_y = RE_YEAR_PATTERN.search(text)
                        if m_y:
                            add_candidate("Tahun Pelajaran", m_y.group(1))
                elif num_c == 2:
                    lbl = cells[0].text.strip()
                    val = cells[1].text.strip()
                    cat = match_category(lbl, aliases)
                    if cat:
                        add_candidate(cat, val)
                elif num_c >= 3 and cells[1].text.strip() == ":":
                    lbl = cells[0].text.strip()
                    val = cells[2].text.strip()
                    cat = match_category(lbl, aliases)
                    if cat:
                        add_candidate(cat, val)

    # 2. Pemindaian Paragraf Dokumen (Body)
    for p in doc.paragraphs:
        t = get_paragraph_text(p).strip()
        if not t:
            continue
        extracted = extract_label_and_placeholder(t)
        if extracted:
            lbl_pfx, pl, _, _ = extracted
            cat = match_category(lbl_pfx, aliases)
            if cat:
                add_candidate(cat, pl)

        # Deteksi pola tahun ajaran di paragraf
        m_year = RE_YEAR_PATTERN.search(t)
        if m_year:
            add_candidate("Tahun Pelajaran", m_year.group(1))

    return candidates


def smart_merge_rules(existing_rules: List[Dict[str, str]], predicted_rules: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Menggabungkan aturan hasil prediksi dengan aturan yang sudah ada di tabel:
    1. Mempertahankan seluruh variasi (label, old) unik yang dimiliki pengguna.
    2. Menambahkan variasi (label, old) baru dari hasil prediksi dokumen.
    3. Jika aturan prediksi belum memiliki nilai 'new', mewarisi nilai 'new' dari aturan
       pengguna yang memiliki label yang sama (agar pengguna tidak perlu mengetik ulang).
    """
    merged: List[Dict[str, str]] = []
    seen_pairs: Set[Tuple[str, str]] = set()

    # Peta nilai new terkini per label dari aturan pengguna yang sudah ada
    user_new_by_label: Dict[str, str] = {}
    for r in existing_rules:
        lbl = r.get("label", "").strip()
        val = r.get("new", "").strip()
        if lbl and val and lbl not in user_new_by_label:
            user_new_by_label[lbl] = val

    # 1. Masukkan aturan pengguna yang sudah ada terlebih dahulu (pertahankan seluruh baris unik)
    for r in existing_rules:
        lbl = r.get("label", "").strip()
        old_val = r.get("old", "").strip()
        new_val = r.get("new", "").strip()
        pair_key = (lbl, old_val)
        if pair_key not in seen_pairs:
            seen_pairs.add(pair_key)
            merged.append({
                "label": lbl,
                "old": old_val,
                "new": new_val
            })

    # 2. Masukkan aturan hasil prediksi
    for p in predicted_rules:
        lbl = p.get("label", "").strip()
        old_val = p.get("old", "").strip()
        new_val = p.get("new", "").strip()
        # Jika nilai new belum terisi, warisi dari isian pengguna untuk label tersebut
        if not new_val and lbl in user_new_by_label:
            new_val = user_new_by_label[lbl]

        pair_key = (lbl, old_val)
        if pair_key not in seen_pairs:
            # Cek apakah ada baris di merged dengan label yang sama dan old masih kosong
            updated_empty = False
            if old_val:
                for m in merged:
                    if m["label"] == lbl and not m["old"]:
                        m["old"] = old_val
                        if not m["new"] and new_val:
                            m["new"] = new_val
                        seen_pairs.add(pair_key)
                        updated_empty = True
                        break
            if not updated_empty:
                seen_pairs.add(pair_key)
                merged.append({
                    "label": lbl,
                    "old": old_val,
                    "new": new_val
                })

    return merged


def predict_rules_from_file(
    docx_path: str,
    current_rules: Optional[List[Dict[str, str]]] = None,
    defaults: Optional[Dict[str, str]] = None
) -> List[Dict[str, str]]:
    """
    Menganalisis 1 file Word contoh (.docx / .doc) dan menghasilkan daftar aturan saran penggantian teks.
    Tanpa PII hardcoded: nilai 'new' diambil dari defaults/current_rules, atau dibiarkan kosong secara aman.
    """
    candidates = extract_candidates_from_document(docx_path)
    predicted: List[Dict[str, str]] = []

    # Kumpulkan nilai 'new' yang diketahui dari defaults atau current_rules
    known_new: Dict[str, str] = dict(defaults or {})
    if current_rules:
        for r in current_rules:
            l = r.get("label", "").strip()
            v = r.get("new", "").strip()
            if l and v and l not in known_new:
                known_new[l] = v

    def resolve_new(label_name: str, fallback_val: str = "") -> str:
        return known_new.get(label_name, fallback_val)

    # 1. Istilah Jabatan Kepala
    jabatan_lbl = CATEGORY_TO_LABEL.get("Istilah Jabatan Kepala", "Istilah Jabatan Kepala")
    jabatan_cands = candidates.get("Istilah Jabatan Kepala", set())
    if "Kepala Sekolah" in jabatan_cands:
        predicted.append({
            "label": jabatan_lbl,
            "old": "Kepala Sekolah",
            "new": resolve_new(jabatan_lbl, "")
        })
    elif "Kepala Madrasah" in jabatan_cands:
        predicted.append({
            "label": jabatan_lbl,
            "old": "Kepala Madrasah",
            "new": resolve_new(jabatan_lbl, "")
        })

    # 2. Tahun Pelajaran
    tp_lbl = CATEGORY_TO_LABEL.get("Tahun Pelajaran", "Tahun Pelajaran")
    tp_cands = candidates.get("Tahun Pelajaran", set()) | candidates.get("Tahun Ajaran", set())
    if tp_cands:
        for tp in sorted(list(tp_cands)):
            predicted.append({
                "label": tp_lbl,
                "old": tp,
                "new": resolve_new(tp_lbl, "")
            })
    else:
        predicted.append({
            "label": tp_lbl,
            "old": "",
            "new": resolve_new(tp_lbl, "")
        })

    # 3. Nama Madrasah
    madrasah_lbl = CATEGORY_TO_LABEL.get("Nama Madrasah", "Nama Madrasah")
    madrasah_cands = candidates.get("Nama Madrasah", set())
    non_pure_madrasah = [m for m in madrasah_cands if not is_pure_placeholder(m)]
    if non_pure_madrasah:
        for m in sorted(non_pure_madrasah, key=len, reverse=True):
            predicted.append({
                "label": madrasah_lbl,
                "old": m,
                "new": resolve_new(madrasah_lbl, "")
            })
    else:
        predicted.append({
            "label": madrasah_lbl,
            "old": "",
            "new": resolve_new(madrasah_lbl, "")
        })

    # 4. Kepala Madrasah & NIP
    k_lbl = CATEGORY_TO_LABEL.get("Nama Kepala", "Nama Kepala Madrasah")
    k_nip_lbl = CATEGORY_TO_LABEL.get("NIP Kepala", "NIP Kepala Madrasah")
    k_cands = [k for k in candidates.get("Nama Kepala", set()) if not is_pure_placeholder(k)]
    if k_cands:
        for k in sorted(k_cands, key=len, reverse=True):
            predicted.append({
                "label": k_lbl,
                "old": k,
                "new": resolve_new(k_lbl, "")
            })
    else:
        predicted.append({
            "label": k_lbl,
            "old": "",
            "new": resolve_new(k_lbl, "")
        })

    predicted.append({
        "label": k_nip_lbl,
        "old": "",
        "new": resolve_new(k_nip_lbl, "")
    })

    # 5. Guru Mata Pelajaran & NIP
    g_lbl = CATEGORY_TO_LABEL.get("Nama Guru", "Nama Guru Mata Pelajaran")
    g_nip_lbl = CATEGORY_TO_LABEL.get("NIP Guru", "NIP Guru Mata Pelajaran")
    guru_cands = candidates.get("Nama Guru", set())
    non_pure_guru = [g for g in guru_cands if not is_pure_placeholder(g)]
    if non_pure_guru:
        for g in sorted(non_pure_guru, key=len, reverse=True):
            predicted.append({
                "label": g_lbl,
                "old": g,
                "new": resolve_new(g_lbl, "")
            })
    else:
        predicted.append({
            "label": g_lbl,
            "old": "",
            "new": resolve_new(g_lbl, "")
        })

    predicted.append({
        "label": g_nip_lbl,
        "old": "",
        "new": resolve_new(g_nip_lbl, "")
    })

    # 6. Titimangsa
    titi_lbl = CATEGORY_TO_LABEL.get("Titimangsa", "Titimangsa (Tempat, Tanggal)")
    titi_cands = candidates.get("Titimangsa", set())
    if titi_cands:
        for titi in sorted(list(titi_cands), key=len, reverse=True):
            predicted.append({
                "label": titi_lbl,
                "old": titi if not is_pure_placeholder(titi) else "",
                "new": resolve_new(titi_lbl, "")
            })
    else:
        predicted.append({
            "label": titi_lbl,
            "old": "",
            "new": resolve_new(titi_lbl, "")
        })

    # 7. Mata Pelajaran
    mapel_lbl = CATEGORY_TO_LABEL.get("Mata Pelajaran", "Mata Pelajaran")
    mapel_cands = [m for m in candidates.get("Mata Pelajaran", set()) if not is_pure_placeholder(m)]
    if mapel_cands:
        for m in sorted(mapel_cands, key=len, reverse=True):
            predicted.append({
                "label": mapel_lbl,
                "old": m,
                "new": resolve_new(mapel_lbl, "")
            })

    # 8. Fase / Kelas
    fase_lbl = CATEGORY_TO_LABEL.get("Fase / Kelas", "Fase / Kelas")
    fase_cands = [f for f in candidates.get("Fase / Kelas", set()) if not is_pure_placeholder(f)]
    if fase_cands:
        for f in sorted(fase_cands, key=len, reverse=True):
            predicted.append({
                "label": fase_lbl,
                "old": f,
                "new": resolve_new(fase_lbl, "")
            })

    if current_rules:
        return smart_merge_rules(current_rules, predicted)
    return predicted


def predict_rules_from_folder(
    folder_path: str,
    current_rules: Optional[List[Dict[str, str]]] = None,
    defaults: Optional[Dict[str, str]] = None
) -> List[Dict[str, str]]:
    """
    Memindai semua file Word (.docx dan .doc) dalam folder input, mengagregasi semua variasi
    teks lama unik antar dokumen, dan menghasilkan saran aturan terpadu tanpa data pribadi hardcoded.
    """
    if not os.path.isdir(folder_path):
        return current_rules or []

    all_predicted: List[Dict[str, str]] = []
    seen_pairs: Set[Tuple[str, str]] = set()

    for root, _, files in os.walk(folder_path):
        for f in files:
            if (f.lower().endswith(".docx") or f.lower().endswith(".doc")) and not f.startswith("~$"):
                full_p = os.path.join(root, f)
                try:
                    file_rules = predict_rules_from_file(full_p, defaults=defaults)
                    for r in file_rules:
                        key = (r["label"], r["old"])
                        if key not in seen_pairs:
                            seen_pairs.add(key)
                            all_predicted.append(r)
                except Exception as e:
                    logger.warning("Gagal memindai file %s untuk prediksi: %s", full_p, e)

    if current_rules:
        return smart_merge_rules(current_rules, all_predicted)
    return all_predicted


def collect_unknown_labels(
    path_or_dir: str,
    dictionary: Optional[Any] = None,
    max_labels: int = 200
) -> Dict[str, int]:
    """
    Mengumpulkan label berdekatan dengan placeholder / isian yang tidak cocok ke field mana pun di kamus.
    Mengembalikan dictionary: {label_tidak_dikenal: jumlah_kemunculan}.
    """
    if dictionary is None:
        from core.field_dictionary import FieldDictionary
        dictionary = FieldDictionary.load()

    file_paths: List[str] = []
    if os.path.isfile(path_or_dir):
        file_paths.append(path_or_dir)
    elif os.path.isdir(path_or_dir):
        from core.doc_compat_service import is_supported_word_file
        for root, _, files in os.walk(path_or_dir):
            for f in files:
                if is_supported_word_file(f):
                    file_paths.append(os.path.join(root, f))
    else:
        return {}

    unknown_counts: Dict[str, int] = {}

    def consider_label(raw_lbl: str):
        clean_lbl = raw_lbl.strip().rstrip(":").strip()
        if not clean_lbl or len(clean_lbl) > 60 or len(clean_lbl) < 3:
            return
        if clean_lbl.isdigit() or re.match(r"^[\W_]+$", clean_lbl):
            return

        res = dictionary.resolve(clean_lbl)
        if res.field is None:
            display_candidate = clean_lbl.strip()
            unknown_counts[display_candidate] = unknown_counts.get(display_candidate, 0) + 1

    for fpath in file_paths:
        try:
            doc = load_document(fpath)
            for table in doc.tables:
                if is_signature_table(table):
                    continue
                for row in table.rows:
                    cells = row.cells
                    num_c = len(cells)
                    if num_c == 1:
                        for p in cells[0].paragraphs:
                            t = get_paragraph_text(p).strip()
                            ext = extract_label_and_placeholder(t)
                            if ext:
                                consider_label(ext[0])
                    elif num_c == 2:
                        val = cells[1].text.strip()
                        if not val or is_pure_placeholder(val) or len(val) <= 50:
                            consider_label(cells[0].text)
                    elif num_c >= 3 and cells[1].text.strip() == ":":
                        val = cells[2].text.strip()
                        if not val or is_pure_placeholder(val) or len(val) <= 50:
                            consider_label(cells[0].text)

            for p in doc.paragraphs:
                t = get_paragraph_text(p).strip()
                ext = extract_label_and_placeholder(t)
                if ext:
                    consider_label(ext[0])

        except Exception as e:
            logger.debug("Gagal memindai unknown labels dari %s: %s", fpath, e)

    sorted_items = sorted(unknown_counts.items(), key=lambda x: x[1], reverse=True)[:max_labels]
    return dict(sorted_items)
