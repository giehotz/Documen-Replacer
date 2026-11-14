"""
Implementasi BaseDocumentDomain untuk Berita Acara dan MOU (BeritaAcaraDomain).
Menerapkan isolasi zona pihak (PIHAK KESATU vs PIHAK KEDUA) dan konversi tanggal terbilang otomatis.
"""
from typing import Dict, Any, List, Optional
import os
import re
from docx import Document

from domains.base_domain import BaseDocumentDomain, DetectResult
from domains.profile_loader import ProfileLoader
from domains.profile_driven_domain import ProfileDrivenDomain
from domains._shared.conflict_resolver import resolve_replacement_overlaps
from domains.berita_acara.pihak_analyzer import analyze_pihak_zones
from domains.berita_acara.tanggal_terbilang_helper import (
    format_date_to_words,
    parse_date_string,
    parse_terbilang_sentence,
    verify_terbilang_sync,
)
from core.replacement_engine import ReplacementPlanItem
from document.paragraph_processor import get_paragraph_text


class BeritaAcaraDomain(BaseDocumentDomain):
    """
    Modul domain untuk pemrosesan Berita Acara, MOU, dan Perjanjian Kerjasama.
    """
    domain_id = "berita_acara"
    display_name = "Berita Acara / MOU"

    def __init__(self, profile_path: Optional[str] = None):
        if not profile_path:
            profile_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config", "profiles", "berita_acara.profile.json"
            )
        self.profile_path = profile_path
        self.profile_data = ProfileLoader.load_profile(profile_path)
        self._driven_domain = ProfileDrivenDomain(self.profile_data)
        self.field_dict = self._driven_domain.field_dict

    def detect_score(self, in_path: str) -> DetectResult:
        """Menghitung skor deteksi kecocokan dokumen sebagai Berita Acara."""
        return self._driven_domain.detect_score(in_path)

    def predict_fields(self, in_path: str) -> Dict[str, Any]:
        """Ekstraksi nilai field profil dari naskah Berita Acara."""
        if not os.path.exists(in_path):
            return {}

        results = self._driven_domain.predict_fields(in_path)

        try:
            doc = Document(in_path)

            # 1. Pindai nomor BA dan kalimat tanggal pembuka
            for idx, p in enumerate(doc.paragraphs[:10]):
                txt = get_paragraph_text(p).strip()
                if not txt:
                    continue

                m_no = re.search(r"^(?:NOMOR|NO)\s*[:\t]\s*(.+)$", txt, re.IGNORECASE)
                if m_no and "nomor_ba" not in results:
                    val = m_no.group(1).strip()
                    results["Nomor Berita Acara"] = val
                    results["nomor_ba"] = val

                if "pada hari ini" in txt.lower():
                    parsed_dt = parse_terbilang_sentence(txt)
                    if parsed_dt:
                        d_str = parsed_dt.strftime("%d-%m-%Y")
                        results["Tanggal Berita Acara"] = d_str
                        results["tanggal_ba"] = d_str

            # 2. Pindai para pihak dengan isolasi zona
            pz = analyze_pihak_zones(doc)
            p1 = pz.get("pihak_kesatu", {})
            p2 = pz.get("pihak_kedua", {})

            if "nama" in p1:
                results["Nama Pihak Kesatu"] = p1["nama"]["value"]
                results["nama_pihak_kesatu"] = p1["nama"]["value"]
            if "nip" in p1:
                results["NIP Pihak Kesatu"] = p1["nip"]["value"]
                results["nip_pihak_kesatu"] = p1["nip"]["value"]
            if "jabatan" in p1:
                results["Jabatan Pihak Kesatu"] = p1["jabatan"]["value"]
                results["jabatan_pihak_kesatu"] = p1["jabatan"]["value"]

            if "nama" in p2:
                results["Nama Pihak Kedua"] = p2["nama"]["value"]
                results["nama_pihak_kedua"] = p2["nama"]["value"]
            if "nip" in p2:
                results["NIP Pihak Kedua"] = p2["nip"]["value"]
                results["nip_pihak_kedua"] = p2["nip"]["value"]
            if "jabatan" in p2:
                results["Jabatan Pihak Kedua"] = p2["jabatan"]["value"]
                results["jabatan_pihak_kedua"] = p2["jabatan"]["value"]

        except Exception:
            pass

        return results

    def plan_document_changes(
        self,
        in_path: str,
        rel_path: str,
        rules: List[Dict[str, str]],
        mode: str = "GABUNGAN",
        case_sensitive: bool = True,
        **ctx
    ) -> List[ReplacementPlanItem]:
        """Merencanakan perubahan Berita Acara dengan jaminan isolasi pihak dan tanggal terbilang."""
        if not os.path.exists(in_path):
            return []

        doc = Document(in_path)
        items: List[ReplacementPlanItem] = []

        # Pindai zona para pihak
        pz = analyze_pihak_zones(doc)
        p1 = pz.get("pihak_kesatu", {})
        p2 = pz.get("pihak_kedua", {})

        # Pindai kalimat pembuka untuk tanggal terbilang
        tgl_rule = None
        for r in rules:
            lbl = r.get("label", "").lower()
            if any(k in lbl for k in ["tanggal", "tgl", "hari"]):
                tgl_rule = r
                break

        if tgl_rule and tgl_rule.get("new"):
            parsed_new_dt = parse_date_string(tgl_rule["new"])
            if parsed_new_dt:
                new_sentence_info = format_date_to_words(parsed_new_dt, capitalize=True)
                # Cari paragraf kalimat pembuka
                for idx, p in enumerate(doc.paragraphs[:10]):
                    raw_p = get_paragraph_text(p)
                    if "pada hari ini" in raw_p.lower():
                        # Ganti kalimat pembuka dengan kalimat terbilang yang selaras
                        item = ReplacementPlanItem(
                            doc_path=in_path,
                            rel_path=rel_path,
                            category="Tanggal Berita Acara (Terbilang)",
                            old_text=raw_p.strip(),
                            new_text=new_sentence_info["kalimat_lengkap"],
                            confidence="HIGH",
                            location_info=f"Paragraf #{idx + 1}",
                            is_approved=True,
                            target_type="PARAGRAPH_SPAN",
                            target_meta={
                                "domain_id": self.domain_id,
                                "para_idx": idx,
                                "start": 0,
                                "end": len(raw_p),
                                "original_text": raw_p,
                                "date_iso": parsed_new_dt.isoformat(),
                            },
                        )
                        items.append(item)
                        break

        # Aturan untuk Pihak Kesatu & Pihak Kedua
        for r in rules:
            lbl = r.get("label", "").strip()
            old_v = r.get("old", "").strip()
            new_v = r.get("new", "").strip()
            if not new_v:
                continue

            low_lbl = lbl.lower()
            target_party = None
            attr_key = None

            if "kesatu" in low_lbl or "pertama" in low_lbl:
                target_party = p1
                party_label = "Pihak Kesatu"
            elif "kedua" in low_lbl:
                target_party = p2
                party_label = "Pihak Kedua"

            if "nama" in low_lbl:
                attr_key = "nama"
            elif "nip" in low_lbl:
                attr_key = "nip"
            elif "jabatan" in low_lbl:
                attr_key = "jabatan"

            if target_party and attr_key and attr_key in target_party:
                f_info = target_party[attr_key]
                span = f_info.get("span", (0, len(f_info["value"])))
                meta = dict(f_info.get("meta", {}))
                meta.update({
                    "domain_id": self.domain_id,
                    "start": span[0],
                    "end": span[1],
                    "party_attr": attr_key,
                })
                loc = f_info.get("location", "body")
                if loc == "table":
                    t_type = "TABLE_CELL_SPAN"
                    loc_desc = f"Tabel #{meta.get('table_idx', 0) + 1} Sel ({meta.get('row_idx', 0)},{meta.get('col_idx', 0)}) [{party_label}]"
                else:
                    t_type = "PARAGRAPH_SPAN"
                    loc_desc = f"Paragraf #{meta.get('para_idx', 0) + 1} [{party_label}]"

                item = ReplacementPlanItem(
                    doc_path=in_path,
                    rel_path=rel_path,
                    category=f"{party_label} ({attr_key.upper()})",
                    old_text=f_info["value"],
                    new_text=new_v,
                    confidence="HIGH",
                    location_info=loc_desc,
                    is_approved=True,
                    target_type=t_type,
                    target_meta=meta,
                )
                items.append(item)

        # 3. Jalankan juga kamus dasar untuk nomor BA atau isian umum lainnya
        base_items = self._driven_domain.plan_document_changes(
            in_path=in_path,
            rel_path=rel_path,
            rules=rules,
            mode=mode,
            case_sensitive=case_sensitive,
            **ctx
        )
        for it in base_items:
            if it.target_meta is not None:
                it.target_meta.setdefault("domain_id", self.domain_id)

        all_items = items + base_items
        resolved_items = resolve_replacement_overlaps(all_items)
        return resolved_items

    def apply_approved_changes(
        self,
        in_path: str,
        out_path: str,
        approved_items: List[ReplacementPlanItem],
        signature_settings: Optional[Dict[str, Any]] = None,
        **ctx
    ) -> int:
        """Menerapkan seluruh perubahan yang disetujui pada Berita Acara."""
        return self._driven_domain.apply_approved_changes(
            in_path=in_path,
            out_path=out_path,
            approved_items=approved_items,
            signature_settings=signature_settings,
            **ctx
        )

    def extra_checks(self, item: ReplacementPlanItem, actual_text: str) -> List[Dict[str, str]]:
        """Pemeriksaan tambahan khusus Berita Acara: sinkronisasi tanggal terbilang."""
        issues: List[Dict[str, str]] = []
        meta = item.target_meta or {}

        # Periksa sinkronisasi tanggal terbilang
        if "date_iso" in meta:
            try:
                import datetime
                dt = datetime.date.fromisoformat(meta["date_iso"])
                if not verify_terbilang_sync(actual_text, dt):
                    issues.append({
                        "code": "TANGGAL_TERBILANG_TIDAK_SINKRON",
                        "message": f"Kalimat terbilang tanggal ({item.new_text}) tidak selaras dengan teks hasil."
                    })
            except Exception:
                pass

        return issues

    def reload_dictionary(self) -> None:
        """Memuat ulang profil Berita Acara."""
        self.profile_data = ProfileLoader.load_profile(self.profile_path)
        self._driven_domain = ProfileDrivenDomain(self.profile_data)
        self.field_dict = self._driven_domain.field_dict
