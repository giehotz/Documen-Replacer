"""
Layanan Kompatibilitas Dokumen Word (.doc & .docx).
Menyediakan jembatan transparan untuk membuka, membaca, dan mengonversi format biner lama (.doc)
menjadi format modern (.docx) menggunakan Microsoft Word COM Automation dengan fallback ke LibreOffice.
"""
import os
import shutil
import tempfile
import hashlib
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

WD_FORMAT_DOC = 0         # Word 97-2003 Binary (.doc)
WD_FORMAT_DOCX = 16       # Word OpenXML (.docx)
WD_ALERTS_NONE = 0
WD_DO_NOT_SAVE_CHANGES = 0

CACHE_DIR = os.path.join(tempfile.gettempdir(), "docomen_compat_cache")


def is_doc_format(path: str) -> bool:
    """Memeriksa apakah berkas berakhiran ekstensi .doc (format biner lama)."""
    return bool(path and path.lower().endswith(".doc"))


def is_docx_format(path: str) -> bool:
    """Memeriksa apakah berkas berakhiran ekstensi .docx (format modern)."""
    return bool(path and path.lower().endswith(".docx"))


def is_supported_word_file(path: str) -> bool:
    """Memeriksa apakah berkas merupakan dokumen Word (.doc atau .docx) dan bukan berkas sementara (~$)."""
    base = os.path.basename(path)
    if base.startswith("~$"):
        return False
    lower = base.lower()
    return lower.endswith(".docx") or lower.endswith(".doc")


