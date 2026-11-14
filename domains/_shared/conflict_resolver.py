"""
Resolusi konflik tumpang tindih usulan perubahan lintas zona maupun antar-aturan.
Mencegah penerapan ganda pada lokasi/rentang karakter yang sama.
"""
from typing import List, Dict
from core.validation_engine import ReplacementPlanItem


def resolve_overlapping_items(items: List[ReplacementPlanItem]) -> List[ReplacementPlanItem]:
    """
    Menyelesaikan usulan perubahan yang tumpang tindih pada lokasi yang sama
    (misal usulan dari zona berbeda atau dari aturan persis & zona pada paragraf yang sama).
    Prinsip: Satu area karakter hanya boleh menerima satu usulan (aturan lebih spesifik/panjang menang).
    """
    if not items:
        return []

    groups: Dict[str, List[ReplacementPlanItem]] = {}
    for it in items:
        t_type = it.target_type
        meta = it.target_meta or {}
        if t_type in ("EXACT", "PARAGRAPH_SPAN"):
            p_idx = meta.get("all_para_idx", meta.get("para_idx", -1))
            loc_key = f"{it.doc_path}#P#{p_idx}"
        elif t_type in ("TABLE_CELL", "TABLE_CELL_SPAN", "TABLE_CELL_PARA", "INSERT_SIGNATURE_TABLE"):
            t_idx = meta.get("table_idx", -1)
            r_idx = meta.get("row_idx", -1)
            c_idx = meta.get("col_idx", -1)
            p_idx = meta.get("para_idx", 0)
            loc_key = f"{it.doc_path}#T#{t_idx}_{r_idx}_{c_idx}_{p_idx}"
        elif t_type == "HEADER_FOOTER":
            s_idx = meta.get("sec_idx", -1)
            hf_attr = meta.get("hf_attr", "header" if meta.get("is_header", True) else "footer")
            p_idx = meta.get("para_idx", -1)
            loc_key = f"{it.doc_path}#HF#{s_idx}_{hf_attr}_{p_idx}"
        elif t_type == "TAB_LINE":
            p_idx = meta.get("all_para_idx", meta.get("para_idx", -1))
            loc_key = f"{it.doc_path}#P#{p_idx}"
        else:
            loc_key = f"{it.doc_path}#{it.location_info}"

        groups.setdefault(loc_key, []).append(it)

    resolved: List[ReplacementPlanItem] = []

    for loc_key, group_items in groups.items():
        if len(group_items) == 1:
            resolved.append(group_items[0])
            continue

        kept: List[ReplacementPlanItem] = []
        for candidate in group_items:
            c_meta = candidate.target_meta or {}
            c_start = c_meta.get("start")
            c_end = c_meta.get("end")
            orig_text = c_meta.get("original_text", "")
            if (c_start is None or c_end is None) and orig_text and candidate.old_text:
                pos = orig_text.find(candidate.old_text)
                if pos != -1:
                    c_start = pos
                    c_end = pos + len(candidate.old_text)
                    c_meta["start"] = c_start
                    c_meta["end"] = c_end

            overlapping_entries = []
            for i, existing in enumerate(kept):
                e_meta = existing.target_meta or {}
                e_start = e_meta.get("start")
                e_end = e_meta.get("end")

                if c_start is not None and c_end is not None and e_start is not None and e_end is not None:
                    overlaps = max(c_start, e_start) < min(c_end, e_end)
                else:
                    overlaps = (candidate.old_text in existing.old_text or existing.old_text in candidate.old_text)

                if overlaps:
                    overlapping_entries.append((i, existing))

            if not overlapping_entries:
                kept.append(candidate)
            else:
                candidate_wins_all = True
                for i, existing in overlapping_entries:
                    c_is_exact = (candidate.target_type == "EXACT")
                    e_is_exact = (existing.target_type == "EXACT")
                    c_special = bool(candidate.target_meta and (candidate.target_meta.get("sync_field") or candidate.target_meta.get("date_iso") or candidate.target_meta.get("party_attr")))
                    e_special = bool(existing.target_meta and (existing.target_meta.get("sync_field") or existing.target_meta.get("date_iso") or existing.target_meta.get("party_attr")))

                    if c_special and not e_special:
                        winner_is_candidate = True
                    elif e_special and not c_special:
                        winner_is_candidate = False
                    elif c_is_exact and not e_is_exact:
                        winner_is_candidate = True
                    elif e_is_exact and not c_is_exact:
                        winner_is_candidate = False
                    else:
                        winner_is_candidate = (len(candidate.old_text) >= len(existing.old_text))

                    if not winner_is_candidate:
                        candidate_wins_all = False
                        existing.target_meta.setdefault("superseded_old_texts", []).append(candidate.old_text)
                        break

                if candidate_wins_all:
                    for i, existing in overlapping_entries:
                        candidate.target_meta.setdefault("superseded_old_texts", []).append(existing.old_text)
                    for i, _ in sorted(overlapping_entries, key=lambda x: x[0], reverse=True):
                        kept.pop(i)
                    kept.append(candidate)

        resolved.extend(kept)

    return resolved


# Alias untuk fleksibilitas pemanggilan
resolve_replacement_overlaps = resolve_overlapping_items

