"""
Mesin Generator Dokumen Massal / Mail Merge (DOM-06 & PRD §5.3-E).
Mendukung sumber data CSV (deteksi pemisah otomatis dan UTF-8 BOM)
serta Excel (.xlsx) dengan modul openpyxl opsional.
Menyediakan pratinjau 3-5 baris contoh, validasi menyeluruh sebelum penulisan ke disk,
sanitasi nama file Windows aman, pembatalan bersih, dan pelaporan eksekusi.
"""
from typing import Dict, Any, List, Tuple, Optional, Callable
import os
import csv
import json
import re
from datetime import datetime
from docx import Document

from document.extensions.token_template_processor import (
    extract_tokens_from_document,
    replace_tokens_in_document,
)
from document.docx_writer import save_document


def sanitize_filename(name: str, max_length: int = 120) -> str:
    """
    Membersihkan nama file dari karakter terlarang Windows (<>:"/\\|?*),
    mencegah path traversal (..), dan membatasi panjang nama file.
    """
    if not name:
        return "dokumen"

    # Ganti karakter terlarang dengan underscore
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(name))
    # Buang path traversal
    cleaned = cleaned.replace("..", "_")
    # Rampingkan underscore berulang
    cleaned = re.sub(r'_+', '_', cleaned)
    # Buang spasi berulang atau titik/garis bawah di awal/akhir
    cleaned = re.sub(r'\s+', ' ', cleaned).strip('_. ')
    if not cleaned:
        cleaned = "dokumen"

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip('. ')

    return cleaned


def detect_csv_delimiter(file_path: str, encoding: str = "utf-8") -> str:
    """Mendeteksi apakah delimiter CSV berupa koma, titik koma, atau tab."""
    try:
        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            sample = f.read(4096)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=[',', ';', '\t', '|'])
        return dialect.delimiter
    except Exception:
        # Fallback heuristik
        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            line = f.readline()
        if ";" in line and "," not in line:
            return ";"
        if "\t" in line:
            return "\t"
        return ","


