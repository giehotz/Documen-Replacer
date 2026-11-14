"""
Modul Orkestrator: Replacement Engine.
Menjalankan pipeline bertingkat (Lapis 1 - 5) dan mendukung:
- Direct Execution: Memproses langsung dokumen ke disk.
- Interactive Planning: Memindai dan menghasilkan ReplacementPlanItem untuk Pratinjau Interaktif.
- Execution of Approved Items: Menerapkan hanya perubahan yang disetujui pengguna.
"""
from typing import List, Tuple, Dict, Any, Optional
import os
import re
import logging

from core.exact_matcher import build_exact_pattern
from core.label_recognizer import load_aliases, match_category
from core.similarity_matcher import find_fuzzy_category_match
from core.placeholder_detector import (
    extract_label_and_placeholder,
    is_pure_placeholder,
    unwrap_parentheses,
    format_with_parentheses,
)
from core.signature_analyzer import (
    is_signature_table,
    classify_zone_role,
    is_titimangsa_line,
    is_academic_name,
    is_paragraph_bold_or_underlined,
    RE_NIP_LINE,
    process_tab_separated_signature_block,
    KEPALA_ROLE_KEYWORDS,
    GURU_ROLE_KEYWORDS,
)
from core.validation_engine import (
    ReplacementPlanItem,
    ConfidenceLevel,
    validate_type_safety,
)
from document.docx_reader import load_document, iter_all_paragraphs, iter_tables
from document.docx_writer import save_document
from document.paragraph_processor import (
    replace_by_pattern,
    replace_span,
    replace_full_text_keep_style,
    get_paragraph_text,
)

logger = logging.getLogger(__name__)


def _insert_signature_image_into_cell(
    cell,
    p_idx: int,
    role: str,
    sig_cfg: Dict[str, Any],
    t_idx: int = 0,
    category: str = "",
) -> bool:
    """
    Menyisipkan gambar tanda tangan dan/atau stempel digital ke dalam sel tabel Word.
    Mengembalikan True jika setidaknya ada satu gambar yang berhasil disisipkan.
    """
    if not sig_cfg:
        return False

    is_k = (role == "KEPALA")
    en = sig_cfg.get("enabled_kepala" if is_k else "enabled_guru", False)
    img_p = sig_cfg.get("kepala_image_path" if is_k else "guru_image_path", "")
    en_s = is_k and sig_cfg.get("enabled_stempel", False)
    img_s = sig_cfg.get("stempel_image_path", "") if is_k else ""

    if not ((en and img_p and os.path.isfile(img_p)) or (en_s and img_s and os.path.isfile(img_s))):
        return False

    try:
        from core.signature_image_service import insert_signature_picture
        al = sig_cfg.get("alignment", "CENTER")
        sb = int(sig_cfg.get("spacing_before_pt", 2))
        sa = int(sig_cfg.get("spacing_after_pt", 2))
        behind = bool(sig_cfg.get("behind_text", True))
        c_w = cell.width

        if behind:
            p_target = cell.paragraphs[p_idx]
        else:
            p_target = None
            for prev_i in range(p_idx):
                if not cell.paragraphs[prev_i].text.strip():
                    p_target = cell.paragraphs[prev_i]
                    break
            if p_target is None:
                p_target = cell.paragraphs[p_idx].insert_paragraph_before()

        inserted_any = False
        if en and img_p and os.path.isfile(img_p):
            w_cm = float(sig_cfg.get("kepala_width_cm" if is_k else "guru_width_cm", 3.5))
            off_x = float(sig_cfg.get("offset_x_kepala_cm" if is_k else "offset_x_guru_cm", 0.0))
            off_y = float(sig_cfg.get("offset_y_kepala_cm" if is_k else "offset_y_guru_cm", 0.0))
            if insert_signature_picture(
                p_target, img_p, width_cm=w_cm, alignment=al,
                spacing_before_pt=sb, spacing_after_pt=sa,
                behind_text=behind, offset_x_cm=off_x, offset_y_cm=off_y,
                cell_width_emu=c_w
            ):
                inserted_any = True

        if en_s and img_s and os.path.isfile(img_s):
            w_s = float(sig_cfg.get("stempel_width_cm", 3.5))
            off_x_s = float(sig_cfg.get("offset_x_stempel_cm", -1.5))
            off_y_s = float(sig_cfg.get("offset_y_stempel_cm", 0.0))
            if insert_signature_picture(
                p_target, img_s, width_cm=w_s, alignment=al,
                spacing_before_pt=sb, spacing_after_pt=sa,
                behind_text=behind, offset_x_cm=off_x_s, offset_y_cm=off_y_s,
                cell_width_emu=c_w
            ):
                inserted_any = True

        return inserted_any
    except Exception as e:
        logger.warning("Gagal menyisipkan TTD/Stempel (%s) pada tabel #%s: %s", category or role, t_idx, e, exc_info=True)
        return False


