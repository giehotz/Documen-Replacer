"""
Analyzer daftar pegawai pada Surat Perintah Tugas (SPT).
Mendeteksi dua variasi tata letak:
1. SPT Tunggal (Format Titik Dua): Nama, NIP, Pangkat/Gol, Jabatan.
2. SPT Kolektif (Format Tabel): Kolom No, Nama/NIP, Pangkat/Gol, Jabatan, Keterangan.

Mendukung pemetaan dataset tabular via datasets={"pegawai": [...]}
dan validasi jumlah baris (JUMLAH_BARIS_TIDAK_SAMA).
"""
from typing import Dict, Any, List, Optional, Tuple
import re
from docx.text.paragraph import Paragraph
from core.replacement_engine import ReplacementPlanItem
from document.paragraph_processor import get_paragraph_text


def analyze_spt_pegawai(doc) -> Dict[str, Any]:
    """
    Menganalisis tata letak penugasan pegawai pada naskah SPT.
    Mengembalikan metadata tata letak (table_kolektif atau single_colon).
    """
    # 1. Periksa tabel pegawai kolektif
    for tbl_idx, table in enumerate(doc.tables):
        if len(table.rows) >= 2:
            h_row = table.rows[0]
            h_texts = [" ".join(get_paragraph_text(p) for p in c.paragraphs).lower() for c in h_row.cells]
            if any("nama" in t or "pegawai" in t for t in h_texts):
                col_map: Dict[str, int] = {}
                for c_i, t in enumerate(h_texts):
                    if "no" in t and "keterangan" not in t:
                        col_map["no"] = c_i
                    if "nama" in t and "nip" in t:
                        col_map["nama_nip"] = c_i
                        col_map["nama"] = c_i
                        col_map["nip"] = c_i
                    elif "nama" in t:
                        col_map["nama"] = c_i
                    elif "nip" in t:
                        col_map["nip"] = c_i
                    if "pangkat" in t or "gol" in t:
                        col_map["pangkat_gol"] = c_i
                    if "jabatan" in t:
                        col_map["jabatan"] = c_i

                data_rows_count = len(table.rows) - 1
                return {
                    "layout_type": "table_kolektif",
                    "table_idx": tbl_idx,
                    "header_row_idx": 0,
                    "data_rows_count": data_rows_count,
                    "columns": col_map,
                }

    # 2. Periksa format titik dua pada paragraf
    single_fields: Dict[str, Any] = {}
    for idx, p in enumerate(doc.paragraphs):
        raw_text = get_paragraph_text(p)
        text = raw_text.strip()
        if not text or ":" not in text:
            continue

        parts = text.split(":", 1)
        lbl = parts[0].strip().lower()
        val = parts[1].strip()
        if not val:
            continue

        v_start = raw_text.find(val)
        v_end = v_start + len(val) if v_start != -1 else len(raw_text)
        item_data = {
            "value": val,
            "para_idx": idx,
            "span": (v_start, v_end),
            "original_text": raw_text,
        }

        if lbl in ["nama", "nama lengkap"] and "nama" not in single_fields:
            single_fields["nama"] = item_data
        elif "nip" in lbl and "nip" not in single_fields:
            single_fields["nip"] = item_data
        elif ("pangkat" in lbl or "gol" in lbl) and "pangkat_gol" not in single_fields:
            single_fields["pangkat_gol"] = item_data
        elif "jabatan" in lbl and "jabatan" not in single_fields:
            single_fields["jabatan"] = item_data

    return {
        "layout_type": "single_colon",
        "fields": single_fields,
    }


