"""Sample-only NSCLC inventory/conversion; quarantine on any ambiguous annotation.

No interpolation, source edits, experiment splits or production preprocessing.
Only source.json-verified acquisitions are accepted; fixtures require synthetic=True.
"""
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4

import nibabel as nib
import numpy as np
import pydicom

from lungseg.data.dicom_geometry import DataIssue, build_ct_geometry, read_ct_pixels
from lungseg.data.msd import FIELDS, inspect_nifti, statistics, write_manifest
from lungseg.data.msd_acquire import file_sha256, require_space
from lungseg.data.nsclc_acquire import LICENSE_URL
from lungseg.data.rtstruct import (choose_referenced_series, choose_rtstruct, rasterize_roi,
                                  roi_catalog, rt_references, select_primary_roi)
from lungseg.environment import git_state
from lungseg.runs import utc_now, write_json

NSCLC_FIELDS = FIELDS + ("study_uid", "ct_series_uid", "rtstruct_series_uid", "rtstruct_sop_uid",
    "frame_of_reference_uid", "source_files", "source_sha256", "roi_number", "roi_name", "available_rois",
    "native_geometry", "conversion_status", "provenance_path", "provenance_sha256", "config_sha256")


def scan_sample(config, *, synthetic=False) -> tuple[dict, dict]:
    root = Path(config.raw_root)
    if not root.is_dir():
        raise FileNotFoundError("NSCLC raw root unavailable; acquire a bounded sample first")
    patients, errors = {}, {}
    global_sops = {}
    for patient in sorted(config.sample_patient_ids):
        items = []
        patients[patient] = items
        try:
            directory = root / "dicom" / patient
            series_dirs = sorted(directory.iterdir()) if directory.is_dir() else []
            if not series_dirs:
                raise DataIssue("missing_patient_acquisition")
            for folder in series_dirs:
                if not folder.is_dir() or not (folder / "source.json").exists():
                    raise DataIssue("incomplete_acquisition_directory", folder.name)
                source = json.loads((folder / "source.json").read_text())
                if (source.get("public_patient_id") != patient or source.get("license_url") != LICENSE_URL
                        or source.get("synthetic", False) != synthetic):
                    raise DataIssue("unverified_public_source_or_fixture_origin")
                if not synthetic and source.get("transport") not in {"official_IDC_S3", "NBIA_getImageWithMD5Hash"}:
                    raise DataIssue("unverified_acquisition_transport")
                expected = source["objects"]
                if not expected or len({obj["sop_uid"] for obj in expected}) != len(expected):
                    raise DataIssue("empty_or_duplicate_source_manifest")
                paths = []
                for obj in expected:
                    sop = obj["sop_uid"]
                    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", sop):
                        raise DataIssue("invalid_source_sop_uid")
                    path = folder / (sop + ".dcm")
                    paths.append(path)
                    digest = file_sha256(path)
                    if digest != obj["sha256"]:
                        raise DataIssue("raw_checksum_mismatch")
                    ds = pydicom.dcmread(path, stop_before_pixels=True)
                    if (str(ds.PatientID) != patient or str(ds.SOPInstanceUID) != sop
                            or str(ds.SeriesInstanceUID) != source["series_uid"]
                            or str(ds.StudyInstanceUID) != source["study_uid"]
                            or str(ds.Modality) != source["modality"]):
                        raise DataIssue("raw_header_source_identity_mismatch")
                    if sop in global_sops:
                        errors[global_sops[sop]] = "duplicate_sop_instance_uid_across_sources"
                        raise DataIssue("duplicate_sop_instance_uid_across_sources")
                    global_sops[sop] = patient
                    items.append({"path": path, "header": ds, "sha256": digest,
                                  "source_marker_sha256": file_sha256(folder / "source.json")})
                if set(folder.glob("*.dcm")) != set(paths):
                    raise DataIssue("unlisted_raw_dicom_files")
        except Exception as exc:
            errors[patient] = str(exc) if isinstance(exc, DataIssue) else f"source_read_error:{type(exc).__name__}"
    return patients, errors


