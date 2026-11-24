"""CT/mask visual QA only: native-grid axis permutation, no resampling or edits."""

import csv
import json
from pathlib import Path

import nibabel as nib
import numpy as np

from lungseg.data.msd import safe_relative
from lungseg.data.msd_acquire import LICENSE_URL, file_sha256
from lungseg.runs import utc_now, write_json


def load_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in ("mask_readable", "image_readable", "geometry_aligned", "qc_errors", "qc_warnings"):
            row[key] = json.loads(row[key]) if row[key] else None
        row["tumor_volume_mm3"] = float(row["tumor_volume_mm3"]) if row["tumor_volume_mm3"] else None
    return rows


def select_cases(rows: list[dict], count: int, case_ids: list[str] | None = None) -> list[dict]:
    usable = [row for row in rows if row["image_readable"] and row["mask_readable"]
              and row["geometry_aligned"] and row["tumor_volume_mm3"] is not None
              and row["tumor_volume_mm3"] > 0 and not row["qc_errors"]]
    usable.sort(key=lambda row: (row["tumor_volume_mm3"], row["case_id"]))
    if case_ids:
        if len(set(case_ids)) != len(case_ids) or len(case_ids) > 20:
            raise ValueError("QA case IDs must be unique, at most 20")
        by_id = {row["case_id"]: row for row in usable}
        missing = set(case_ids) - by_id.keys()
        if missing:
            raise ValueError(f"Requested QA cases are not valid/aligned labeled cases: {sorted(missing)}")
        return [by_id[case_id] for case_id in case_ids]
    if not usable:
        raise ValueError("No readable aligned nonempty masks available for QA; inspect inventory findings")
    indices = np.linspace(0, len(usable) - 1, min(count, len(usable)), dtype=int)
    return [usable[index] for index in indices]


def read_canonical_planes(image, transform: np.ndarray, slices: list[int], slab_slices: int) -> list[np.ndarray]:
    """Collect three CT planes in one sequential pass rather than loading a full CT."""
    input_indices = []
    planes = []
    for axis in range(3):
        output_axis = int(transform[axis, 0])
        position = slices[output_axis]
        input_indices.append(position if transform[axis, 1] == 1 else image.shape[axis] - 1 - position)
        planes.append(np.empty(tuple(size for index, size in enumerate(image.shape) if index != axis), dtype=np.float32))
    for start in range(0, image.shape[2], slab_slices):
        end = min(start + slab_slices, image.shape[2])
        block = np.asarray(image.dataobj[:, :, start:end], dtype=np.float32)
        planes[0][:, start:end] = block[input_indices[0], :, :]
        planes[1][:, start:end] = block[:, input_indices[1], :]
        if start <= input_indices[2] < end:
            planes[2][:, :] = block[:, :, input_indices[2] - start]
    result = [None] * 3
    for axis, plane in enumerate(planes):
        output_axis = int(transform[axis, 0])
        thin = nib.orientations.apply_orientation(np.expand_dims(plane, axis=axis), transform)
        result[output_axis] = np.take(thin, 0, axis=output_axis).T
    return result


