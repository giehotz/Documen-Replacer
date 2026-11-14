"""
Registry sentral untuk pendaftaran dan pencarian modul domain dokumen.
"""
from typing import Dict, List, Optional
from domains.base_domain import BaseDocumentDomain


class DomainRegistry:
    """
    Registry pengelola seluruh instance BaseDocumentDomain yang aktif.
    """
    _instance: Optional["DomainRegistry"] = None

    def __init__(self, auto_register_defaults: bool = True):
        self._domains: Dict[str, BaseDocumentDomain] = {}
        if auto_register_defaults:
            self._register_defaults()

    @classmethod
    def get_instance(cls) -> "DomainRegistry":
        """Mengambil singleton instance dari DomainRegistry."""
        if cls._instance is None:
            cls._instance = DomainRegistry(auto_register_defaults=True)
        return cls._instance

    def _register_defaults(self) -> None:
        """Mendaftarkan domain bawaan sistem."""
        try:
            from domains.rpp_domain_adapter import RPPDomainAdapter
            self.register(RPPDomainAdapter())
        except Exception:
            pass

        try:
            from domains.sk.sk_domain import SKDomain
            self.register(SKDomain())
        except Exception:
            pass

        try:
            from domains.surat_dinas.surat_dinas_domain import SuratDinasDomain
            self.register(SuratDinasDomain())
        except Exception:
            pass

        try:
            from domains.spt.spt_domain import SPTDomain
            self.register(SPTDomain())
        except Exception:
            pass

        try:
            from domains.berita_acara.berita_acara_domain import BeritaAcaraDomain
            self.register(BeritaAcaraDomain())
        except Exception:
            pass

    def register(self, domain: BaseDocumentDomain) -> None:
        """Mendaftarkan sebuah instance domain ke dalam registry."""
        self._domains[domain.domain_id] = domain

    def get(self, domain_id: str) -> Optional[BaseDocumentDomain]:
        """Mengambil instance domain berdasarkan domain_id."""
        return self._domains.get(domain_id)

    def list_domains(self) -> List[BaseDocumentDomain]:
        """Mengembalikan daftar seluruh domain terdaftar."""
        return list(self._domains.values())

    def clear(self) -> None:
        """Membersihkan seluruh pendaftaran domain (berguna untuk pengujian unit)."""
        self._domains.clear()
