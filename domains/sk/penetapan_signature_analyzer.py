"""
Analyzer bagian Titi Mangsa Penetapan dan Tanda Tangan Surat Keputusan (SK).
Mendeteksi format penetapan:
- Ditetapkan di : [Tempat]
- Pada tanggal : [Tanggal]
Serta blok tanda tangan pengesahan SK (Jabatan, Nama Kepala, NIP).
"""
from typing import Dict, Any, Optional, List, Tuple
import re
from document.paragraph_processor import get_paragraph_text


def analyze_penetapan_and_signature(doc) -> Dict[str, Any]:
    """
    Mendeteksi area penetapan dan tanda tangan pejabat pengesah SK.
    Mengembalikan mapping:
    {
        "tempat_penetapan": {"value": str, "para_idx": int, "span": (int, int), "location": "body"|"table", "meta": {...}},
        "tanggal_penetapan": {"value": str, "para_idx": int, "span": (int, int), ...},
        "jabatan_kepala": {"value": str, "para_idx": int, ...},
        "nama_kepala": {"value": str, "para_idx": int, ...},
        "nip_kepala": {"value": str, "para_idx": int, ...}
    }
    """
    results: Dict[str, Any] = {}

    # 1. Pindai paragraf dokumen dari belakang ke depan (karena penetapan selalu di akhir naskah SK)
    paras = doc.paragraphs
    for idx, p in enumerate(paras):
        raw_text = get_paragraph_text(p)
        text = raw_text.strip()
        if not text:
            continue

        # Tempat Penetapan
        m_tempat = re.search(r"Ditetapkan di\s*[:\t]\s*(.+)$", text, re.IGNORECASE)
        if m_tempat and "tempat_penetapan" not in results:
            val = m_tempat.group(1).strip()
            v_start = raw_text.find(val)
            v_end = v_start + len(val)
            results["tempat_penetapan"] = {
                "value": val,
                "para_idx": idx,
                "span": (v_start, v_end),
                "location": "body",
                "meta": {"para_idx": idx}
            }

        # Tanggal Penetapan
        m_tgl = re.search(r"Pada tanggal\s*[:\t]\s*(.+)$", text, re.IGNORECASE)
        if m_tgl and "tanggal_penetapan" not in results:
            val = m_tgl.group(1).strip()
            v_start = raw_text.find(val)
            v_end = v_start + len(val)
            results["tanggal_penetapan"] = {
                "value": val,
                "para_idx": idx,
                "span": (v_start, v_end),
                "location": "body",
                "meta": {"para_idx": idx}
            }

        # NIP Kepala
        m_nip = re.search(r"NIP[\.\s:]+([0-9\s]{9,25})", text, re.IGNORECASE)
        if m_nip and "nip_kepala" not in results:
            val = m_nip.group(1).strip()
            v_start = raw_text.find(val)
            v_end = v_start + len(val)
            results["nip_kepala"] = {
                "value": val,
                "para_idx": idx,
                "span": (v_start, v_end),
                "location": "body",
                "meta": {"para_idx": idx}
            }
            # Biasanya 1-2 baris di atas NIP adalah Nama Kepala
            if idx > 0 and "nama_kepala" not in results:
                for back_i in range(idx - 1, max(-1, idx - 4), -1):
                    cand_name = get_paragraph_text(paras[back_i]).strip()
                    if cand_name and not cand_name.upper().startswith("KEPALA") and not cand_name.upper().startswith("PADA TANGGAL"):
                        results["nama_kepala"] = {
                            "value": cand_name,
                            "para_idx": back_i,
                            "span": (0, len(cand_name)),
                            "location": "body",
                            "meta": {"para_idx": back_i}
                        }
                        break

    # 2. Pindai jika penetapan ditaruh di dalam tabel tanda tangan
    for tbl_idx, table in enumerate(doc.tables):
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell in enumerate(row.cells):
                for p_idx, p in enumerate(cell.paragraphs):
                    raw_text = get_paragraph_text(p)
                    text = raw_text.strip()
                    if not text:
                        continue

                    m_tempat = re.search(r"Ditetapkan di\s*[:\t]\s*(.+)$", text, re.IGNORECASE)
                    if m_tempat and "tempat_penetapan" not in results:
                        val = m_tempat.group(1).strip()
                        v_start = raw_text.find(val)
                        v_end = v_start + len(val)
                        results["tempat_penetapan"] = {
                            "value": val,
                            "location": "table",
                            "meta": {"table_idx": tbl_idx, "row_idx": r_idx, "col_idx": c_idx, "para_idx": p_idx},
                            "span": (v_start, v_end)
                        }

                    m_tgl = re.search(r"Pada tanggal\s*[:\t]\s*(.+)$", text, re.IGNORECASE)
                    if m_tgl and "tanggal_penetapan" not in results:
                        val = m_tgl.group(1).strip()
                        v_start = raw_text.find(val)
                        v_end = v_start + len(val)
                        results["tanggal_penetapan"] = {
                            "value": val,
                            "location": "table",
                            "meta": {"table_idx": tbl_idx, "row_idx": r_idx, "col_idx": c_idx, "para_idx": p_idx},
                            "span": (v_start, v_end)
                        }

    return results