def survey(config, *, synthetic=False) -> dict:
    patients, errors = scan_sample(config, synthetic=synthetic)
    cases = []
    names = Counter()
    for patient, items in patients.items():
        rts = []
        for item in items:
            ds = item["header"]
            if str(ds.Modality) != "RTSTRUCT":
                continue
            try:
                rois = roi_catalog(ds)
                names.update(roi["name"] for roi in rois)
                contour_types = Counter(str(contour.ContourGeometricType)
                    for entry in getattr(ds, "ROIContourSequence", []) for contour in getattr(entry, "ContourSequence", []))
                rts.append({"sop_uid": str(ds.SOPInstanceUID), "series_uid": str(ds.SeriesInstanceUID),
                            "references": rt_references(ds), "rois": rois, "contour_types": dict(contour_types)})
            except Exception as exc:
                errors[patient] = str(exc) if isinstance(exc, DataIssue) else f"rtstruct_read_error:{type(exc).__name__}"
        cases.append({"patient_id": patient, "ct_objects": sum(str(i["header"].Modality) == "CT" for i in items),
                      "rtstructs": rts, "error": errors.get(patient)})
    verified = sum(bool(items) and patient not in errors for patient, items in patients.items())
    origin = False if synthetic else True if verified else None
    report = {"dataset": "NSCLC-Radiomics", "real_data": origin, "verified_source_patients": verified,
              "scope": "sample_ROI_survey",
              "config_sha256": config.sha256, "cases": cases, "roi_name_counts": dict(sorted(names.items())),
              "errors": errors, "timestamp_utc": utc_now()}
    write_json(Path(config.output_dir) / "roi_survey.json", report)
    return report


def save_nifti(path, array, affine):
    image = nib.Nifti1Image(array, affine)
    image.header.set_xyzt_units("mm")
    image.set_sform(affine, code=1)
    # qform cannot encode shear. Do not write a misleading approximated qform.
    directions = affine[:3, :3] / np.linalg.norm(affine[:3, :3], axis=0)
    orthogonal = np.allclose(directions.T @ directions, np.eye(3), atol=1e-6, rtol=0)
    image.set_qform(affine if orthogonal else None, code=1 if orthogonal else 0)
    nib.save(image, path)


