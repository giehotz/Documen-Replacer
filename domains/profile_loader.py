"""
Pemuat berkas profil domain (*.profile.json) skema versi 2.
Mendukung inheritance dari kamus dasar serta parsing zona dan aturan sinkronisasi.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class DomainProfile:
    """Representasi objek terstruktur dari profil domain dokumen."""
    schema_version: int
    profile_id: str
    display_name: str
    description: str = ""
    auto_detect: Dict[str, List[str]] = field(default_factory=dict)
    global_never_match: List[str] = field(default_factory=list)
    global_ignore_exact: List[str] = field(default_factory=list)
    fields: List[Dict[str, Any]] = field(default_factory=list)
    zones: List[Dict[str, Any]] = field(default_factory=list)
    sync: List[Dict[str, Any]] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)


def load_domain_profile(profile_path: str, base_dir: Optional[str] = None) -> DomainProfile:
    """
    Memuat berkas profil domain dari disk.
    Jika profil memiliki bagian 'inherit', field yang ditentukan akan digabung dari berkas induk.
    """
    if not os.path.isabs(profile_path) and base_dir:
        profile_path = os.path.join(base_dir, profile_path)

    if not os.path.isfile(profile_path):
        raise FileNotFoundError(f"Berkas profil domain tidak ditemukan: {profile_path}")

    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ver = data.get("schema_version")
    if ver != 2:
        raise ValueError(
            f"Versi skema profil tidak didukung: {ver} (diharapkan skema versi 2 pada {profile_path})"
        )

    profile_id = data.get("profile_id", "unnamed_profile")
    display_name = data.get("display_name", profile_id)
    description = data.get("description", "")
    auto_detect = data.get("auto_detect", {})
    global_never_match = list(data.get("global_never_match", []))
    global_ignore_exact = list(data.get("global_ignore_exact", []))
    fields = list(data.get("fields", []))
    zones = list(data.get("zones", []))
    sync = list(data.get("sync", []))

    # Proses inheritance bila ditentukan
    inherit_cfg = data.get("inherit")
    if inherit_cfg and isinstance(inherit_cfg, dict):
        from_file = inherit_cfg.get("from")
        target_field_ids = set(inherit_cfg.get("fields", []))
        if from_file:
            if not os.path.isabs(from_file) and base_dir:
                parent_path = os.path.join(base_dir, from_file)
            else:
                parent_path = from_file

            if os.path.isfile(parent_path):
                with open(parent_path, "r", encoding="utf-8") as pf:
                    parent_data = json.load(pf)
                p_fields = parent_data.get("fields", [])
                inherited_fields = [
                    fld for fld in p_fields
                    if not target_field_ids or fld.get("id") in target_field_ids
                ]
                # Sisipkan field warisan di awal sebelum field spesifik profil
                existing_ids = {f.get("id") for f in fields}
                for fld in inherited_fields:
                    if fld.get("id") not in existing_ids:
                        fields.append(fld)

                # Gabungkan global_never_match dari parent
                for nm in parent_data.get("global_never_match", []):
                    if nm not in global_never_match:
                        global_never_match.append(nm)

    return DomainProfile(
        schema_version=ver,
        profile_id=profile_id,
        display_name=display_name,
        description=description,
        auto_detect=auto_detect,
        global_never_match=global_never_match,
        global_ignore_exact=global_ignore_exact,
        fields=fields,
        zones=zones,
        sync=sync,
        raw_data=data
    )


class ProfileLoader:
    """Kelas helper pemuat profil domain."""
    @staticmethod
    def load_profile(profile_path: str, base_dir: Optional[str] = None) -> DomainProfile:
        return load_domain_profile(profile_path, base_dir=base_dir)
