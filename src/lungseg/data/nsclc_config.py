"""Explicit NSCLC sample/conversion configuration, including external data roots."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re

import yaml


@dataclass(frozen=True)
class NsclcConfig:
    schema_version: int
    kind: str
    raw_root: str
    converted_root: str
    output_dir: str
    qa_dir: str
    evidence_dir: str
    sample_patient_ids: list[str]
    reserve_bytes: int
    geometry_tolerance_mm: float
    orientation_atol: float
    spacing_atol_mm: float
    contour_plane_tolerance_mm: float
    affine_atol_mm: float
    slab_slices: int
    accepted_roi_names: list[str]
    accepted_roi_interpreted_types: list[str]
    roi_number_overrides: dict
    rtstruct_sop_overrides: dict

    @classmethod
    def from_dict(cls, value: dict) -> "NsclcConfig":
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("NSCLC config must contain exactly the fields in configs/nsclc.yaml")
        if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["kind"] != "nsclc_rtstruct_inventory":
            raise ValueError("Expected NSCLC schema_version=1 / kind=nsclc_rtstruct_inventory")
        paths = []
        for key in ("raw_root", "converted_root", "output_dir", "qa_dir", "evidence_dir"):
            if not isinstance(value[key], str) or not value[key].strip():
                raise ValueError(f"{key} must be a nonempty path (absolute/external roots supported)")
            paths.append((key, Path(value[key]).resolve()))
        for index, (name, path) in enumerate(paths):
            for other_name, other in paths[index+1:]:
                if path == other or path in other.parents or other in path.parents:
                    raise ValueError(f"Keep {name} separate from {other_name}; do not overwrite raw or artifacts")
        patients = value["sample_patient_ids"]
        if (not isinstance(patients, list) or not 1 <= len(patients) <= 20 or len(set(patients)) != len(patients)
                or any(not isinstance(p, str) or not re.fullmatch(r"LUNG1-\d{3}", p) for p in patients)):
            raise ValueError("sample_patient_ids requires 1-20 unique public TCIA LUNG1-### IDs")
        if type(value["reserve_bytes"]) is not int or value["reserve_bytes"] < 2 * 1024**3:
            raise ValueError("reserve_bytes must reserve at least 2 GiB")
        for key in ("geometry_tolerance_mm", "orientation_atol", "spacing_atol_mm", "contour_plane_tolerance_mm", "affine_atol_mm"):
            number = value[key]
            if type(number) not in (float, int) or not math.isfinite(number) or not 0 < number <= 0.5:
                raise ValueError(f"{key} must be finite and in (0,0.5]")
        if type(value["slab_slices"]) is not int or not 1 <= value["slab_slices"] <= 64:
            raise ValueError("slab_slices must be 1-64")
        if not isinstance(value["accepted_roi_names"], list) or any(not isinstance(x, str) or not x.strip() for x in value["accepted_roi_names"]):
            raise ValueError("accepted_roi_names is an explicit list; empty means survey only, no automatic ROI policy")
        if (not isinstance(value["accepted_roi_interpreted_types"], list)
                or any(x not in {"GTV", "ORGAN"} for x in value["accepted_roi_interpreted_types"])):
            raise ValueError("Explicit ROI interpreted types must be GTV / observed generic ORGAN")
        for key in ("roi_number_overrides", "rtstruct_sop_overrides"):
            if not isinstance(value[key], dict) or any(p not in patients for p in value[key]):
                raise ValueError(f"{key} must map configured public patient IDs")
        if any(type(x) is not int or x < 0 for x in value["roi_number_overrides"].values()):
            raise ValueError("ROI overrides must be explicit nonnegative integers")
        if any(not isinstance(x, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", x) for x in value["rtstruct_sop_overrides"].values()):
            raise ValueError("RTSTRUCT overrides must be SOP Instance UIDs")
        return cls(**value)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def load_nsclc_config(path: str | Path, **overrides) -> NsclcConfig:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return NsclcConfig.from_dict({**value, **{key: str(val) for key, val in overrides.items() if val is not None}})
