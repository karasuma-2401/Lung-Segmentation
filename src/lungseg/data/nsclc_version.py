"""Conservative conversion cache identity; legacy artifacts are incompatible.

Hash complete participating modules, not function names or Git HEAD (which may
be dirty). Normalize source newlines so LF/CRLF checkout alone is not a new
algorithm. Dependency/Python versions participate because their numeric, DICOM
decode and NIfTI serialization implementations affect the output.
"""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform

ALGORITHM_VERSION = "nsclc-native-v2"
SOURCE_FILES = (
    "data/dicom_geometry.py",  # spatial ordering/affine, LUT/rescale
    "data/rtstruct.py",        # reference/ROI selection, polygon semantics
    "data/nsclc.py",           # orchestration, cache validation, NIfTI writing
    "data/nsclc_config.py",    # resolved geometry/ROI configuration validation
    "data/msd.py",             # converted-volume validation/statistics
    "data/msd_acquire.py",     # byte hashing and capacity checks
    "data/nsclc_version.py",   # identity construction itself
)


def conversion_implementation() -> dict:
    root = Path(__file__).resolve().parents[1]
    sources = {name: hashlib.sha256((root / name).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
               for name in SOURCE_FILES}
    identity = {"identity_schema_version": 1, "algorithm_version": ALGORITHM_VERSION,
                "source_sha256": sources,
                "runtime": {"python": platform.python_version(),
                            **{name: version(name) for name in ("numpy", "nibabel", "pydicom")}}}
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {**identity, "fingerprint_sha256": hashlib.sha256(encoded).hexdigest()}
