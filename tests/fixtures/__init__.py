"""
Modul fixture pengujian otomatis dokumen Word sintetis.
"""
from tests.fixtures.make_sample_docs import (
    create_sample_rpp,
    create_sample_sk,
    create_sample_sk_with_attachment,
    create_sample_sk_with_textbox_kop,
    create_sample_surat_dinas,
    create_sample_spt,
    create_sample_berita_acara,
)

__all__ = [
    "create_sample_rpp",
    "create_sample_sk",
    "create_sample_sk_with_attachment",
    "create_sample_sk_with_textbox_kop",
    "create_sample_surat_dinas",
    "create_sample_spt",
    "create_sample_berita_acara",
]
