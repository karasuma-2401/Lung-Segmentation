"""All volumes here are synthetic NIfTI fixtures, never real MSD cases."""

from dataclasses import asdict, replace
import csv
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from lungseg.data.msd import CaseSpec, discover_cases, inventory, mark_duplicates, validate_case
from lungseg.data.msd_config import MsdConfig, load_msd_config
from lungseg.data.msd_qa import generate_qa, read_canonical_planes


def save_volume(path, values, affine=None, unit="mm"):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = nib.Nifti1Image(values, np.diag([0.7, 0.8, 2.5, 1]) if affine is None else affine)
    image.header.set_xyzt_units(unit)
    nib.save(image, path)


@pytest.fixture
def synthetic_msd(tmp_path):
    root = tmp_path / "Task06_Lung"
    settings = asdict(load_msd_config("configs/msd.yaml"))
    settings.update(dataset_root=str(root), output_dir=str(tmp_path / "manifest"),
                    qa_dir=str(tmp_path / "qa"), qa_count=1)
    config = MsdConfig.from_dict(settings)
    ct = np.arange(8 * 10 * 6, dtype=np.float32).reshape(8, 10, 6) - 1000
    mask = np.zeros(ct.shape, dtype=np.uint8)
    mask[2:4, 3:6, 1:4] = 1
    save_volume(root / "imagesTr/synthetic_001.nii.gz", ct)
    save_volume(root / "labelsTr/synthetic_001.nii.gz", mask)
    metadata = {"name": "SyntheticFixture_NOT_MSD", "modality": {"0": "CT"},
                "labels": {"0": "background", "1": "cancer"}, "numTraining": 1, "numTest": 0,
                "training": [{"image": "./imagesTr/synthetic_001.nii.gz", "label": "./labelsTr/synthetic_001.nii.gz"}],
                "test": []}
    (root / "dataset.json").write_text(json.dumps(metadata), encoding="utf-8")
    spec = CaseSpec("synthetic_001", "imagesTr/synthetic_001.nii.gz", "labelsTr/synthetic_001.nii.gz", "official_training")
    return root, spec, config, ct, mask


def test_valid_nifti_geometry_and_physical_volume(synthetic_msd):
    root, spec, config, _, _ = synthetic_msd
    row = validate_case(root, spec, config)
    assert row["qc_status"] == "pass"
    assert row["image_shape"] == [8, 10, 6]
    assert row["image_spacing_mm"] == pytest.approx([0.7, 0.8, 2.5])
    assert row["image_orientation"] == "RAS"
    assert row["label_values"] == [0, 1]
    assert row["foreground_voxels"] == 18
    assert row["voxel_volume_mm3"] == pytest.approx(1.4)
    assert row["tumor_volume_mm3"] == pytest.approx(25.2)
    assert row["geometry_aligned"] and row["strong_eligible"]
    assert row["patient_id"] is None
    assert row["patient_id_source"] == "not_provided_in_dataset_json"


def test_missing_training_mask_is_not_unlabeled_official_test(synthetic_msd):
    root, spec, config, _, _ = synthetic_msd
    (root / spec.mask_path).unlink()
    row = validate_case(root, spec, config)
    assert "missing_mask" in row["qc_errors"]
    assert row["annotation_kind"] == "missing_mask"
    assert not row["ground_truth_available"] and not row["strong_eligible"]
    assert row["tumor_volume_mm3"] is None
    test_row = validate_case(root, replace(spec, mask_path=None, source_partition="official_test"), config)
    assert test_row["qc_status"] == "pass"
    assert test_row["annotation_kind"] == "none" and not test_row["strong_eligible"]


def test_shape_mismatch(synthetic_msd):
    root, spec, config, _, _ = synthetic_msd
    save_volume(root / spec.mask_path, np.ones((8, 10, 7), dtype=np.uint8))
    row = validate_case(root, spec, config)
    assert "shape_mismatch" in row["qc_errors"]
    assert not row["geometry_aligned"] and not row["strong_eligible"]


def test_affine_mismatch(synthetic_msd):
    root, spec, config, _, mask = synthetic_msd
    affine = np.diag([0.7, 0.8, 2.5, 1])
    affine[0, 3] = 2
    save_volume(root / spec.mask_path, mask, affine)
    row = validate_case(root, spec, config)
    assert "affine_mismatch" in row["qc_errors"]
    assert not row["geometry_aligned"]


