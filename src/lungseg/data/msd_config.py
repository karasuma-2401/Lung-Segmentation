"""Configuration shared by MSD acquisition, native inventory and visual QA."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

import yaml

from lungseg.data.msd_acquire import SOURCE_URL


@dataclass(frozen=True)
class MsdConfig:
    schema_version: int
    kind: str
    dataset_root: str
    output_dir: str
    qa_dir: str
    qa_count: int
    affine_atol_mm: float
    spacing_atol_mm: float
    slab_slices: int
    acquisition: dict

    @classmethod
    def from_dict(cls, values: dict) -> "MsdConfig":
        if not isinstance(values, dict) or set(values) != set(cls.__dataclass_fields__):
            raise ValueError("MSD config must have exactly the fields shown in configs/msd.yaml")
        if type(values["schema_version"]) is not int or values["schema_version"] != 1 or values["kind"] != "msd_inventory":
            raise ValueError("Expected schema_version=1, kind=msd_inventory")
        for key in ("dataset_root", "output_dir", "qa_dir"):
            if not isinstance(values[key], str) or not values[key].strip():
                raise ValueError(f"{key} must be a nonempty path")
        root = Path(values["dataset_root"]).resolve()
        for key in ("output_dir", "qa_dir"):
            output = Path(values[key]).resolve()
            if output == root or root in output.parents or output in root.parents:
                raise ValueError(f"{key} must be separate from raw dataset_root")
        for key, low, high in (("qa_count", 1, 20), ("slab_slices", 1, 64)):
            if type(values[key]) is not int or not low <= values[key] <= high:
                raise ValueError(f"{key} must be an integer in [{low}, {high}]")
        for key in ("affine_atol_mm", "spacing_atol_mm"):
            value = values[key]
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value <= 0.1:
                raise ValueError(f"{key} must be finite and in (0,0.1] mm")
        acquisition = values["acquisition"]
        fields = {"url", "archive_path", "report_path", "reserve_bytes"}
        if not isinstance(acquisition, dict) or set(acquisition) != fields or acquisition["url"] != SOURCE_URL:
            raise ValueError("acquisition must specify the verified official MSD URL and required paths/reserve_bytes")
        for key in ("archive_path", "report_path"):
            if not isinstance(acquisition[key], str) or not acquisition[key].strip():
                raise ValueError(f"acquisition.{key} must be a nonempty path")
            output = Path(acquisition[key]).resolve()
            if output == root or root in output.parents or output in root.parents:
                raise ValueError(f"acquisition.{key} must be separate from dataset_root")
        reserve = acquisition["reserve_bytes"]
        if type(reserve) is not int or reserve < 1024**3:
            raise ValueError("reserve_bytes must be an integer of at least 1 GiB")
        return cls(**values)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def load_msd_config(path: str | Path) -> MsdConfig:
    return MsdConfig.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