def render_case(root: Path, row: dict, destination: Path, *, synthetic: bool = False,
                affine_atol_mm: float = 0.001, slab_slices: int = 16) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    image = nib.load(root / safe_relative(root, row["image_path"]), keep_file_open=True)
    mask = nib.load(root / safe_relative(root, row["mask_path"]), keep_file_open=True)
    factors = {"mm": 1, "meter": 1000, "micron": 0.001}
    image_factor = factors.get(image.header.get_xyzt_units()[0])
    mask_factor = factors.get(mask.header.get_xyzt_units()[0])
    if image_factor is None or mask_factor is None:
        raise ValueError("QA physical scale requires known spatial units")
    image_mm, mask_mm = image.affine.copy(), mask.affine.copy()
    image_mm[:3, :] *= image_factor
    mask_mm[:3, :] *= mask_factor
    if image.shape != mask.shape or not np.allclose(image_mm, mask_mm, atol=affine_atol_mm, rtol=0):
        raise ValueError("QA input geometry changed since inventory; rerun inventory")
    if file_sha256(root / row["image_path"]) != row["image_sha256"] or file_sha256(root / row["mask_path"]) != row["mask_sha256"]:
        raise ValueError("QA inputs changed since inventory; refusing stale overlays")
    transform = nib.orientations.ornt_transform(nib.orientations.io_orientation(image.affine),
                                                nib.orientations.axcodes2ornt(("R", "A", "S")))
    raw_label = np.empty(mask.shape, dtype=np.uint8)
    for start in range(0, mask.shape[2], slab_slices):
        raw_label[:, :, start:start + slab_slices] = np.asarray(mask.dataobj[:, :, start:start + slab_slices], dtype=np.uint8)
    label = nib.orientations.apply_orientation(raw_label, transform)
    canonical_affine = image.affine @ nib.orientations.inv_ornt_aff(transform, image.shape)
    factor = {"mm": 1, "meter": 1000, "micron": 0.001}.get(image.header.get_xyzt_units()[0])
    if factor is None:
        raise ValueError("QA physical scale requires known spatial units")
    spacing = np.linalg.norm(canonical_affine[:3, :3], axis=0) * factor
    slices = [int(np.argmax(label.sum(axis=tuple(other for other in range(3) if other != axis))))
              for axis in range(3)]
    ct_planes = read_canonical_planes(image, transform, slices, slab_slices)
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    planes = ((2, "Axial", "L → R", "P → A"), (1, "Coronal", "L → R", "I → S"),
              (0, "Sagittal", "P → A", "I → S"))
    red = ListedColormap(["#ff3838"])
    for column, (axis, name, horizontal, vertical) in enumerate(planes):
        ct_slice = ct_planes[axis]
        mask_slice = np.take(label, slices[axis], axis=axis).T
        h_axis, v_axis = [other for other in range(3) if other != axis]
        extent = (0, ct_slice.shape[1] * spacing[h_axis], 0, ct_slice.shape[0] * spacing[v_axis])
        for plot_row in (0, 1):
            ax = axes[plot_row, column]
            ax.imshow(ct_slice, cmap="gray", vmin=-1000, vmax=400, origin="lower", extent=extent,
                      interpolation="nearest")
            ax.imshow(np.ma.masked_where(mask_slice == 0, mask_slice), cmap=red, alpha=0.45,
                      origin="lower", extent=extent, interpolation="nearest", vmin=0, vmax=1)
            ax.set_xlabel(f"{horizontal} (mm)")
            ax.set_ylabel(f"{vertical} (mm)")
            ax.set_title(f"{name}, canonical slice {slices[axis]}" + (" — QA zoom" if plot_row else ""))
            if plot_row:
                yy, xx = np.where(mask_slice)
                margin = 20  # display context in voxels, not a production crop
                ax.set_xlim(max(0, xx.min() - margin) * spacing[h_axis],
                            min(ct_slice.shape[1], xx.max() + margin + 1) * spacing[h_axis])
                ax.set_ylim(max(0, yy.min() - margin) * spacing[v_axis],
                            min(ct_slice.shape[0], yy.max() + margin + 1) * spacing[v_axis])
    attribution = "SYNTHETIC NIfTI FIXTURE — NOT MSD DATA" if synthetic else "MSD / Simpson et al. | CC BY-SA 4.0"
    fig.suptitle(f"{row['case_id']} | tumor {row['tumor_volume_mm3']/1000:.3f} cm³ | "
                 f"native grid, axis permutation only\n{attribution} | "
                 "CT window [-1000,400], red=expert mask; display modifications only", fontsize=12)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=125)
    plt.close(fig)
    return {"case_id": row["case_id"], "tumor_volume_mm3": row["tumor_volume_mm3"],
            "canonical_slices_xyz": slices, "file": destination.name,
            "image_sha256": row["image_sha256"], "mask_sha256": row["mask_sha256"],
            "automated_geometry_check": "pass", "manual_review": "pending"}


def generate_qa(config, case_ids: list[str] | None = None) -> dict:
    manifest = Path(config.output_dir) / "manifest_msd.csv"
    source_run = json.loads((Path(config.output_dir) / "inventory_run.json").read_text())
    manifest_digest = file_sha256(manifest)
    if source_run.get("manifest_sha256") != manifest_digest:
        raise ValueError("Manifest changed since inventory; rerun audit-msd before QA")
    rows = load_manifest(manifest)
    selected = select_cases(rows, config.qa_count, case_ids)
    destination = Path(config.qa_dir)
    records = [render_case(Path(config.dataset_root), row, destination / f"{row['case_id']}_qa.png",
                           synthetic=source_run["real_data"] is False,
                           affine_atol_mm=config.affine_atol_mm, slab_slices=config.slab_slices) for row in selected]
    report = {"timestamp_utc": utc_now(), "dataset": "MSD-Task06_Lung", "config_sha256": config.sha256,
              "manifest_sha256": manifest_digest, "real_data": source_run["real_data"], "n_cases": len(records),
              "selection": "explicit_case_ids" if case_ids else "evenly_spaced_ranks_by_tumor_volume_including_extremes",
              "source_labeled_cases": sum(row["mask_readable"] for row in rows), "cases": records,
              "license": "CC-BY-SA-4.0", "license_url": LICENSE_URL,
              "attribution": "Medical Segmentation Decathlon / Simpson et al., https://medicaldecathlon.com/",
              "modifications": "CT window, orthogonal slices, RAS axis permutation, red overlay and display-only zoom",
              "spatial_resampling": False, "original_data_modified": False,
              "limitation": "Same NIfTI grid does not prove anatomical correctness. Oblique scans shown on closest canonical voxel planes."}
    write_json(destination / "qa_index.json", report)
    return report
