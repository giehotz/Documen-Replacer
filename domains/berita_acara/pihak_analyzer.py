"""
Analyzer zona para pihak (PIHAK KESATU vs PIHAK KEDUA) pada Berita Acara & Perjanjian.
Menerapkan isolasi zona berbasis jangkar (anchor-based zone scoping) agar atribut
Nama, NIP, dan Jabatan milik Pihak Kesatu dan Pihak Kedua tidak pernah tertukar
meskipun memiliki label teks yang identik (mis. 'Nama : ...').
"""
from typing import Dict, Any, List, Optional, Tuple
import re
from document.paragraph_processor import get_paragraph_text


def analyze_pihak_zones(doc) -> Dict[str, Any]:
    """
    Membedah naskah menjadi dua zona terisolasi:
    1. zona_pihak_kesatu: dari anchor PIHAK KESATU sampai sebelum PIHAK KEDUA
    2. zona_pihak_kedua: dari anchor PIHAK KEDUA sampai penutup/tanda tangan
    
    Mengembalikan mapping atribut terisolasi:
    {
        "pihak_kesatu": {
            "nama": {"value": str, "para_idx": int, "span": (int, int), "location": "body"|"table", "meta": {...}},
            "nip": {...},
            "jabatan": {...},
            "instansi": {...},
        },
        "pihak_kedua": {
            "nama": {...},
            "nip": {...},
            "jabatan": {...},
            "instansi": {...},
        }
    }
    """
    results: Dict[str, Any] = {
        "pihak_kesatu": {},
        "pihak_kedua": {},
    }

    paras = doc.paragraphs
    idx_p1 = -1
    idx_p2 = -1

    for idx, p in enumerate(paras):
        t = get_paragraph_text(p).upper()
        if ("PIHAK KESATU" in t or "PIHAK PERTAMA" in t) and idx_p1 == -1:
            idx_p1 = idx
        elif "PIHAK KEDUA" in t and idx_p2 == -1:
            idx_p2 = idx

    # 1. Pindai zona PIHAK KESATU
    if idx_p1 != -1:
        end_p1 = idx_p2 if idx_p2 != -1 else min(len(paras), idx_p1 + 8)
        _extract_party_attributes(paras, idx_p1, end_p1, results["pihak_kesatu"], party_tag="pihak_kesatu")

    # 2. Pindai zona PIHAK KEDUA
    if idx_p2 != -1:
        end_p2 = min(len(paras), idx_p2 + 8)
        # Cari jika ada batas akhir seperti "Kedua belah pihak" atau tanda tangan
        for k in range(idx_p2 + 1, len(paras)):
            upper_k = get_paragraph_text(paras[k]).upper()
            if any(m in upper_k for m in ["KEDUA BELAH PIHAK", "DEMIKIAN BERITA ACARA", "MENGETAHUI"]):
                end_p2 = k
                break
        _extract_party_attributes(paras, idx_p2, end_p2, results["pihak_kedua"], party_tag="pihak_kedua")

    # 3. Pindai jika pihak-pihak ditaruh dalam tabel terpisah (misal kolom 0 Pihak Kesatu, kolom 1 Pihak Kedua)
    for tbl_idx, table in enumerate(doc.tables):
        for r_idx, row in enumerate(table.rows):
            if len(row.cells) >= 2:
                c0_text = " ".join(get_paragraph_text(p) for p in row.cells[0].paragraphs).upper()
                c1_text = " ".join(get_paragraph_text(p) for p in row.cells[1].paragraphs).upper()
                if "PIHAK KESATU" in c0_text or "PIHAK PERTAMA" in c0_text:
                    _extract_party_attributes_from_cell(
                        row.cells[0].paragraphs, results["pihak_kesatu"], tbl_idx, r_idx, 0, party_tag="pihak_kesatu"
                    )
                if "PIHAK KEDUA" in c1_text:
                    _extract_party_attributes_from_cell(
                        row.cells[1].paragraphs, results["pihak_kedua"], tbl_idx, r_idx, 1, party_tag="pihak_kedua"
                    )

    return results


