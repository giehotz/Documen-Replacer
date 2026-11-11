"""
Modul Abstraksi Mesin Konversi PDF.
Menyediakan antarmuka seragam (BasePdfConverter) untuk implementasi Word COM dan LibreOffice.
"""
from abc import ABC, abstractmethod


class BasePdfConverter(ABC):
    """Kelas abstrak dasar untuk semua mesin konverter Word ke PDF."""

    @abstractmethod
    def is_available(self) -> bool:
        """Memeriksa apakah mesin konversi tersedia dan dapat dijalankan di sistem operasi."""
        pass

    @abstractmethod
    def convert_file(self, in_path: str, out_path: str) -> bool:
        """
        Mengonversi satu berkas .doc atau .docx menjadi .pdf.
        Mengembalikan True jika berkas PDF berhasil dibuat dan ukurannya > 0 byte.
        """
        pass
