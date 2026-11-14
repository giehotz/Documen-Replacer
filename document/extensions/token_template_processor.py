"""
Pemroses templat berbasis token untuk Mail Merge dan generator massal (DOM-06).
Mendukung pola token:
- {{FIELD_NAME}}
- <<FIELD_NAME>>
- [[FIELD_NAME]]

Mampu menangani token yang terpecah di beberapa run XML Word (w:r),
mempertahankan format run pertama, dan melaporkan token yang tidak memiliki kolom sumber data.
"""
from typing import Dict, Any, List, Tuple, Set, Optional
import re
from docx.text.paragraph import Paragraph
from document.paragraph_processor import get_paragraph_text, replace_span
from document.extensions.kop_surat_processor import iter_all_paragraphs_safe

TOKEN_REGEXES = [
    re.compile(r"\{\{([A-Za-z0-9_\-\s]+)\}\}"),
    re.compile(r"<<([A-Za-z0-9_\-\s]+)>>"),
    re.compile(r"\[\[([A-Za-z0-9_\-\s]+)\]\]"),
]


def find_tokens_in_text(text: str) -> List[Tuple[int, int, str, str]]:
    """
    Menemukan seluruh kecocokan token di dalam teks.
    Mengembalikan list of tuple: (start_idx, end_idx, token_name_normalized, raw_token_match)
    diurutkan berdasarkan start_idx menaik.
    """
    matches: List[Tuple[int, int, str, str]] = []
    if not text:
        return matches

    for rx in TOKEN_REGEXES:
        for m in rx.finditer(text):
            raw_match = m.group(0)
            token_key = m.group(1).strip()
            matches.append((m.start(), m.end(), token_key, raw_match))

    matches.sort(key=lambda x: x[0])
    return matches


def extract_tokens_from_document(doc) -> List[str]:
    """
    Mengekstrak seluruh token unik yang ditemukan di dalam dokumen templat:
    - Seluruh paragraf badan dokumen
    - Seluruh tabel dokumen
    - Seluruh header dan footer
    """
    unique_tokens: Set[str] = set()

    for p in iter_all_document_paragraphs(doc):
        t = get_paragraph_text(p)
        for _, _, key, _ in find_tokens_in_text(t):
            unique_tokens.add(key)

    return sorted(list(unique_tokens))


def replace_tokens_in_paragraph(
    paragraph: Paragraph,
    data: Dict[str, Any],
    case_sensitive: bool = False,
) -> Tuple[int, List[str]]:
    """
    Mengganti token pada sebuah paragraf dari kanan ke kiri (descending order)
    agar pergeseran offset tidak merusak indeks penggantian berikutnya.
    Mengembalikan (jumlah_terganti, list_token_tanpa_data).
    """
    full_text = get_paragraph_text(paragraph)
    if not full_text:
        return 0, []

    tokens = find_tokens_in_text(full_text)
    if not tokens:
        return 0, []

    # Buat lookup data yang toleran terhadap case
    norm_data: Dict[str, str] = {}
    for k, v in data.items():
        val_str = str(v) if v is not None else ""
        norm_data[k] = val_str
        if not case_sensitive:
            norm_data[k.lower()] = val_str
            norm_data[k.upper()] = val_str

    replaced_count = 0
    unmapped_tokens: List[str] = []

    # Urutkan dari belakang ke depan (descending start)
    tokens_descending = sorted(tokens, key=lambda x: x[0], reverse=True)

    for start_pos, end_pos, token_key, raw_match in tokens_descending:
        lookup_key = token_key if case_sensitive else token_key.lower()
        if lookup_key in norm_data or token_key in norm_data:
            replacement_val = norm_data.get(token_key, norm_data.get(lookup_key, ""))
            success = replace_span(paragraph, start_pos, end_pos, replacement_val)
            if success:
                replaced_count += 1
        else:
            unmapped_tokens.append(token_key)

    return replaced_count, unmapped_tokens


def replace_tokens_in_document(
    doc,
    data: Dict[str, Any],
    case_sensitive: bool = False,
) -> Dict[str, Any]:
    """
    Mengganti seluruh token templat pada dokumen Word dengan nilai dari data dictionary.
    Menelusuri badan naskah, tabel, dan header/footer.
    """
    total_replaced = 0
    all_unmapped: Set[str] = set()

    for p in iter_all_document_paragraphs(doc):
        c, unmapped = replace_tokens_in_paragraph(p, data, case_sensitive=case_sensitive)
        total_replaced += c
        all_unmapped.update(unmapped)

    return {
        "total_replaced": total_replaced,
        "unmapped_tokens": sorted(list(all_unmapped)),
    }


def iter_all_document_paragraphs(doc) -> List[Paragraph]:
    """
    Mengumpulkan seluruh paragraf dalam dokumen secara menyeluruh dan aman dari duplikasi:
    1. Paragraf badan (termasuk kotak teks dan alternateContent pilihan)
    2. Seluruh sel tabel
    3. Seluruh header dan footer
    """
    paras: List[Paragraph] = []
    seen_elem_ids = set()

    # 1. Badan dokumen
    if hasattr(doc, "_body") and doc._body is not None:
        body_p = iter_all_paragraphs_safe(doc._body._element, doc)
        for p in body_p:
            p_id = id(p._p)
            if p_id not in seen_elem_ids:
                seen_elem_ids.add(p_id)
                paras.append(p)

    # 2. Header dan Footer
    header_attrs = ["header", "first_page_header", "even_page_header", "footer", "first_page_footer", "even_page_footer"]
    for sec in getattr(doc, "sections", []):
        for h_attr in header_attrs:
            hf = getattr(sec, h_attr, None)
            if hf is not None and hasattr(hf, "_element") and hf._element is not None:
                for p in iter_all_paragraphs_safe(hf._element, hf):
                    p_id = id(p._p)
                    if p_id not in seen_elem_ids:
                        seen_elem_ids.add(p_id)
                        paras.append(p)

    return paras