def source_digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def convert_one(config, patient, items, *, synthetic=False):
    row = {key: None for key in NSCLC_FIELDS}
    row.update(schema_version=1, dataset="NSCLC-Radiomics", source_version="TCIA_v4_UID_matched_IDC",
               case_id=patient, patient_id=patient, patient_id_source="synthetic_fixture" if synthetic else "TCIA_public_deidentified_PatientID_verified_against_DICOM",
               source_partition="acquisition_sample_not_experiment_split", strong_eligible=False,
               ground_truth_available=False, image_readable=False, mask_readable=False, geometry_aligned=False,
               qc_errors=[], qc_warnings=["anatomical_annotation_review_pending"], conversion_status="quarantined",
               annotation_kind="unresolved_expert_RTSTRUCT", config_sha256=config.sha256)
    raw_root, output_root = Path(config.raw_root), Path(config.converted_root)
    sources = [{"path": i["path"].relative_to(raw_root).as_posix(), "sha256": i["sha256"],
                "source_marker_sha256": i["source_marker_sha256"]} for i in items]
    sources.sort(key=lambda item: item["path"])
    row.update(source_files=sources, source_sha256=source_digest(sources))
    try:
        rt = choose_rtstruct([i["header"] for i in items if str(i["header"].Modality) == "RTSTRUCT"],
                             config.rtstruct_sop_overrides.get(patient))
        row.update(rtstruct_sop_uid=str(rt.SOPInstanceUID), rtstruct_series_uid=str(rt.SeriesInstanceUID),
                   study_uid=str(rt.StudyInstanceUID), available_rois=roi_catalog(rt),
                   annotation_kind="expert_RTSTRUCT_primary_unresolved")
        groups = defaultdict(list)
        for item in items:
            ds = item["header"]
            if str(ds.Modality) == "CT" and str(ds.StudyInstanceUID) == str(rt.StudyInstanceUID):
                groups[str(ds.SeriesInstanceUID)].append(item)
        uid, selected = choose_referenced_series(rt, groups)
        row["ct_series_uid"] = uid
        geometry = build_ct_geometry([i["header"] for i in selected], config)
        row.update(frame_of_reference_uid=geometry.frame_uid, native_geometry=geometry.to_dict())
        roi = select_primary_roi(rt, config.accepted_roi_names, config.roi_number_overrides.get(patient),
                                 config.accepted_roi_interpreted_types)
        if "ORGAN" in roi["interpreted_types"]:
            row["qc_warnings"].append("primary_roi_has_generic_ORGAN_tag_selected_by_documented_name_policy")
        row.update(roi_number=roi["number"], roi_name=roi["name"], annotation_kind="expert_RTSTRUCT_primary_tumor")
        mask, annotation = rasterize_roi(rt, geometry, roi, config)
        row["ground_truth_available"] = True
        destination = output_root / patient
        if destination.exists():
            provenance = json.loads((destination / "provenance.json").read_text())
            if provenance["source_sha256"] != row["source_sha256"] or provenance["config_sha256"] != config.sha256:
                raise DataIssue("existing_conversion_source_or_config_changed", "Use a separate converted root; never overwrite")
            for key, filename in (("image_sha256", "ct.nii.gz"), ("mask_sha256", "mask.nii.gz")):
                if file_sha256(destination / filename) != provenance[key]:
                    raise DataIssue("existing_conversion_checksum_mismatch")
        else:
            # Array sizes are calculated from verified dimensions before allocation.
            require_space(output_root, int(np.prod(geometry.shape)) * 5 + config.reserve_bytes)
            ct, transforms = read_ct_pixels([i["path"] for i in selected], geometry)
            output_root.mkdir(parents=True, exist_ok=True)
            stage = output_root / (patient + ".partial-" + uuid4().hex[:8])
            stage.mkdir()
            save_nifti(stage / "ct.nii.gz", ct, geometry.affine_ras)
            save_nifti(stage / "mask.nii.gz", mask.astype(np.uint8), geometry.affine_ras)
            provenance = {"dataset": "NSCLC-Radiomics", "real_data": not synthetic,
                          "source_sha256": row["source_sha256"], "source_files": sources,
                          "config_sha256": config.sha256, "config": asdict(config), "native_geometry": geometry.to_dict(),
                          "annotation": annotation, "intensity_transforms_in_spatial_order": transforms,
                          "coordinate_transform": "RAS = diag(-1,-1,1,1) @ LPS; native grid, no resampling",
                          "image_sha256": file_sha256(stage / "ct.nii.gz"), "mask_sha256": file_sha256(stage / "mask.nii.gz"),
                          "source_annotation_edited": False, "timestamp_utc": utc_now()}
            write_json(stage / "provenance.json", provenance)
            os.rename(stage, destination)
        for prefix, filename in (("image", "ct.nii.gz"), ("mask", "mask.nii.gz")):
            info, errors, warnings = inspect_nifti(destination / filename, prefix, config, label=prefix == "mask")
            row.update(info)
            row["qc_errors"].extend(errors)
            row["qc_warnings"].extend(warnings)
        aligned = (row["image_shape"] == row["mask_shape"] == list(geometry.shape)
            and np.allclose(row["image_affine_mm"], geometry.affine_ras, atol=config.affine_atol_mm, rtol=0)
            and np.allclose(row["mask_affine_mm"], geometry.affine_ras, atol=config.affine_atol_mm, rtol=0))
        row["geometry_aligned"] = bool(aligned)
        if not aligned:
            raise DataIssue("converted_native_geometry_mismatch")
        row.update(image_path=f"{patient}/ct.nii.gz", mask_path=f"{patient}/mask.nii.gz",
                   provenance_path=f"{patient}/provenance.json", provenance_sha256=file_sha256(destination / "provenance.json"),
                   conversion_status="converted" if not row["qc_errors"] else "quarantined")
        row["tumor_volume_mm3"] = row["foreground_voxels"] * abs(float(np.linalg.det(geometry.affine_ras[:3, :3])))
    except Exception as exc:
        row["qc_errors"].append(str(exc) if isinstance(exc, DataIssue) else f"conversion_error:{type(exc).__name__}:{exc}")
    row["qc_errors"] = sorted(set(row["qc_errors"]))
    row["qc_warnings"] = sorted(set(row["qc_warnings"]))
    row["qc_status"] = "fail" if row["qc_errors"] else "warn"
    # Native conversion is not clearance for strong training or split assignment.
    return row


