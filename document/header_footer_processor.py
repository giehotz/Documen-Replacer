"""
Modul pemrosesan header dan footer dokumen Word (.docx).
"""
from typing import Callable, Any
from docx import Document
from document.docx_reader import iter_all_paragraphs


def process_headers_footers(doc: Document, processor_func: Callable[[Any], int]) -> int:
    """
    Menjalankan processor_func(paragraph) pada semua paragraf di header dan footer
    dari setiap section dokumen, tanpa merusak linked header/footer.
    """
    total = 0
    seen = set()

    for section in doc.sections:
        for hf in (
            section.header,
            section.first_page_header,
            section.even_page_header,
            section.footer,
            section.first_page_footer,
            section.even_page_footer,
        ):
            if hf.is_linked_to_previous:
                continue
            el = hf._element
            if id(el) in seen:
                continue
            seen.add(id(el))
            for p in iter_all_paragraphs(el, hf):
                total += processor_func(p)

    return total
