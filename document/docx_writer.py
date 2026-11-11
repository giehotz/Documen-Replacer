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
    Mendukung penyimpanan format .docx maupun konversi kembali ke .doc jika diminta.
    """
    dir_name = os.path.dirname(output_path) or "."
    os.makedirs(dir_name, exist_ok=True)

    if output_path.lower().endswith(".doc"):
        fd, tmp_docx = tempfile.mkstemp(suffix=".tmp.docx", dir=dir_name)
        os.close(fd)
        try:
            doc.save(tmp_docx)
            from core.doc_compat_service import convert_docx_to_doc
            if not convert_docx_to_doc(tmp_docx, output_path):
                raise RuntimeError(
                    f"Gagal mengonversi dan menyimpan dokumen ke format .doc: {output_path}. "
                    "Pastikan Microsoft Word atau LibreOffice terpasang pada komputer Anda."
                )
        finally:
            if os.path.exists(tmp_docx):
                try:
                    os.remove(tmp_docx)
                except OSError:
                    pass
        return

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
