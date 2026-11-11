"""
Manajer Orkestrasi Konversi Word ke PDF.
Menangani:
- Pemindaian berkas Word (.doc / .docx) dan pemfilteran berkas sementara (~$)
- Resolusi path tujuan (preservasi subfolder, penanganan duplikasi nama)
- Pemilihan mesin terbaik (Word COM -> LibreOffice)
- Eksekusi batch konversi dengan pelaporan progres real-time
"""
import os
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable, Set

from core.pdf_converter.base import BasePdfConverter
from core.pdf_converter.word_com_engine import WordComConverter
from core.pdf_converter.libreoffice_engine import LibreOfficeConverter

logger = logging.getLogger(__name__)


@dataclass
class DocItem:
    """Representasi berkas Word dalam antrean konversi."""
    path: str
    rel_path: str
    filename: str
    size_bytes: int
    ext: str
    target_pdf: str = ""
    status: str = "Menunggu"  # Menunggu, Memproses, Berhasil, Gagal, Dilewati
    error_msg: str = ""

    @property
    def size_formatted(self) -> str:
        """Ukuran berkas dalam format ramah manusia (KB/MB)."""
        kb = self.size_bytes / 1024.0
        if kb < 1024:
            return f"{kb:.1f} KB"
        return f"{kb / 1024.0:.1f} MB"


