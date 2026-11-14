"""
Analyzer metadata Surat Dinas / Undangan (blok kiri atas dan tujuan).
Mendeteksi:
- Nomor Surat
- Sifat Surat
- Lampiran Surat
- Hal / Perihal
- Tujuan Yth.
"""
from typing import Dict, Any, Optional, List, Tuple
import re
from document.paragraph_processor import get_paragraph_text


def analyze_meta_surat(doc, max_search_paras: int = 20) -> Dict[str, Any]:
    """
    Menganalisis area metadata awal Surat Dinas.
    Mengembalikan mapping:
    {
        "nomor_surat": {"value": str, "para_idx": int, "span": (int, int), "location": "body"|"table"},
        "sifat_surat": {"value": str, ...},
        "lampiran_surat": {"value": str, ...},
        "hal_surat": {"value": str, ...},
        "tujuan_surat": {"value": str, ...},
    }
    """
    results: Dict[str, Any] = {}

    # 1. Pindai paragraf awal dokumen
    paras = doc.paragraphs[:max_search_paras]
    for idx, p in enumerate(paras):
        raw_text = get_paragraph_text(p)
        text = raw_text.strip()
        if not text:
            continue

        _parse_meta_line(raw_text, text, idx, results, location="body", meta={"para_idx": idx})

        # Deteksi Kepada Yth
        if re.search(r"^(?:Kepada\s+)?Yth[\.:]?", text, re.IGNORECASE) and "tujuan_surat" not in results:
            # Kumpulkan 1-3 baris berikutnya sebagai tujuan surat
            tujuan_lines = []
            for j in range(idx + 1, min(len(paras), idx + 4)):
                tj_text = get_paragraph_text(paras[j]).strip()
                if not tj_text or any(tj_text.lower().startswith(m) for m in ["di tempat", "di-tempat", "assalamu", "dengan hormat"]):
                    if tj_text.lower().startswith("di"):
                        tujuan_lines.append(tj_text)
                    break
                tujuan_lines.append(tj_text)
            if tujuan_lines:
                results["tujuan_surat"] = {
                    "value": ", ".join(tujuan_lines),
                    "para_idx": idx + 1,
                    "location": "body",
                    "meta": {"para_idx": idx + 1},
                }

    # 2. Pindai jika metadata diformat dalam tabel 2 atau 3 kolom di awal dokumen
    if len(doc.tables) > 0:
        first_table = doc.tables[0]
        # Periksa apakah tabel ini tabel metadata surat
        for r_idx, row in enumerate(first_table.rows):
            if len(row.cells) >= 2:
                c0_text = get_paragraph_text(row.cells[0].paragraphs[0]).strip() if row.cells[0].paragraphs else ""
                c_val = row.cells[-1]
                val_text = get_paragraph_text(c_val.paragraphs[0]).strip() if c_val.paragraphs else ""
                line_str = f"{c0_text} : {val_text}"
                _parse_meta_line(
                    line_str,
                    line_str.strip(),
                    0,
                    results,
                    location="table",
                    meta={"table_idx": 0, "row_idx": r_idx, "col_idx": len(row.cells) - 1, "para_idx": 0},
                )

    return results


def _parse_meta_line(raw_text: str, text: str, idx: int, results: Dict[str, Any], location: str, meta: Dict[str, Any]) -> None:
    delims = [":", "\t"]
    for delim in delims:
        if delim in text:
            parts = text.split(delim, 1)
            lbl = parts[0].strip().lower()
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

            if lbl in ["nomor", "no", "nomor surat", "no."]:
                _store("nomor_surat")
            elif lbl in ["sifat", "sifat surat"]:
                _store("sifat_surat")
            elif lbl in ["lampiran", "lamp", "lampiran surat"]:
                _store("lampiran_surat")
            elif lbl in ["hal", "perihal", "hal/perihal"]:
                _store("hal_surat")
            break
