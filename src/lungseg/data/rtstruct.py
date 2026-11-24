"""Explicit RTSTRUCT reference checks and pixel-center polygon rasterization."""

from collections import defaultdict

import numpy as np
from pydicom.uid import RTStructureSetStorage

from lungseg.data.dicom_geometry import DataIssue, required


def roi_catalog(dataset) -> list[dict]:
    result = []
    observations = defaultdict(list)
    for observation in getattr(dataset, "RTROIObservationsSequence", []):
        observations[int(observation.ReferencedROINumber)].append(str(getattr(observation, "RTROIInterpretedType", "")))
    for roi in getattr(dataset, "StructureSetROISequence", []):
        result.append({"number": int(roi.ROINumber), "name": str(roi.ROIName),
                       "frame_uid": str(getattr(roi, "ReferencedFrameOfReferenceUID", "")),
                       "interpreted_types": observations[int(roi.ROINumber)]})
    if len({r["number"] for r in result}) != len(result):
        raise DataIssue("duplicate_roi_numbers")
    return result


def rt_references(dataset) -> dict:
    if str(required(dataset, "SOPClassUID")) != str(RTStructureSetStorage) or str(required(dataset, "Modality")) != "RTSTRUCT":
        raise DataIssue("not_rtstruct")
    frames, studies, series, sops = set(), set(), set(), set()
    for frame in getattr(dataset, "ReferencedFrameOfReferenceSequence", []):
        frames.add(str(frame.FrameOfReferenceUID))
        for study in getattr(frame, "RTReferencedStudySequence", []):
            studies.add(str(study.ReferencedSOPInstanceUID))
            for item in getattr(study, "RTReferencedSeriesSequence", []):
                series.add(str(item.SeriesInstanceUID))
                sops.update(str(image.ReferencedSOPInstanceUID) for image in getattr(item, "ContourImageSequence", []))
    if not series or not frames:
        raise DataIssue("missing_rtstruct_series_or_frame_reference")
    return {"frames": sorted(frames), "studies": sorted(studies), "series": sorted(series), "sop_uids": sorted(sops)}


def choose_rtstruct(candidates: list, selected_sop_uid: str | None = None):
    if selected_sop_uid:
        candidates = [ds for ds in candidates if str(ds.SOPInstanceUID) == selected_sop_uid]
    if len(candidates) != 1:
        raise DataIssue("ambiguous_or_missing_rtstruct", f"candidate_count={len(candidates)}")
    return candidates[0]


def choose_referenced_series(dataset, series_groups: dict[str, list]):
    references = rt_references(dataset)
    if len(references["series"]) != 1:
        raise DataIssue("unsupported_multiseries_rtstruct", "Explicit review needed; never choose largest series")
    uid = references["series"][0]
    if uid not in series_groups:
        raise DataIssue("referenced_ct_series_unavailable")
    return uid, series_groups[uid]


def select_primary_roi(dataset, accepted_names: list[str], override: int | None = None,
                       accepted_interpreted_types: list[str] | None = None) -> dict:
    rois = roi_catalog(dataset)
    if override is not None:
        candidates = [roi for roi in rois if roi["number"] == override]
    else:
        accepted = {name.strip().casefold() for name in accepted_names}
        candidates = [roi for roi in rois if roi["name"].strip().casefold() in accepted]
    if not candidates:
        raise DataIssue("primary_tumor_roi_not_identified", "Keep annotation; do not create an empty mask")
    if len(candidates) != 1:
        raise DataIssue("ambiguous_primary_tumor_roi")
    chosen = candidates[0]
    types = {name.upper() for name in chosen["interpreted_types"] if name}
    if types and not types.issubset(accepted_interpreted_types or ["GTV"]):
        raise DataIssue("primary_roi_interpreted_type_conflict", ",".join(sorted(types)))
    return chosen


def validate_rt_ct_identity(dataset, geometry, roi: dict) -> dict:
    refs = rt_references(dataset)
    if str(required(dataset, "PatientID")) != geometry.patient_id:
        raise DataIssue("rt_ct_patient_mismatch")
    if str(required(dataset, "StudyInstanceUID")) != geometry.study_uid or refs["studies"] != [geometry.study_uid]:
        raise DataIssue("rt_ct_study_mismatch")
    if refs["series"] != [geometry.series_uid]:
        raise DataIssue("rt_ct_series_mismatch")
    if refs["frames"] != [geometry.frame_uid] or roi["frame_uid"] != geometry.frame_uid:
        raise DataIssue("rt_ct_frame_mismatch")
    if hasattr(dataset, "FrameOfReferenceUID") and str(dataset.FrameOfReferenceUID) != geometry.frame_uid:
        raise DataIssue("rt_ct_frame_mismatch")
    if not set(refs["sop_uids"]).issubset(geometry.sop_uids):
        raise DataIssue("rt_references_missing_ct_sop")
    return refs


