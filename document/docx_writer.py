"""
Modul penyimpan dokumen Word (.docx) ke media penyimpanan.
Mendukung penyimpanan atomik untuk mencegah berkas asli rusak bila proses terhenti.
"""
import os
import tempfile
from docx import Document


def save_document(doc: Document, output_path: str) -> None:
    """
    Menyimpan objek Document ke output_path secara atomik.
    Menulis ke berkas sementara terlebih dahulu lalu memindahkannya dengan os.replace.
    """
    dir_name = os.path.dirname(output_path) or "."
    os.makedirs(dir_name, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(suffix=".tmp.docx", dir=dir_name)
    os.close(fd)
    try:
        doc.save(tmp_path)
        os.replace(tmp_path, output_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
