"""
Modul pemrosesan struktur tabel dokumen Word (.docx):
- Membedakan tabel identitas vs tabel tanda tangan
- Menangani tabel 2 kolom (Label | Nilai)
- Menangani tabel 3 kolom (Label | : | Nilai)
- Mengalihkan tabel tanda tangan ke signature_analyzer
"""
from typing import Dict, List, Optional, Any
from docx.table import Table, _Cell
from core.label_recognizer import match_category
from core.placeholder_detector import is_pure_placeholder
from core.signature_analyzer import is_signature_table, process_table_signatures
from document.paragraph_processor import replace_full_text_keep_style, get_paragraph_text


def process_tables(
    tables: List[Table],
    target_values: Dict[str, str],
    aliases: Dict[str, List[str]],
    smart_mode: bool = True,
    signature_settings: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Memindai dan memproses seluruh tabel dalam dokumen.
    Mengembalikan total perubahan yang dilakukan.
    """
    total_changes = 0

    for table in tables:
        # Jika merupakan tabel tanda tangan, proses via signature_analyzer
        if is_signature_table(table):
            total_changes += process_table_signatures(table, target_values, signature_settings)
            continue

        # Jika bukan tabel tanda tangan, periksa apakah tabel identitas (2 atau 3 kolom)
        for row in table.rows:
            cells = row.cells
            num_cols = len(cells)

            label_text = ""
            target_cell: Optional[_Cell] = None

            if num_cols == 2:
                label_text = cells[0].text.strip()
                target_cell = cells[1]
            elif num_cols >= 3 and cells[1].text.strip() == ":":
                label_text = cells[0].text.strip()
                target_cell = cells[2]
            else:
                continue

            if not label_text or not target_cell:
                continue

            matched_cat = match_category(label_text, aliases)
            if matched_cat and matched_cat in target_values:
                new_val = target_values[matched_cat].strip()
                if not new_val:
                    continue

                cell_text = target_cell.text.strip()

                # Dalam smart mode: jika sel kosong, berisi placeholder, atau teks lama berbeda
                should_replace = False
                if is_pure_placeholder(cell_text) or cell_text == "":
                    should_replace = True
                elif smart_mode and cell_text != new_val:
                    should_replace = True

                if should_replace:
                    if target_cell.paragraphs:
                        replace_full_text_keep_style(target_cell.paragraphs[0], new_val)
                    else:
                        target_cell.text = new_val
                    total_changes += 1

    return total_changes
