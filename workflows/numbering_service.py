"""
Layanan penomoran dokumen otomatis (Surat Dinas, SK, SPT).
Mendukung format token berurutan, penyimpanan counter persisten di folder konfigurasi pengguna,
mode pratinjau aman (dry-run tanpa mengonsumsi nomor), rollback nomor saat pembatalan,
serta deteksi duplikasi nomor pada folder keluaran.
"""
import os
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

ROMAN_MONTHS = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
    7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII"
}


class NumberingService:
    """
    Mengelola urutan nomor dokumen persisten per jenis dokumen dan tahun.
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = os.path.abspath(storage_path)
        else:
            user_home = os.path.expanduser("~")
            self.storage_path = os.path.join(user_home, ".documen_replacer", "numbering_counters.json")
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        except Exception:
            pass

    def _load_counters(self) -> Dict[str, Any]:
        if not os.path.exists(self.storage_path):
            return {}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_counters(self, counters: Dict[str, Any]) -> None:
        self._ensure_storage_dir()
        try:
            temp_path = self.storage_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(counters, f, indent=2, ensure_ascii=False)
            if os.path.exists(self.storage_path):
                os.replace(temp_path, self.storage_path)
            else:
                os.rename(temp_path, self.storage_path)
        except Exception:
            pass

    def get_current_counter(self, doc_type: str, year: int) -> int:
        """Mengambil nilai counter saat ini untuk jenis dokumen dan tahun tertentu."""
        counters = self._load_counters()
        key = f"{doc_type}_{year}"
        return int(counters.get(key, 0))

    def set_counter(self, doc_type: str, year: int, value: int) -> None:
        """Menetapkan nilai counter secara manual."""
        counters = self._load_counters()
        key = f"{doc_type}_{year}"
        counters[key] = max(0, value)
        self._save_counters(counters)

    def preview_next_number(
        self,
        doc_type: str,
        format_template: str,
        ref_date: Optional[datetime] = None,
        manual_start: Optional[int] = None,
        extra_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Menghasilkan nomor surat berikutnya dalam mode DRY-RUN (tanpa menambah counter persisten).
        """
        dt = ref_date or datetime.now()
        year = dt.year
        if manual_start is not None:
            next_val = manual_start
        else:
            curr = self.get_current_counter(doc_type, year)
            next_val = curr + 1

        return self._format_number(format_template, next_val, dt, extra_vars)

    def consume_number(
        self,
        doc_type: str,
        format_template: str,
        ref_date: Optional[datetime] = None,
        manual_start: Optional[int] = None,
        extra_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Menghasilkan nomor surat berikutnya dan SECARA ATOMIK menyimpan penambahan counter ke disk.
        """
        dt = ref_date or datetime.now()
        year = dt.year
        counters = self._load_counters()
        key = f"{doc_type}_{year}"

        if manual_start is not None:
            next_val = manual_start
        else:
            curr = int(counters.get(key, 0))
            next_val = curr + 1

        counters[key] = next_val
        self._save_counters(counters)

        return self._format_number(format_template, next_val, dt, extra_vars)

    def rollback_number(self, doc_type: str, year: int, count: int = 1) -> bool:
        """
        Mengembalikan counter ke nilai sebelumnya bila proses dibatalkan atau gagal.
        """
        counters = self._load_counters()
        key = f"{doc_type}_{year}"
        curr = int(counters.get(key, 0))
        if curr <= 0:
            return False

        new_val = max(0, curr - count)
        counters[key] = new_val
        self._save_counters(counters)
        return True

    def check_duplicate_in_dir(self, target_dir: str, formatted_number: str) -> List[str]:
        """
        Memeriksa apakah terdapat file .docx di target_dir yang namanya
        atau isinya terindikasi memuat formatted_number (peringatan duplikasi).
        """
        duplicates: List[str] = []
        if not os.path.isdir(target_dir):
            return duplicates

        # Normalisasi: ubah seluruh pemisah (spasi, garis miring, tanda hubung, titik) menjadi satu format
        clean_num = re.sub(r"[\W_\-]+", "_", formatted_number).strip("_").lower()
        for fname in os.listdir(target_dir):
            if fname.lower().endswith(".docx"):
                clean_fname = re.sub(r"[\W_\-]+", "_", fname).strip("_").lower()
                if clean_num in clean_fname:
                    duplicates.append(os.path.join(target_dir, fname))

        return duplicates

    def _format_number(
        self,
        format_template: str,
        seq_num: int,
        dt: datetime,
        extra_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """Menerapkan substitusi token format ke nomor dokumen."""
        vars_map = {
            "NO_URUT": str(seq_num),
            "BULAN_ROMAWI": ROMAN_MONTHS.get(dt.month, "I"),
            "BULAN_2DIGIT": f"{dt.month:02d}",
            "TAHUN": str(dt.year),
            "TAHUN_2DIGIT": f"{dt.year % 100:02d}",
        }
        if extra_vars:
            vars_map.update(extra_vars)

        result = format_template

        # Format {NO_URUT:03d} atau {NO_URUT:04d}
        def _replace_seq(match):
            spec = match.group(1)
            if spec:
                try:
                    return f"{seq_num:{spec}}"
                except Exception:
                    pass
            return str(seq_num)

        result = re.sub(r"\{NO_URUT(?::([^}]+))?\}", _replace_seq, result)

        for k, v in vars_map.items():
            result = result.replace(f"{{{k}}}", v)

        return result
