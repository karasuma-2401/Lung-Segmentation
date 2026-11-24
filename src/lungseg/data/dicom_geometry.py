"""Classic single-frame CT geometry/intensity conversion, without resampling."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pydicom
from pydicom.pixels import apply_modality_lut
from pydicom.uid import CTImageStorage


class DataIssue(ValueError):
    """A review/quarantine reason code rather than an empty-mask fallback."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(code + (": " + detail if detail else ""))


@dataclass
class CtGeometry:
    patient_id: str
    study_uid: str
    series_uid: str
    frame_uid: str
    shape: tuple[int, int, int]
    affine_lps: np.ndarray
    affine_ras: np.ndarray
    normal: np.ndarray
    slice_positions: np.ndarray
    slice_spacing_mm: float
    sorted_indices: list[int]
    sop_uids: list[str]
    headers: list

    def world_to_voxel(self, points_lps: np.ndarray) -> np.ndarray:
        points = np.asarray(points_lps, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
            raise DataIssue("invalid_physical_points")
        homogeneous = np.column_stack((points, np.ones(len(points))))
        return (np.linalg.inv(self.affine_lps) @ homogeneous.T).T[:, :3]

    def to_dict(self) -> dict:
        return {"patient_id": self.patient_id, "study_uid": self.study_uid, "series_uid": self.series_uid,
                "frame_of_reference_uid": self.frame_uid, "shape_ijk": list(self.shape),
                "affine_lps": self.affine_lps.tolist(), "affine_ras": self.affine_ras.tolist(),
                "spacing_ijk_mm": np.linalg.norm(self.affine_ras[:3, :3], axis=0).tolist(),
                "slice_spacing_normal_mm": self.slice_spacing_mm,
                "slice_positions_normal_mm": self.slice_positions.tolist(), "sop_uids_in_spatial_order": self.sop_uids,
                "coordinates": "NIfTI array [column,row,slice]; LPS→RAS changes world signs, not voxel indices"}


def required(dataset, key: str):
    value = getattr(dataset, key, None)
    if value is None or str(value) == "":
        raise DataIssue("missing_dicom_attribute", key)
    return value


def build_ct_geometry(headers: list, config) -> CtGeometry:
    if len(headers) < 2:
        raise DataIssue("insufficient_ct_slices", "Need at least two positions to establish slice spacing")
    first = headers[0]
    identity = {key: str(required(first, key)) for key in ("PatientID", "StudyInstanceUID", "SeriesInstanceUID", "FrameOfReferenceUID")}
    rows, columns = int(required(first, "Rows")), int(required(first, "Columns"))
    if min(rows, columns) < 1:
        raise DataIssue("invalid_ct_dimensions")
    orientation = np.asarray(required(first, "ImageOrientationPatient"), dtype=float)
    spacing = np.asarray(required(first, "PixelSpacing"), dtype=float)
    if orientation.shape != (6,) or not np.isfinite(orientation).all():
        raise DataIssue("invalid_image_orientation")
    x_direction, y_direction = orientation[:3], orientation[3:]
    if (not np.isclose(np.linalg.norm(x_direction), 1, atol=config.orientation_atol, rtol=0)
            or not np.isclose(np.linalg.norm(y_direction), 1, atol=config.orientation_atol, rtol=0)
            or abs(np.dot(x_direction, y_direction)) > config.orientation_atol):
        raise DataIssue("nonorthonormal_image_orientation")
    if spacing.shape != (2,) or not np.isfinite(spacing).all() or (spacing <= 0).any():
        raise DataIssue("invalid_pixel_spacing")
    normal = np.cross(x_direction, y_direction)
    positions, uids = [], []
    for dataset in headers:
        if str(required(dataset, "Modality")) != "CT" or str(required(dataset, "SOPClassUID")) != str(CTImageStorage):
            raise DataIssue("unsupported_ct_object", "Only classic CT Image Storage supported")
        if int(getattr(dataset, "NumberOfFrames", 1)) != 1:
            raise DataIssue("unsupported_multiframe_ct")
        if any(str(required(dataset, key)) != value for key, value in identity.items()):
            raise DataIssue("mixed_ct_identity_or_frame")
        if (int(required(dataset, "Rows")), int(required(dataset, "Columns"))) != (rows, columns):
            raise DataIssue("inconsistent_ct_dimensions")
        iop = np.asarray(required(dataset, "ImageOrientationPatient"), dtype=float)
        px = np.asarray(required(dataset, "PixelSpacing"), dtype=float)
        if iop.shape != (6,) or not np.allclose(iop, orientation, atol=config.orientation_atol, rtol=0):
            raise DataIssue("inconsistent_slice_orientation")
        if px.shape != (2,) or not np.allclose(px, spacing, atol=config.spacing_atol_mm, rtol=0):
            raise DataIssue("inconsistent_pixel_spacing")
        position = np.asarray(required(dataset, "ImagePositionPatient"), dtype=float)
        if position.shape != (3,) or not np.isfinite(position).all():
            raise DataIssue("invalid_image_position")
        positions.append(position)
        uids.append(str(required(dataset, "SOPInstanceUID")))
    if len(set(uids)) != len(uids):
        raise DataIssue("duplicate_sop_instance_uid")
    positions = np.asarray(positions)
    order = np.argsort(positions @ normal, kind="stable")
    sorted_positions = positions[order]
    projected = sorted_positions @ normal
    gaps = np.diff(projected)
    if (gaps <= config.geometry_tolerance_mm).any():
        raise DataIssue("duplicate_or_overlapping_slice_positions")
    slice_spacing = float(np.median(gaps))
    if not np.allclose(gaps, slice_spacing, atol=config.spacing_atol_mm, rtol=0):
        raise DataIssue("missing_slices_or_nonuniform_spacing", f"gaps_mm={np.round(gaps,6).tolist()}")
    # SliceThickness is not inter-slice spacing. SpacingBetweenSlices, if present,
    # provides independent evidence; uniform subsampling without such evidence is unknowable.
    for dataset in headers:
        if hasattr(dataset, "SpacingBetweenSlices"):
            declared = abs(float(dataset.SpacingBetweenSlices))
            if not np.isfinite(declared) or not np.isclose(declared, slice_spacing, atol=config.spacing_atol_mm, rtol=0):
                raise DataIssue("declared_slice_spacing_mismatch")
    step = np.mean(np.diff(sorted_positions, axis=0), axis=0)
    predicted = sorted_positions[0] + np.arange(len(headers))[:, None] * step
    if np.max(np.abs(predicted - sorted_positions)) > config.geometry_tolerance_mm:
        raise DataIssue("nonaffine_slice_positions")
    affine = np.eye(4)
    # DICOM PixelSpacing is [row, column]; first IOP triplet is column-index direction.
    affine[:3, 0] = x_direction * spacing[1]
    affine[:3, 1] = y_direction * spacing[0]
    affine[:3, 2] = step
    affine[:3, 3] = sorted_positions[0]
    if abs(np.linalg.det(affine[:3, :3])) < 1e-9:
        raise DataIssue("singular_ct_affine")
    ras = np.diag([-1., -1., 1., 1.]) @ affine
    return CtGeometry(identity["PatientID"], identity["StudyInstanceUID"], identity["SeriesInstanceUID"],
                      identity["FrameOfReferenceUID"], (columns, rows, len(headers)), affine, ras, normal,
                      projected, slice_spacing, order.tolist(), [uids[i] for i in order], [headers[i] for i in order])


def read_ct_pixels(paths: list[Path], geometry: CtGeometry) -> tuple[np.ndarray, list[dict]]:
    volume = np.empty(geometry.shape, dtype=np.float32)
    transforms = []
    for k, source_index in enumerate(geometry.sorted_indices):
        dataset = pydicom.dcmread(paths[source_index])
        if str(dataset.SOPInstanceUID) != geometry.sop_uids[k]:
            raise DataIssue("source_changed_during_conversion")
        has_lut = bool(getattr(dataset, "ModalityLUTSequence", []))
        if not has_lut:
            slope, intercept = float(required(dataset, "RescaleSlope")), float(required(dataset, "RescaleIntercept"))
            if not np.isfinite([slope, intercept]).all() or slope == 0:
                raise DataIssue("invalid_ct_rescale")
            units = str(getattr(dataset, "RescaleType", "HU"))
            if units.upper() != "HU":
                raise DataIssue("non_hu_ct_rescale", units)
            transform = {"kind": "RescaleSlopeIntercept", "slope": slope, "intercept": intercept,
                         "units": units, "rescale_type_present": hasattr(dataset, "RescaleType")}
        else:
            lut = dataset.ModalityLUTSequence[0]
            if str(getattr(lut, "ModalityLUTType", "")).upper() != "HU":
                raise DataIssue("non_hu_modality_lut")
            transform = {"kind": "ModalityLUTSequence", "units": "HU"}
        pixels = np.asarray(apply_modality_lut(dataset.pixel_array, dataset), dtype=np.float32)
        if pixels.shape != (geometry.shape[1], geometry.shape[0]) or not np.isfinite(pixels).all():
            raise DataIssue("invalid_ct_pixel_data")
        volume[:, :, k] = pixels.T
        transforms.append(transform)
    return volume, transforms