def plan_collective_spt_items(
    doc,
    doc_path: str,
    rel_path: str,
    pegawai_dataset: List[Dict[str, Any]],
    table_info: Dict[str, Any],
) -> Tuple[List[ReplacementPlanItem], List[Dict[str, str]]]:
    """
    Menghasilkan ReplacementPlanItem untuk mengisi baris tabel pegawai kolektif.
    Memeriksa kesesuaian jumlah record data dengan baris tabel.
    """
    plan_items: List[ReplacementPlanItem] = []
    issues: List[Dict[str, str]] = []

    tbl_idx = table_info.get("table_idx", 0)
    col_map = table_info.get("columns", {})
    table = doc.tables[tbl_idx]
    data_rows_count = len(table.rows) - 1
    dataset_count = len(pegawai_dataset)

    if dataset_count != data_rows_count:
        issues.append({
            "code": "JUMLAH_BARIS_TIDAK_SAMA",
            "message": f"Jumlah pegawai pada data ({dataset_count}) berbeda dengan jumlah baris tabel SPT ({data_rows_count})."
        })

    # Isi baris tabel yang ada
    limit = min(data_rows_count, dataset_count)
    for i in range(limit):
        r_idx = i + 1  # Lewati baris header
        row = table.rows[r_idx]
        peg = pegawai_dataset[i]

        # 1. Kolom Nama & NIP (bisa tergabung atau terpisah)
        if "nama_nip" in col_map:
            c_idx = col_map["nama_nip"]
            cell = row.cells[c_idx]
            cell_txt = " ".join(get_paragraph_text(p) for p in cell.paragraphs).strip()
            new_nama = peg.get("nama", "")
            new_nip = peg.get("nip", "")
            # Pertahankan pemisah jika ada (misal garis miring atau newline)
            if "/" in cell_txt:
                new_comb = f"{new_nama} / {new_nip}" if new_nip else new_nama
            else:
                new_comb = f"{new_nama}\n{new_nip}" if new_nip else new_nama

            plan_items.append(ReplacementPlanItem(
                doc_path=doc_path,
                rel_path=rel_path,
                category=f"Pegawai #{i + 1} (Nama/NIP)",
                old_text=cell_txt,
                new_text=new_comb,
                confidence="HIGH",
                location_info=f"Tabel #{tbl_idx + 1} Sel ({r_idx},{c_idx})",
                is_approved=True,
                target_type="TABLE_CELL",
                target_meta={
                    "domain_id": "spt_penugasan",
                    "table_idx": tbl_idx,
                    "row_idx": r_idx,
                    "col_idx": c_idx,
                    "para_idx": 0,
                    "original_text": cell_txt,
                }
            ))
        else:
            if "nama" in col_map and peg.get("nama"):
                c_idx = col_map["nama"]
                cell_txt = " ".join(get_paragraph_text(p) for p in row.cells[c_idx].paragraphs).strip()
                plan_items.append(ReplacementPlanItem(
                    doc_path=doc_path,
                    rel_path=rel_path,
                    category=f"Pegawai #{i + 1} (Nama)",
                    old_text=cell_txt,
                    new_text=peg["nama"],
                    confidence="HIGH",
                    location_info=f"Tabel #{tbl_idx + 1} Sel ({r_idx},{c_idx})",
                    is_approved=True,
                    target_type="TABLE_CELL",
                    target_meta={
                        "domain_id": "spt_penugasan",
                        "table_idx": tbl_idx,
                        "row_idx": r_idx,
                        "col_idx": c_idx,
                        "para_idx": 0,
                        "original_text": cell_txt,
                    }
                ))
            if "nip" in col_map and peg.get("nip"):
                c_idx = col_map["nip"]
                cell_txt = " ".join(get_paragraph_text(p) for p in row.cells[c_idx].paragraphs).strip()
                plan_items.append(ReplacementPlanItem(
                    doc_path=doc_path,
                    rel_path=rel_path,
                    category=f"Pegawai #{i + 1} (NIP)",
                    old_text=cell_txt,
                    new_text=peg["nip"],
                    confidence="HIGH",
                    location_info=f"Tabel #{tbl_idx + 1} Sel ({r_idx},{c_idx})",
                    is_approved=True,
                    target_type="TABLE_CELL",
                    target_meta={
                        "domain_id": "spt_penugasan",
                        "table_idx": tbl_idx,
                        "row_idx": r_idx,
                        "col_idx": c_idx,
                        "para_idx": 0,
                        "original_text": cell_txt,
                    }
                ))

        # 2. Kolom Pangkat / Golongan
        if "pangkat_gol" in col_map and peg.get("pangkat_gol"):
            c_idx = col_map["pangkat_gol"]
            cell_txt = " ".join(get_paragraph_text(p) for p in row.cells[c_idx].paragraphs).strip()
            plan_items.append(ReplacementPlanItem(
                doc_path=doc_path,
                rel_path=rel_path,
                category=f"Pegawai #{i + 1} (Pangkat/Gol)",
                old_text=cell_txt,
                new_text=peg["pangkat_gol"],
                confidence="HIGH",
                location_info=f"Tabel #{tbl_idx + 1} Sel ({r_idx},{c_idx})",
                is_approved=True,
                target_type="TABLE_CELL",
                target_meta={
                    "domain_id": "spt_penugasan",
                    "table_idx": tbl_idx,
                    "row_idx": r_idx,
                    "col_idx": c_idx,
                    "para_idx": 0,
                    "original_text": cell_txt,
                }
            ))

        # 3. Kolom Jabatan
        if "jabatan" in col_map and peg.get("jabatan"):
            c_idx = col_map["jabatan"]
            cell_txt = " ".join(get_paragraph_text(p) for p in row.cells[c_idx].paragraphs).strip()
            plan_items.append(ReplacementPlanItem(
                doc_path=doc_path,
                rel_path=rel_path,
                category=f"Pegawai #{i + 1} (Jabatan)",
                old_text=cell_txt,
                new_text=peg["jabatan"],
                confidence="HIGH",
                location_info=f"Tabel #{tbl_idx + 1} Sel ({r_idx},{c_idx})",
                is_approved=True,
                target_type="TABLE_CELL",
                target_meta={
                    "domain_id": "spt_penugasan",
                    "table_idx": tbl_idx,
                    "row_idx": r_idx,
                    "col_idx": c_idx,
                    "para_idx": 0,
                    "original_text": cell_txt,
                }
            ))

    return plan_items, issues
