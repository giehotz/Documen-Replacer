"""
Modul pembaca dokumen Word (.docx) ke dalam objek struktur memori.
"""
import os
from typing import Iterator, Tuple, Set, List
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.table import Table


def load_document(file_path: str) -> Document:
    """Membuka file .docx (mendukung transparan berkas format lama .doc)."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    from core.doc_compat_service import ensure_docx
    actual_path, _ = ensure_docx(file_path)
    return Document(actual_path)


def iter_all_paragraphs(root_element, parent_doc) -> Iterator[Paragraph]:
    """
    Menghasilkan semua objek Paragraph dalam root_element (isi biasa, tabel,
    tabel bersarang, dan text box).
    Melewati mc:Fallback agar tidak terjadi duplikasi pembacaan text box.
    """
    for p in root_element.iter(qn("w:p")):
        if any(a.tag.endswith("}Fallback") for a in p.iterancestors()):
            continue
        yield Paragraph(p, parent_doc)


def iter_tables(doc: Document) -> List[Table]:
    """Mengembalikan daftar semua tabel tingkat atas pada dokumen."""
    return list(doc.tables)