def load_csv_data(file_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Memuat data dari berkas CSV dengan penanganan UTF-8 dan UTF-8 BOM otomatis.
    Mengembalikan (headers, rows).
    """
    # Deteksi encoding UTF-8 vs UTF-8-sig
    encoding = "utf-8-sig"
    try:
        delimiter = detect_csv_delimiter(file_path, encoding=encoding)
    except Exception:
        delimiter = ","

    with open(file_path, "r", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        raw_headers = next(reader, None)
        if not raw_headers:
            return [], []

        headers = [h.strip() for h in raw_headers if h.strip()]
        rows: List[Dict[str, str]] = []

        for row_idx, r in enumerate(reader):
            if not any(c.strip() for c in r):
                continue
            row_dict: Dict[str, str] = {}
            for col_idx, h in enumerate(headers):
                val = r[col_idx].strip() if col_idx < len(r) else ""
                row_dict[h] = val
            row_dict["_row_number"] = str(row_idx + 1)
            rows.append(row_dict)

    return headers, rows


def load_excel_data(file_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Memuat data dari berkas Excel (.xlsx).
    Memerlukan modul openpyxl (opsional). Jika belum terpasang, melempar ImportError ramah pengguna.
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError(
            "Modul 'openpyxl' diperlukan untuk membaca berkas Excel (.xlsx). "
            "Silakan pasang dengan menjalankan 'pip install openpyxl' atau gunakan format CSV."
        )

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    headers: List[str] = []
    rows: List[Dict[str, str]] = []

    # Baris pertama sebagai header
    for cell in ws[1]:
        val = str(cell.value or "").strip()
        if val:
            headers.append(val)

    if not headers:
        return [], []

    for r_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=1):
        if not any(c is not None and str(c).strip() for c in row):
            continue
        row_dict: Dict[str, str] = {}
        for c_idx, h in enumerate(headers):
            val = str(row[c_idx] or "").strip() if c_idx < len(row) else ""
            row_dict[h] = val
        row_dict["_row_number"] = str(r_idx)
        rows.append(row_dict)

    return headers, rows


def load_data_file(file_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """Memuat data tabular dari CSV atau Excel sesuai ekstensi berkas."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".xlsx", ".xlsm"]:
        return load_excel_data(file_path)
    return load_csv_data(file_path)


def validate_dataset_against_template(
    headers: List[str],
    rows: List[Dict[str, str]],
    template_tokens: List[str],
    required_columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Melakukan validasi awal sebelum generasi:
    - Token templat yang tidak memiliki kolom sumber data
    - Baris yang memiliki kolom wajib bernilai kosong
    """
    header_lower_map = {h.lower(): h for h in headers}
    unmapped_template_tokens: List[str] = []

    for tok in template_tokens:
        tok_low = tok.lower()
        if tok_low not in header_lower_map and tok not in headers:
            # Token bawaan seperti NO_URUT, TAHUN dapat dihasilkan otomatis
            if tok.upper() not in ["NO", "NO_URUT", "NOMOR", "TAHUN"]:
                unmapped_template_tokens.append(tok)

    missing_required_columns: List[str] = []
    empty_cell_warnings: List[Dict[str, Any]] = []

    if required_columns:
        for col in required_columns:
            if col.lower() not in header_lower_map and col not in headers:
                missing_required_columns.append(col)

        for r in rows:
            for col in required_columns:
                actual_col = header_lower_map.get(col.lower(), col)
                if not r.get(actual_col):
                    empty_cell_warnings.append({
                        "row_number": r.get("_row_number", "?"),
                        "column": col,
                        "message": f"Baris #{r.get('_row_number')} kolom '{col}' bernilai kosong.",
                    })

    is_valid = (len(unmapped_template_tokens) == 0 and len(missing_required_columns) == 0)

    return {
        "is_valid": is_valid,
        "total_rows": len(rows),
        "total_columns": len(headers),
        "unmapped_tokens": unmapped_template_tokens,
        "missing_required_columns": missing_required_columns,
        "empty_cell_warnings": empty_cell_warnings,
    }


class BatchMailMerge:
    """
    Layanan eksekusi pembuatan dokumen massal berbasis templat dan data baris.
    """

    def preview_data(self, data_path: str, limit: int = 3) -> Tuple[List[str], List[Dict[str, str]]]:
        """Mengambil kolom dan 3-5 baris contoh data untuk pratinjau antarmuka."""
        headers, rows = load_data_file(data_path)
        return headers, rows[:limit]

    def generate_batch(
        self,
        template_path: str,
        data_path: str,
        output_dir: str,
        filename_pattern: str = "{NO:03d}_{NAMA}",
        required_columns: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Menjalankan proses Mail Merge massal:
        Satu baris data = satu dokumen Word (.docx) di folder keluaran.
        """
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"Berkas templat tidak ditemukan: {template_path}")

        headers, rows = load_data_file(data_path)
        if not rows:
            raise ValueError(f"Berkas data kosong atau tidak memuat baris data: {data_path}")

        # Baca token pada templat
        doc_tpl = Document(template_path)
        tokens = extract_tokens_from_document(doc_tpl)

        # Validasi sebelum memulai penulisan
        val_result = validate_dataset_against_template(headers, rows, tokens, required_columns)
        if not val_result["is_valid"]:
            return {
                "success": False,
                "status": "VALIDATION_FAILED",
                "validation": val_result,
                "generated_count": 0,
                "generated_files": [],
            }

        os.makedirs(output_dir, exist_ok=True)
        generated_files: List[str] = []
        seen_filenames: Set[str] = set()
        total_rows = len(rows)
        canceled = False

        for idx, row in enumerate(rows, start=1):
            if cancel_check and cancel_check():
                canceled = True
                break

            # Buat copy data row dengan variabel tambahan
            row_vars = dict(row)
            row_vars["NO"] = f"{idx:03d}"
            row_vars["NO_URUT"] = f"{idx:03d}"
            row_vars["INDEX"] = str(idx)

            # Buat dokumen baru dari templat
            doc = Document(template_path)
            replace_tokens_in_document(doc, row_vars)

            # Tentukan nama file dari pattern
            raw_filename = self._format_filename(filename_pattern, row_vars, idx)
            clean_base = sanitize_filename(raw_filename)

            # Penanganan nama kembar
            final_name = f"{clean_base}.docx"
            counter = 2
            while final_name.lower() in seen_filenames or os.path.exists(os.path.join(output_dir, final_name)):
                final_name = f"{clean_base}_{counter}.docx"
                counter += 1

            seen_filenames.add(final_name.lower())
            out_file_path = os.path.join(output_dir, final_name)

            save_document(doc, out_file_path)
            generated_files.append(out_file_path)

            if progress_callback:
                progress_callback(idx, total_rows, final_name)

        # Jika proses dibatalkan di tengah jalan, hapus file yang setengah jadi
        if canceled:
            for f in generated_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except Exception:
                    pass
            return {
                "success": False,
                "status": "CANCELED",
                "total_rows": total_rows,
                "generated_count": 0,
                "generated_files": [],
            }

        # Simpan Laporan Hasil ke _laporan/mail_merge_report.json
        report_dir = os.path.join(output_dir, "_laporan")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, "mail_merge_report.json")

        report_data = {
            "meta": {
                "dibuat_pada": datetime.now().isoformat(),
                "templat": os.path.abspath(template_path),
                "sumber_data": os.path.abspath(data_path),
                "folder_keluaran": os.path.abspath(output_dir),
                "total_baris": total_rows,
                "berhasil_dibuat": len(generated_files),
            },
            "daftar_berkas": [os.path.basename(f) for f in generated_files],
        }

        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return {
            "success": True,
            "status": "COMPLETED",
            "total_rows": total_rows,
            "generated_count": len(generated_files),
            "generated_files": generated_files,
            "report_path": report_path,
        }

    def _format_filename(self, pattern: str, row_vars: Dict[str, str], seq_num: int) -> str:
        """Mengganti token pada pola nama berkas."""
        res = pattern
        # Tangani token dengan spesifikasi format {NO:03d}
        def _replace_fmt(m):
            key = m.group(1)
            fmt = m.group(2)
            if key in ["NO", "NO_URUT", "INDEX"]:
                try:
                    return f"{seq_num:{fmt}}"
                except Exception:
                    pass
            val = row_vars.get(key, "")
            return str(val)

        res = re.sub(r'\{([A-Za-z0-9_]+):([^}]+)\}', _replace_fmt, res)

        for k, v in row_vars.items():
            res = res.replace(f"{{{k}}}", str(v))

        return res
