"""
Paket domain dokumen untuk ekspansi multi-domain Smart Document Replacer.
Menyediakan abstraksi BaseDocumentDomain, DomainRegistry, dan adapter domain spesifik.
"""
from domains.base_domain import BaseDocumentDomain, DetectResult
from domains.domain_registry import DomainRegistry

__all__ = ["BaseDocumentDomain", "DetectResult", "DomainRegistry"]
