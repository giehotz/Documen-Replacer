"""
Analyzer dan generator sinkronisasi Lampiran Surat Keputusan (SK).
Menemukan blok pojok kanan atas lampiran (Nomor, Tanggal, Tentang)
dan menghasilkan usulan penggantian (ReplacementPlanItem) yang menyelaraskan
seluruh lampiran dengan nilai SK utama.
"""
from typing import List, Dict, Any, Optional
from core.replacement_engine import ReplacementPlanItem
from document.extensions.attachment_table_processor import find_attachment_headers


def plan_attachment_sync_items(
    doc,
    doc_path: str,
    rel_path: str,
    rules_dict: Dict[str, str],
) -> List[ReplacementPlanItem]:
    """
    Menghasilkan ReplacementPlanItem untuk menyinkronkan field di seluruh lampiran SK:
    - nomor_sk -> sinkron ke Nomor Lampiran
    - tanggal_penetapan -> sinkron ke Tanggal Lampiran
    - tentang_sk -> sinkron ke Tentang Lampiran
    """
    sync_items: List[ReplacementPlanItem] = []
    attachments = find_attachment_headers(doc)

    # Pemetaan antara field lampiran dan key rules
    field_mapping = {
        "nomor_sk": ["nomor_sk", "Nomor SK", "Nomor"],
        "tanggal_penetapan": ["tanggal_penetapan", "Tanggal Penetapan", "Tanggal"],
        "tentang_sk": ["tentang_sk", "Tentang SK", "Tentang"],
    }

    # Cari nilai baru yang diinginkan dari rules_dict
    new_values: Dict[str, str] = {}
    for target_key, candidate_keys in field_mapping.items():
        for k in candidate_keys:
            if k in rules_dict and rules_dict[k]:
                new_values[target_key] = rules_dict[k]
                break

    if not new_values:
        return sync_items

    for att_idx, att in enumerate(attachments):
        fields = att.get("fields", {})
        for f_name, f_info in fields.items():
            if f_name not in new_values:
                continue

            new_val = new_values[f_name]
            old_val = f_info.get("raw_text", "")
            span = f_info.get("span", (0, len(old_val)))
            loc = f_info.get("location", "body")

            meta: Dict[str, Any] = {
                "domain_id": "sk_keputusan",
                "sync_field": f_name,
                "attachment_index": att_idx,
                "start": span[0],
                "end": span[1],
                "original_text": f_info.get("original_text", ""),
            }

            if loc == "table":
                target_type = "TABLE_CELL_SPAN"
                meta.update({
                    "table_idx": f_info.get("table_idx", 0),
                    "row_idx": f_info.get("row_idx", 0),
                    "col_idx": f_info.get("col_idx", 0),
                    "para_idx": f_info.get("para_idx", 0),
                })
                loc_info = f"Tabel #{f_info.get('table_idx', 0) + 1} Sel ({f_info.get('row_idx', 0)},{f_info.get('col_idx', 0)}) [Lampiran {att_idx + 1}]"
            else:
                target_type = "PARAGRAPH_SPAN"
                meta["para_idx"] = f_info.get("para_idx", 0)
                loc_info = f"Paragraf #{f_info.get('para_idx', 0) + 1} [Lampiran {att_idx + 1}]"

            plan_item = ReplacementPlanItem(
                doc_path=doc_path,
                rel_path=rel_path,
                category=f"Lampiran SK ({f_name})",
                old_text=old_val,
                new_text=new_val,
                confidence="HIGH",
                location_info=loc_info,
                is_approved=True,
                target_type=target_type,
                target_meta=meta,
            )
            sync_items.append(plan_item)

    return sync_items