class ReplacementEngine:
    def __init__(
        self,
        aliases_path: str = "",
        signature_settings_path: str = "",
        field_dictionary: Optional[Any] = None
    ):
        if field_dictionary is not None:
            self.field_dictionary = field_dictionary
            self.aliases = field_dictionary.to_legacy_aliases()
        else:
            try:
                from core.field_dictionary import FieldDictionary
                self.field_dictionary = FieldDictionary.load()
                self.aliases = self.field_dictionary.to_legacy_aliases()
            except Exception:
                self.field_dictionary = None
                self.aliases = load_aliases(aliases_path)

        from core.signature_image_service import load_signature_settings
        self.signature_settings = load_signature_settings(signature_settings_path)

    def reload_signature_settings(self, signature_settings_path: str = "") -> None:
        """Memuat ulang konfigurasi tanda tangan & stempel digital."""
        try:
            from core.signature_image_service import load_signature_settings
            self.signature_settings = load_signature_settings(signature_settings_path)
        except Exception as e:
            logger.warning("Gagal memuat ulang pengaturan tanda tangan: %s", e)

    def reload_dictionary(self, user_path: str = "") -> None:
        """Memuat ulang kamus field dan menyinkronkan kamus aliases pada engine."""
        try:
            from core.field_dictionary import FieldDictionary
            self.field_dictionary = FieldDictionary.load(user_path=user_path)
            self.aliases = self.field_dictionary.to_legacy_aliases()
        except Exception as e:
            logger.warning("Gagal memuat ulang kamus field: %s", e)

    # =========================================================================
    # 1. PERENCANAAN PRATINJAU INTERAKTIF (PLANNING PHASE)
    # =========================================================================
    def plan_document_changes(
        self,
        in_path: str,
        rel_path: str,
        rules: List[Dict[str, str]],
        mode: str = "GABUNGAN",
        case_sensitive: bool = True,
    ) -> List[ReplacementPlanItem]:
        """
        Memindai dokumen dan menghasilkan daftar usulan perubahan (ReplacementPlanItem)
        lengkap dengan penilaian keyakinan (HIGH, MEDIUM, LOW) tanpa menulis ke disk.
        """
        doc = load_document(in_path)
        items: List[ReplacementPlanItem] = []

        target_values: Dict[str, str] = {}
        exact_rules: List[Tuple[str, str]] = []

        for r in rules:
            lbl = r.get("label", "").strip()
            old = r.get("old", "").strip()
            new = r.get("new", "").strip()
            if old:
                exact_rules.append((old, new))
            cat = match_category(lbl, self.aliases) or lbl
            if new:
                target_values[cat] = new

        # Pemetaan elemen XML <w:p> ke indeks kanonikal iter_all_paragraphs (Bug 2 Fix)
        elem_to_all_idx = {p._element: idx for idx, p in enumerate(iter_all_paragraphs(doc.element.body, doc))}

        # A. Mode Khusus: Hanya Sisipkan Tanda Tangan
        if mode == "SIGNATURE_ONLY":
            items.extend(self._plan_signature_tables(doc, in_path, rel_path, target_values, mode="SIGNATURE_ONLY"))
            if not items:
                items.extend(self._plan_tab_signatures(doc, in_path, rel_path, target_values, elem_to_all_idx=elem_to_all_idx))
            return items

        # B. Rencana Pencocokan Persis (Body & Header/Footer)
        if mode in ("PERSIS", "GABUNGAN") and exact_rules:
            items.extend(self._plan_exact(doc, in_path, rel_path, exact_rules, case_sensitive))
            items.extend(self._plan_headers_footers(doc, in_path, rel_path, exact_rules, case_sensitive))

        if mode == "PERSIS":
            return items

        # C. Rencana Pemeriksaan Tabel (Tanda Tangan & Identitas)
        items.extend(self._plan_signature_tables(doc, in_path, rel_path, target_values, mode=mode))
        items.extend(self._plan_identity_tables(doc, in_path, rel_path, target_values))

        # D. Rencana Paragraf Dokumen (Inline Labels & Blok TTD Tabulasi)
        items.extend(self._plan_inline_paragraphs(doc, in_path, rel_path, target_values, elem_to_all_idx=elem_to_all_idx))
        items.extend(self._plan_tab_signatures(doc, in_path, rel_path, target_values, elem_to_all_idx=elem_to_all_idx))

        # E. Resolusi Tumpang Tindih & Deduplikasi Usulan
        items = self._deduplicate_and_resolve_overlaps(items)

        return items

    # -------------------------------------------------------------------------
    # SUB-MODUL PERENCANAAN SPESIFIK
    # -------------------------------------------------------------------------
    def _plan_exact(
        self,
        doc,
        in_path: str,
        rel_path: str,
        exact_rules: List[Tuple[str, str]],
        case_sensitive: bool
    ) -> List[ReplacementPlanItem]:
        items: List[ReplacementPlanItem] = []
        compiled_exact = build_exact_pattern(exact_rules, case_sensitive)
        if not compiled_exact:
            return items
        pattern, mapping, is_cs = compiled_exact
        for p_idx, p in enumerate(iter_all_paragraphs(doc.element.body, doc)):
            text = get_paragraph_text(p)
            for m in pattern.finditer(text):
                old_match = m.group(0)
                if is_pure_placeholder(old_match):
                    continue  # Anti-blind replacement: pure placeholders cannot be globally replaced without a label!
                key = old_match if is_cs else old_match.lower()
                new_val = mapping.get(key, [""])[0]
                if new_val:
                    items.append(ReplacementPlanItem(
                        doc_path=in_path,
                        rel_path=rel_path,
                        category="Pencocokan Persis",
                        old_text=old_match,
                        new_text=new_val,
                        confidence=ConfidenceLevel.HIGH,
                        location_info=f"Paragraf #{p_idx}",
                        is_approved=True,
                        target_type="EXACT",
                        target_meta={
                            "para_idx": p_idx,
                            "all_para_idx": p_idx,
                            "old_text": old_match,
                            "new_text": new_val,
                            "start": m.start(),
                            "end": m.end(),
                            "original_text": text,
                        }
                    ))
        return items

    def _plan_headers_footers(
        self,
        doc,
        in_path: str,
        rel_path: str,
        exact_rules: List[Tuple[str, str]],
        case_sensitive: bool
    ) -> List[ReplacementPlanItem]:
        items: List[ReplacementPlanItem] = []
        compiled_exact = build_exact_pattern(exact_rules, case_sensitive)
        if not compiled_exact:
            return items
        pattern, mapping, is_cs = compiled_exact
        for s_idx, sec in enumerate(doc.sections):
            hf_targets = [
                ("header", "Header Normal", sec.header),
                ("footer", "Footer Normal", sec.footer),
            ]
            if getattr(sec, "different_first_page_header_footer", False):
                hf_targets.extend([
                    ("first_page_header", "Header Halaman Pertama", sec.first_page_header),
                    ("first_page_footer", "Footer Halaman Pertama", sec.first_page_footer),
                ])
            try:
                if getattr(doc.settings, "odd_and_even_pages_header_footer", False):
                    hf_targets.extend([
                        ("even_page_header", "Header Halaman Genap", sec.even_page_header),
                        ("even_page_footer", "Footer Halaman Genap", sec.even_page_footer),
                    ])
            except Exception:
                pass

            for hf_attr, hf_name, hf in hf_targets:
                if hf and not getattr(hf, "is_linked_to_previous", False):
                    all_hf_paras = list(iter_all_paragraphs(hf._element, doc))
                    for hf_p_idx, p in enumerate(all_hf_paras):
                        text = get_paragraph_text(p)
                        for m in pattern.finditer(text):
                            old_match = m.group(0)
                            if is_pure_placeholder(old_match):
                                continue  # Anti-blind replacement: pure placeholders cannot be globally replaced without a label!
                            key = old_match if is_cs else old_match.lower()
                            new_val = mapping.get(key, [""])[0]
                            if new_val:
                                items.append(ReplacementPlanItem(
                                    doc_path=in_path,
                                    rel_path=rel_path,
                                    category="Header/Footer",
                                    old_text=old_match,
                                    new_text=new_val,
                                    confidence=ConfidenceLevel.HIGH,
                                    location_info=f"{hf_name} Bagian #{s_idx} Paragraf #{hf_p_idx}",
                                    is_approved=True,
                                    target_type="HEADER_FOOTER",
                                    target_meta={
                                        "sec_idx": s_idx,
                                        "is_header": "header" in hf_attr,
                                        "hf_attr": hf_attr,
                                        "para_idx": hf_p_idx,
                                        "old_text": old_match,
                                        "new_text": new_val,
                                        "start": m.start(),
                                        "end": m.end(),
                                        "original_text": text,
                                    }
                                ))
        return items

    def _deduplicate_and_resolve_overlaps(
        self, items: List[ReplacementPlanItem]
    ) -> List[ReplacementPlanItem]:
        """
        Mendeteksi dan menyelesaikan usulan perubahan yang tumpang tindih pada lokasi yang sama
        (misal usulan EXACT dan PARAGRAPH_SPAN pada satu paragraf yang sama).
        Prinsip: Satu area karakter hanya boleh menerima satu usulan (aturan spesifik/lengkap menang).
        """
        if not items:
            return items

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
                # Baris tanda tangan tabulasi memuat kolom kiri (Kepala) dan kanan (Guru) pada baris yang sama
                loc_key = f"{it.doc_path}#{it.location_info}#{it.category}"
            else:
                loc_key = f"{it.doc_path}#{it.location_info}"

            groups.setdefault(loc_key, []).append(it)

        resolved_items: List[ReplacementPlanItem] = []

        for loc_key, group_items in groups.items():
            if len(group_items) == 1:
                resolved_items.append(group_items[0])
                continue

            kept: List[ReplacementPlanItem] = []
            for candidate in group_items:
                c_start = candidate.target_meta.get("start")
                c_end = candidate.target_meta.get("end")
                orig_text = candidate.target_meta.get("original_text", "")
                if (c_start is None or c_end is None) and orig_text and candidate.old_text:
                    pos = orig_text.find(candidate.old_text)
                    if pos != -1:
                        c_start = pos
                        c_end = pos + len(candidate.old_text)
                        candidate.target_meta["start"] = c_start
                        candidate.target_meta["end"] = c_end

                overlapping_entries = []
                for i, existing in enumerate(kept):
                    e_start = existing.target_meta.get("start")
                    e_end = existing.target_meta.get("end")

                    if c_start is not None and c_end is not None and e_start is not None and e_end is not None:
                        overlaps = max(c_start, e_start) < min(c_end, e_end)
                    else:
                        overlaps = (candidate.old_text in existing.old_text or existing.old_text in candidate.old_text)

                    if overlaps:
                        overlapping_entries.append((i, existing))

                if not overlapping_entries:
                    kept.append(candidate)
                else:
                    # Bug 4 Fix: Periksa apakah kandidat mengalahkan SEMUA item yang beririsan
                    candidate_wins_all = True
                    for i, existing in overlapping_entries:
                        c_is_exact = (candidate.target_type == "EXACT")
                        e_is_exact = (existing.target_type == "EXACT")

                        if c_is_exact and not e_is_exact:
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

            resolved_items.extend(kept)

        return resolved_items

    def _plan_signature_tables(
        self,
        doc,
        in_path: str,
        rel_path: str,
        target_values: Dict[str, str],
        mode: str
    ) -> List[ReplacementPlanItem]:
        from core.signature_image_service import is_document_landscape, resolve_signature_settings_for_orientation
        raw_sig_cfg = self.signature_settings or {}
        is_land = is_document_landscape(doc)
        sig_cfg = resolve_signature_settings_for_orientation(raw_sig_cfg, is_land)

        items: List[ReplacementPlanItem] = []
        for t_idx, table in enumerate(iter_tables(doc)):
            if not is_signature_table(table):
                continue
            num_cols = len(table.columns)
            for c_idx in range(num_cols):
                col_paras_meta = []
                for r_idx, row in enumerate(table.rows):
                    if c_idx < len(row.cells):
                        cell = row.cells[c_idx]
                        for p_sub_idx, p in enumerate(cell.paragraphs):
                            col_paras_meta.append((p, r_idx, c_idx, p_sub_idx))

                paras = [item[0] for item in col_paras_meta]
                role = classify_zone_role(paras)
                if role == "UNKNOWN" and num_cols >= 2:
                    role = "KEPALA" if c_idx == 0 else "GURU"

                if role not in ("KEPALA", "GURU"):
                    continue

                zone_name = "Zona Kepala" if role == "KEPALA" else "Zona Guru"
                num_p = len(paras)
                is_k = (role == "KEPALA")

                # Cari Role Anchor
                anchor_idx = -1
                for i in range(min(4, num_p)):
                    txt = get_paragraph_text(paras[i]).strip()
                    if txt.startswith("(") or is_pure_placeholder(txt) or is_academic_name(txt):
                        continue
                    txt_low = txt.lower()
                    if is_k and any(k in txt_low for k in KEPALA_ROLE_KEYWORDS):
                        anchor_idx = i
                        break
                    elif not is_k and any(k in txt_low for k in GURU_ROLE_KEYWORDS):
                        anchor_idx = i
                        break

                start_scan = anchor_idx + 1 if anchor_idx != -1 else 0

                # Cari posisi NIP
                nip_idx = -1
                for i in range(start_scan, num_p):
                    t = get_paragraph_text(paras[i]).strip()
                    if RE_NIP_LINE.match(t):
                        nip_idx = i
                        break

                # Mode Khusus: Hanya Sisipkan Tanda Tangan
                if mode == "SIGNATURE_ONLY":
                    en = sig_cfg.get("enabled_kepala" if is_k else "enabled_guru", False)
                    img_p = sig_cfg.get("kepala_image_path" if is_k else "guru_image_path", "")
                    en_s = is_k and sig_cfg.get("enabled_stempel", False)
                    img_s = sig_cfg.get("stempel_image_path", "") if is_k else ""

                    has_k_or_s = (en and img_p and os.path.isfile(img_p)) or (en_s and img_s and os.path.isfile(img_s))
                    has_g = (en and img_p and os.path.isfile(img_p))
                    if not (has_k_or_s if is_k else has_g):
                        continue

                    for i in range(start_scan, num_p):
                        if i == nip_idx:
                            continue
                        p, r_i, c_i, p_s = col_paras_meta[i]
                        t = get_paragraph_text(p).strip()
                        if not t:
                            continue
                        if is_pure_placeholder(t) or is_academic_name(t) or is_paragraph_bold_or_underlined(p) or (nip_idx != -1 and i == nip_idx - 1):
                            if is_k:
                                if en and en_s:
                                    cat_name = "Tanda Tangan & Stempel Kepala"
                                    desc_new = "[Sisipkan TTD & Stempel Kepala]"
                                elif en_s:
                                    cat_name = "Stempel Resmi Kepala"
                                    desc_new = "[Sisipkan Stempel Resmi]"
                                else:
                                    cat_name = "Tanda Tangan Kepala"
                                    desc_new = "[Sisipkan Gambar Tanda Tangan]"
                            else:
                                cat_name = "Tanda Tangan Guru"
                                desc_new = "[Sisipkan Gambar Tanda Tangan]"

                            items.append(ReplacementPlanItem(
                                doc_path=in_path,
                                rel_path=rel_path,
                                category=cat_name,
                                old_text=f"{t} (Teks Tetap)",
                                new_text=desc_new,
                                confidence=ConfidenceLevel.HIGH,
                                location_info=f"Tabel Tanda Tangan: {zone_name}",
                                is_approved=True,
                                target_type="INSERT_SIGNATURE_TABLE",
                                target_meta={"table_idx": t_idx, "row_idx": r_i, "col_idx": c_i, "para_idx": p_s, "role": role}
                            ))
                            break
                    continue

                # Titimangsa (Zona Guru)
                new_titimangsa = target_values.get("Titimangsa", "").strip()
                if new_titimangsa and not is_k:
                    for i in range(min(3, num_p)):
                        p, r_i, c_i, p_s = col_paras_meta[i]
                        t = get_paragraph_text(p).strip()
                        if is_titimangsa_line(t):
                            items.append(ReplacementPlanItem(
                                doc_path=in_path,
                                rel_path=rel_path,
                                category="Titimangsa",
                                old_text=t,
                                new_text=new_titimangsa,
                                confidence=ConfidenceLevel.HIGH,
                                location_info=f"Tabel Tanda Tangan: {zone_name}",
                                is_approved=True,
                                target_type="TABLE_CELL_PARA",
                                target_meta={"table_idx": t_idx, "row_idx": r_i, "col_idx": c_i, "para_idx": p_s}
                            ))
                            break

                # Target Nama
                target_name_key = "Nama Kepala" if is_k else "Nama Guru"
                new_name = target_values.get(target_name_key, "").strip()
                if new_name:
                    for i in range(start_scan, num_p):
                        if i == nip_idx:
                            continue
                        p, r_i, c_i, p_s = col_paras_meta[i]
                        t = get_paragraph_text(p).strip()
                        if not t:
                            continue
                        if is_pure_placeholder(t) or is_academic_name(t) or is_paragraph_bold_or_underlined(p) or (nip_idx != -1 and i == nip_idx - 1):
                            _, had_parens = unwrap_parentheses(t)
                            formatted_name = format_with_parentheses(new_name, had_parens)
                            items.append(ReplacementPlanItem(
                                doc_path=in_path,
                                rel_path=rel_path,
                                category=target_name_key,
                                old_text=t,
                                new_text=formatted_name,
                                confidence=ConfidenceLevel.HIGH,
                                location_info=f"Tabel Tanda Tangan: {zone_name}",
                                is_approved=True,
                                target_type="TABLE_CELL_PARA",
                                target_meta={"table_idx": t_idx, "row_idx": r_i, "col_idx": c_i, "para_idx": p_s}
                            ))
                            break

                # Target NIP
                target_nip_key = "NIP Kepala" if is_k else "NIP Guru"
                new_nip = target_values.get(target_nip_key, "").strip()
                if new_nip and nip_idx != -1:
                    p, r_i, c_i, p_s = col_paras_meta[nip_idx]
                    t = get_paragraph_text(p).strip()
                    m = RE_NIP_LINE.match(t)
                    if m:
                        prefix = m.group(1)
                        formatted_nip = f"{prefix}. {new_nip}"
                        items.append(ReplacementPlanItem(
                            doc_path=in_path,
                            rel_path=rel_path,
                            category=target_nip_key,
                            old_text=t,
                            new_text=formatted_nip,
                            confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tabel Tanda Tangan: {zone_name}",
                            is_approved=True,
                            target_type="TABLE_CELL_PARA",
                            target_meta={"table_idx": t_idx, "row_idx": r_i, "col_idx": c_i, "para_idx": p_s}
                        ))

        return items

    def _plan_identity_tables(
        self,
        doc,
        in_path: str,
        rel_path: str,
        target_values: Dict[str, str]
    ) -> List[ReplacementPlanItem]:
        items: List[ReplacementPlanItem] = []
        for t_idx, table in enumerate(iter_tables(doc)):
            if is_signature_table(table):
                continue
            for r_idx, row in enumerate(table.rows):
                cells = row.cells
                num_c = len(cells)

                if num_c == 1:
                    cell = cells[0]
                    for p_sub_idx, p in enumerate(cell.paragraphs):
                        text = get_paragraph_text(p)
                        extracted = extract_label_and_placeholder(text)
                        if extracted:
                            label_pfx, placeholder_str, start_pos, end_pos = extracted
                            clean_label = label_pfx.rstrip(": \t")
                            matched_cat = match_category(clean_label, self.aliases) or match_category(label_pfx, self.aliases)
                            conf = ConfidenceLevel.HIGH
                            if not matched_cat:
                                f_cat, f_score, _ = find_fuzzy_category_match(clean_label, self.aliases, threshold=0.80)
                                if f_cat:
                                    matched_cat = f_cat
                                    conf = ConfidenceLevel.MEDIUM if f_score >= 0.90 else ConfidenceLevel.LOW

                            new_val = ""
                            if matched_cat and matched_cat in target_values:
                                new_val = target_values[matched_cat].strip()
                            elif matched_cat == "Tahun Penyusunan" and "Tahun Ajaran" in target_values:
                                new_val = target_values["Tahun Ajaran"].strip()
                            elif matched_cat == "Tahun Ajaran" and "Tahun Penyusunan" in target_values:
                                new_val = target_values["Tahun Penyusunan"].strip()

                            if matched_cat and new_val:
                                items.append(ReplacementPlanItem(
                                    doc_path=in_path,
                                    rel_path=rel_path,
                                    category=matched_cat,
                                    old_text=placeholder_str,
                                    new_text=new_val,
                                    confidence=conf,
                                    location_info=f"Tabel Identitas #{t_idx} Baris #{r_idx} (Inline)",
                                    is_approved=(conf != ConfidenceLevel.LOW),
                                    target_type="TABLE_CELL_SPAN",
                                    target_meta={
                                        "table_idx": t_idx,
                                        "row_idx": r_idx,
                                        "col_idx": 0,
                                        "para_idx": p_sub_idx,
                                        "start": start_pos,
                                        "end": end_pos,
                                        "original_text": text,
                                    }
                                ))
                    continue

                # Kasus num_c >= 2
                if num_c == 2:
                    target_col = 1
                elif num_c >= 3:
                    c1_clean = [p.text.strip() for p in cells[1].paragraphs if p.text.strip()]
                    if c1_clean and all(t == ":" for t in c1_clean):
                        target_col = 2
                    elif cells[1].text.strip().startswith(":"):
                        target_col = 2
                    else:
                        target_col = num_c - 1
                else:
                    continue

                if cells[0]._tc == cells[target_col]._tc:
                    continue

                p0_non_empty = [(idx, p.text.strip(), p) for idx, p in enumerate(cells[0].paragraphs) if p.text.strip()]
                pt_non_empty = [(idx, p.text.strip(), p) for idx, p in enumerate(cells[target_col].paragraphs) if p.text.strip()]

                if len(p0_non_empty) > 1 and pt_non_empty:
                    # KASUS: Tabel Multi-Paragraf (seperti A. IDENTITAS MODUL pada Modul Ajar)
                    pair_count = min(len(p0_non_empty), len(pt_non_empty))
                    for k in range(pair_count):
                        p0_idx, label_text, label_p = p0_non_empty[k]
                        pt_idx, val_text, val_p = pt_non_empty[k]

                        clean_label = label_text.rstrip(": \t")
                        if not clean_label or len(clean_label) > 40 or len(clean_label.split()) > 6:
                            continue

                        matched_cat = match_category(clean_label, self.aliases) or match_category(label_text, self.aliases)
                        conf = ConfidenceLevel.HIGH

                        if not matched_cat:
                            f_cat, f_score, _ = find_fuzzy_category_match(clean_label, self.aliases, threshold=0.80)
                            if f_cat:
                                matched_cat = f_cat
                                conf = ConfidenceLevel.MEDIUM if f_score >= 0.90 else ConfidenceLevel.LOW

                        if not matched_cat:
                            continue

                        new_val = ""
                        if matched_cat in target_values:
                            new_val = target_values[matched_cat].strip()
                        elif matched_cat == "Tahun Penyusunan" and "Tahun Ajaran" in target_values:
                            new_val = target_values["Tahun Ajaran"].strip()
                        elif matched_cat == "Tahun Ajaran" and "Tahun Penyusunan" in target_values:
                            new_val = target_values["Tahun Penyusunan"].strip()
                        elif matched_cat == "Jenjang Sekolah":
                            if "Jenjang Sekolah" in target_values:
                                new_val = target_values["Jenjang Sekolah"].strip()
                            elif "Nama Madrasah" in target_values or "Nama Sekolah" in target_values:
                                v_upper = val_text.strip().upper()
                                if v_upper == "SD":
                                    new_val = "SD/MI"
                                elif v_upper == "SMP":
                                    new_val = "SMP/MTs"
                                elif v_upper == "SMA":
                                    new_val = "SMA/MA"

                        if not new_val:
                            continue

                        if matched_cat == "Nama Madrasah":
                            formatted_new = new_val
                        elif "Tahun" in matched_cat:
                            if val_text.lower().startswith("tahun ") and not new_val.lower().startswith("tahun"):
                                formatted_new = f"Tahun {new_val}"
                            else:
                                formatted_new = new_val
                        else:
                            _, had_parens = unwrap_parentheses(val_text)
                            formatted_new = format_with_parentheses(new_val, had_parens)

                        if is_pure_placeholder(val_text) or "..." in val_text or "…" in val_text or "____" in val_text or val_text.strip() != formatted_new:
                            items.append(ReplacementPlanItem(
                                doc_path=in_path,
                                rel_path=rel_path,
                                category=matched_cat,
                                old_text=val_text,
                                new_text=formatted_new,
                                confidence=conf,
                                location_info=f"Tabel Identitas #{t_idx} Baris #{r_idx} Paragraf #{pt_idx} ({clean_label})",
                                is_approved=(conf != ConfidenceLevel.LOW),
                                target_type="TABLE_CELL_PARA",
                                target_meta={
                                    "table_idx": t_idx,
                                    "row_idx": r_idx,
                                    "col_idx": target_col,
                                    "para_idx": pt_idx,
                                }
                            ))
                    continue

                # KASUS: Tabel 1 Baris per Field biasa (Single-Paragraph per Cell)
                label_text = cells[0].text.strip()
                clean_label = label_text.rstrip(": \t")
                if not clean_label or len(clean_label) > 40 or len(clean_label.split()) > 6:
                    continue

                matched_cat = match_category(clean_label, self.aliases) or match_category(label_text, self.aliases)
                conf = ConfidenceLevel.HIGH

                if not matched_cat:
                    f_cat, f_score, _ = find_fuzzy_category_match(clean_label, self.aliases, threshold=0.80)
                    if f_cat:
                        matched_cat = f_cat
                        conf = ConfidenceLevel.MEDIUM if f_score >= 0.90 else ConfidenceLevel.LOW

                if not matched_cat:
                    continue

                new_val = ""
                if matched_cat in target_values:
                    new_val = target_values[matched_cat].strip()
                elif matched_cat == "Tahun Penyusunan" and "Tahun Ajaran" in target_values:
                    new_val = target_values["Tahun Ajaran"].strip()
                elif matched_cat == "Tahun Ajaran" and "Tahun Penyusunan" in target_values:
                    new_val = target_values["Tahun Penyusunan"].strip()
                elif matched_cat == "Jenjang Sekolah":
                    if "Jenjang Sekolah" in target_values:
                        new_val = target_values["Jenjang Sekolah"].strip()
                    elif "Nama Madrasah" in target_values or "Nama Sekolah" in target_values:
                        v_upper = cells[target_col].text.strip().upper()
                        if v_upper == "SD":
                            new_val = "SD/MI"
                        elif v_upper == "SMP":
                            new_val = "SMP/MTs"
                        elif v_upper == "SMA":
                            new_val = "SMA/MA"

                if not new_val:
                    continue

                old_val = cells[target_col].text.strip()
                if matched_cat == "Nama Madrasah":
                    formatted_new = new_val
                elif "Tahun" in matched_cat and old_val.lower().startswith("tahun ") and not new_val.lower().startswith("tahun"):
                    formatted_new = f"Tahun {new_val}"
                else:
                    _, had_parens = unwrap_parentheses(old_val)
                    formatted_new = format_with_parentheses(new_val, had_parens)

                if is_pure_placeholder(old_val) or "..." in old_val or "…" in old_val or "____" in old_val or old_val == "" or old_val != formatted_new:
                    items.append(ReplacementPlanItem(
                        doc_path=in_path,
                        rel_path=rel_path,
                        category=matched_cat,
                        old_text=old_val,
                        new_text=formatted_new,
                        confidence=conf,
                        location_info=f"Tabel Identitas #{t_idx} Baris {r_idx}",
                        is_approved=(conf != ConfidenceLevel.LOW),
                        target_type="TABLE_CELL",
                        target_meta={"table_idx": t_idx, "row_idx": r_idx, "col_idx": target_col}
                    ))
        return items

    def _plan_inline_paragraphs(
        self,
        doc,
        in_path: str,
        rel_path: str,
        target_values: Dict[str, str],
        elem_to_all_idx: Optional[Dict[Any, int]] = None
    ) -> List[ReplacementPlanItem]:
        # S5: Gunakan doc.paragraphs (paragraf root body saja, tidak di dalam sel tabel)
        # untuk mencegah duplikasi pemindaian dengan Tabel Identitas!
        items: List[ReplacementPlanItem] = []
        for p_idx, p in enumerate(doc.paragraphs):
            all_p_idx = elem_to_all_idx.get(p._element, p_idx) if elem_to_all_idx else p_idx
            text = get_paragraph_text(p)
            extracted = extract_label_and_placeholder(text)
            if extracted:
                label_pfx, placeholder_str, start_pos, end_pos = extracted
                matched_cat = match_category(label_pfx, self.aliases)
                conf = ConfidenceLevel.HIGH
                if not matched_cat:
                    f_cat, f_score, _ = find_fuzzy_category_match(label_pfx, self.aliases, threshold=0.80)
                    if f_cat:
                        matched_cat = f_cat
                        conf = ConfidenceLevel.MEDIUM if f_score >= 0.90 else ConfidenceLevel.LOW

                new_val = ""
                if matched_cat and matched_cat in target_values:
                    new_val = target_values[matched_cat].strip()
                elif matched_cat == "Tahun Penyusunan" and "Tahun Ajaran" in target_values:
                    new_val = target_values["Tahun Ajaran"].strip()
                elif matched_cat == "Tahun Ajaran" and "Tahun Penyusunan" in target_values:
                    new_val = target_values["Tahun Penyusunan"].strip()

                if matched_cat and new_val:
                    items.append(ReplacementPlanItem(
                        doc_path=in_path,
                        rel_path=rel_path,
                        category=matched_cat,
                        old_text=placeholder_str,
                        new_text=new_val,
                        confidence=conf,
                        location_info=f"Paragraf #{p_idx} (Inline)",
                        is_approved=(conf != ConfidenceLevel.LOW),
                        target_type="PARAGRAPH_SPAN",
                        target_meta={
                            "para_idx": p_idx,
                            "all_para_idx": all_p_idx,
                            "start": start_pos,
                            "end": end_pos,
                            "original_text": text,
                        }
                    ))
            else:
                # Cek jika ada nilai yang sudah terisi (mis. 'Tahun Pelajaran : 2025/2026')
                from core.placeholder_detector import extract_filled_value_span
                filled_extracted = extract_filled_value_span(text)
                if filled_extracted:
                    label_pfx, filled_str, start_pos, end_pos = filled_extracted
                    matched_cat = match_category(label_pfx, self.aliases)
                    if not matched_cat:
                        f_cat, f_score, _ = find_fuzzy_category_match(label_pfx, self.aliases, threshold=0.80)
                        if f_cat and f_score >= 0.85:
                            matched_cat = f_cat

                    new_val = ""
                    if matched_cat and matched_cat in target_values:
                        new_val = target_values[matched_cat].strip()
                    elif matched_cat == "Tahun Penyusunan" and "Tahun Ajaran" in target_values:
                        new_val = target_values["Tahun Ajaran"].strip()
                    elif matched_cat == "Tahun Ajaran" and "Tahun Penyusunan" in target_values:
                        new_val = target_values["Tahun Penyusunan"].strip()

                    if matched_cat and new_val and new_val != filled_str:
                        items.append(ReplacementPlanItem(
                                doc_path=in_path,
                                rel_path=rel_path,
                                category=matched_cat,
                                old_text=filled_str,
                                new_text=new_val,
                                confidence=ConfidenceLevel.MEDIUM,
                                location_info=f"Paragraf #{p_idx} (Inline - Terisi)",
                                is_approved=True,
                                target_type="PARAGRAPH_SPAN",
                                target_meta={
                                    "para_idx": p_idx,
                                    "all_para_idx": all_p_idx,
                                    "start": start_pos,
                                    "end": end_pos,
                                    "original_text": text,
                                    "is_existing_value": True,
                                }
                            ))
        return items

    def _plan_tab_signatures(
        self,
        doc,
        in_path: str,
        rel_path: str,
        target_values: Dict[str, str],
        elem_to_all_idx: Optional[Dict[Any, int]] = None
    ) -> List[ReplacementPlanItem]:
        items: List[ReplacementPlanItem] = []
        body_paras = doc.paragraphs
        tab_indices = [idx for idx, p in enumerate(body_paras) if "\t" in get_paragraph_text(p)]
        if not tab_indices:
            return items

        blocks: List[List[int]] = []
        cur_b: List[int] = []
        for idx in tab_indices:
            if not cur_b or idx == cur_b[-1] + 1:
                cur_b.append(idx)
            else:
                if len(cur_b) >= 3:
                    blocks.append(cur_b)
                cur_b = [idx]
        if len(cur_b) >= 3:
            blocks.append(cur_b)

        for b_idx, block in enumerate(blocks):
            block_txt = " ".join(get_paragraph_text(body_paras[i]) for i in block).lower()
            has_k = any(k in block_txt for k in KEPALA_ROLE_KEYWORDS)
            has_g = any(k in block_txt for k in GURU_ROLE_KEYWORDS)
            if not (has_k and has_g):
                continue

            for i in block:
                p = body_paras[i]
                t = get_paragraph_text(p)
                all_p_idx = elem_to_all_idx.get(p._element, i) if elem_to_all_idx else i
                parts = re.split(r"\t+", t)
                if len(parts) >= 2:
                    left = parts[0].strip()
                    right = parts[-1].strip()
                    left_pos = t.find(left) if left else 0
                    right_pos = t.rfind(right) if right else len(t)

                    new_titi = target_values.get("Titimangsa", "").strip()
                    if new_titi and is_titimangsa_line(right):
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="Titimangsa",
                            old_text=right, new_text=new_titi, confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i} (Kanan)", is_approved=True,
                            target_type="TAB_LINE",
                            target_meta={
                                "para_idx": i,
                                "all_para_idx": all_p_idx,
                                "side": "right",
                                "start": right_pos,
                                "end": right_pos + len(right),
                                "original_text": t,
                                "old_text": right,
                                "new_text": new_titi,
                                "block_idx": b_idx,
                            }
                        ))
                    new_kepala = target_values.get("Nama Kepala", "").strip()
                    if new_kepala and (is_pure_placeholder(left) or is_academic_name(left)):
                        _, had_p = unwrap_parentheses(left)
                        fmt_k = format_with_parentheses(new_kepala, had_p)
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="Nama Kepala",
                            old_text=left, new_text=fmt_k, confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i} (Kiri)", is_approved=True,
                            target_type="TAB_LINE",
                            target_meta={
                                "para_idx": i,
                                "all_para_idx": all_p_idx,
                                "side": "left",
                                "start": left_pos,
                                "end": left_pos + len(left),
                                "original_text": t,
                                "old_text": left,
                                "new_text": fmt_k,
                                "block_idx": b_idx,
                            }
                        ))
                    new_guru = target_values.get("Nama Guru", "").strip()
                    if new_guru and (is_pure_placeholder(right) or is_academic_name(right)):
                        _, had_p = unwrap_parentheses(right)
                        fmt_g = format_with_parentheses(new_guru, had_p)
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="Nama Guru",
                            old_text=right, new_text=fmt_g, confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i} (Kanan)", is_approved=True,
                            target_type="TAB_LINE",
                            target_meta={
                                "para_idx": i,
                                "all_para_idx": all_p_idx,
                                "side": "right",
                                "start": right_pos,
                                "end": right_pos + len(right),
                                "original_text": t,
                                "old_text": right,
                                "new_text": fmt_g,
                                "block_idx": b_idx,
                            }
                        ))
                    new_nip_k = target_values.get("NIP Kepala", "").strip()
                    if new_nip_k and RE_NIP_LINE.match(left):
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="NIP Kepala",
                            old_text=left, new_text=f"NIP. {new_nip_k}", confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i} (Kiri)", is_approved=True,
                            target_type="TAB_LINE",
                            target_meta={
                                "para_idx": i,
                                "all_para_idx": all_p_idx,
                                "side": "left",
                                "start": left_pos,
                                "end": left_pos + len(left),
                                "original_text": t,
                                "old_text": left,
                                "new_text": f"NIP. {new_nip_k}",
                                "block_idx": b_idx,
                            }
                        ))
                    new_nip_g = target_values.get("NIP Guru", "").strip()
                    if new_nip_g and RE_NIP_LINE.match(right):
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="NIP Guru",
                            old_text=right, new_text=f"NIP. {new_nip_g}", confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i} (Kanan)", is_approved=True,
                            target_type="TAB_LINE",
                            target_meta={
                                "para_idx": i,
                                "all_para_idx": all_p_idx,
                                "side": "right",
                                "start": right_pos,
                                "end": right_pos + len(right),
                                "original_text": t,
                                "old_text": right,
                                "new_text": f"NIP. {new_nip_g}",
                                "block_idx": b_idx,
                            }
                        ))

        return items

    # =========================================================================
    # 2. PENERAPAN PERUBAHAN YANG DISETUJUI (EXECUTION OF APPROVED ITEMS)
    # =========================================================================
    def apply_approved_changes(
        self,
        in_path: str,
        out_path: str,
        approved_items: List[ReplacementPlanItem],
        signature_settings: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Menerapkan perubahan yang disetujui (is_approved=True) ke dalam dokumen
        dan menyimpannya ke out_path. Mengembalikan jumlah titik yang diganti.
        """
        doc = load_document(in_path)
        tables = iter_tables(doc)
        body_paras = doc.paragraphs
        changes = 0

        from core.signature_image_service import is_document_landscape, resolve_signature_settings_for_orientation
        raw_sig_cfg = signature_settings or self.signature_settings or {}
        is_land = is_document_landscape(doc)
        sig_cfg = resolve_signature_settings_for_orientation(raw_sig_cfg, is_land)

        for item in approved_items:
            if not item.is_approved:
                continue

            # Validasi keamanan tipe data sebelum menimpa
            if not validate_type_safety(item.category, item.old_text, item.new_text):
                logger.warning(
                    "Penyuntingan dibatalkan oleh proteksi type-safety: category=%s, old=%s, new=%s",
                    item.category, item.old_text, item.new_text
                )
                continue

            meta = item.target_meta
            t_type = item.target_type

            if t_type == "TABLE_CELL":
                t_idx = meta.get("table_idx", 0)
                r_idx = meta.get("row_idx", 0)
                c_idx = meta.get("col_idx", 0)
                if t_idx < len(tables):
                    table = tables[t_idx]
                    if r_idx < len(table.rows) and c_idx < len(table.rows[r_idx].cells):
                        cell = table.rows[r_idx].cells[c_idx]
                        if cell.paragraphs:
                            replace_full_text_keep_style(cell.paragraphs[0], item.new_text)
                        else:
                            cell.text = item.new_text
                        changes += 1

            elif t_type == "TABLE_CELL_PARA":
                t_idx = meta.get("table_idx", 0)
                r_idx = meta.get("row_idx", 0)
                c_idx = meta.get("col_idx", 0)
                p_idx = meta.get("para_idx", 0)
                if t_idx < len(tables):
                    table = tables[t_idx]
                    if r_idx < len(table.rows) and c_idx < len(table.rows[r_idx].cells):
                        cell = table.rows[r_idx].cells[c_idx]
                        if p_idx < len(cell.paragraphs):
                            # Terapkan teks pengganti terlebih dahulu (T1: hanya hitung 1 kali per item!)
                            replace_full_text_keep_style(cell.paragraphs[p_idx], item.new_text)
                            changes += 1

                            # Jika item ini adalah Nama Kepala atau Nama Guru, dan tanda tangan digital/stempel aktif:
                            if sig_cfg and item.category in ("Nama Kepala", "Nama Guru"):
                                role = "KEPALA" if item.category == "Nama Kepala" else "GURU"
                                _insert_signature_image_into_cell(
                                    cell, p_idx, role, sig_cfg, t_idx=t_idx, category=item.category
                                )

            elif t_type == "INSERT_SIGNATURE_TABLE":
                t_idx = meta.get("table_idx", 0)
                r_idx = meta.get("row_idx", 0)
                c_idx = meta.get("col_idx", 0)
                p_idx = meta.get("para_idx", 0)
                role = meta.get("role", "KEPALA")
                if t_idx < len(tables):
                    table = tables[t_idx]
                    if r_idx < len(table.rows) and c_idx < len(table.rows[r_idx].cells):
                        cell = table.rows[r_idx].cells[c_idx]
                        if p_idx < len(cell.paragraphs):
                            if _insert_signature_image_into_cell(
                                cell, p_idx, role, sig_cfg, t_idx=t_idx, category=item.category
                            ):
                                changes += 1

            elif t_type == "PARAGRAPH_SPAN":
                p_idx = meta.get("para_idx", 0)
                s = meta.get("start", 0)
                e = meta.get("end", 0)
                if p_idx < len(body_paras):
                    p_target = body_paras[p_idx]
                    curr_text = get_paragraph_text(p_target)
                    if curr_text[s:e] == item.old_text:
                        if replace_span(p_target, s, e, item.new_text):
                            changes += 1
                    else:
                        pos = curr_text.find(item.old_text)
                        if pos != -1:
                            if replace_span(p_target, pos, pos + len(item.old_text), item.new_text):
                                changes += 1
                        else:
                            # Jika teks bergeser karena penggantian lain tetapi mengandung new_text, anggap sudah terupdate
                            if item.new_text in curr_text:
                                changes += 1
                            else:
                                logger.warning(
                                    "PARAGRAPH_SPAN dilewati karena teks target bergeser: para #%s, old=%r",
                                    p_idx, item.old_text
                                )

            elif t_type == "TABLE_CELL_SPAN":
                t_idx = meta.get("table_idx", 0)
                r_idx = meta.get("row_idx", 0)
                c_idx = meta.get("col_idx", 0)
                p_idx = meta.get("para_idx", 0)
                s = meta.get("start", 0)
                e = meta.get("end", 0)
                if t_idx < len(tables):
                    table = tables[t_idx]
                    if r_idx < len(table.rows) and c_idx < len(table.rows[r_idx].cells):
                        cell = table.rows[r_idx].cells[c_idx]
                        if p_idx < len(cell.paragraphs):
                            p_target = cell.paragraphs[p_idx]
                            curr_text = get_paragraph_text(p_target)
                            if curr_text[s:e] == item.old_text:
                                if replace_span(p_target, s, e, item.new_text):
                                    changes += 1
                            else:
                                pos = curr_text.find(item.old_text)
                                if pos != -1:
                                    if replace_span(p_target, pos, pos + len(item.old_text), item.new_text):
                                        changes += 1
                                elif item.new_text in curr_text:
                                    changes += 1

            elif t_type == "HEADER_FOOTER":
                s_idx = meta.get("sec_idx", 0)
                hf_attr = meta.get("hf_attr", "header" if meta.get("is_header", True) else "footer")
                p_idx = meta.get("para_idx", 0)
                old_t = meta.get("old_text", "")
                new_t = meta.get("new_text", "")
                if s_idx < len(doc.sections):
                    sec = doc.sections[s_idx]
                    hf = getattr(sec, hf_attr, sec.header if meta.get("is_header", True) else sec.footer)
                    all_hf_paras = list(iter_all_paragraphs(hf._element, doc))
                    if p_idx < len(all_hf_paras):
                        compiled = build_exact_pattern([(old_t, new_t)], case_sensitive=True)
                        if compiled:
                            changes += replace_by_pattern(all_hf_paras[p_idx], compiled, {})

            elif t_type == "EXACT":
                p_idx = meta.get("para_idx", 0)
                old_t = meta.get("old_text", "")
                new_t = meta.get("new_text", "")
                all_body = list(iter_all_paragraphs(doc.element.body, doc))
                if p_idx < len(all_body):
                    compiled = build_exact_pattern([(old_t, new_t)], case_sensitive=True)
                    if compiled:
                        changes += replace_by_pattern(all_body[p_idx], compiled, {})

        # K2: Proses blok tanda tangan bertabulasi HANYA untuk item yang benar-benar disetujui!
        tab_approved = [it for it in approved_items if it.is_approved and it.target_type == "TAB_LINE"]
        if tab_approved:
            paras_by_idx: Dict[int, List[ReplacementPlanItem]] = {}
            for it in tab_approved:
                m = it.target_meta or {}
                p_idx = m.get("para_idx")
                if p_idx is not None and p_idx < len(body_paras):
                    paras_by_idx.setdefault(p_idx, []).append(it)

            for p_idx, p_items in paras_by_idx.items():
                p = body_paras[p_idx]
                curr_t = get_paragraph_text(p)
                sorted_items = sorted(
                    p_items,
                    key=lambda it: (it.target_meta or {}).get("start", 0),
                    reverse=True
                )
                for it in sorted_items:
                    m = it.target_meta or {}
                    s_pos = m.get("start")
                    e_pos = m.get("end")
                    old_t = it.old_text
                    new_t = it.new_text
                    if s_pos is not None and e_pos is not None and curr_t[s_pos:e_pos] == old_t:
                        if replace_span(p, s_pos, e_pos, new_t):
                            changes += 1
                            curr_t = get_paragraph_text(p)
                    else:
                        side = m.get("side", "")
                        pos = curr_t.rfind(old_t) if side == "right" else curr_t.find(old_t)
                        if pos != -1:
                            if replace_span(p, pos, pos + len(old_t), new_t):
                                changes += 1
                                curr_t = get_paragraph_text(p)

        save_document(doc, out_path)
        return changes

    # =========================================================================
    # 3. DIRECT EXECUTION (STANDALONE METHOD)
    # =========================================================================
    def process_file(
        self,
        in_path: str,
        out_path: str,
        rules: List[Dict[str, str]],
        mode: str = "GABUNGAN",
        case_sensitive: bool = True,
        skip_low_confidence: bool = True,
        signature_settings: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Eksekusi langsung dokumen (digunakan jika pratinjau dinonaktifkan atau dalam script test)."""
        rel_name = os.path.basename(in_path)
        plan_items = self.plan_document_changes(in_path, rel_name, rules, mode, case_sensitive)

        approved = []
        for it in plan_items:
            if skip_low_confidence and it.confidence == ConfidenceLevel.LOW:
                it.is_approved = False
            else:
                it.is_approved = True
            approved.append(it)

        return self.apply_approved_changes(in_path, out_path, approved, signature_settings=signature_settings)
