"""Strict configuration for a bounded synthetic smoke run only."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SmokeConfig:
    schema_version: int
    kind: str
    seed: int
    device: str
    spatial_shape: tuple[int, int, int]
    channels: tuple[int, int, int]
    steps: int
    learning_rate: float
    num_threads: int
    output_dir: str

    @classmethod
    def from_dict(cls, data: dict) -> "SmokeConfig":
        if not isinstance(data, dict):
            raise ValueError("Smoke config must be a YAML mapping")
        fields = set(cls.__dataclass_fields__)
        missing, unknown = fields - data.keys(), data.keys() - fields
        if missing or unknown:
            raise ValueError(f"Config keys: missing={sorted(missing)}, unknown={sorted(unknown)}")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("schema_version must be integer 1")
        if data["kind"] != "synthetic_smoke":
            raise ValueError("kind must be synthetic_smoke; reference/research configs cannot run here")
        for key, low, high in (("seed", 0, 2**32 - 1), ("steps", 1, 10), ("num_threads", 1, 8)):
            if type(data[key]) is not int or not low <= data[key] <= high:
                raise ValueError(f"{key} must be an integer in [{low}, {high}]")
        if not isinstance(data["device"], str) or data["device"] not in {"cpu", "cuda", "auto"}:
            raise ValueError("device must be cpu, cuda, or auto")
        for key, low, high in (("spatial_shape", 8, 64), ("channels", 1, 32)):
            value = data[key]
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                raise ValueError(f"{key} must contain three integers")
            if any(type(x) is not int or not low <= x <= high for x in value):
                raise ValueError(f"{key} entries must be integers in [{low}, {high}]")
        if any(x % 4 for x in data["spatial_shape"]):
            raise ValueError("spatial_shape must be divisible by 4 for two downsamplings")
        lr = data["learning_rate"]
        if type(lr) not in (int, float) or not math.isfinite(lr) or not 0 < lr <= 1:
            raise ValueError("learning_rate must be finite and in (0, 1]")
        if not isinstance(data["output_dir"], str) or not data["output_dir"].strip():
            raise ValueError("output_dir must be a nonempty path")
        return cls(**{**data, "spatial_shape": tuple(data["spatial_shape"]),
                      "channels": tuple(data["channels"]), "learning_rate": float(lr)})

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def sha256(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_smoke_config(path: str | Path) -> SmokeConfig:
    with Path(path).open(encoding="utf-8") as handle:
        return SmokeConfig.from_dict(yaml.safe_load(handle))
