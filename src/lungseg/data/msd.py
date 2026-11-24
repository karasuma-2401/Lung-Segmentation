"""MSD native-grid NIfTI inventory. Never changes images, masks or dataset splits."""

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath

import nibabel as nib
import numpy as np

from lungseg.data.msd_acquire import file_sha256
from lungseg.data.msd_config import MsdConfig
from lungseg.environment import git_state
from lungseg.runs import utc_now, write_json

SCHEMA_VERSION = 1
FIELDS = (
    "schema_version", "dataset", "source_version", "case_id", "patient_id", "patient_id_source", "source_partition",
    "image_path", "mask_path", "annotation_kind", "ground_truth_available", "strong_eligible",
    "image_readable", "mask_readable", "image_shape", "mask_shape", "image_spacing_mm", "mask_spacing_mm",
    "image_spatial_unit", "mask_spatial_unit", "image_affine", "mask_affine", "image_affine_mm", "mask_affine_mm",
    "image_orientation", "mask_orientation", "image_qform_code", "image_sform_code", "mask_qform_code", "mask_sform_code",
    "image_dtype", "mask_dtype", "image_sha256", "mask_sha256", "image_voxel_sha256", "image_affine_sha256",
    "ct_min", "ct_max", "label_values", "label_values_truncated", "foreground_voxels", "voxel_volume_mm3",
    "tumor_volume_mm3", "geometry_aligned", "qc_status", "qc_errors", "qc_warnings",
)
UNIT_TO_MM = {"mm": 1.0, "meter": 1000.0, "micron": 0.001}


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    image_path: str
    mask_path: str | None
    source_partition: str
    listed: bool = True


def case_id_from_path(path: str) -> str:
    name = PurePosixPath(path).name
    for extension in (".nii.gz", ".nii"):
        if name.endswith(extension):
            return name[:-len(extension)]
    raise ValueError(f"Expected .nii or .nii.gz, found {name!r}")


