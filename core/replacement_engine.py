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


class ReplacementEngine:
    def __init__(self, aliases_path: str = "", signature_settings_path: str = ""):
        self.aliases = load_aliases(aliases_path)
        from core.signature_image_service import load_signature_settings
        self.signature_settings = load_signature_settings(signature_settings_path)

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

        # A. Mode Khusus: Hanya Sisipkan Tanda Tangan
        if mode == "SIGNATURE_ONLY":
            items.extend(self._plan_signature_tables(doc, in_path, rel_path, target_values, mode="SIGNATURE_ONLY"))
            if not items:
                items.extend(self._plan_tab_signatures(doc, in_path, rel_path, target_values))
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
        items.extend(self._plan_inline_paragraphs(doc, in_path, rel_path, target_values))
        items.extend(self._plan_tab_signatures(doc, in_path, rel_path, target_values))

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
                        target_meta={"para_idx": p_idx, "old_text": old_match, "new_text": new_val}
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
            for hf_name, hf in [("Header", sec.header), ("Footer", sec.footer)]:
                if hf and not hf.is_linked_to_previous:
                    for hf_p_idx, p in enumerate(hf.paragraphs):
                        text = get_paragraph_text(p)
                        for m in pattern.finditer(text):
                            old_match = m.group(0)
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
                                    location_info=f"{hf_name} Bagian #{s_idx}",
                                    is_approved=True,
                                    target_type="HEADER_FOOTER",
                                    target_meta={
                                        "sec_idx": s_idx,
                                        "is_header": (hf_name == "Header"),
                                        "para_idx": hf_p_idx,
                                        "old_text": old_match,
                                        "new_text": new_val,
                                    }
                                ))
        return items

    def _plan_signature_tables(
        self,
        doc,
        in_path: str,
        rel_path: str,
        target_values: Dict[str, str],
        mode: str
    ) -> List[ReplacementPlanItem]:
        from core.signature_image_service import load_signature_settings
        sig_cfg = load_signature_settings()
        self.signature_settings = sig_cfg

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
                for i in range(num_p):
                    txt = get_paragraph_text(paras[i]).lower()
                    if is_k and any(k in txt for k in KEPALA_ROLE_KEYWORDS):
                        anchor_idx = i
                    elif not is_k and any(k in txt for k in GURU_ROLE_KEYWORDS):
                        anchor_idx = i

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
                    if not (en and img_p and os.path.isfile(img_p)):
                        continue

                    for i in range(start_scan, num_p):
                        if i == nip_idx:
                            continue
                        p, r_i, c_i, p_s = col_paras_meta[i]
                        t = get_paragraph_text(p).strip()
                        if not t:
                            continue
                        if is_pure_placeholder(t) or is_academic_name(t) or is_paragraph_bold_or_underlined(p) or (nip_idx != -1 and i == nip_idx - 1):
                            cat_name = "Tanda Tangan Kepala" if is_k else "Tanda Tangan Guru"
                            items.append(ReplacementPlanItem(
                                doc_path=in_path,
                                rel_path=rel_path,
                                category=cat_name,
                                old_text=f"{t} (Teks Tetap)",
                                new_text="[Sisipkan Gambar Tanda Tangan]",
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
                label_text = ""
                target_col = -1

                if num_c == 2:
                    label_text = cells[0].text.strip()
                    target_col = 1
                elif num_c >= 3 and cells[1].text.strip() == ":":
                    label_text = cells[0].text.strip()
                    target_col = 2
                else:
                    continue

                if not label_text or target_col == -1:
                    continue

                matched_cat = match_category(label_text, self.aliases)
                conf = ConfidenceLevel.HIGH

                if not matched_cat:
                    f_cat, f_score, _ = find_fuzzy_category_match(label_text, self.aliases, threshold=0.80)
                    if f_cat:
                        matched_cat = f_cat
                        conf = ConfidenceLevel.MEDIUM if f_score >= 0.90 else ConfidenceLevel.LOW

                if matched_cat and matched_cat in target_values:
                    new_val = target_values[matched_cat].strip()
                    if not new_val:
                        continue
                    old_val = cells[target_col].text.strip()
                    if is_pure_placeholder(old_val) or old_val == "" or old_val != new_val:
                        items.append(ReplacementPlanItem(
                            doc_path=in_path,
                            rel_path=rel_path,
                            category=matched_cat,
                            old_text=old_val,
                            new_text=new_val,
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
        target_values: Dict[str, str]
    ) -> List[ReplacementPlanItem]:
        # S5: Gunakan doc.paragraphs (paragraf root body saja, tidak di dalam sel tabel)
        # untuk mencegah duplikasi pemindaian dengan Tabel Identitas!
        items: List[ReplacementPlanItem] = []
        for p_idx, p in enumerate(doc.paragraphs):
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

                if matched_cat and matched_cat in target_values:
                    new_val = target_values[matched_cat].strip()
                    if new_val:
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
                            target_meta={"para_idx": p_idx, "start": start_pos, "end": end_pos}
                        ))
        return items

    def _plan_tab_signatures(
        self,
        doc,
        in_path: str,
        rel_path: str,
        target_values: Dict[str, str]
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

        for block in blocks:
            block_txt = " ".join(get_paragraph_text(body_paras[i]) for i in block).lower()
            has_k = any(k in block_txt for k in KEPALA_ROLE_KEYWORDS)
            has_g = any(k in block_txt for k in GURU_ROLE_KEYWORDS)
            if not (has_k and has_g):
                continue

            for i in block:
                p = body_paras[i]
                t = get_paragraph_text(p)
                parts = re.split(r"\t+", t)
                if len(parts) >= 2:
                    left = parts[0].strip()
                    right = parts[-1].strip()

                    new_titi = target_values.get("Titimangsa", "").strip()
                    if new_titi and is_titimangsa_line(right):
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="Titimangsa",
                            old_text=right, new_text=new_titi, confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i}", is_approved=True,
                            target_type="TAB_LINE"
                        ))
                    new_kepala = target_values.get("Nama Kepala", "").strip()
                    if new_kepala and (is_pure_placeholder(left) or is_academic_name(left)):
                        _, had_p = unwrap_parentheses(left)
                        fmt_k = format_with_parentheses(new_kepala, had_p)
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="Nama Kepala",
                            old_text=left, new_text=fmt_k, confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i}", is_approved=True,
                            target_type="TAB_LINE"
                        ))
                    new_guru = target_values.get("Nama Guru", "").strip()
                    if new_guru and (is_pure_placeholder(right) or is_academic_name(right)):
                        _, had_p = unwrap_parentheses(right)
                        fmt_g = format_with_parentheses(new_guru, had_p)
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="Nama Guru",
                            old_text=right, new_text=fmt_g, confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i}", is_approved=True,
                            target_type="TAB_LINE"
                        ))
                    new_nip_k = target_values.get("NIP Kepala", "").strip()
                    if new_nip_k and RE_NIP_LINE.match(left):
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="NIP Kepala",
                            old_text=left, new_text=f"NIP. {new_nip_k}", confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i}", is_approved=True,
                            target_type="TAB_LINE"
                        ))
                    new_nip_g = target_values.get("NIP Guru", "").strip()
                    if new_nip_g and RE_NIP_LINE.match(right):
                        items.append(ReplacementPlanItem(
                            doc_path=in_path, rel_path=rel_path, category="NIP Guru",
                            old_text=right, new_text=f"NIP. {new_nip_g}", confidence=ConfidenceLevel.HIGH,
                            location_info=f"Tanda Tangan Tabulasi Baris #{i}", is_approved=True,
                            target_type="TAB_LINE"
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

        from core.signature_image_service import load_signature_settings
        sig_cfg = signature_settings or load_signature_settings()

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
                            # Jika item ini adalah Nama Kepala atau Nama Guru, dan tanda tangan digital aktif:
                            if sig_cfg and item.category in ("Nama Kepala", "Nama Guru"):
                                is_k = (item.category == "Nama Kepala")
                                en = sig_cfg.get("enabled_kepala" if is_k else "enabled_guru", False)
                                img_p = sig_cfg.get("kepala_image_path" if is_k else "guru_image_path", "")
                                if en and img_p and os.path.isfile(img_p):
                                    try:
                                        from core.signature_image_service import insert_signature_picture
                                        w_cm = float(sig_cfg.get("kepala_width_cm" if is_k else "guru_width_cm", 3.5))
                                        al = sig_cfg.get("alignment", "CENTER")
                                        sb = int(sig_cfg.get("spacing_before_pt", 2))
                                        sa = int(sig_cfg.get("spacing_after_pt", 2))
                                        behind = bool(sig_cfg.get("behind_text", True))
                                        off_x = float(sig_cfg.get("offset_x_kepala_cm" if is_k else "offset_x_guru_cm", 0.0))
                                        off_y = float(sig_cfg.get("offset_y_kepala_cm" if is_k else "offset_y_guru_cm", 0.0))
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

                                        insert_signature_picture(
                                            p_target, img_p, width_cm=w_cm, alignment=al,
                                            spacing_before_pt=sb, spacing_after_pt=sa,
                                            behind_text=behind, offset_x_cm=off_x, offset_y_cm=off_y,
                                            cell_width_emu=c_w
                                        )
                                    except Exception as e:
                                        logger.warning("Gagal menyisipkan TTD (%s) pada tabel #%s: %s", item.category, t_idx, e, exc_info=True)

                            # Terapkan teks pengganti (T1: hanya hitung 1 kali per item!)
                            replace_full_text_keep_style(cell.paragraphs[p_idx], item.new_text)
                            changes += 1

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
                            is_k = (role == "KEPALA")
                            en = sig_cfg.get("enabled_kepala" if is_k else "enabled_guru", False)
                            img_p = sig_cfg.get("kepala_image_path" if is_k else "guru_image_path", "")
                            if en and img_p and os.path.isfile(img_p):
                                try:
                                    from core.signature_image_service import insert_signature_picture
                                    w_cm = float(sig_cfg.get("kepala_width_cm" if is_k else "guru_width_cm", 3.5))
                                    al = sig_cfg.get("alignment", "CENTER")
                                    sb = int(sig_cfg.get("spacing_before_pt", 2))
                                    sa = int(sig_cfg.get("spacing_after_pt", 2))
                                    behind = bool(sig_cfg.get("behind_text", True))
                                    off_x = float(sig_cfg.get("offset_x_kepala_cm" if is_k else "offset_x_guru_cm", 0.0))
                                    off_y = float(sig_cfg.get("offset_y_kepala_cm" if is_k else "offset_y_guru_cm", 0.0))
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

                                    if insert_signature_picture(
                                        p_target, img_p, width_cm=w_cm, alignment=al,
                                        spacing_before_pt=sb, spacing_after_pt=sa,
                                        behind_text=behind, offset_x_cm=off_x, offset_y_cm=off_y,
                                        cell_width_emu=c_w
                                    ):
                                        changes += 1
                                except Exception as e:
                                    logger.warning("Gagal menyisipkan TTD (%s) pada tabel #%s: %s", item.category, t_idx, e, exc_info=True)

            elif t_type == "PARAGRAPH_SPAN":
                p_idx = meta.get("para_idx", 0)
                s = meta.get("start", 0)
                e = meta.get("end", 0)
                if p_idx < len(body_paras):
                    if replace_span(body_paras[p_idx], s, e, item.new_text):
                        changes += 1

            elif t_type == "HEADER_FOOTER":
                s_idx = meta.get("sec_idx", 0)
                is_hdr = meta.get("is_header", True)
                p_idx = meta.get("para_idx", 0)
                old_t = meta.get("old_text", "")
                new_t = meta.get("new_text", "")
                if s_idx < len(doc.sections):
                    hf = doc.sections[s_idx].header if is_hdr else doc.sections[s_idx].footer
                    if p_idx < len(hf.paragraphs):
                        compiled = build_exact_pattern([(old_t, new_t)], case_sensitive=True)
                        if compiled:
                            changes += replace_by_pattern(hf.paragraphs[p_idx], compiled, {})

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
            target_dict = {it.category: it.new_text for it in tab_approved}
            changes += process_tab_separated_signature_block(body_paras, target_dict)

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