def _extract_party_attributes(
    paras: List[Any],
    start_idx: int,
    end_idx: int,
    party_dict: Dict[str, Any],
    party_tag: str,
) -> None:
    for idx in range(start_idx, end_idx):
        p = paras[idx]
        raw_text = get_paragraph_text(p)
        text = raw_text.strip()
        if not text:
            continue

        _parse_party_line(raw_text, text, idx, party_dict, location="body", meta={"para_idx": idx, "party": party_tag})


def _extract_party_attributes_from_cell(
    cell_paras: List[Any],
    party_dict: Dict[str, Any],
    tbl_idx: int,
    r_idx: int,
    c_idx: int,
    party_tag: str,
) -> None:
    for p_idx, p in enumerate(cell_paras):
        raw_text = get_paragraph_text(p)
        text = raw_text.strip()
        if not text:
            continue
        _parse_party_line(
            raw_text, text, p_idx, party_dict,
            location="table",
            meta={"table_idx": tbl_idx, "row_idx": r_idx, "col_idx": c_idx, "para_idx": p_idx, "party": party_tag}
        )


def _parse_party_line(raw_text: str, text: str, idx: int, party_dict: Dict[str, Any], location: str, meta: Dict[str, Any]) -> None:
    delims = [":", "\t"]

    # Kasus baris gabungan inline: PIHAK KESATU: Budi Santoso, M.Pd, Jabatan: Kepala Madrasah Lama
    if "PIHAK" in text.upper() and ("NAMA" not in text.upper()):
        # Coba cari nama setelah titik dua
        m_inline = re.search(r"PIHAK\s+(?:KESATU|PERTAMA|KEDUA)\s*[:\t]\s*(.+?)(?:,\s*Jabatan\s*[:\t]|\s*$)", text, re.IGNORECASE)
        if m_inline and "nama" not in party_dict:
            val = m_inline.group(1).strip()
            v_start = raw_text.find(val)
            v_end = v_start + len(val)
            item_meta = dict(meta)
            item_meta.update({"span": (v_start, v_end), "original_text": raw_text})
            party_dict["nama"] = {
                "value": val,
                "location": location,
                "span": (v_start, v_end),
                "meta": item_meta,
            }

        # Coba cari jabatan inline
        m_jab = re.search(r"Jabatan\s*[:\t]\s*(.+)$", text, re.IGNORECASE)
        if m_jab and "jabatan" not in party_dict:
            val = m_jab.group(1).strip()
            v_start = raw_text.find(val)
            v_end = v_start + len(val)
            item_meta = dict(meta)
            item_meta.update({"span": (v_start, v_end), "original_text": raw_text})
            party_dict["jabatan"] = {
                "value": val,
                "location": location,
                "span": (v_start, v_end),
                "meta": item_meta,
            }
        return

    # Kasus baris terpisah: Label : Nilai
    for delim in delims:
        if delim in text:
            parts = text.split(delim, 1)
            lbl = re.sub(r"\s+", " ", parts[0]).strip().lower()
            val = parts[1].strip()
            if not val:
                continue

            v_start = raw_text.find(val)
            v_end = v_start + len(val) if v_start != -1 else len(raw_text)

            def _store(key):
                if key not in party_dict:
                    item_meta = dict(meta)
                    item_meta.update({"span": (v_start, v_end), "original_text": raw_text})
                    party_dict[key] = {
                        "value": val,
                        "location": location,
                        "span": (v_start, v_end),
                        "meta": item_meta,
                    }

            if lbl in ["nama", "nama lengkap"]:
                _store("nama")
            elif "nip" in lbl:
                _store("nip")
            elif "jabatan" in lbl:
                _store("jabatan")
            elif any(k in lbl for k in ["instansi", "sekolah", "madrasah", "unit kerja"]):
                _store("instansi")
            break
