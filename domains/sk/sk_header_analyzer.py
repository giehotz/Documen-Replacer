"""
Analyzer blok judul dan nomor Surat Keputusan (SK).
Mendeteksi nomor SK yang berada di bawah judul terpusat (format NOMOR : ...)
dan judul SK di bawah kata TENTANG (sering berupa paragraf tanpa titik dua).
"""
from typing import Dict, Any, Optional, List, Tuple
import re
from document.paragraph_processor import get_paragraph_text


def analyze_sk_header(doc, max_search_paras: int = 15) -> Dict[str, Any]:
    """
    Menganalisis area atas dokumen untuk mendeteksi nomor SK dan tentang/judul SK.
    Mengembalikan dictionary:
    {
        "nomor_sk": {
            "value": str,
            "para_idx": int,
            "span": (int, int),
            "raw_line": str
        },
        "tentang_sk": {
            "value": str,
            "para_indices": List[int],
            "raw_text": str
        }
    }
    """
    results: Dict[str, Any] = {}
    paras = doc.paragraphs[:max_search_paras]

    nomor_info = None
    tentang_idx = -1

    for idx, p in enumerate(paras):
        text = get_paragraph_text(p).strip()
        if not text:
            continue

        # 1. Deteksi Nomor SK
        if nomor_info is None:
            m_nomor = re.search(r"^(?:NOMOR|NO)\s*[:\t]\s*(.+)$", text, re.IGNORECASE)
            if m_nomor:
                val = m_nomor.group(1).strip()
                # Hitung span nilai di dalam paragraf asli
                raw_p_text = get_paragraph_text(p)
                val_start = raw_p_text.find(val)
                val_end = val_start + len(val) if val_start != -1 else len(raw_p_text)
                nomor_info = {
                    "value": val,
                    "para_idx": idx,
                    "span": (val_start, val_end),
                    "raw_line": raw_p_text,
                }
                results["nomor_sk"] = nomor_info

        # 2. Deteksi Kata TENTANG
        if text.upper() == "TENTANG" or (text.upper().startswith("TENTANG") and len(text) < 15):
            tentang_idx = idx

    # 3. Kumpulkan judul SK setelah kata TENTANG
    if tentang_idx != -1 and tentang_idx + 1 < len(paras):
        tentang_paras: List[int] = []
        tentang_texts: List[str] = []

        for j in range(tentang_idx + 1, len(paras)):
            p_text = get_paragraph_text(paras[j]).strip()
            if not p_text:
                continue
            # Berhenti bila menjumpai awal konsiderans atau diktum
            upper_t = p_text.upper()
            if any(upper_t.startswith(marker) for marker in ["MENIMBANG", "MENGINGAT", "MEMUTUSKAN", "MENETAPKAN"]):
                break

            tentang_paras.append(j)
            tentang_texts.append(p_text)

        if tentang_texts:
            full_tentang = " ".join(tentang_texts)
            results["tentang_sk"] = {
                "value": full_tentang,
                "para_indices": tentang_paras,
                "raw_text": full_tentang,
            }

    return results
