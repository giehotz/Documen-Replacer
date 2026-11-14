"""
Ekstensi pemroses kop surat Word.
Menelusuri seluruh paragraf kop surat secara konsisten baik yang terletak di:
1. Header dokumen (header, first_page_header, even_page_header).
2. Tabel kop surat (di dalam header atau badan dokumen).
3. Kotak teks (DrawingML / VML w:txbxContent).

Menyaring elemen <mc:Fallback> di dalam <mc:AlternateContent>
untuk mencegah duplikasi teks antara cabang Choice dan Fallback.
"""
from typing import List, Tuple, Dict, Any, Optional
from docx.text.paragraph import Paragraph
from document.paragraph_processor import get_paragraph_text

WORD_NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "v": "urn:schemas-microsoft-com:vml",
}


def is_inside_alternate_fallback(p_elem) -> bool:
    """
    Memeriksa apakah elemen <w:p> berada di dalam cabang <mc:Fallback>
    dari sebuah <mc:AlternateContent>.
    """
    xpath_expr = 'ancestor::*[local-name()="Fallback" and parent::*[local-name()="AlternateContent"]]'
    fallback_ancestors = p_elem.xpath(xpath_expr)
    return len(fallback_ancestors) > 0


def iter_all_paragraphs_safe(container_elem, parent_doc_or_part) -> List[Paragraph]:
    """
    Mengiterasi seluruh <w:p> di bawah container_elem tanpa duplikasi mc:Fallback,
    membungkusnya dengan objek Paragraph docx.
    """
    if container_elem is None:
        return []

    try:
        all_p_elems = container_elem.xpath(".//w:p")
    except Exception:
        all_p_elems = []

    paragraphs: List[Paragraph] = []
    for p_el in all_p_elems:
        if is_inside_alternate_fallback(p_el):
            continue
        try:
            p_obj = Paragraph(p_el, parent_doc_or_part)
            paragraphs.append(p_obj)
        except Exception:
            pass
    return paragraphs


def iter_kop_paragraphs(doc, max_body_paragraphs: int = 12) -> List[Tuple[Paragraph, Dict[str, Any]]]:
    """
    Mengumpulkan seluruh paragraf yang berpotensi menjadi bagian kop surat:
    1. Seluruh variasi Header (default, first_page, even_page) pada seluruh Section.
    2. Blok bagian atas dokumen utama (hingga batas max_body_paragraphs atau tabel kop).

    Mengembalikan list of tuple: (Paragraph, metadata_dict)
    """
    results: List[Tuple[Paragraph, Dict[str, Any]]] = []
    seen_elem_ids = set()

    # 1. Header pada setiap Section
    header_attrs = ["header", "first_page_header", "even_page_header"]
    for sec_idx, section in enumerate(doc.sections):
        for h_attr in header_attrs:
            hf = getattr(section, h_attr, None)
            if hf is None:
                continue
            hf_elem = getattr(hf, "_element", None)
            if hf_elem is None:
                continue

            hf_paras = iter_all_paragraphs_safe(hf_elem, hf)
            for p_idx, p in enumerate(hf_paras):
                p_id = id(p._p)
                if p_id in seen_elem_ids:
                    continue
                seen_elem_ids.add(p_id)

                is_txbx = len(p._p.xpath('ancestor::*[local-name()="txbxContent"]')) > 0
                results.append((p, {
                    "location": "header",
                    "section_idx": sec_idx,
                    "hf_attr": h_attr,
                    "para_idx": p_idx,
                    "is_textbox": is_txbx,
                }))

    # 2. Blok atas badan dokumen
    body_paras = iter_all_paragraphs_safe(doc._body._element, doc)
    body_count = 0
    for p_idx, p in enumerate(body_paras):
        if body_count >= max_body_paragraphs:
            break

        p_id = id(p._p)
        if p_id in seen_elem_ids:
            continue
        seen_elem_ids.add(p_id)

        text = get_paragraph_text(p).strip().upper()
        # Jika menemukan awal judul dokumen atau keputusan, hentikan cakupan kop badan
        if any(marker in text for marker in ["MEMUTUSKAN", "SURAT KEPUTUSAN", "KEPUTUSAN KEPALA", "SURAT PERINTAH TUGAS", "KEPADA YTH"]):
            break

        is_txbx = len(p._p.xpath('ancestor::*[local-name()="txbxContent"]')) > 0
        results.append((p, {
            "location": "body_top",
            "section_idx": 0,
            "para_idx": p_idx,
            "is_textbox": is_txbx,
        }))
        body_count += 1

    return results


def extract_kop_text(doc) -> str:
    """Mengembalikan gabungan seluruh baris teks yang terdeteksi di area kop surat."""
    kop_items = iter_kop_paragraphs(doc)
    lines = [get_paragraph_text(p).strip() for p, _ in kop_items]
    return "\n".join(l for l in lines if l)
