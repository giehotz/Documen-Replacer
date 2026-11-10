"""
Modul penyimpan dokumen Word (.docx) ke media penyimpanan.
"""
import os
from docx import Document


def save_document(doc: Document, output_path: str) -> None:
    """
    Menyimpan objek Document ke output_path.
    Otomatis membuat direktori jika belum ada.
    """
    dir_name = os.path.dirname(output_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    doc.save(output_path)