def safe_relative(root: Path, value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Dataset paths must be relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Dataset path escapes root")
    (root / path).resolve().relative_to(root.resolve())
    case_id_from_path(value)
    return path.as_posix()


def discover_cases(root: Path) -> tuple[list[CaseSpec], dict, list[str]]:
    metadata = json.loads((root / "dataset.json").read_text(encoding="utf-8"))
    if metadata.get("modality") != {"0": "CT"} or metadata.get("labels") != {"0": "background", "1": "cancer"}:
        raise ValueError("Task06 CT modality/label mapping differs from expected background=0, cancer=1; review metadata")
    specs = []
    findings = []
    listed_images, listed_masks = set(), set()
    for group, count_key in (("training", "numTraining"), ("test", "numTest")):
        entries = metadata.get(group)
        if not isinstance(entries, list):
            raise ValueError(f"dataset.json requires a {group} list")
        if type(metadata.get(count_key)) is not int or len(entries) != metadata[count_key]:
            findings.append(f"metadata_count_mismatch:{group}")
        for entry in entries:
            image = safe_relative(root, entry["image"] if group == "training" else entry)
            mask = safe_relative(root, entry["label"]) if group == "training" else None
            expected_folder = "imagesTr" if group == "training" else "imagesTs"
            if PurePosixPath(image).parts[0] != expected_folder or (mask and PurePosixPath(mask).parts[0] != "labelsTr"):
                raise ValueError(f"Unexpected Task06 folder assignment in {group}")
            specs.append(CaseSpec(case_id_from_path(image), image, mask, f"official_{group}"))
            listed_images.add(image)
            if mask:
                listed_masks.add(mask)
    for folder in ("imagesTr", "imagesTs", "labelsTr"):
        for path in sorted((root / folder).rglob("*")):
            if not path.is_file() or path.name.startswith("._") or not path.name.endswith((".nii", ".nii.gz")):
                continue
            relative = safe_relative(root, path.relative_to(root).as_posix())
            if folder == "labelsTr":
                if relative not in listed_masks:
                    findings.append(f"unlisted_mask:{relative}")
            elif relative not in listed_images:
                specs.append(CaseSpec(case_id_from_path(relative), relative, None, "unlisted", False))
    return sorted(specs, key=lambda item: (item.case_id, item.source_partition, item.image_path)), metadata, findings


def inspect_nifti(path: Path, prefix: str, config: MsdConfig, *, label: bool = False) -> tuple[dict, list[str], list[str]]:
    info, errors, warnings = {}, [], []
    if not path.is_file():
        return {f"{prefix}_readable": False}, [f"missing_{prefix}"], []
    try:
        info[f"{prefix}_sha256"] = file_sha256(path)
        image = nib.load(path, mmap=True, keep_file_open=True)
        shape = image.shape
        affine = np.asarray(image.affine, dtype=np.float64)
        spacing = np.asarray(image.header.get_zooms()[:3], dtype=np.float64)
        unit = image.header.get_xyzt_units()[0]
        factor = UNIT_TO_MM.get(unit)
        affine_valid = (affine.shape == (4, 4) and np.isfinite(affine).all()
                        and np.allclose(affine[3], [0, 0, 0, 1], atol=1e-8, rtol=0)
                        and abs(np.linalg.det(affine[:3, :3])) > 1e-12)
        spacing_valid = len(spacing) == 3 and np.isfinite(spacing).all() and (spacing > 0).all()
        affine_mm = affine.copy() if affine_valid and factor is not None else None
        if affine_mm is not None:
            affine_mm[:3, :] *= factor
        info.update({f"{prefix}_shape": list(shape), f"{prefix}_spatial_unit": unit,
                     f"{prefix}_dtype": str(image.get_data_dtype()),
                     f"{prefix}_affine": affine.tolist() if affine_valid else None,
                     f"{prefix}_affine_mm": affine_mm.tolist() if affine_mm is not None else None,
                     f"{prefix}_spacing_mm": (spacing * factor).tolist() if spacing_valid and factor is not None else None,
                     f"{prefix}_orientation": "".join(nib.aff2axcodes(affine)) if affine_valid else None,
                     f"{prefix}_qform_code": int(image.header["qform_code"]),
                     f"{prefix}_sform_code": int(image.header["sform_code"])})
        if not affine_valid:
            errors.append(f"invalid_{prefix}_affine")
        if not spacing_valid:
            errors.append(f"invalid_{prefix}_spacing")
        if factor is None:
            errors.append(f"unknown_{prefix}_spatial_unit")
        if affine_valid and spacing_valid and not np.allclose(np.linalg.norm(affine[:3, :3], axis=0), spacing,
                                                             rtol=0, atol=config.spacing_atol_mm / (factor or 1)):
            errors.append(f"{prefix}_header_affine_spacing_mismatch")
        if affine_valid:
            qform, qcode = image.get_qform(coded=True)
            sform, scode = image.get_sform(coded=True)
            if qcode and scode and not np.allclose(qform, sform, atol=config.affine_atol_mm / (factor or 1), rtol=0):
                warnings.append(f"{prefix}_qform_sform_disagree")
        if len(shape) != 3 or any(size < 1 for size in shape):
            errors.append(f"invalid_{prefix}_dimensions")
            info[f"{prefix}_readable"] = False
            return info, errors, warnings
        digest = hashlib.sha256(json.dumps(list(shape)).encode())
        finite = True
        labels, labels_truncated, foreground = set(), False, 0
        valid_labels = True
        minimum, maximum = None, None
        for start in range(0, shape[2], config.slab_slices):
            block = np.asanyarray(image.dataobj[:, :, start:start + config.slab_slices])
            block_finite = bool(np.isfinite(block).all())
            finite &= block_finite
            if label:
                valid_labels &= bool(block_finite and np.isin(block, (0, 1)).all())
                unique = np.unique(block)
                labels_truncated |= len(unique) > 64
                labels.update(float(value) for value in unique[:64] if np.isfinite(value))
                if len(labels) > 64:
                    labels = set(sorted(labels)[:64])
                    labels_truncated = True
                foreground += int(np.count_nonzero(block == 1))
            else:
                if block_finite:
                    low, high = float(block.min()), float(block.max())
                    minimum = low if minimum is None else min(minimum, low)
                    maximum = high if maximum is None else max(maximum, high)
                # Float64 voxel fingerprints catch identical CT arrays with
                # different gzip/header bytes. This is not patient identity evidence.
                digest.update(np.ascontiguousarray(block.transpose(2, 0, 1), dtype="<f8").tobytes())
        info[f"{prefix}_readable"] = True
        if not finite:
            errors.append(f"nonfinite_{prefix}_voxels")
        if label:
            info.update(label_values=sorted(labels), label_values_truncated=labels_truncated,
                        foreground_voxels=foreground)
            if not valid_labels:
                errors.append("invalid_label_values")
            if valid_labels and foreground == 0:
                warnings.append("empty_mask")
            voxel_volume = abs(float(np.linalg.det(affine_mm[:3, :3]))) if affine_mm is not None else None
            info.update(voxel_volume_mm3=voxel_volume,
                        tumor_volume_mm3=foreground * voxel_volume if voxel_volume is not None and valid_labels else None)
        else:
            info.update(ct_min=minimum, ct_max=maximum,
                        image_voxel_sha256=digest.hexdigest() if finite else None,
                        image_affine_sha256=hashlib.sha256(affine.astype("<f8").tobytes()).hexdigest() if affine_valid else None)
    except Exception as exc:
        # Record the failing component and error type without inventing an empty mask
        # or leaking absolute source paths into a shareable manifest.
        info[f"{prefix}_readable"] = False
        errors.append(f"unreadable_{prefix}:{type(exc).__name__}")
    return info, errors, warnings


def validate_case(root: Path, spec: CaseSpec, config: MsdConfig) -> dict:
    image_path = safe_relative(root, spec.image_path)
    mask_path = safe_relative(root, spec.mask_path) if spec.mask_path else None
    row = {field: None for field in FIELDS}
    available = bool(mask_path and (root / mask_path).is_file())
    row.update(schema_version=SCHEMA_VERSION, dataset="MSD-Task06_Lung", case_id=spec.case_id,
               patient_id=None, patient_id_source="not_provided_in_dataset_json",
               source_partition=spec.source_partition, image_path=image_path, mask_path=mask_path,
               annotation_kind="strong_mask" if available else "missing_mask" if mask_path else "none",
               ground_truth_available=available, strong_eligible=False, geometry_aligned=None,
               mask_readable=False, label_values_truncated=False)
    info, errors, warnings = inspect_nifti(root / image_path, "image", config)
    row.update(info)
    if not spec.listed:
        errors.append("unlisted_image")
    if mask_path:
        info, mask_errors, mask_warnings = inspect_nifti(root / mask_path, "mask", config, label=True)
        row.update(info)
        errors.extend(mask_errors)
        warnings.extend(mask_warnings)
        if case_id_from_path(mask_path) != spec.case_id:
            errors.append("image_mask_case_id_mismatch")
        if row["image_shape"] and row["mask_shape"] and row["image_shape"] != row["mask_shape"]:
            errors.append("shape_mismatch")
        if row["image_affine_mm"] is not None and row["mask_affine_mm"] is not None:
            if not np.allclose(row["image_affine_mm"], row["mask_affine_mm"], rtol=0, atol=config.affine_atol_mm):
                errors.append("affine_mismatch")
            if row["image_spacing_mm"] is None or row["mask_spacing_mm"] is None or not np.allclose(
                    row["image_spacing_mm"], row["mask_spacing_mm"], rtol=0, atol=config.spacing_atol_mm):
                errors.append("spacing_mismatch")
            row["geometry_aligned"] = bool(row["image_shape"] == row["mask_shape"] and
                                            "affine_mismatch" not in errors and "spacing_mismatch" not in errors)
    elif spec.source_partition != "official_test":
        errors.append("mask_annotation_unspecified")
    row.update(qc_errors=sorted(set(errors)), qc_warnings=sorted(set(warnings)))
    finalize_row(row)
    return row


def finalize_row(row: dict) -> None:
    row["qc_status"] = "fail" if row["qc_errors"] else "warn" if row["qc_warnings"] else "pass"
    row["strong_eligible"] = bool(row["ground_truth_available"] and row["image_readable"] and row["mask_readable"]
                                  and row["geometry_aligned"] and not row["qc_errors"]
                                  and (row["foreground_voxels"] or 0) > 0)


def mark_duplicates(rows: list[dict]) -> None:
    for field, issue in (("case_id", "duplicate_case_id"), ("image_path", "duplicate_image_path"),
                         ("image_voxel_sha256", "duplicate_image_voxels")):
        groups = defaultdict(list)
        for row in rows:
            if row[field] is not None:
                groups[row[field]].append(row)
        for group in groups.values():
            if len(group) > 1:
                for row in group:
                    row["qc_errors"] = sorted(set(row["qc_errors"] + [issue]))
                    finalize_row(row)


def statistics(values: list[float]) -> dict | None:
    if not values:
        return None
    return {"n": len(values), "min": float(np.min(values)), "median": float(np.median(values)),
            "max": float(np.max(values)), "q25": float(np.quantile(values, 0.25)),
            "q75": float(np.quantile(values, 0.75))}


def summarize(rows: list[dict], metadata: dict, findings: list[str]) -> dict:
    shapes = [row["image_shape"] for row in rows if row["image_shape"] and len(row["image_shape"]) == 3]
    spacings = [row["image_spacing_mm"] for row in rows if row["image_spacing_mm"]]
    return {"schema_version": SCHEMA_VERSION, "dataset": "MSD-Task06_Lung", "real_data": True,
            "rows": len(rows), "unique_case_ids": len({row["case_id"] for row in rows}),
            "source_partitions": dict(Counter(row["source_partition"] for row in rows)),
            "declared_training": metadata.get("numTraining"), "declared_test": metadata.get("numTest"),
            "ct_volumes_readable": sum(bool(row["image_readable"]) for row in rows),
            "mask_volumes_readable": sum(bool(row["mask_readable"]) for row in rows),
            "ground_truth_available": sum(row["ground_truth_available"] for row in rows),
            "strong_eligible_count": sum(row["strong_eligible"] for row in rows),
            "qc_status_counts": dict(Counter(row["qc_status"] for row in rows)),
            "error_counts": dict(sorted(Counter(issue for row in rows for issue in row["qc_errors"]).items())),
            "warning_counts": dict(sorted(Counter(issue for row in rows for issue in row["qc_warnings"]).items())),
            "dataset_findings": sorted(findings), "patient_identity_verified": False,
            "patient_id_policy": "null: no patient mapping in distributed dataset.json; case IDs are not patient IDs",
            "shape_min_xyz": np.min(shapes, axis=0).tolist() if shapes else None,
            "shape_max_xyz": np.max(shapes, axis=0).tolist() if shapes else None,
            "spacing_min_xyz_mm": np.min(spacings, axis=0).tolist() if spacings else None,
            "spacing_max_xyz_mm": np.max(spacings, axis=0).tolist() if spacings else None,
            "orientation_counts": dict(Counter(row["image_orientation"] or "unavailable" for row in rows)),
            "label_values_union": sorted({value for row in rows for value in row["label_values"] or []}),
            "foreground_voxels": statistics([row["foreground_voxels"] for row in rows if row["foreground_voxels"] is not None]),
            "tumor_volume_mm3": statistics([row["tumor_volume_mm3"] for row in rows if row["tumor_volume_mm3"] is not None]),
            "scope": "native-grid inventory, not a train/validation/test assignment or preprocessing"}


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, separators=(",", ":"), allow_nan=False)
                             if isinstance(value, (list, dict, bool)) else value for key, value in row.items()})
    temporary.replace(path)


