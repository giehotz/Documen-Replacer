"""
Mesin Konversi Word ke PDF menggunakan LibreOffice Headless.
Digunakan sebagai alternatif (fallback) jika Microsoft Word tidak terpasang di sistem.
"""
import os
import shutil
import subprocess
import tempfile
import logging
from typing import Optional

from core.pdf_converter.base import BasePdfConverter

logger = logging.getLogger(__name__)


class LibreOfficeConverter(BasePdfConverter):
    """Konverter Word ke PDF berbasis LibreOffice headless subprocess."""

    def __init__(self, custom_soffice_path: str = ""):
        self.soffice_path = custom_soffice_path or self._find_soffice()

    def _find_soffice(self) -> str:
        """Mencari lokasi executable soffice.exe di sistem operasi."""
        which_path = shutil.which("soffice") or shutil.which("libreoffice")
        if which_path and os.path.isfile(which_path):
            return which_path

        common_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            r"C:\Program Files\LibreOffice 7\program\soffice.exe",
            r"C:\Program Files\LibreOffice 24\program\soffice.exe",
        ]
        for p in common_paths:
            if os.path.isfile(p):
                return p

        return ""

    def is_available(self) -> bool:
        """Memeriksa apakah LibreOffice tersedia."""
        if not self.soffice_path:
            self.soffice_path = self._find_soffice()
        return bool(self.soffice_path and os.path.isfile(self.soffice_path))

    def convert_file(self, in_path: str, out_path: str) -> bool:
        """Mengonversi dokumen Word ke PDF menggunakan LibreOffice headless."""
        if not self.is_available():
            logger.warning("LibreOffice soffice.exe tidak ditemukan.")
            return False

        abs_in = os.path.abspath(in_path)
        abs_out = os.path.abspath(out_path)
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)

        # Konversi ke folder sementara unik agar berkas bernama sama tidak saling
        # menimpa sebelum dipindahkan ke target final.
        with tempfile.TemporaryDirectory(prefix="lo_conv_") as tmp_dir:
            profile_url = "file:///" + os.path.join(tmp_dir, "profile").replace(os.sep, "/")
            cmd = [
                self.soffice_path,
                f"-env:UserInstallation={profile_url}",
                "--headless",
                "--convert-to",
                "pdf:writer_pdf_Export",
                "--outdir",
                tmp_dir,
                abs_in,
            ]

            try:
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=120,
                    check=False
                )
                if res.returncode != 0:
                    logger.warning("LibreOffice gagal (exit=%d): %s", res.returncode, res.stderr)
                    return False

                base_name = os.path.splitext(os.path.basename(abs_in))[0] + ".pdf"
                generated_pdf = os.path.join(tmp_dir, base_name)
                if not (os.path.isfile(generated_pdf) and os.path.getsize(generated_pdf) > 0):
                    return False

                if os.path.exists(abs_out):
                    os.remove(abs_out)
                shutil.move(generated_pdf, abs_out)
                return os.path.isfile(abs_out) and os.path.getsize(abs_out) > 0
            except Exception as e:
                logger.error("Eksekusi LibreOffice error: %s", e, exc_info=True)
                return False
