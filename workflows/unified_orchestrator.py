"""
Unified Orchestrator: Facade orkestrasi pemrosesan dokumen multi-domain.
Memiliki antarmuka yang identik dengan ReplacementEngine sehingga siap menggantikannya
secara transparan tanpa mengubah pemanggil di GUI (gui/app.py).
"""
import os
import tempfile
from typing import List, Dict, Any, Optional

from domains.base_domain import BaseDocumentDomain
from domains.domain_registry import DomainRegistry
from workflows.auto_classifier import AutoClassifier
from core.validation_engine import ReplacementPlanItem
from core.field_dictionary import FieldDictionary


class UnifiedOrchestrator:
    """
    Facade orkestrasi pemrosesan dokumen.
    Meneruskan permintaan perencanaan dan penerapan perubahan ke domain yang tepat.
    """
    def __init__(
        self,
        registry: Optional[DomainRegistry] = None,
        default_domain_id: str = "rpp_modul",
        field_dictionary: Optional[FieldDictionary] = None,
        signature_settings: Optional[Dict[str, Any]] = None,
    ):
        self.registry = registry or DomainRegistry.get_instance()
        self.default_domain_id = default_domain_id
        self.classifier = AutoClassifier(self.registry)
        self.signature_settings = signature_settings or {}

        # Pastikan domain default (RPP) memiliki field_dictionary yang sesuai
        rpp_domain = self.registry.get("rpp_modul")
        if rpp_domain and hasattr(rpp_domain, "engine"):
            if field_dictionary:
                rpp_domain.engine.dict = field_dictionary
            if signature_settings:
                rpp_domain.engine.signature_settings = signature_settings

    @property
    def dict(self) -> FieldDictionary:
        """Mengembalikan FieldDictionary aktif dari domain default (RPP) untuk kompatibilitas."""
        rpp = self.registry.get("rpp_modul")
        if rpp and hasattr(rpp, "engine"):
            return rpp.engine.dict
        return FieldDictionary.load()

    def get_domain(self, in_path: Optional[str] = None, domain_id: Optional[str] = None) -> BaseDocumentDomain:
        """
        Menentukan domain yang bertugas:
        1. Jika domain_id diberikan secara eksplisit, gunakan domain tersebut.
        2. Jika in_path diberikan dan domain_id adalah None/'auto', lakukan klasifikasi otomatis.
        3. Jika tidak ditemukan atau ambigu, jatuh ke domain default.
        """
        if domain_id and domain_id != "auto":
            dom = self.registry.get(domain_id)
            if dom:
                return dom

        if in_path and os.path.isfile(in_path):
            res = self.classifier.classify_document(in_path)
            if res.selected_domain_id:
                dom = self.registry.get(res.selected_domain_id)
                if dom:
                    return dom

        # Fallback ke default domain (RPP)
        dom = self.registry.get(self.default_domain_id)
        if not dom:
            # Jika belum terdaftar, ambil domain pertama yang ada
            all_doms = self.registry.list_domains()
            if all_doms:
                return all_doms[0]
            raise RuntimeError("Tidak ada domain dokumen yang terdaftar dalam DomainRegistry.")
        return dom

    def plan_document_changes(
        self,
        in_path: str,
        rel_path: str,
        rules: List[Dict[str, str]],
        mode: str = "GABUNGAN",
        case_sensitive: bool = True,
        domain_id: Optional[str] = None,
        **ctx
    ) -> List[ReplacementPlanItem]:
        """
        Merencanakan perubahan dokumen dengan meneruskannya ke domain yang sesuai.
        Menjamin seluruh item membawa penanda domain_id.
        """
        target_domain = self.get_domain(in_path=in_path, domain_id=domain_id)
        items = target_domain.plan_document_changes(
            in_path=in_path,
            rel_path=rel_path,
            rules=rules,
            mode=mode,
            case_sensitive=case_sensitive,
            **ctx
        )
        for it in items:
            if it.target_meta is not None:
                it.target_meta.setdefault("domain_id", target_domain.domain_id)
        return items

    def apply_approved_changes(
        self,
        in_path: str,
        out_path: str,
        approved_items: List[ReplacementPlanItem],
        signature_settings: Optional[Dict[str, Any]] = None,
        **ctx
    ) -> int:
        """
        Menerapkan perubahan dokumen yang disetujui.
        Mengelompokkan item berdasarkan domain_id dan mendelegasikannya secara berurutan.
        """
        if not approved_items:
            # Tidak ada item disetujui, salin berkas dokumen apa adanya
            from document.docx_reader import load_document
            from document.docx_writer import save_document
            doc = load_document(in_path)
            save_document(doc, out_path)
            return 0

        # Kelompokkan item berdasarkan domain_id
        items_by_domain: Dict[str, List[ReplacementPlanItem]] = {}
        for it in approved_items:
            if not it.is_approved:
                continue
            meta = it.target_meta or {}
            dom_id = meta.get("domain_id", self.default_domain_id)
            items_by_domain.setdefault(dom_id, []).append(it)

        if not items_by_domain:
            from document.docx_reader import load_document
            from document.docx_writer import save_document
            doc = load_document(in_path)
            save_document(doc, out_path)
            return 0

        sig_cfg = signature_settings or self.signature_settings
        total_changes = 0

        # Jika hanya ada satu domain (kasus 99% umum)
        if len(items_by_domain) == 1:
            dom_id, dom_items = next(iter(items_by_domain.items()))
            domain = self.registry.get(dom_id) or self.get_domain(domain_id=self.default_domain_id)
            return domain.apply_approved_changes(
                in_path=in_path,
                out_path=out_path,
                approved_items=dom_items,
                signature_settings=sig_cfg,
                **ctx
            )

        # Jika ada multi-domain dalam satu dokumen: jalankan secara berantai aman
        current_in = in_path
        tmp_files: List[str] = []

        try:
            domain_entries = list(items_by_domain.items())
            for idx, (dom_id, dom_items) in enumerate(domain_entries):
                is_last = (idx == len(domain_entries) - 1)
                if is_last:
                    step_out = out_path
                else:
                    fd, step_out = tempfile.mkstemp(suffix=".docx")
                    os.close(fd)
                    tmp_files.append(step_out)

                domain = self.registry.get(dom_id) or self.get_domain(domain_id=self.default_domain_id)
                changes = domain.apply_approved_changes(
                    in_path=current_in,
                    out_path=step_out,
                    approved_items=dom_items,
                    signature_settings=sig_cfg,
                    **ctx
                )
                total_changes += changes
                current_in = step_out
        finally:
            for tf in tmp_files:
                if os.path.exists(tf):
                    try:
                        os.remove(tf)
                    except OSError:
                        pass

        return total_changes

    def process_file(
        self,
        in_path: str,
        out_path: str,
        rules: List[Dict[str, str]],
        mode: str = "GABUNGAN",
        case_sensitive: bool = True,
        signature_settings: Optional[Dict[str, Any]] = None,
        domain_id: Optional[str] = None,
        **ctx
    ) -> int:
        """Metode langsung tanpa pratinjau (direct processing)."""
        rel_path = os.path.basename(in_path)
        plan_items = self.plan_document_changes(
            in_path=in_path,
            rel_path=rel_path,
            rules=rules,
            mode=mode,
            case_sensitive=case_sensitive,
            domain_id=domain_id,
            **ctx
        )
        return self.apply_approved_changes(
            in_path=in_path,
            out_path=out_path,
            approved_items=plan_items,
            signature_settings=signature_settings,
            **ctx
        )

    def reload_dictionary(self) -> None:
        """Memuat ulang kamus pada seluruh domain terdaftar."""
        for d in self.registry.list_domains():
            d.reload_dictionary()

    def reload_signature_settings(self, settings: Dict[str, Any]) -> None:
        """Memuat ulang konfigurasi tanda tangan."""
        self.signature_settings = settings
        rpp = self.registry.get("rpp_modul")
        if rpp and hasattr(rpp, "reload_signature_settings"):
            rpp.reload_signature_settings(settings)