def inventory(config: MsdConfig, *, synthetic: bool = False) -> dict:
    root = Path(config.dataset_root)
    if not root.is_dir():
        raise FileNotFoundError(f"MSD root unavailable: {root}; run acquire-msd first or configure an existing download")
    specs, metadata, findings = discover_cases(root)
    rows = []
    for index, spec in enumerate(specs, 1):
        row = validate_case(root, spec, config)
        row["source_version"] = metadata.get("relase") or metadata.get("release")
        rows.append(row)
        if index % 10 == 0:
            print(f"MSD inventory: {index}/{len(specs)} CT cases checked", flush=True)
    mark_duplicates(rows)
    summary = summarize(rows, metadata, findings)
    acquisition_path = root / ".acquisition.json"
    provenance = json.loads(acquisition_path.read_text()) if acquisition_path.exists() else None
    real_data = False if synthetic else True if provenance and provenance.get("archive_sha256") else None
    summary["real_data"] = real_data
    summary["data_origin"] = ("synthetic_fixture" if synthetic else "acquired_MSD_archive" if real_data
                              else "manually_supplied_source_not_verified")
    summary["publisher_metadata"] = {key: metadata.get(key) for key in ("name", "description", "reference", "licence", "relase")}
    output = Path(config.output_dir)
    manifest = output / "manifest_msd.csv"
    write_manifest(manifest, rows)
    write_json(output / "summary.json", summary)
    write_json(output / "inventory_run.json", {
        "schema_version": SCHEMA_VERSION, "timestamp_utc": utc_now(), "config": asdict(config),
        "config_sha256": config.sha256, "dataset_json_sha256": file_sha256(root / "dataset.json"),
        "manifest_sha256": file_sha256(manifest), "git": git_state(), "real_data": real_data,
        "annotation_changed": False, "source_partition_is_experiment_split": False,
        "acquisition": provenance,
    })
    return summary
