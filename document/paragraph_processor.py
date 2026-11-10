"""
Pemroses teks pada objek Paragraph python-docx.
Mempertahankan format (bold, italic, warna, font) walau teks terpotong di beberapa run.
"""
from typing import List, Tuple, Dict, Any
import re


def get_paragraph_text(paragraph) -> str:
    """Mengembalikan teks utuh dari semua runs dalam paragraf."""
    return "".join(r.text for r in paragraph.runs)


def replace_span(paragraph, start: int, end: int, replacement: str) -> bool:
    """
    Mengganti potongan karakter pada indeks [start:end] dalam paragraph
    dengan replacement, tetap menjaga formatting run Word.
    """
    runs = paragraph.runs
    if not runs or start >= end:
        return False

    texts = [r.text for r in runs]
    full = "".join(texts)
    if start < 0 or end > len(full):
        return False

    bounds: List[Tuple[int, int]] = []
    pos = 0
    for t in texts:
        bounds.append((pos, pos + len(t)))
        pos += len(t)

    new_texts = texts[:]
    first = True
    changed = set()

    for i, (rs, re_) in enumerate(bounds):
        if rs == re_ or re_ <= start or rs >= end:
            continue
        a = max(start, rs) - rs
        b = min(end, re_) - rs
        t = new_texts[i]
        if first:
            new_texts[i] = t[:a] + replacement + t[b:]
            first = False
        else:
            new_texts[i] = t[:a] + t[b:]
        changed.add(i)

    for i in changed:
        runs[i].text = new_texts[i]
    return True


def replace_full_text_keep_style(paragraph, new_text: str) -> bool:
    """
    Mengganti seluruh teks paragraf dengan new_text,
    tetap mempertahankan style (bold, underline, dsb) dari run pertama yang ada.
    """
    runs = paragraph.runs
    if not runs:
        paragraph.text = new_text
        return True

    # Temukan run pertama yang memiliki format atau teks
    runs[0].text = new_text
    for r in runs[1:]:
        r.text = ""
    return True


def replace_by_pattern(paragraph, compiled_pattern_info: Tuple[Any, Dict[str, List[str]], bool], counters: Dict[str, int]) -> int:
    """
    Mengganti teks berdasarkan pola compiled (Exact Matcher).
    compiled_pattern_info = (regex_pattern, mapping_dict, case_sensitive)
    """
    pattern, mapping, case_sensitive = compiled_pattern_info
    runs = paragraph.runs
    if not runs:
        return 0

    texts = [r.text for r in runs]
    full = "".join(texts)
    matches = list(pattern.finditer(full))
    if not matches:
        return 0

    plan = []
    for m in matches:
        key = m.group(0) if case_sensitive else m.group(0).lower()
        n = counters.get(key, 0)
        counters[key] = n + 1
        options = mapping.get(key, [])
        if n < len(options):
            plan.append((m, options[n]))

    if not plan:
        return 0

    bounds = []
    pos = 0
    for t in texts:
        bounds.append((pos, pos + len(t)))
        pos += len(t)

    new_texts = texts[:]
    changed = set()

    for m, repl in reversed(plan):
        s, e = m.span()
        first = True
        for i, (rs, re_) in enumerate(bounds):
            if rs == re_ or re_ <= s or rs >= e:
                continue
            a = max(s, rs) - rs
            b = min(e, re_) - rs
            t = new_texts[i]
            if first:
                new_texts[i] = t[:a] + repl + t[b:]
                first = False
            else:
                new_texts[i] = t[:a] + t[b:]
            changed.add(i)

    for i in changed:
        runs[i].text = new_texts[i]
    return len(plan)
