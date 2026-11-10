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
from docx import Document

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
)
from core.validation_engine import (
    ReplacementPlanItem,
    ConfidenceLevel,
    validate_type_safety,
    evaluate_confidence,
)
from document.docx_reader import load_document, iter_all_paragraphs, iter_tables
from document.docx_writer import save_document
from document.paragraph_processor import (
    replace_by_pattern,
    replace_span,
    replace_full_text_keep_style,
    get_paragraph_text,
)
from document.table_processor import process_tables
from document.header_footer_processor import process_headers_footers


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

        # A. Rencana Pencocokan Persis (Exact Matching)
        if mode in ("PERSIS", "GABUNGAN") and exact_rules:
            compiled_exact = build_exact_pattern(exact_rules, case_sensitive)
            if compiled_exact:
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

        if mode == "PERSIS":
            return items

        # B. Rencana Pemeriksaan Tabel (Identitas & Tanda Tangan)
        tables = iter_tables(doc)
        for t_idx, table in enumerate(tables):
            # 1. Tabel Tanda Tangan
            if is_signature_table(table):
                num_cols = len(table.columns)
                for c_idx in range(num_cols):
                    # Kumpulkan paragraf dalam kolom ini beserta koordinatnya
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

                    if role in ("KEPALA", "GURU"):
                        zone_name = "Zona Kepala" if role == "KEPALA" else "Zona Guru"
                        num_p = len(paras)

                        # Titimangsa (Zona Guru)
                        new_titimangsa = target_values.get("Titimangsa", "").strip()
                        if new_titimangsa and role == "GURU":
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

                        # Cari Role Anchor & NIP
                        anchor_idx = -1
                        for i in range(num_p):
                            txt = get_paragraph_text(paras[i]).lower()
                            if role == "KEPALA" and ("kepala" in txt or "mengetahui" in txt):
                                anchor_idx = i
                            elif role == "GURU" and any(k in txt for k in ["guru", "penyusun", "wali kelas", "pendidik"]):
                                anchor_idx = i

                        start_scan = anchor_idx + 1 if anchor_idx != -1 else 0

                        # Cari posisi NIP
                        nip_idx = -1
                        for i in range(start_scan, num_p):
                            t = get_paragraph_text(paras[i]).strip()
                            if RE_NIP_LINE.match(t):
                                nip_idx = i
                                break

                        # Target Nama
                        target_name_key = "Nama Kepala" if role == "KEPALA" else "Nama Guru"
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
                        target_nip_key = "NIP Kepala" if role == "KEPALA" else "NIP Guru"
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
                continue

            # 2. Tabel Identitas (2 atau 3 kolom)
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

                # Jika tidak cocok persis di kamus alias, coba fuzzy similarity
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

        # C. Rencana Paragraf Inline (Label + Placeholder)
        body_paras = list(iter_all_paragraphs(doc.element.body, doc))
        for p_idx, p in enumerate(body_paras):
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

        # D. Rencana Tanda Tangan Bertabulasi (\t) pada Paragraf
        tab_indices = [idx for idx, p in enumerate(body_paras) if "\t" in get_paragraph_text(p)]
        if tab_indices:
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
                if ("mengetahui" in block_txt or "kepala" in block_txt) and any(k in block_txt for k in ["guru", "penyusun", "wali", "pendidik"]):
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
        body_paras = list(iter_all_paragraphs(doc.element.body, doc))
        changes = 0

        sig_cfg = signature_settings or self.signature_settings

        # Eksekusi per item yang disetujui
        for item in approved_items:
            if not item.is_approved:
                continue

            # Validasi keamanan tipe data sebelum menimpa
            if not validate_type_safety(item.category, item.old_text, item.new_text):
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
                                        p_img = cell.paragraphs[p_idx].insert_paragraph_before()
                                        if insert_signature_picture(p_img, img_p, w_cm, al, sb, sa):
                                            changes += 1
                                    except Exception:
                                        pass

                            replace_full_text_keep_style(cell.paragraphs[p_idx], item.new_text)
                            changes += 1

            elif t_type == "PARAGRAPH_SPAN":
                p_idx = meta.get("para_idx", 0)
                s = meta.get("start", 0)
                e = meta.get("end", 0)
                if p_idx < len(body_paras):
                    if replace_span(body_paras[p_idx], s, e, item.new_text):
                        changes += 1

            elif t_type == "EXACT":
                p_idx = meta.get("para_idx", 0)
                old_t = meta.get("old_text", "")
                new_t = meta.get("new_text", "")
                if p_idx < len(body_paras):
                    compiled = build_exact_pattern([(old_t, new_t)], case_sensitive=True)
                    if compiled:
                        changes += replace_by_pattern(body_paras[p_idx], compiled, {})

        # Proses juga blok tanda tangan bertabulasi jika ada
        target_dict = {it.category: it.new_text for it in approved_items if it.is_approved}
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
