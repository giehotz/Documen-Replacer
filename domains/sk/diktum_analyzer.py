"""
Analyzer bagian Konsiderans dan Diktum Surat Keputusan (SK).
Mendeteksi bagian Menimbang, Mengingat, Menetapkan, serta diktum KESATU, KEDUA, dst.,
baik yang berupa paragraf biasa maupun tabel tanpa garis (borderless table).
"""
from typing import Dict, Any, List, Tuple
import re
from document.paragraph_processor import get_paragraph_text


def analyze_diktums(doc) -> Dict[str, Any]:
    """
    Mendeteksi diktum keputusan pada dokumen SK.
    Mengembalikan dictionary:
    {
        "diktums": [
            {
                "label": "KESATU",
                "text": "Menetapkan pembagian tugas...",
                "para_idx": int,
                "location": "paragraph" | "table",
                "table_meta": Optional[Dict]
            }
        ],
        "konsiderans": {
            "menimbang": [...],
            "mengingat": [...]
        }
    }
    """
    results: Dict[str, Any] = {
        "diktums": [],
        "konsiderans": {"menimbang": [], "mengingat": []}
    }

    # 1. Pindai pada paragraf dokumen
    for idx, p in enumerate(doc.paragraphs):
        text = get_paragraph_text(p).strip()
        if not text:
            continue

        upper_t = text.upper()
        if upper_t.startswith("MENIMBANG"):
            results["konsiderans"]["menimbang"].append({"para_idx": idx, "text": text})
        elif upper_t.startswith("MENGINGAT"):
            results["konsiderans"]["mengingat"].append({"para_idx": idx, "text": text})

        m_diktum = re.match(r"^(KESATU|KEDUA|KETIGA|KEEMPAT|KELIMA|KEENAM|KETUJUH|KEDELAPAN|KESEMBILAN|KESEPULUH)\s*[:\t]\s*(.+)$", text, re.IGNORECASE)
        if m_diktum:
            label = m_diktum.group(1).upper()
            content = m_diktum.group(2).strip()
            results["diktums"].append({
                "label": label,
                "text": content,
                "para_idx": idx,
                "location": "paragraph",
                "table_meta": None
            })

    # 2. Pindai pada tabel (jika diktum diformat dalam tabel 2 kolom)
    for tbl_idx, table in enumerate(doc.tables):
        for r_idx, row in enumerate(table.rows):
            if len(row.cells) >= 2:
                c0_text = get_paragraph_text(row.cells[0].paragraphs[0]).strip() if row.cells[0].paragraphs else ""
                m_tbl_diktum = re.match(r"^(KESATU|KEDUA|KETIGA|KEEMPAT|KELIMA|KEENAM|KETUJUH|KEDELAPAN|KESEMBILAN|KESEPULUH)\s*[:\t]?$", c0_text, re.IGNORECASE)
                if m_tbl_diktum:
                    label = m_tbl_diktum.group(1).upper()
                    c1_text = " ".join(get_paragraph_text(p).strip() for p in row.cells[1].paragraphs).strip()
                    results["diktums"].append({
                        "label": label,
                        "text": c1_text,
                        "para_idx": 0,
                        "location": "table",
                        "table_meta": {
                            "table_idx": tbl_idx,
                            "row_idx": r_idx,
                            "col_idx": 1
                        }
                    })

    return results
