"""
Ekstensi pemroses blok bagian dokumen berbatas (anchored section).
Mendeteksi dan mengekstrak zona teks berbatas antara start_anchor dan end_anchor
atau kumpulan kata kunci jangkar (anchors) dengan batasan kedalaman maksimum (max_paragraphs)
untuk mencegah usulan 'bocor' ke zona dokumen lain.
"""
from typing import List, Tuple, Dict, Any, Optional
import re
from docx.text.paragraph import Paragraph
from document.paragraph_processor import get_paragraph_text


def find_anchored_section(
    paragraphs: List[Paragraph],
    start_anchor: str,
    end_anchor: Optional[str] = None,
    max_paragraphs: int = 15,
    case_sensitive: bool = False,
) -> List[Tuple[int, Paragraph]]:
    """
    Menemukan rentang paragraf yang diawali oleh start_anchor hingga end_anchor
    (atau hingga batas max_paragraphs).
    Mengembalikan list of tuple: (global_para_idx, Paragraph).
    """
    matched_paras: List[Tuple[int, Paragraph]] = []
    in_section = False

    s_anchor = start_anchor if case_sensitive else start_anchor.lower()
    e_anchor = (end_anchor if case_sensitive else end_anchor.lower()) if end_anchor else None

    for idx, p in enumerate(paragraphs):
        raw_text = get_paragraph_text(p)
        text = raw_text if case_sensitive else raw_text.lower()

        if not in_section:
            if s_anchor in text:
                in_section = True
                matched_paras.append((idx, p))
                # Jika end_anchor juga ada di paragraf yang sama (mis. satu baris), selesai
                if e_anchor and e_anchor in text and text.find(e_anchor) > text.find(s_anchor):
                    break
        else:
            if e_anchor and e_anchor in text:
                matched_paras.append((idx, p))
                break
            matched_paras.append((idx, p))
            if len(matched_paras) >= max_paragraphs:
                break

    return matched_paras


def find_section_by_anchors(
    paragraphs: List[Paragraph],
    anchors: List[str],
    max_paragraphs: int = 15,
    case_sensitive: bool = False,
) -> List[Tuple[int, Paragraph]]:
    """
    Menemukan bagian paragraf yang memuat salah satu dari jangkar yang ditentukan.
    """
    matched: List[Tuple[int, Paragraph]] = []
    if not anchors:
        return matched

    norm_anchors = [a if case_sensitive else a.lower() for a in anchors]
    start_found = False

    for idx, p in enumerate(paragraphs):
        raw_text = get_paragraph_text(p)
        text = raw_text if case_sensitive else raw_text.lower()

        if not start_found:
            if any(a in text for a in norm_anchors):
                start_found = True
                matched.append((idx, p))
        else:
            matched.append((idx, p))
            if len(matched) >= max_paragraphs:
                break

    return matched


def extract_key_values_from_paragraphs(
    paragraphs_with_indices: List[Tuple[int, Paragraph]],
    delimiter: str = ":",
) -> Dict[str, Dict[str, Any]]:
    """
    Mengekstrak pasangan key-value berformat 'Label : Nilai' atau 'Label \\t Nilai'.
    Mengembalikan mapping:
    {
        "label_bersih": {
            "key": str,
            "value": str,
            "para_idx": int,
            "span_start": int,
            "span_end": int,
            "paragraph": Paragraph
        }
    }
    """
    results: Dict[str, Dict[str, Any]] = {}

    for idx, p in paragraphs_with_indices:
        raw_text = get_paragraph_text(p)
        if delimiter in raw_text:
            parts = raw_text.split(delimiter, 1)
            k = parts[0].strip()
            v = parts[1].strip()
            # Hitung offset span karakter nilai di dalam paragraf
            # v_start adalah posisi setelah delimiter ditambah spasi awal
            delim_pos = raw_text.find(delimiter)
            val_start = delim_pos + 1
            while val_start < len(raw_text) and raw_text[val_start].isspace():
                val_start += 1
            val_end = delim_pos + 1 + len(parts[1].rstrip())

            norm_k = re.sub(r"\s+", " ", k).strip().lower()
            results[norm_k] = {
                "key": k,
                "value": v,
                "para_idx": idx,
                "span_start": val_start,
                "span_end": val_end,
                "paragraph": p,
            }
        elif "\t" in raw_text:
            parts = raw_text.split("\t", 1)
            k = parts[0].strip()
            v = parts[1].strip()
            if k and v:
                tab_pos = raw_text.find("\t")
                val_start = tab_pos + 1
                while val_start < len(raw_text) and raw_text[val_start].isspace():
                    val_start += 1
                val_end = len(raw_text.rstrip())

                norm_k = re.sub(r"\s+", " ", k).strip().lower()
                results[norm_k] = {
                    "key": k,
                    "value": v,
                    "para_idx": idx,
                    "span_start": val_start,
                    "span_end": val_end,
                    "paragraph": p,
                }

    return results
