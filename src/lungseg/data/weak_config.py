"""Bounded T06 acquisition/native bbox conversion configuration."""
from dataclasses import dataclass, asdict
import hashlib
import json
import math
from pathlib import Path
import re
import yaml


@dataclass(frozen=True)
class WeakConfig:
    schema_version: int
    kind: str
    raw_root: str
    converted_root: str
    output_dir: str
    qa_dir: str
    evidence_dir: str
    sample_patient_ids: list[str]
    annotation_format: str
    reserve_bytes: int
    max_download_bytes: int
    max_volume_voxels: int
    geometry_tolerance_mm: float
    orientation_atol: float
    spacing_atol_mm: float
    affine_atol_mm: float
    slab_slices: int
    min_extent_mm: float
    max_extent_mm: float

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError('Expected exact configs/weak.yaml fields')
        if value['schema_version'] != 1 or value['kind'] != 'lung_pet_ct_dx_native_bbox' or value['annotation_format'] != 'dicom_sr_idc_2025':
            raise ValueError('Only surveyed IDC expert-box SR format supported; XML convention not verified')
        paths = [Path(value[k]).resolve() for k in ('raw_root','converted_root','output_dir','qa_dir','evidence_dir')]
        if any(a == b or a in b.parents or b in a.parents for i,a in enumerate(paths) for b in paths[i+1:]):
            raise ValueError('Keep raw/converted/manifest/QA/evidence paths separate')
        patients = value['sample_patient_ids']
        if not isinstance(patients,list) or not 1 <= len(patients) <= 12 or len(set(patients)) != len(patients) or any(not re.fullmatch(r'Lung_Dx-[ABEG]\d{4}',p) for p in patients):
            raise ValueError('Sample requires 1-12 unique verified public Lung_Dx IDs')
        for key in ('reserve_bytes','max_download_bytes','max_volume_voxels','slab_slices'):
            if type(value[key]) is not int or value[key] <= 0: raise ValueError(key)
        if value['reserve_bytes'] < 4*1024**3 or value['max_download_bytes'] > 2*1024**3 or value['max_volume_voxels'] > 100_000_000 or value['slab_slices'] > 16:
            raise ValueError('Bounded CPU sample resource limits exceeded')
        for key in ('geometry_tolerance_mm','orientation_atol','spacing_atol_mm','affine_atol_mm'):
            if type(value[key]) not in (int,float) or not math.isfinite(value[key]) or not 0 < value[key] <= .5: raise ValueError(key)
        if value['min_extent_mm'] != 160 or value['max_extent_mm'] != 600:
            raise ValueError('T06 paper range is fixed closed [160,600] mm; do not tune to 665')
        return cls(**value)

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()


def load_weak_config(path):
    return WeakConfig.from_dict(yaml.safe_load(Path(path).read_text(encoding='utf-8')))
