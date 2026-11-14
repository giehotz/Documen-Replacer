"""
Ekstensi pemroses lampiran dokumen (khususnya Lampiran SK).
Mendeteksi blok header lampiran (baik di paragraf maupun di dalam sel tabel)
dan mengekstrak atau menyinkronkan field:
- Nomor SK
- Tanggal Penetapan
- Tentang SK
"""
from typing import List, Dict, Any, Optional, Tuple
import re
from docx.text.paragraph import Paragraph
from document.paragraph_processor import get_paragraph_text


def find_attachment_headers(doc) -> List[Dict[str, Any]]:
    """
    Menelusuri seluruh dokumen untuk mendeteksi blok header lampiran.
    Header lampiran ditandai oleh frasa 'LAMPIRAN KEPUTUSAN' atau 'LAMPIRAN SK'.
    
    Mengembalikan list data lampiran:
    [
        {
            "header_para_idx": int,
            "fields": {
                "nomor": {"raw": str, "para_idx": int, "span": (int, int), "location": "body"|"table", "meta": {...}},
                "tanggal": {"raw": str, ...},
                "tentang": {"raw": str, ...}
            }
        }
    ]
    """
    results: List[Dict[str, Any]] = []

    # 1. Cari pada paragraf badan dokumen
    body_paras = doc.paragraphs
    for i, p in enumerate(body_paras):
        t = get_paragraph_text(p).strip().upper()
        if "LAMPIRAN KEPUTUSAN" in t or "LAMPIRAN SK" in t or t.startswith("LAMPIRAN"):
            # Periksa 5-8 paragraf berikutnya untuk menemukan Nomor, Tanggal, Tentang
            att_info = _extract_att_fields_from_paras(body_paras, start_idx=i, max_search=8, location="body")
            if att_info["fields"]:
                results.append(att_info)

    # 2. Cari di dalam seluruh tabel dokumen (lampiran sering ditaruh di sel tabel pojok kanan)
    for tbl_idx, table in enumerate(doc.tables):
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell in enumerate(row.cells):
                for p_idx, p in enumerate(cell.paragraphs):
                    t = get_paragraph_text(p).strip().upper()
                    if "LAMPIRAN KEPUTUSAN" in t or "LAMPIRAN SK" in t or t.startswith("LAMPIRAN"):
                        att_info = _extract_att_fields_from_cell(
                            cell.paragraphs,
                            start_idx=p_idx,
                            max_search=8,
                            tbl_idx=tbl_idx,
                            r_idx=r_idx,
                            c_idx=c_idx,
                        )
                        if att_info["fields"]:
                            results.append(att_info)

    return results


def _extract_att_fields_from_paras(
    paras: List[Paragraph],
    start_idx: int,
    max_search: int,
    location: str = "body",
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    limit = min(len(paras), start_idx + max_search)

    for idx in range(start_idx, limit):
        p = paras[idx]
        text = get_paragraph_text(p)
        _parse_att_line(text, idx, fields, location=location, meta={"para_idx": idx})

    return {
        "header_para_idx": start_idx,
        "location": location,
        "fields": fields,
    }


def _extract_att_fields_from_cell(
    paras: List[Paragraph],
    start_idx: int,
    max_search: int,
    tbl_idx: int,
    r_idx: int,
    c_idx: int,
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    limit = min(len(paras), start_idx + max_search)

    for p_idx in range(start_idx, limit):
        p = paras[p_idx]
        text = get_paragraph_text(p)
        _parse_att_line(
            text,
            p_idx,
            fields,
            location="table",
            meta={
                "table_idx": tbl_idx,
                "row_idx": r_idx,
                "col_idx": c_idx,
                "para_idx": p_idx,
            },
        )

    return {
        "header_para_idx": start_idx,
        "location": "table",
        "fields": fields,
    }


def _parse_att_line(text: str, idx: int, fields: Dict[str, Any], location: str, meta: Dict[str, Any]) -> None:
    delims = [":", "\t"]
    for delim in delims:
        if delim in text:
            parts = text.split(delim, 1)
            label = parts[0].strip().lower()
            val = parts[1].strip()
            val_start = text.find(val) if val else len(text)
            val_end = val_start + len(val)

            target_key = None
            if "nomor" in label or "no" in label:
                target_key = "nomor_sk"
            elif "tanggal" in label or "tgl" in label:
                target_key = "tanggal_penetapan"
            elif "tentang" in label or "perihal" in label:
                target_key = "tentang_sk"

            if target_key and target_key not in fields and val:
                item_meta = dict(meta)
                item_meta["span"] = (val_start, val_end)
                item_meta["raw_text"] = val
                item_meta["original_text"] = text
                fields[target_key] = item_meta
            break