@pytest.mark.parametrize("value", [2.0, -1.0, 0.5, float("nan")])
def test_invalid_label_values(synthetic_msd, value):
    root, spec, config, _, mask = synthetic_msd
    mask = mask.astype(np.float32)
    mask[0, 0, 0] = value
    save_volume(root / spec.mask_path, mask)
    row = validate_case(root, spec, config)
    assert "invalid_label_values" in row["qc_errors"]
    assert row["tumor_volume_mm3"] is None and not row["strong_eligible"]


def test_empty_mask_is_reported_not_removed_or_rewritten(synthetic_msd):
    root, spec, config, _, mask = synthetic_msd
    save_volume(root / spec.mask_path, np.zeros_like(mask))
    before = (root / spec.mask_path).read_bytes()
    row = validate_case(root, spec, config)
    assert row["ground_truth_available"] and row["annotation_kind"] == "strong_mask"
    assert row["foreground_voxels"] == 0 and row["tumor_volume_mm3"] == 0
    assert "empty_mask" in row["qc_warnings"] and not row["strong_eligible"]
    assert (root / spec.mask_path).read_bytes() == before


def test_corrupt_ct_is_reported(synthetic_msd):
    root, spec, config, _, _ = synthetic_msd
    (root / spec.image_path).write_bytes(b"not nifti")
    row = validate_case(root, spec, config)
    assert not row["image_readable"] and row["qc_status"] == "fail"
    assert any(issue.startswith("unreadable_image:") for issue in row["qc_errors"])


def test_duplicate_cases_and_identical_voxels_are_flagged(synthetic_msd):
    root, spec, config, _, _ = synthetic_msd
    rows = [validate_case(root, spec, config), validate_case(root, spec, config)]
    mark_duplicates(rows)
    for row in rows:
        assert {"duplicate_case_id", "duplicate_image_path", "duplicate_image_voxels"} <= set(row["qc_errors"])
        assert not row["strong_eligible"]


def test_voxel_fingerprint_independent_of_slab_size(synthetic_msd):
    root, spec, config, _, _ = synthetic_msd
    first = validate_case(root, spec, replace(config, slab_slices=1))
    second = validate_case(root, spec, replace(config, slab_slices=4))
    assert first["image_voxel_sha256"] == second["image_voxel_sha256"]


def test_volume_uses_affine_determinant_for_sheared_voxels(synthetic_msd):
    root, spec, config, ct, mask = synthetic_msd
    affine = np.array([[2, 0.4, 0, 0], [0, 3, 0, 0], [0, 0, 4, 0], [0, 0, 0, 1]], dtype=float)
    save_volume(root / spec.image_path, ct, affine)
    save_volume(root / spec.mask_path, mask, affine)
    row = validate_case(root, spec, config)
    assert row["voxel_volume_mm3"] == pytest.approx(24)
    assert row["tumor_volume_mm3"] == pytest.approx(18 * 24)


def test_unknown_units_are_not_silently_assumed_mm(synthetic_msd):
    root, spec, config, ct, mask = synthetic_msd
    save_volume(root / spec.image_path, ct, unit="unknown")
    save_volume(root / spec.mask_path, mask, unit="unknown")
    row = validate_case(root, spec, config)
    assert "unknown_image_spatial_unit" in row["qc_errors"]
    assert row["tumor_volume_mm3"] is None


def test_meter_units_converted_to_mm(synthetic_msd):
    root, spec, config, ct, mask = synthetic_msd
    affine = np.diag([0.001, 0.001, 0.002, 1])
    save_volume(root / spec.image_path, ct, affine, "meter")
    save_volume(root / spec.mask_path, mask, affine, "meter")
    row = validate_case(root, spec, config)
    assert row["image_spacing_mm"] == pytest.approx([1, 1, 2])
    assert row["tumor_volume_mm3"] == pytest.approx(36)


def test_manifest_reproducible_and_no_fake_patient_or_split(synthetic_msd):
    root, _, config, ct, _ = synthetic_msd
    save_volume(root / "imagesTs/synthetic_002.nii.gz", ct + 1)
    metadata = json.loads((root / "dataset.json").read_text())
    metadata.update(numTest=1, test=["./imagesTs/synthetic_002.nii.gz"])
    (root / "dataset.json").write_text(json.dumps(metadata))
    summary = inventory(config, synthetic=True)
    manifest = Path(config.output_dir) / "manifest_msd.csv"
    original = manifest.read_bytes()
    assert summary["real_data"] is False
    assert summary["ground_truth_available"] == 1
    assert summary["source_partitions"] == {"official_training": 1, "official_test": 1}
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert all(not row["patient_id"] for row in rows)
    assert "split" not in rows[0]
    assert rows[1]["annotation_kind"] == "none" and rows[1]["strong_eligible"] == "false"
    inventory(config, synthetic=True)
    assert original == manifest.read_bytes()