class PdfConversionManager:
    """Manajer alur kerja konversi massal Word ke PDF."""

    def __init__(self, preferred_engine: str = "AUTO"):
        self.preferred_engine = preferred_engine.upper()
        self.word_engine = WordComConverter()
        self.libre_engine = LibreOfficeConverter()

    def get_active_engine(self) -> Optional[BasePdfConverter]:
        """Menentukan mesin konversi aktif yang tersedia."""
        if self.preferred_engine == "WORD" and self.word_engine.is_available():
            return self.word_engine
        if self.preferred_engine == "LIBREOFFICE" and self.libre_engine.is_available():
            return self.libre_engine

        # Mode AUTO: utamakan Word COM, lalu LibreOffice
        if self.word_engine.is_available():
            return self.word_engine
        if self.libre_engine.is_available():
            return self.libre_engine

        return None

    def get_engine_name(self) -> str:
        """Mengembalikan nama mesin konversi aktif."""
        engine = self.get_active_engine()
        if isinstance(engine, WordComConverter):
            return "Microsoft Word (COM Automation)"
        elif isinstance(engine, LibreOfficeConverter):
            return "LibreOffice (Headless)"
        return "Tidak Ada Mesin Konversi Tersedia"

    def scan_documents(self, source_dir: str, recursive: bool = True) -> List[DocItem]:
        """
        Memindai seluruh berkas Word .doc dan .docx pada folder sumber.
        Mengabaikan berkas sementara (~$*) dan berkas tersembunyi.
        """
        items: List[DocItem] = []
        if not source_dir or not os.path.isdir(source_dir):
            return items

        norm_root = os.path.normpath(source_dir)

        if recursive:
            for root, _, files in os.walk(norm_root):
                for f in files:
                    if self._is_supported_word_file(f):
                        full_p = os.path.join(root, f)
                        try:
                            size = os.path.getsize(full_p)
                        except OSError as e:
                            logger.warning("Gagal membaca berkas '%s': %s", full_p, e)
                            continue
                        rel_p = os.path.relpath(full_p, norm_root)
                        ext = os.path.splitext(f)[1].lower()
                        items.append(DocItem(
                            path=full_p,
                            rel_path=rel_p,
                            filename=f,
                            size_bytes=size,
                            ext=ext
                        ))
        else:
            try:
                for f in os.listdir(norm_root):
                    full_p = os.path.join(norm_root, f)
                    if os.path.isfile(full_p) and self._is_supported_word_file(f):
                        size = os.path.getsize(full_p)
                        ext = os.path.splitext(f)[1].lower()
                        items.append(DocItem(
                            path=full_p,
                            rel_path=f,
                            filename=f,
                            size_bytes=size,
                            ext=ext
                        ))
            except Exception as e:
                logger.warning("Gagal membaca direktori '%s': %s", norm_root, e)

        items.sort(key=lambda it: it.rel_path.lower())
        return items

    @staticmethod
    def _is_supported_word_file(filename: str) -> bool:
        """Memvalidasi apakah berkas merupakan dokumen Word yang didukung."""
        if filename.startswith("~$") or filename.startswith("."):
            return False
        ext = os.path.splitext(filename)[1].lower()
        return ext in (".docx", ".doc")

    def prepare_targets(
        self,
        items: List[DocItem],
        out_dir: str,
        preserve_subfolders: bool = True,
        skip_existing: bool = True,
    ) -> None:
        """
        Menghitung target_pdf untuk setiap DocItem dan mengatur status awal jika sudah ada berkas PDF.
        """
        norm_out = os.path.normpath(out_dir)
        used_target_paths: Set[str] = set()

        for it in items:
            base_no_ext = os.path.splitext(it.filename)[0]

            if preserve_subfolders:
                rel_dir = os.path.dirname(it.rel_path)
                target_dir = os.path.join(norm_out, rel_dir) if rel_dir else norm_out
            else:
                target_dir = norm_out

            target_file = f"{base_no_ext}.pdf"
            candidate_path = os.path.normpath(os.path.join(target_dir, target_file))

            # Penanganan benturan nama jika subfolder tidak dipertahankan
            if not preserve_subfolders and candidate_path.lower() in used_target_paths:
                counter = 2
                while True:
                    alt_name = f"{base_no_ext} ({counter}).pdf"
                    candidate_path = os.path.normpath(os.path.join(target_dir, alt_name))
                    if candidate_path.lower() not in used_target_paths and not os.path.exists(candidate_path):
                        break
                    counter += 1

            used_target_paths.add(candidate_path.lower())
            it.target_pdf = candidate_path

            # Pengecekan file sudah ada
            if skip_existing and os.path.isfile(candidate_path) and os.path.getsize(candidate_path) > 0:
                it.status = "Dilewati"
                it.error_msg = "Berkas PDF sudah ada sebelumnya"
            else:
                it.status = "Menunggu"
                it.error_msg = ""

    def convert_batch(
        self,
        items: List[DocItem],
        progress_callback: Optional[Callable[[int, int, DocItem], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Mengeksekusi konversi seluruh antrean dokumen.
        Returns: summary dict (total, processed, success, failed, skipped, canceled)
        """
        engine = self.get_active_engine()
        if engine is None:
            raise RuntimeError("Tidak ada mesin konverter yang tersedia (Microsoft Word atau LibreOffice).")

        total = len(items)
        success_count = 0
        failed_count = 0
        processed_count = 0

        # Kumpulkan berkas yang benar-benar butuh dikonversi
        to_convert: List[DocItem] = [it for it in items if it.status != "Dilewati"]
        skipped_count = total - len(to_convert)

        # Jika menggunakan WordComConverter, gunakan convert_batch untuk efisiensi instans Word
        if isinstance(engine, WordComConverter):
            pairs = [(it.path, it.target_pdf) for it in to_convert]

            def on_word_progress(idx, cnt, fname, is_ok, err):
                doc_it = to_convert[idx - 1]
                if is_ok:
                    doc_it.status = "Berhasil"
                    doc_it.error_msg = ""
                else:
                    doc_it.status = "Gagal"
                    doc_it.error_msg = err
                if progress_callback:
                    progress_callback(idx, cnt, doc_it)

            results = engine.convert_batch(pairs, progress_callback=on_word_progress, cancel_check=cancel_check)
            processed_count = len(results)
            for _, _, is_ok, _ in results:
                if is_ok:
                    success_count += 1
                else:
                    failed_count += 1
        else:
            # Fallback eksekusi satu per satu (LibreOffice)
            for idx, it in enumerate(to_convert, start=1):
                if cancel_check and cancel_check():
                    logger.info("Batch conversion dibatalkan.")
                    break

                it.status = "Memproses"
                if progress_callback:
                    progress_callback(idx, len(to_convert), it)

                ok = engine.convert_file(it.path, it.target_pdf)
                if ok:
                    it.status = "Berhasil"
                    it.error_msg = ""
                    success_count += 1
                else:
                    it.status = "Gagal"
                    it.error_msg = "Konversi LibreOffice gagal menghasilkan berkas PDF valid."
                    failed_count += 1
                processed_count += 1

                if progress_callback:
                    progress_callback(idx, len(to_convert), it)

        # Item yang belum sempat diproses (batal/gagal fatal) ditandai jelas.
        for it in to_convert[processed_count:]:
            it.status = "Dibatalkan"

        return {
            "total": total,
            "processed": processed_count,
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "canceled": len(to_convert) - processed_count,
        }
