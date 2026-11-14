"""
Analyzer blok kegiatan/agenda pada Surat Undangan dan Surat Dinas.
Mendeteksi rincian kegiatan:
- Hari, Tanggal pelaksanaan
- Waktu / Pukul
- Tempat kegiatan
- Acara / Agenda kegiatan

Menjaga isolasi ketat agar tanggal acara (hari_tanggal_acara) TIDAK PERNAH
tertukar atau tertimpa oleh tanggal surat (tanggal pembuatan surat).
"""
from typing import Dict, Any, List, Optional, Tuple
import re
from document.paragraph_processor import get_paragraph_text


def analyze_agenda_block(doc) -> Dict[str, Any]:
    """
    Mendeteksi blok agenda kegiatan di dalam badan surat atau tabel.
    Mengembalikan mapping:
    {
        "hari_tanggal_acara": {"value": str, "para_idx": int, "span": (int, int), "location": "body"|"table", "meta": {...}},
        "waktu_acara": {"value": str, ...},
        "tempat_acara": {"value": str, ...},
        "acara_kegiatan": {"value": str, ...}
    }
    """
    results: Dict[str, Any] = {}

    # 1. Pindai paragraf naskah
    for idx, p in enumerate(doc.paragraphs):
        raw_text = get_paragraph_text(p)
        text = raw_text.strip()
        if not text:
            continue

        _parse_agenda_line(raw_text, text, idx, results, location="body", meta={"para_idx": idx})

    # 2. Pindai tabel agenda (bila agenda ditaruh di dalam tabel)
    for tbl_idx, table in enumerate(doc.tables):
        for r_idx, row in enumerate(table.rows):
            if len(row.cells) >= 2:
                c0_text = get_paragraph_text(row.cells[0].paragraphs[0]).strip() if row.cells[0].paragraphs else ""
                c_val = row.cells[-1]
                val_text = get_paragraph_text(c_val.paragraphs[0]).strip() if c_val.paragraphs else ""
                line_str = f"{c0_text} : {val_text}"
                _parse_agenda_line(
                    line_str,
                    line_str.strip(),
                    0,
                    results,
                    location="table",
                    meta={"table_idx": tbl_idx, "row_idx": r_idx, "col_idx": len(row.cells) - 1, "para_idx": 0},
                )

    return results


def _parse_agenda_line(raw_text: str, text: str, idx: int, results: Dict[str, Any], location: str, meta: Dict[str, Any]) -> None:
    delims = [":", "\t"]
    for delim in delims:
        if delim in text:
            parts = text.split(delim, 1)
            lbl = re.sub(r"\s+", " ", parts[0]).strip().lower()
            val = parts[1].strip()
            if not val:
                continue

            v_start = raw_text.find(val)
            v_end = v_start + len(val) if v_start != -1 else len(raw_text)

            def _store(field_key):
                if field_key not in results:
                    item_meta = dict(meta)
                    item_meta["span"] = (v_start, v_end)
                    item_meta["original_text"] = raw_text
                    results[field_key] = {
                        "value": val,
                        "location": location,
                        "span": (v_start, v_end),
                        "meta": item_meta,
                    }

            if any(k in lbl for k in ["hari, tanggal", "hari/tanggal", "hari dan tanggal", "hari, tgl"]):
                _store("hari_tanggal_acara")
            elif any(k in lbl for k in ["waktu", "pukul", "jam"]):
                _store("waktu_acara")
            elif any(k in lbl for k in ["tempat", "lokasi"]):
                _store("tempat_acara")
            elif any(k in lbl for k in ["acara", "kegiatan", "agenda"]):
                _store("acara_kegiatan")
            break
