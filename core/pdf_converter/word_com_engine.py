"""
Mesin Konversi Word ke PDF menggunakan Microsoft Word COM Automation.
Memberikan hasil konversi 100% presisi sesuai tampilan rendering Word,
termasuk tata letak gambar tanda tangan mengambang (behind text), tabel, dan font.
"""
import os
import logging
from typing import List, Tuple, Callable, Optional

from core.pdf_converter.base import BasePdfConverter

logger = logging.getLogger(__name__)

WD_FORMAT_PDF = 17
WD_ALERTS_NONE = 0
WD_DO_NOT_SAVE_CHANGES = 0


class WordComConverter(BasePdfConverter):
    """Konverter Word ke PDF berbasis Microsoft Word COM Automation."""

    def __init__(self):
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Memeriksa apakah Microsoft Word COM dapat diakses pada sistem."""
        if self._available is not None:
            return self._available

        try:
            import pythoncom
            import win32com.client
        except ImportError:
            logger.info("pywin32 tidak terpasang; Microsoft Word COM tidak tersedia.")
            self._available = False
            return self._available

        pythoncom.CoInitialize()
        word = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = WD_ALERTS_NONE
            self._available = True
        except Exception as e:
            logger.info("Microsoft Word COM tidak tersedia di sistem ini: %s", e)
            self._available = False
        finally:
            if word is not None:
                try:
                    word.Quit(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
                except Exception:
                    logger.warning("Gagal menutup Word saat pemeriksaan ketersediaan.", exc_info=True)
            pythoncom.CoUninitialize()

        return self._available

    def convert_file(self, in_path: str, out_path: str) -> bool:
        """Mengonversi satu berkas dokumen Word menjadi PDF."""
        import pythoncom
        import win32com.client

        abs_in = os.path.abspath(in_path)
        abs_out = os.path.abspath(out_path)

        if not os.path.isfile(abs_in):
            logger.error("Berkas sumber tidak ditemukan: %s", abs_in)
            return False

        os.makedirs(os.path.dirname(abs_out), exist_ok=True)

        pythoncom.CoInitialize()
        word = None
        doc = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = WD_ALERTS_NONE

            doc = word.Documents.Open(
                abs_in,
                ReadOnly=True,
                ConfirmConversions=False,
                AddToRecentFiles=False
            )
            doc.SaveAs2(abs_out, FileFormat=WD_FORMAT_PDF)
            doc.Close(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
            doc = None

            return os.path.isfile(abs_out) and os.path.getsize(abs_out) > 0
        except Exception as e:
            logger.error("Gagal mengonversi '%s' ke PDF: %s", abs_in, e, exc_info=True)
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

    def convert_batch(
        self,
        file_pairs: List[Tuple[str, str]],
        progress_callback: Optional[Callable[[int, int, str, bool, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[Tuple[str, str, bool, str]]:
        """
        Mengonversi banyak berkas sekaligus dengan satu instans Word aktif (jauh lebih cepat).
        file_pairs: list of (in_path, out_path)
        progress_callback: fn(current_index, total_count, filename, success, error_msg)
        cancel_check: fn() -> bool
        Returns: list of (in_path, out_path, success, error_msg)
        """
        import pythoncom
        import win32com.client

        results = []
        total = len(file_pairs)
        if total == 0:
            return results

        pythoncom.CoInitialize()
        word = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = WD_ALERTS_NONE

            for idx, (in_p, out_p) in enumerate(file_pairs, start=1):
                if cancel_check and cancel_check():
                    logger.info("Konversi batch dibatalkan oleh pengguna.")
                    break

                abs_in = os.path.abspath(in_p)
                abs_out = os.path.abspath(out_p)
                fname = os.path.basename(abs_in)

                if not os.path.isfile(abs_in):
                    err = f"Berkas tidak ditemukan: {abs_in}"
                    results.append((abs_in, abs_out, False, err))
                    if progress_callback:
                        progress_callback(idx, total, fname, False, err)
                    continue

                os.makedirs(os.path.dirname(abs_out), exist_ok=True)
                doc = None
                success = False
                err_msg = ""
                try:
                    doc = word.Documents.Open(
                        abs_in,
                        ReadOnly=True,
                        ConfirmConversions=False,
                        AddToRecentFiles=False
                    )
                    doc.SaveAs2(abs_out, FileFormat=WD_FORMAT_PDF)
                    doc.Close(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
                    doc = None

                    if os.path.isfile(abs_out) and os.path.getsize(abs_out) > 0:
                        success = True
                    else:
                        err_msg = "Berkas PDF tidak terbentuk atau berukuran 0 byte."
                except Exception as e:
                    err_msg = str(e)
                    logger.warning("Gagal konversi '%s': %s", fname, e)
                finally:
                    if doc is not None:
                        try:
                            doc.Close(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
                        except Exception:
                            pass

                results.append((abs_in, abs_out, success, err_msg))
                if progress_callback:
                    progress_callback(idx, total, fname, success, err_msg)

        except Exception as e:
            logger.error("Terjadi kegagalan fatal pada Word COM: %s", e, exc_info=True)
        finally:
            if word is not None:
                try:
                    word.Quit(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
                except Exception:
                    pass
            pythoncom.CoUninitialize()

        return results