def test_metadata_count_mismatch_and_unlisted_files_reported(synthetic_msd):
    root, _, config, ct, mask = synthetic_msd
    metadata = json.loads((root / "dataset.json").read_text())
    metadata["numTraining"] = 99
    (root / "dataset.json").write_text(json.dumps(metadata))
    save_volume(root / "imagesTr/synthetic_extra.nii.gz", ct + 2)
    save_volume(root / "labelsTr/orphan.nii.gz", mask)
    summary = inventory(config, synthetic=True)
    assert "metadata_count_mismatch:training" in summary["dataset_findings"]
    assert "unlisted_mask:labelsTr/orphan.nii.gz" in summary["dataset_findings"]
    assert summary["error_counts"]["unlisted_image"] == 1


def test_metadata_path_traversal_rejected(synthetic_msd):
    root, _, _, _, _ = synthetic_msd
    data = json.loads((root / "dataset.json").read_text())
    data["training"][0]["image"] = "../private.nii.gz"
    (root / "dataset.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="escapes"):
        discover_cases(root)


def test_qa_writes_three_plane_synthetic_overlay_and_rejects_stale_input(synthetic_msd):
    root, spec, config, ct, _ = synthetic_msd
    inventory(config, synthetic=True)
    report = generate_qa(config)
    assert report["n_cases"] == 1 and report["spatial_resampling"] is False
    assert report["real_data"] is False
    assert report["cases"][0]["manual_review"] == "pending"
    assert (Path(config.qa_dir) / "synthetic_001_qa.png").stat().st_size > 1000
    save_volume(root / spec.image_path, ct + 3)
    with pytest.raises(ValueError, match="changed since inventory"):
        generate_qa(config)


def test_streamed_qa_planes_match_axis_permutation_and_flips(synthetic_msd):
    root, spec, _, ct, _ = synthetic_msd
    image = nib.load(root / spec.image_path, keep_file_open=True)
    transform = np.array([[1, -1], [2, 1], [0, 1]])
    expected = nib.orientations.apply_orientation(ct, transform)
    slices = [size // 2 for size in expected.shape]
    actual = read_canonical_planes(image, transform, slices, slab_slices=2)
    for axis in range(3):
        np.testing.assert_array_equal(actual[axis], np.take(expected, slices[axis], axis=axis).T)


def test_qa_rejects_modified_manifest_before_using_paths(synthetic_msd):
    _, _, config, _, _ = synthetic_msd
    inventory(config, synthetic=True)
    manifest = Path(config.output_dir) / "manifest_msd.csv"
    manifest.write_text(manifest.read_text().replace("synthetic_001", "../tampered"))
    with pytest.raises(ValueError, match="Manifest changed since inventory"):
        generate_qa(config)


def test_missing_image_and_invalid_dimension(synthetic_msd):
    root, spec, config, ct, _ = synthetic_msd
    (root / spec.image_path).unlink()
    assert "missing_image" in validate_case(root, spec, config)["qc_errors"]
    save_volume(root / spec.image_path, ct[..., np.newaxis])
    row = validate_case(root, spec, config)
    assert "invalid_image_dimensions" in row["qc_errors"]
    assert not row["strong_eligible"]


@pytest.mark.parametrize("key,value", [("qa_count", True), ("slab_slices", 0),
                                      ("affine_atol_mm", float("nan")), ("spacing_atol_mm", 1)])
def test_invalid_msd_config_rejected(synthetic_msd, key, value):
    _, _, config, _, _ = synthetic_msd
    data = asdict(config)
    data[key] = value
    with pytest.raises(ValueError):
        MsdConfig.from_dict(data)


def test_output_paths_cannot_overwrite_raw_dataset(synthetic_msd):
    root, _, config, _, _ = synthetic_msd
    data = asdict(config)
    data["output_dir"] = str(root / "output")
    with pytest.raises(ValueError, match="separate"):
        MsdConfig.from_dict(data)
    data = asdict(config)
    data["acquisition"]["report_path"] = str(root / "dataset.json")
    with pytest.raises(ValueError, match="separate"):
        MsdConfig.from_dict(data)