def get_cache_docx_path(doc_path: str) -> str:
    """Menghasilkan path berkas .docx di direktori cache berdasarkan hash path, size, dan mtime."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    abs_p = os.path.abspath(doc_path)
    try:
        st = os.stat(abs_p)
        key_str = f"{abs_p}_{st.st_size}_{st.st_mtime_ns}"
    except OSError:
        key_str = abs_p
    h = hashlib.md5(key_str.encode("utf-8", errors="ignore")).hexdigest()[:12]
    base_name = os.path.splitext(os.path.basename(doc_path))[0]
    safe_name = "".join(c for c in base_name if c.isalnum() or c in (" ", "-", "_")).strip()
    return os.path.join(CACHE_DIR, f"{safe_name}_{h}.docx")


def clear_compat_cache() -> int:
    """Menghapus semua berkas cache sementara konversi dokumen. Mengembalikan jumlah berkas terhapus."""
    if not os.path.isdir(CACHE_DIR):
        return 0
    count = 0
    for fname in os.listdir(CACHE_DIR):
        fpath = os.path.join(CACHE_DIR, fname)
        try:
            if os.path.isfile(fpath):
                os.remove(fpath)
                count += 1
        except OSError:
            pass
    return count


def convert_doc_to_docx_word_com(doc_path: str, out_docx_path: str) -> bool:
    """Mengonversi berkas .doc ke .docx menggunakan Microsoft Word COM Automation."""
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        logger.warning("pywin32 tidak terpasang untuk Word COM.")
        return False

    abs_in = os.path.abspath(doc_path)
    abs_out = os.path.abspath(out_docx_path)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)

    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = WD_ALERTS_NONE

        doc = word.Documents.Open(abs_in, ReadOnly=True, ConfirmConversions=False)
        doc.SaveAs2(abs_out, FileFormat=WD_FORMAT_DOCX)
        return os.path.isfile(abs_out) and os.path.getsize(abs_out) > 0
    except Exception as e:
        logger.warning("Gagal mengonversi .doc ke .docx via Word COM (%s): %s", doc_path, e)
        return False
    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
            except Exception:
                pass
        pythoncom.CoUninitialize()


def convert_doc_to_docx_libreoffice(doc_path: str, out_docx_path: str) -> bool:
    """Mengonversi berkas .doc ke .docx menggunakan LibreOffice Headless (Fallback)."""
    from core.pdf_converter.libreoffice_engine import LibreOfficeConverter
    lo = LibreOfficeConverter()
    if not lo.is_available():
        return False

    import subprocess
    abs_in = os.path.abspath(doc_path)
    abs_out = os.path.abspath(out_docx_path)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lo_compat_in_") as tmp_dir:
        profile_url = "file:///" + os.path.join(tmp_dir, "profile").replace(os.sep, "/")
        tmp_out_dir = os.path.join(tmp_dir, "out")
        os.makedirs(tmp_out_dir, exist_ok=True)

        cmd = [
            lo.soffice_path,
            f"-env:UserInstallation={profile_url}",
            "--headless",
            "--convert-to",
            "docx",
            abs_in,
            "--outdir",
            tmp_out_dir,
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
            base_name = os.path.splitext(os.path.basename(abs_in))[0]
            expected_lo_name = os.path.join(tmp_out_dir, base_name + ".docx")
            if os.path.isfile(expected_lo_name) and os.path.getsize(expected_lo_name) > 0:
                shutil.copy2(expected_lo_name, abs_out)
                return os.path.isfile(abs_out) and os.path.getsize(abs_out) > 0
        except Exception as e:
            logger.warning("Gagal mengonversi .doc ke .docx via LibreOffice (%s): %s", doc_path, e)
    return False


def convert_doc_to_docx(doc_path: str, out_docx_path: str) -> bool:
    """
    Mengonversi berkas .doc ke .docx dengan mencoba Word COM terlebih dahulu,
    lalu mencoba LibreOffice sebagai fallback.
    """
    if convert_doc_to_docx_word_com(doc_path, out_docx_path):
        return True
    if convert_doc_to_docx_libreoffice(doc_path, out_docx_path):
        return True
    raise RuntimeError(
        f"Gagal mengonversi berkas format lama ({os.path.basename(doc_path)}). "
        "Pastikan Microsoft Word atau LibreOffice terpasang pada komputer Anda."
    )


def convert_docx_to_doc_word_com(docx_path: str, out_doc_path: str) -> bool:
    """Mengonversi berkas .docx ke .doc menggunakan Microsoft Word COM."""
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return False

    abs_in = os.path.abspath(docx_path)
    abs_out = os.path.abspath(out_doc_path)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)

    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = WD_ALERTS_NONE

        doc = word.Documents.Open(abs_in, ReadOnly=True, ConfirmConversions=False)
        doc.SaveAs2(abs_out, FileFormat=WD_FORMAT_DOC)
        return os.path.isfile(abs_out) and os.path.getsize(abs_out) > 0
    except Exception as e:
        logger.warning("Gagal mengonversi .docx ke .doc via Word COM (%s): %s", docx_path, e)
        return False
    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
            except Exception:
                pass
        pythoncom.CoUninitialize()


def convert_docx_to_doc_libreoffice(docx_path: str, out_doc_path: str) -> bool:
    """Mengonversi berkas .docx ke .doc menggunakan LibreOffice Headless (Fallback)."""
    from core.pdf_converter.libreoffice_engine import LibreOfficeConverter
    lo = LibreOfficeConverter()
    if not lo.is_available():
        return False

    import subprocess
    abs_in = os.path.abspath(docx_path)
    abs_out = os.path.abspath(out_doc_path)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lo_compat_out_") as tmp_dir:
        profile_url = "file:///" + os.path.join(tmp_dir, "profile").replace(os.sep, "/")
        tmp_out_dir = os.path.join(tmp_dir, "out")
        os.makedirs(tmp_out_dir, exist_ok=True)

        cmd = [
            lo.soffice_path,
            f"-env:UserInstallation={profile_url}",
            "--headless",
            "--convert-to",
            "doc",
            abs_in,
            "--outdir",
            tmp_out_dir,
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
            base_name = os.path.splitext(os.path.basename(abs_in))[0]
            expected_lo_name = os.path.join(tmp_out_dir, base_name + ".doc")
            if os.path.isfile(expected_lo_name) and os.path.getsize(expected_lo_name) > 0:
                shutil.copy2(expected_lo_name, abs_out)
                return os.path.isfile(abs_out) and os.path.getsize(abs_out) > 0
        except Exception as e:
            logger.warning("Gagal mengonversi .docx ke .doc via LibreOffice (%s): %s", docx_path, e)
    return False


def convert_docx_to_doc(docx_path: str, out_doc_path: str) -> bool:
    """Mengonversi berkas .docx kembali ke .doc menggunakan Word COM dengan fallback LibreOffice."""
    if convert_docx_to_doc_word_com(docx_path, out_doc_path):
        return True
    if convert_docx_to_doc_libreoffice(docx_path, out_doc_path):
        return True
    return False


def ensure_docx(file_path: str) -> Tuple[str, bool]:
    """
    Memastikan berkas yang diberikan dapat dibaca sebagai .docx:
    - Jika sudah .docx: mengembalikan (file_path, False).
    - Jika .doc: mengonversi transparan ke folder cache dan mengembalikan (cache_docx_path, True).
    Memanfaatkan cache jika berkas cache sudah ada dan lebih baru daripada sumber .doc.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Berkas tidak ditemukan: {file_path}")

    if not is_doc_format(file_path):
        return file_path, False

    cache_path = get_cache_docx_path(file_path)

    # Validasi cache mtime
    if os.path.isfile(cache_path):
        src_mtime = os.path.getmtime(file_path)
        cache_mtime = os.path.getmtime(cache_path)
        if cache_mtime >= src_mtime and os.path.getsize(cache_path) > 0:
            return cache_path, True

    # Lakukan konversi transparan
    logger.info("Mengonversi transparan berkas .doc ke .docx: %s -> %s", file_path, cache_path)
    convert_doc_to_docx(file_path, cache_path)
    return cache_path, True
