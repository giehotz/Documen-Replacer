"""
Layanan Pelaporan Pemrosesan Batch (Report Service).
Menghitung statistik dokumen dan rincian penggantian per kategori,
serta mencetak laporan eksekutif ke layar dan berkas LAPORAN_PENGGANTIAN_RPP.txt.
"""
from typing import Dict, List, Any
import os
from datetime import datetime


class ReportService:
    def __init__(self):
        self.reset()

    def reset(self):
        self.total_scanned = 0
        self.succeeded = 0
        self.unchanged = 0
        self.needs_review = 0
        self.failed = 0
        self.category_counts: Dict[str, int] = {}
        self.file_details: List[Dict[str, Any]] = []
        self.json_report_path: str = ""
        self.verification_summary: Dict[str, Any] = {}

    def set_verification_report(self, json_path: str, summary: Dict[str, Any]):
        """Menyimpan referensi berkas laporan JSON dan ringkasan vonis verifikasi."""
        self.json_report_path = json_path
        self.verification_summary = summary or {}

    def record_document(
        self,
        rel_path: str,
        status: str,  # 'SUCCESS', 'UNCHANGED', 'NEEDS_REVIEW', 'FAILED'
        changes_count: int = 0,
        cat_breakdown: Dict[str, int] = None,
        error_msg: str = "",
    ):
        self.total_scanned += 1
        if status == "SUCCESS":
            self.succeeded += 1
        elif status == "UNCHANGED":
            self.unchanged += 1
        elif status == "NEEDS_REVIEW":
            self.needs_review += 1
        elif status == "FAILED":
            self.failed += 1

        if cat_breakdown:
            for cat, count in cat_breakdown.items():
                self.category_counts[cat] = self.category_counts.get(cat, 0) + count

        self.file_details.append({
            "rel_path": rel_path,
            "status": status,
            "changes": changes_count,
            "error": error_msg,
        })

    def generate_summary_text(self) -> str:
        total_replacements = sum(self.category_counts.values())
        now_str = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        lines = [
            "====================================================",
            "            LAPORAN PEMROSESAN RPP                  ",
            "====================================================",
            f"Waktu Pemrosesan      : {now_str}",
            "",
            "RINGKASAN DOKUMEN",
            f"Total dokumen dipindai : {self.total_scanned}",
            f"Berhasil diperbarui    : {self.succeeded}",
            f"Tidak berubah          : {self.unchanged}",
            f"Perlu pemeriksaan      : {self.needs_review}",
            f"Gagal diproses         : {self.failed}",
            "----------------------------------------------------",
            "RINCIAN PENGGANTIAN PER KATEGORI",
            f"Total penggantian teks : {total_replacements} titik",
            "",
        ]

        if self.category_counts:
            for cat, count in sorted(self.category_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {cat:<22}: {count} kali")
        else:
            lines.append("- (Tidak ada penggantian yang dilakukan)")

        lines.append("====================================================")
        return "\n".join(lines)

    def write_report_file(self, out_dir: str) -> str:
        """Menyimpan ringkasan ke LAPORAN_PENGGANTIAN_RPP.txt di out_dir."""
        os.makedirs(out_dir, exist_ok=True)
        report_path = os.path.join(out_dir, "LAPORAN_PENGGANTIAN_RPP.txt")
        text = self.generate_summary_text()
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(text)
        return report_path