def convert_sample(config, *, synthetic=False):
    if not config.accepted_roi_names and not config.roi_number_overrides:
        raise ValueError("Survey real ROIs and document primary tumor policy before conversion")
    patients, acquisition_errors = scan_sample(config, synthetic=synthetic)
    rows = []
    for patient, items in patients.items():
        row = convert_one(config, patient, items, synthetic=synthetic) if patient not in acquisition_errors else None
        if row is None:
            row = {key: None for key in NSCLC_FIELDS}
            row.update(schema_version=1, dataset="NSCLC-Radiomics", case_id=patient, patient_id=patient,
                       patient_id_source="synthetic_fixture" if synthetic else "TCIA_public_catalog_requested_ID",
                       ground_truth_available=False, strong_eligible=False, image_readable=False, mask_readable=False,
                       conversion_status="quarantined", qc_status="fail", qc_errors=[acquisition_errors[patient]],
                       qc_warnings=[], config_sha256=config.sha256)
        rows.append(row)
        print(f"NSCLC {patient}: {row['conversion_status']}", flush=True)
    output = Path(config.output_dir)
    manifest = output / "manifest_nsclc.csv"
    write_manifest(manifest, rows, fields=NSCLC_FIELDS)
    write_manifest(output / "quarantine.csv", [r for r in rows if r["conversion_status"] == "quarantined"], fields=NSCLC_FIELDS)
    converted = [r for r in rows if r["conversion_status"] == "converted"]
    verified = sum(bool(items) and patient not in acquisition_errors for patient, items in patients.items())
    origin = False if synthetic else True if verified else None
    summary = {"dataset": "NSCLC-Radiomics", "real_data": origin, "verified_source_patients": verified,
               "status": "SAMPLE_CONVERTED_QA_PENDING" if converted else "PARTIAL",
               "full_corpus_status": "NOT_VALIDATED", "sample_patients": len(rows), "converted_cases": len(converted),
               "quarantined_cases": len(rows) - len(converted), "manifest_sha256": file_sha256(manifest),
               "config_sha256": config.sha256, "config": asdict(config), "git": git_state(),
               "shape_counts": dict(Counter(str(r["image_shape"]) for r in converted)),
               "spacing_counts": dict(Counter(str(r["image_spacing_mm"]) for r in converted)),
               "label_values_union": sorted({v for r in converted for v in r["label_values"]}),
               "tumor_volume_mm3": statistics([r["tumor_volume_mm3"] for r in converted]),
               "quarantine": [{"case_id": r["case_id"], "reasons": r["qc_errors"]} for r in rows if r["qc_errors"]],
               "anatomical_annotation_correctness": "not established by geometry or montage alone",
               "timestamp_utc": utc_now()}
    write_json(output / "conversion_report.json", summary)
    return summary


def generate_qa(config):
    from lungseg.data.msd_qa import load_manifest, render_case
    manifest = Path(config.output_dir) / "manifest_nsclc.csv"
    run = json.loads((Path(config.output_dir) / "conversion_report.json").read_text())
    if run["manifest_sha256"] != file_sha256(manifest) or run["config_sha256"] != config.sha256:
        raise ValueError("Manifest/config changed; rerun conversion inventory")
    rows = load_manifest(manifest)
    selected = [r for r in rows if r["conversion_status"] == "converted" and not r["qc_errors"]]
    if not selected:
        raise ValueError("No converted non-quarantined cases available for QA")
    cases = [render_case(Path(config.converted_root), row, Path(config.qa_dir) / f"{row['case_id']}_qa.png",
                         synthetic=not run["real_data"], affine_atol_mm=config.affine_atol_mm, slab_slices=config.slab_slices,
                         source_label="NSCLC-Radiomics / Aerts et al. / TCIA | CC BY-NC 3.0") for row in selected]
    report = {"dataset": "NSCLC-Radiomics", "real_data": run["real_data"], "cases": cases, "n_cases": len(cases),
              "manifest_sha256": run["manifest_sha256"], "config_sha256": config.sha256, "license_url": LICENSE_URL,
              "manual_review": "pending; rendering is not visual acceptance", "timestamp_utc": utc_now()}
    write_json(Path(config.qa_dir) / "qa_index.json", report)
    return report
