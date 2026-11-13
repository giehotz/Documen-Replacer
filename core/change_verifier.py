"""
Modul Verifikasi & Pelaporan Perubahan Dokumen (Change Verifier & Reporting Engine).
Mengimplementasikan verifikasi mekanis & semantik, pendeteksian bendera kualitas,
serta penerbitan laporan perubahan berformat JSON sesuai spesifikasi
RANCANGAN_OUTPUT_LAPORAN_PERUBAHAN.md.
"""
from typing import List, Dict, Any, Optional, Tuple, Set
import os
import re
import json
import logging
from datetime import datetime

from core.validation_engine import ReplacementPlanItem, ConfidenceLevel
from document.docx_reader import load_document, iter_all_paragraphs, iter_tables
from document.paragraph_processor import get_paragraph_text

logger = logging.getLogger(__name__)


def highlight_span(text: str, start: int, end: int) -> str:
    """Membungkus rentang [start:end] dengan penanda sorotan ⟦ ⟧."""
    if not text:
        return ""
    start = max(0, min(start, len(text)))
    end = max(start, min(end, len(text)))
    return f"{text[:start]}⟦{text[start:end]}⟧{text[end:]}"


def anonymize_pii_text(text: str) -> str:
    """Menyamarkan NIP (menjadi 19800101••••••1001) untuk opsi privasi laporan."""
    if not text:
        return text

    def _mask_nip(m):
        val = m.group(0)
        if len(val) >= 16:
            return val[:8] + "••••••" + val[-4:]
        return val

    return re.sub(r"\b\d{16,18}\b", _mask_nip, text)