def polygon_mask(vertices: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Even-odd interior plus inclusive boundaries at integer voxel centers.

    A keyhole's doubled channel is a contour path and therefore included (DICOM
    C.8.8.6.3). No subvoxel area weighting or supersampling is implied.
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    if vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) < 3 or not np.isfinite(vertices).all():
        raise DataIssue("invalid_polygon")
    if len(np.unique(vertices, axis=0)) < 3:
        raise DataIssue("degenerate_polygon")
    area = 0.5 * abs(np.dot(vertices[:, 0], np.roll(vertices[:, 1], -1)) - np.dot(vertices[:, 1], np.roll(vertices[:, 0], -1)))
    if area < 1e-8:
        raise DataIssue("zero_area_polygon")
    if (vertices < -0.5 - 1e-4).any() or (vertices[:, 0] > shape[0] - 0.5 + 1e-4).any() or (vertices[:, 1] > shape[1] - 0.5 + 1e-4).any():
        raise DataIssue("contour_outside_ct_grid")
    low = np.maximum(np.ceil(vertices.min(axis=0)).astype(int), 0)
    high = np.minimum(np.floor(vertices.max(axis=0)).astype(int), np.array(shape) - 1)
    output = np.zeros(shape, dtype=bool)
    if (low > high).any():
        raise DataIssue("contour_has_no_voxel_centers")
    x, y = np.meshgrid(np.arange(low[0], high[0]+1), np.arange(low[1], high[1]+1), indexing="ij")
    inside, boundary = np.zeros(x.shape, bool), np.zeros(x.shape, bool)
    for start, end in zip(vertices, np.roll(vertices, -1, axis=0)):
        dx, dy = end - start
        length2 = dx*dx + dy*dy
        if length2 < 1e-20:
            continue
        cross = (x - start[0])*dy - (y - start[1])*dx
        dot = (x - start[0])*dx + (y - start[1])*dy
        boundary |= (np.abs(cross) <= 1e-7 * max(1, np.sqrt(length2))) & (dot >= -1e-7) & (dot <= length2+1e-7)
        if abs(dy) > 1e-15:
            crossing = ((start[1] > y) != (end[1] > y)) & (x < start[0] + (y - start[1])*dx/dy)
            inside ^= crossing
    output[low[0]:high[0]+1, low[1]:high[1]+1] = inside | boundary
    return output


def rasterize_roi(dataset, geometry, roi: dict, config) -> tuple[np.ndarray, dict]:
    refs = validate_rt_ct_identity(dataset, geometry, roi)
    groups = [item for item in getattr(dataset, "ROIContourSequence", []) if int(item.ReferencedROINumber) == roi["number"]]
    if len(groups) != 1:
        raise DataIssue("ambiguous_or_missing_roi_contour_sequence")
    contours = list(getattr(groups[0], "ContourSequence", []))
    if not contours:
        raise DataIssue("selected_roi_has_no_contours")
    types = {str(contour.ContourGeometricType) for contour in contours}
    if not types.issubset({"CLOSED_PLANAR", "CLOSEDPLANAR_XOR"}) or len(types) != 1:
        raise DataIssue("unsupported_or_mixed_contour_types", ",".join(sorted(types)))
    # Slab/source-grid semantics require an explicit implementation; do not guess.
    if getattr(groups[0], "SourcePixelPlanesCharacteristicsSequence", []):
        raise DataIssue("unsupported_source_pixel_planes_characteristics")
    mask = np.zeros(geometry.shape, dtype=np.uint8)
    contour_log = []
    per_slice_polygons = defaultdict(list)
    sop_index = {uid: index for index, uid in enumerate(geometry.sop_uids)}
    for index, contour in enumerate(contours):
        if hasattr(contour, "ContourSlabThickness") or hasattr(contour, "ContourOffsetVector"):
            raise DataIssue("unsupported_contour_slab_or_offset")
        points = np.asarray(required(contour, "ContourData"), dtype=float)
        count = int(required(contour, "NumberOfContourPoints"))
        if points.size != 3 * count or count < 3:
            raise DataIssue("contour_point_count_mismatch")
        points = points.reshape(-1, 3)
        voxels = geometry.world_to_voxel(points)
        distances = points @ geometry.normal
        if np.ptp(distances) > config.contour_plane_tolerance_mm:
            raise DataIssue("nonplanar_contour")
        nearest = int(round(float(voxels[:, 2].mean())))
        if not 0 <= nearest < geometry.shape[2]:
            raise DataIssue("contour_plane_outside_ct")
        error = float(np.max(np.abs((voxels[:, 2] - nearest) * geometry.slice_spacing_mm)))
        if error > config.contour_plane_tolerance_mm:
            raise DataIssue("contour_does_not_match_slice_plane", f"distance_mm={error:.6g}")
        references = [str(item.ReferencedSOPInstanceUID) for item in getattr(contour, "ContourImageSequence", [])]
        if references and (len(set(references)) != 1 or references[0] not in sop_index or sop_index[references[0]] != nearest):
            raise DataIssue("contour_sop_reference_mismatch")
        try:
            polygon = polygon_mask(voxels[:, :2], geometry.shape[:2])
        except DataIssue as exc:
            raise DataIssue(exc.code, f"contour_index={index}; slice_index={nearest}; {exc.detail}") from exc
        if "CLOSEDPLANAR_XOR" in types:
            mask[:, :, nearest] ^= polygon.astype(np.uint8)
        else:
            # Distinct closed contours use union. Separate nested CLOSED_PLANAR
            # rings have ambiguous hole intent: require XOR or a keyhole instead.
            for previous in per_slice_polygons[nearest]:
                if (polygon & previous).any() and ((polygon & ~previous).any() != (previous & ~polygon).any()):
                    raise DataIssue("ambiguous_nested_closed_planar_contours")
            mask[:, :, nearest] |= polygon.astype(np.uint8)
            per_slice_polygons[nearest].append(polygon)
        contour_log.append({"index": index, "slice_index": nearest, "point_count": count,
                            "referenced_sop_uids": references, "plane_error_mm": error})
    if not mask.any():
        raise DataIssue("rasterized_primary_roi_is_empty")
    return mask, {"roi": roi, "references": refs, "contour_type": next(iter(types)),
                  "contours": contour_log, "rasterization_rule": "integer voxel centers; even-odd interior, inclusive boundary; union CLOSED_PLANAR, XOR CLOSEDPLANAR_XOR",
                  "contour_count": len(contours), "source_contours_preserved": True}