class ChangeReportGenerator:
    """
    Generator laporan perubahan JSON dengan verifikasi mekanis & semantik otomatis.
    Membaca ulang berkas keluaran dari disk dan memverifikasi ketepatan hasil.
    """

    def __init__(self, anonymize_pii: bool = False):
        self.anonymize_pii = anonymize_pii

    def generate_report(
        self,
        output_dir: str,
        input_dir: str,
        plan_items: List[ReplacementPlanItem],
        rules: List[Dict[str, str]],
        mode: str = "GABUNGAN",
        report_time: Optional[datetime] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Menjalankan verifikasi lengkap dan menyimpan berkas JSON ke folder <output_dir>\\_laporan.
        Mengembalikan (json_file_path, report_dict).
        """
        now = report_time or datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        laporan_dir = os.path.join(output_dir, "_laporan")
        os.makedirs(laporan_dir, exist_ok=True)
        json_file_path = os.path.join(laporan_dir, f"laporan_perubahan_{timestamp_str}.json")

        # 1. Kelompokkan item berdasarkan berkas dokumen keluaran
        items_by_rel: Dict[str, List[ReplacementPlanItem]] = {}
        for it in plan_items:
            items_by_rel.setdefault(it.rel_path, []).append(it)

        # 2. Muat dokumen hasil dari disk
        loaded_out_docs: Dict[str, Any] = {}
        unique_rel_files = list(items_by_rel.keys())

        for rel in unique_rel_files:
            root_name, ext = os.path.splitext(rel)
            out_rel = (root_name + ".docx") if ext.lower() == ".doc" else rel
            out_path = os.path.join(output_dir, out_rel)
            if os.path.isfile(out_path):
                try:
                    loaded_out_docs[rel] = load_document(out_path)
                except Exception as e:
                    logger.warning("Gagal memuat dokumen hasil %s: %s", out_path, e)
                    loaded_out_docs[rel] = None
            else:
                loaded_out_docs[rel] = None

        # 3. Deteksi keterkaitan dan penomoran ID stabil (P-0001, P-0002, ...)
        perubahan_list: List[Dict[str, Any]] = []
        item_ids: Dict[int, str] = {}
        loc_keys: Dict[int, str] = {}

        for idx, item in enumerate(plan_items, 1):
            p_id = f"P-{idx:04d}"
            item_ids[idx] = p_id
            meta = item.target_meta or {}
            t_type = item.target_type

            if t_type in ("EXACT", "PARAGRAPH_SPAN"):
                p_idx = meta.get("para_idx", 0)
                loc_key = f"{item.rel_path}#Paragraf #{p_idx}"
                loc_desc = f"Paragraf #{p_idx}"
                loc_type = "paragraf"
            elif t_type in ("TABLE_CELL", "TABLE_CELL_SPAN", "TABLE_CELL_PARA", "INSERT_SIGNATURE_TABLE"):
                t_idx = meta.get("table_idx", 0)
                r_idx = meta.get("row_idx", 0)
                c_idx = meta.get("col_idx", 0)
                p_idx = meta.get("para_idx", 0)
                loc_key = f"{item.rel_path}#Tabel #{t_idx}_R{r_idx}_C{c_idx}_P{p_idx}"
                loc_desc = f"Tabel #{t_idx}, Baris #{r_idx}, Kolom #{c_idx}"
                loc_type = "tabel"
            elif t_type == "HEADER_FOOTER":
                s_idx = meta.get("sec_idx", 0)
                is_hdr = meta.get("is_header", True)
                p_idx = meta.get("para_idx", 0)
                loc_key = f"{item.rel_path}#HF_{s_idx}_{is_hdr}_{p_idx}"
                loc_desc = f"{'Header' if is_hdr else 'Footer'} Bagian #{s_idx}"
                loc_type = "header_footer"
            else:
                loc_key = f"{item.rel_path}#{item.location_info}"
                loc_desc = item.location_info
                loc_type = "lainnya"

            loc_keys[idx] = loc_key
            item.target_meta["_temp_id"] = p_id
            item.target_meta["_temp_loc_key"] = loc_key
            item.target_meta["_temp_loc_desc"] = loc_desc
            item.target_meta["_temp_loc_type"] = loc_type

        # Cari item yang saling beririsan pada lokasi yang sama
        related_map: Dict[str, List[str]] = {}
        for i in range(len(plan_items)):
            id_i = plan_items[i].target_meta["_temp_id"]
            k_i = plan_items[i].target_meta["_temp_loc_key"]
            for j in range(i + 1, len(plan_items)):
                id_j = plan_items[j].target_meta["_temp_id"]
                k_j = plan_items[j].target_meta["_temp_loc_key"]
                if k_i == k_j:
                    related_map.setdefault(id_i, []).append(id_j)
                    related_map.setdefault(id_j, []).append(id_i)

        # 4. Lakukan verifikasi tiap butir perubahan
        for idx, item in enumerate(plan_items, 1):
            p_id = item.target_meta["_temp_id"]
            loc_key = item.target_meta["_temp_loc_key"]
            loc_desc = item.target_meta["_temp_loc_desc"]
            loc_type = item.target_meta["_temp_loc_type"]

            out_doc = loaded_out_docs.get(item.rel_path)
            sesudah_aktual = self._extract_actual_text(out_doc, item)
            sebelum = item.target_meta.get("original_text", "")
            if not sebelum:
                sebelum = item.old_text

            start_pos = item.target_meta.get("start")
            end_pos = item.target_meta.get("end")
            if (start_pos is None or end_pos is None) and sebelum and item.old_text:
                pos = sebelum.find(item.old_text)
                if pos != -1:
                    start_pos = pos
                    end_pos = pos + len(item.old_text)
                else:
                    start_pos = 0
                    end_pos = len(item.old_text)
            elif start_pos is None or end_pos is None:
                start_pos = 0
                end_pos = len(item.old_text)

            # Hitung harapan mekanis: teks sebelum yang hanya diganti di posisi yang dijanjikan
            if sebelum and start_pos is not None and end_pos is not None and start_pos <= len(sebelum):
                harapan_mekanis = sebelum[:start_pos] + item.new_text + sebelum[end_pos:]
            else:
                harapan_mekanis = item.new_text

            # Status usulan
            if not item.is_approved:
                status = "ditolak_pengguna" if item.confidence != ConfidenceLevel.LOW else "dilewati"
            else:
                status = "diterapkan"

            # Pemeriksaan Mekanis & Semantik
            verifikasi = self._verify_item(
                item=item,
                sebelum=sebelum,
                sesudah_aktual=sesudah_aktual,
                harapan_mekanis=harapan_mekanis,
                start_pos=start_pos,
                end_pos=end_pos,
                status=status,
                related_ids=related_map.get(p_id, []),
            )

            # Penyorotan ⟦ ⟧
            sebelum_sorot = highlight_span(sebelum, start_pos, end_pos)
            pos_new = sesudah_aktual.find(item.new_text) if sesudah_aktual else -1
            if pos_new != -1:
                sesudah_sorot = highlight_span(sesudah_aktual, pos_new, pos_new + len(item.new_text))
            elif sesudah_aktual:
                sesudah_sorot = f"⟦{sesudah_aktual}⟧"
            else:
                sesudah_sorot = ""

            # Penyamaran PII jika aktif
            if self.anonymize_pii:
                disp_sebelum = anonymize_pii_text(sebelum)
                disp_sebelum_sorot = anonymize_pii_text(sebelum_sorot)
                disp_sesudah_aktual = anonymize_pii_text(sesudah_aktual)
                disp_sesudah_sorot = anonymize_pii_text(sesudah_sorot)
                disp_old = anonymize_pii_text(item.old_text)
                disp_new = anonymize_pii_text(item.new_text)
            else:
                disp_sebelum = sebelum
                disp_sebelum_sorot = sebelum_sorot
                disp_sesudah_aktual = sesudah_aktual
                disp_sesudah_sorot = sesudah_sorot
                disp_old = item.old_text
                disp_new = item.new_text

            rule_id = item.target_meta.get("rule_id", "R1")
            field_type = "year_range" if "Tahun" in item.category else (
                "nip" if "NIP" in item.category else "text"
            )

            butir_laporan = {
                "id": p_id,
                "berkas": {
                    "nama": os.path.basename(item.rel_path),
                    "path_relatif": item.rel_path.replace("\\", "/"),
                },
                "lokasi": {
                    "jenis": loc_type,
                    "deskripsi": loc_desc,
                    "kunci": loc_key.replace("\\", "/"),
                },
                "isian": {
                    "id": item.category.lower().replace(" ", "_"),
                    "kategori": item.category,
                    "jenis_nilai": field_type,
                },
                "aturan_id": rule_id,
                "metode": item.target_type,
                "keyakinan": item.confidence,
                "disetujui": item.is_approved,
                "status": status,
                "perubahan": {
                    "teks_lama": disp_old,
                    "teks_baru": disp_new,
                    "mulai": start_pos,
                    "akhir": end_pos,
                },
                "konteks": {
                    "sebelum": disp_sebelum,
                    "sebelum_sorot": disp_sebelum_sorot,
                    "sesudah_aktual": disp_sesudah_aktual,
                    "sesudah_sorot": disp_sesudah_sorot,
                },
                "verifikasi": verifikasi,
            }

            if status != "diterapkan":
                butir_laporan["alasan_dilewati"] = (
                    "Ditolak oleh pengguna pada tahap pratinjau"
                    if status == "ditolak_pengguna"
                    else "Tingkat keyakinan rendah atau tidak ada teks pengganti disetujui"
                )

            perubahan_list.append(butir_laporan)

        # 5. Urutkan butir: SALAH lebih dulu, lalu PERIKSA, baru OK
        order_map = {"SALAH": 0, "PERIKSA": 1, "OK": 2}
        perubahan_list.sort(key=lambda x: (order_map.get(x["verifikasi"]["verdict"], 3), x["id"]))

        # 6. Susun Ringkasan Tingkat Tinggi
        ringkasan = self._build_summary(perubahan_list, unique_rel_files, rules, loaded_out_docs)

        # 7. Susun Dokumen Laporan Lengkap
        report_data = {
            "meta": {
                "dibuat_pada": now.isoformat(),
                "folder_masukan": input_dir,
                "folder_keluaran": output_dir,
                "mode": mode,
                "jumlah_berkas": len(unique_rel_files),
                "samarkan_data_pribadi": self.anonymize_pii,
                "total_perubahan_terekam": len(perubahan_list),
            },
            "aturan": [
                {
                    "id": f"R{i}",
                    "label": r.get("label", ""),
                    "old": r.get("old", ""),
                    "new": r.get("new", ""),
                }
                for i, r in enumerate(rules, 1)
            ],
            "ringkasan": ringkasan,
            "perubahan": perubahan_list,
        }

        # 8. Tulis Berkas JSON
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        return json_file_path, report_data

    def _extract_actual_text(self, doc, item: ReplacementPlanItem) -> str:
        """Mengekstrak teks aktual dari dokumen hasil pada lokasi yang sama."""
        if not doc:
            return ""

        meta = item.target_meta or {}
        t_type = item.target_type

        try:
            if t_type in ("EXACT", "PARAGRAPH_SPAN"):
                p_idx = meta.get("para_idx", 0)
                paras = doc.paragraphs
                if p_idx < len(paras):
                    return get_paragraph_text(paras[p_idx])
            elif t_type in ("TABLE_CELL", "TABLE_CELL_SPAN", "TABLE_CELL_PARA", "INSERT_SIGNATURE_TABLE"):
                t_idx = meta.get("table_idx", 0)
                r_idx = meta.get("row_idx", 0)
                c_idx = meta.get("col_idx", 0)
                p_idx = meta.get("para_idx", 0)
                tables = iter_tables(doc)
                if t_idx < len(tables):
                    tbl = tables[t_idx]
                    if r_idx < len(tbl.rows) and c_idx < len(tbl.rows[r_idx].cells):
                        cell = tbl.rows[r_idx].cells[c_idx]
                        if p_idx < len(cell.paragraphs):
                            return get_paragraph_text(cell.paragraphs[p_idx])
            elif t_type == "HEADER_FOOTER":
                s_idx = meta.get("sec_idx", 0)
                is_hdr = meta.get("is_header", True)
                p_idx = meta.get("para_idx", 0)
                if s_idx < len(doc.sections):
                    sec = doc.sections[s_idx]
                    hf = sec.header if is_hdr else sec.footer
                    if p_idx < len(hf.paragraphs):
                        return get_paragraph_text(hf.paragraphs[p_idx])
        except Exception as e:
            logger.debug("Error saat membaca sesudah_aktual: %s", e)

        # Fallback: cari paragraf yang memuat new_text
        for p in iter_all_paragraphs(doc.element.body, doc):
            t = get_paragraph_text(p)
            if item.new_text and item.new_text in t:
                return t

        return ""

    def _verify_item(
        self,
        item: ReplacementPlanItem,
        sebelum: str,
        sesudah_aktual: str,
        harapan_mekanis: str,
        start_pos: int,
        end_pos: int,
        status: str,
        related_ids: List[str],
    ) -> Dict[str, Any]:
        """Melakukan pengujian mekanis & semantik serta pengumpulan bendera."""
        bendera: List[Dict[str, str]] = []

        # 1. Bendera Tumpang Tindih
        if related_ids:
            bendera.append({
                "kode": "PERUBAHAN_TUMPANG_TINDIH",
                "tingkat": "ERROR",
                "pesan": f"Dua atau lebih usulan menyasar area yang sama ({', '.join(related_ids)}).",
                "saran": "Satu area hanya boleh satu usulan; gunakan aturan yang lebih spesifik.",
            })

        # 2. Verifikasi Mekanis
        if status == "diterapkan":
            cocok_mekanis = (harapan_mekanis.strip() == sesudah_aktual.strip())
            if not cocok_mekanis and sesudah_aktual:
                bendera.append({
                    "kode": "HASIL_TIDAK_SESUAI_HARAPAN",
                    "tingkat": "ERROR",
                    "pesan": "Teks akhir berbeda dari hasil substitusi murni yang direncanakan.",
                    "saran": "Periksa pergeseran offset atau penimpaan teks ganda.",
                })
        else:
            cocok_mekanis = None

        # 3. Verifikasi Semantik
        cocok_semantik = True

        if status == "diterapkan":
            # Bendera Awalan Tahun Ganda (Kasus 202026)
            if re.search(r"(?<!\d)20(20\d{2})(?!\d)", sesudah_aktual):
                cocok_semantik = False
                bendera.append({
                    "kode": "TAHUN_AWALAN_GANDA",
                    "tingkat": "ERROR",
                    "pesan": "Hasil memuat pola tahun ganda (misal '202026'): awalan '20' dari template tidak ikut diganti.",
                    "saran": "Perlakukan '20.... / 20....' sebagai satu unit placeholder tahun penuh.",
                })

            # Bendera Sisa Placeholder Titik / Garis Bawah
            if re.search(r"\.{2,}|_{3,}|…", sesudah_aktual):
                # Kecuali jika memang teks baru sengaja memuat titik
                if not re.search(r"\.{2,}|_{3,}|…", item.new_text):
                    cocok_semantik = False
                    bendera.append({
                        "kode": "SISA_PLACEHOLDER",
                        "tingkat": "ERROR",
                        "pesan": "Masih ada karakter placeholder (titik-titik atau garis bawah) yang tersisa.",
                        "saran": "Ganti seluruh pola rentang teks sekaligus.",
                    })

            # Bendera Teks Baru Tidak Ada Sama Sekali
            if item.new_text and item.new_text not in sesudah_aktual:
                cocok_semantik = False
                bendera.append({
                    "kode": "TEKS_BARU_TIDAK_ADA",
                    "tingkat": "ERROR",
                    "pesan": f"Teks baru '{item.new_text}' tidak ditemukan pada teks hasil.",
                    "saran": "Periksa kegagalan penulisan dokumen atau run-level replacement.",
                })

            # Format Validasi Tahun
            if "Tahun" in item.category:
                m_yr = re.search(r"(?<!\d)(20\d{2})\s*[/\\-]\s*(20\d{2})(?!\d)", sesudah_aktual)
                if m_yr:
                    y1 = int(m_yr.group(1))
                    y2 = int(m_yr.group(2))
                    if y2 != y1 + 1:
                        bendera.append({
                            "kode": "TAHUN_TIDAK_BERURUTAN",
                            "tingkat": "WARN",
                            "pesan": f"Tahun kedua ({y2}) bukan tahun pertama ({y1}) + 1.",
                            "saran": "Pastikan penulisan tahun ajaran berurutan (misal 2026/2027).",
                        })
                elif not re.search(r"(?<!\d)20\d{2}(?!\d)", sesudah_aktual):
                    cocok_semantik = False
                    bendera.append({
                        "kode": "TAHUN_FORMAT_SALAH",
                        "tingkat": "ERROR",
                        "pesan": "Nilai tahun terbaca tidak berformat tahun standar 20xx atau 20xx/20xx.",
                        "saran": f"Harapan format: '{item.new_text}'.",
                    })

            # Format Validasi NIP
            if "NIP" in item.category:
                digits_only = re.sub(r"\D", "", sesudah_aktual)
                if digits_only and len(digits_only) not in (16, 18) and sesudah_aktual.strip() != "-":
                    bendera.append({
                        "kode": "NIP_PANJANG_TIDAK_LAZIM",
                        "tingkat": "WARN",
                        "pesan": f"Panjang digit NIP ({len(digits_only)}) tidak lazim (standar 18 digit untuk PNS atau 16 untuk NIK).",
                        "saran": "Periksa kemungkinan salah ketik atau digit terpotong.",
                    })

            # Sisa Teks Lama (jika teks lama bukan placeholder murni)
            clean_old = item.old_text.strip()
            if len(clean_old) >= 4 and not re.match(r"^[\s\._\-\(\)]+$", clean_old):
                if clean_old in sesudah_aktual and clean_old != item.new_text:
                    bendera.append({
                        "kode": "SISA_TEKS_LAMA",
                        "tingkat": "WARN",
                        "pesan": f"Teks lama '{clean_old}' masih ditemukan pada hasil.",
                        "saran": "Pastikan penggantian mencakup seluruh kemunculan istilah lama.",
                    })

            # Perubahan Berlebihan
            if len(item.old_text) > 3 * len(item.new_text) + 25:
                bendera.append({
                    "kode": "PERUBAHAN_BERLEBIHAN",
                    "tingkat": "WARN",
                    "pesan": "Panjang teks yang diganti jauh lebih besar dari teks baru yang disisipkan.",
                    "saran": "Periksa apakah ada kalimat lain di sekitar yang ikut terhapus.",
                })

            # Spasi Ganda atau Titik Dua Ganda
            if re.search(r"[ ]{3,}|::|,,", sesudah_aktual):
                bendera.append({
                    "kode": "SPASI_ATAU_TANDA_GANDA",
                    "tingkat": "INFO",
                    "pesan": "Ditemukan spasi ganda atau tanda baca ganda pada teks hasil.",
                    "saran": "Rapikan spasi agar tampilan dokumen lebih rapi.",
                })

            # Keyakinan Rendah Diterapkan
            if item.confidence == ConfidenceLevel.LOW:
                bendera.append({
                    "kode": "YAKIN_RENDAH",
                    "tingkat": "INFO",
                    "pesan": "Usulan dengan keyakinan RENDAH (LOW) tetap diterapkan.",
                    "saran": "Disarankan meninjau langsung letak penggantian ini.",
                })

        elif status == "dilewati" and item.target_meta.get("is_existing_value"):
            bendera.append({
                "kode": "NILAI_LAMA_TERISI_TIDAK_DIGANTI",
                "tingkat": "WARN",
                "pesan": f"Nilai lama '{item.old_text}' masih terisi dan dilewati tanpa pembaruan ke '{item.new_text}'.",
                "saran": "Centang usulan ini di jendela pratinjau jika ingin memperbarui nilai tersebut.",
            })

        # Hitung Vonis Akhir
        has_error = any(b["tingkat"] == "ERROR" for b in bendera)
        has_warn = any(b["tingkat"] == "WARN" for b in bendera)

        if has_error or (status == "diterapkan" and (not cocok_mekanis or not cocok_semantik)):
            verdict = "SALAH"
        elif has_warn:
            verdict = "PERIKSA"
        else:
            verdict = "OK"

        return {
            "verdict": verdict,
            "mekanis": {
                "harapan": harapan_mekanis,
                "aktual": sesudah_aktual,
                "cocok": cocok_mekanis,
            },
            "semantik": {
                "nilai_diharapkan": item.new_text,
                "nilai_terbaca": sesudah_aktual,
                "cocok": cocok_semantik if status == "diterapkan" else None,
            },
            "bendera": bendera,
            "terkait": related_ids,
        }

    def _build_summary(
        self,
        perubahan_list: List[Dict[str, Any]],
        files: List[str],
        rules: List[Dict[str, str]],
        loaded_out_docs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Menyusun bagian ringkasan eksekutif laporan."""
        total_proposals = len(perubahan_list)
        diterapkan = sum(1 for p in perubahan_list if p["status"] == "diterapkan")
        dilewati = sum(1 for p in perubahan_list if p["status"] == "dilewati")
        ditolak = sum(1 for p in perubahan_list if p["status"] == "ditolak_pengguna")

        ok_count = sum(1 for p in perubahan_list if p["verifikasi"]["verdict"] == "OK")
        periksa_count = sum(1 for p in perubahan_list if p["verifikasi"]["verdict"] == "PERIKSA")
        salah_count = sum(1 for p in perubahan_list if p["verifikasi"]["verdict"] == "SALAH")

        perlu_tinjau = [p["id"] for p in perubahan_list if p["verifikasi"]["verdict"] in ("SALAH", "PERIKSA")]

        # Hitung Pasangan Unik
        pasangan_dict: Dict[Tuple[str, str, str], Dict[str, int]] = {}
        for p in perubahan_list:
            key = (p["isian"]["kategori"], p["perubahan"]["teks_lama"], p["perubahan"]["teks_baru"])
            if key not in pasangan_dict:
                pasangan_dict[key] = {"jumlah": 0, "bermasalah": 0}
            pasangan_dict[key]["jumlah"] += 1
            if p["verifikasi"]["verdict"] != "OK":
                pasangan_dict[key]["bermasalah"] += 1

        pasangan_unik = [
            {
                "isian": k[0],
                "dari": k[1],
                "ke": k[2],
                "jumlah": v["jumlah"],
                "bermasalah": v["bermasalah"],
            }
            for k, v in pasangan_dict.items()
        ]
        pasangan_unik.sort(key=lambda x: (x["bermasalah"] == 0, -x["jumlah"]))

        # Hitung Berkas Bermasalah
        berkas_dict: Dict[str, Dict[str, int]] = {}
        for p in perubahan_list:
            f_rel = p["berkas"]["path_relatif"]
            v = p["verifikasi"]["verdict"]
            if v != "OK":
                berkas_dict.setdefault(f_rel, {"salah": 0, "periksa": 0})
                if v == "SALAH":
                    berkas_dict[f_rel]["salah"] += 1
                else:
                    berkas_dict[f_rel]["periksa"] += 1

        berkas_bermasalah = [
            {"berkas": k, "salah": v["salah"], "periksa": v["periksa"]}
            for k, v in berkas_dict.items()
        ]
        berkas_bermasalah.sort(key=lambda x: (-x["salah"], -x["periksa"]))

        # Hitung Sisa Istilah Lama pada Seluruh Dokumen Hasil
        sisa_istilah_lama = []
        for r in rules:
            old_term = r.get("old", "").strip()
            if old_term and len(old_term) >= 3 and not re.match(r"^[\s\._\-]+$", old_term):
                count_remaining = 0
                affected_files = []
                for f_rel, doc in loaded_out_docs.items():
                    if not doc:
                        continue
                    file_count = 0
                    for p in iter_all_paragraphs(doc.element.body, doc):
                        txt = get_paragraph_text(p)
                        if old_term in txt:
                            file_count += 1
                    if file_count > 0:
                        count_remaining += file_count
                        affected_files.append(f_rel)
                if count_remaining > 0:
                    sisa_istilah_lama.append({
                        "istilah": old_term,
                        "tersisa": count_remaining,
                        "berkas": affected_files,
                    })

        return {
            "total_usulan": total_proposals,
            "status": {
                "diterapkan": diterapkan,
                "dilewati": dilewati,
                "ditolak_pengguna": ditolak,
            },
            "verdict": {
                "OK": ok_count,
                "PERIKSA": periksa_count,
                "SALAH": salah_count,
            },
            "perlu_tinjau": perlu_tinjau,
            "pasangan_unik": pasangan_unik,
            "sisa_istilah_lama": sisa_istilah_lama,
            "berkas_bermasalah": berkas_bermasalah,
        }
