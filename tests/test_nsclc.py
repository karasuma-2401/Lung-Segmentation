"""Synthetic DICOM/RTSTRUCT fixtures ONLY; not NSCLC experimental evidence."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
from io import BytesIO
import json
from pathlib import Path
import zipfile

import nibabel as nib
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, RTStructureSetStorage, ExplicitVRLittleEndian
import pytest

from lungseg.data.dicom_geometry import DataIssue, build_ct_geometry, read_ct_pixels
from lungseg.data.nsclc import convert_sample, survey
from lungseg.data.nsclc_acquire import capacity_plan, safe_zip_members, validate_catalog, LICENSE_URL
from lungseg.data.nsclc_config import NsclcConfig, load_nsclc_config
from lungseg.data.rtstruct import (choose_referenced_series, choose_rtstruct, polygon_mask,
    rasterize_roi, roi_catalog, select_primary_roi)
from lungseg.data.msd_acquire import file_sha256
from lungseg.runs import write_json

STUDY, SERIES, FRAME, RTSERIES = "1.2.3.1", "1.2.3.2", "1.2.3.3", "1.2.3.4"


@pytest.fixture
def config(tmp_path):
    base = load_nsclc_config("configs/nsclc.yaml")
    return replace(base, raw_root=str(tmp_path / "raw"), converted_root=str(tmp_path / "converted"),
                   output_dir=str(tmp_path / "manifest"), qa_dir=str(tmp_path / "qa"),
                   evidence_dir=str(tmp_path / "evidence"), sample_patient_ids=["LUNG1-001"])


def file_dataset(sop_class, sop_uid):
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID = sop_class, sop_uid
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID, ds.SOPInstanceUID = sop_class, sop_uid
    ds.PatientID, ds.StudyInstanceUID, ds.FrameOfReferenceUID = "LUNG1-001", STUDY, FRAME
    return ds


def ct_headers(n=4, oblique=False):
    angle = np.pi / 6 if oblique else 0
    x, y = np.array([np.cos(angle), 0, np.sin(angle)]), np.array([0., 1., 0.])
    normal = np.cross(x, y)
    result = []
    for k in range(n):
        ds = file_dataset(CTImageStorage, f"1.2.3.10.{k+1}")
        ds.Modality, ds.SeriesInstanceUID = "CT", SERIES
        ds.Rows, ds.Columns = 12, 12
        ds.ImageOrientationPatient = list(x) + list(y)
        ds.ImagePositionPatient = (np.array([10., 20., 30.]) + normal * 3 * k).tolist()
        ds.PixelSpacing, ds.SpacingBetweenSlices, ds.SliceThickness = [2., 1.5], 3., 7.
        ds.InstanceNumber = 100-k  # deliberately conflicts with physical ordering
        ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
        ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 16, 15, 1
        ds.RescaleSlope, ds.RescaleIntercept, ds.RescaleType = 2., -1000., "HU"
        ds.PixelData = np.full((12, 12), k+1, dtype="<i2").tobytes()
        result.append(ds)
    return result


def item(**values):
    ds = Dataset()
    for key, value in values.items():
        setattr(ds, key, value)
    return ds


def rtstruct(geometry, polygons=None, kind="CLOSED_PLANAR", names=None):
    ds = file_dataset(RTStructureSetStorage, "1.2.3.20.1")
    ds.Modality, ds.SeriesInstanceUID = "RTSTRUCT", RTSERIES
    ds.ReferencedFrameOfReferenceSequence = [item(FrameOfReferenceUID=FRAME, RTReferencedStudySequence=[
        item(ReferencedSOPInstanceUID=STUDY, RTReferencedSeriesSequence=[item(SeriesInstanceUID=SERIES,
            ContourImageSequence=[item(ReferencedSOPInstanceUID=uid, ReferencedSOPClassUID=CTImageStorage) for uid in geometry.sop_uids])])])]
    names = names or ["GTV-1", "Lung-Left"]
    ds.StructureSetROISequence = [item(ROINumber=i+1, ROIName=name, ReferencedFrameOfReferenceUID=FRAME) for i, name in enumerate(names)]
    ds.RTROIObservationsSequence = [item(ReferencedROINumber=i+1, ObservationNumber=i+1, RTROIInterpretedType="GTV" if i == 0 else "ORGAN") for i in range(len(names))]
    polygons = polygons or [np.array([[2., 2.], [4., 2.], [4., 4.], [2., 4.]])]
    contours = []
    for polygon in polygons:
        voxels = np.column_stack([polygon, np.ones(len(polygon)), np.ones(len(polygon))])
        points = (geometry.affine_lps @ voxels.T).T[:, :3]
        contours.append(item(ContourGeometricType=kind, NumberOfContourPoints=len(points), ContourData=points.ravel().tolist(),
                             ContourImageSequence=[item(ReferencedSOPInstanceUID=geometry.sop_uids[1], ReferencedSOPClassUID=CTImageStorage)]))
    ds.ROIContourSequence = [item(ReferencedROINumber=1, ContourSequence=contours)]
    return ds


def write_sources(config, headers, rt):
    for datasets, modality, series in ((headers, "CT", SERIES), ([rt], "RTSTRUCT", RTSERIES)):
        folder = Path(config.raw_root) / "dicom" / "LUNG1-001" / series
        folder.mkdir(parents=True)
        objects = []
        for ds in datasets:
            path = folder / f"{ds.SOPInstanceUID}.dcm"
            ds.save_as(path, enforce_file_format=True)
            objects.append({"sop_uid": str(ds.SOPInstanceUID), "sha256": file_sha256(path)})
        write_json(folder / "source.json", {"synthetic": True, "series_uid": series, "study_uid": STUDY,
            "modality": modality, "public_patient_id": "LUNG1-001", "license_url": LICENSE_URL, "objects": objects})


def test_ordering_oblique_lps_ras_world_mapping(config, tmp_path):
    headers = ct_headers(oblique=True)
    shuffled = [headers[i] for i in (2, 0, 3, 1)]
    geometry = build_ct_geometry(shuffled, config)
    assert geometry.sorted_indices == [1, 3, 0, 2]
    assert geometry.shape == (12, 12, 4)
    np.testing.assert_allclose(geometry.affine_ras, np.diag([-1,-1,1,1]) @ geometry.affine_lps)
    voxel = np.array([[3., 5., 2.]])
    world = (geometry.affine_lps @ np.c_[voxel, [1.]].T).T[:, :3]
    np.testing.assert_allclose(geometry.world_to_voxel(world), voxel, atol=1e-12)
    paths = []
    for i, ds in enumerate(shuffled):
        path = tmp_path / f"filename_{3-i}.dcm"
        ds.save_as(path, enforce_file_format=True)
        paths.append(path)
    volume, transforms = read_ct_pixels(paths, geometry)
    assert volume.dtype == np.float32
    np.testing.assert_array_equal(volume[0,0,:], [-998,-996,-994,-992])
    assert transforms[0]["slope"] == 2


@pytest.mark.parametrize("mutation,reason", [
    ("duplicate_uid", "duplicate_sop"), ("duplicate_position", "duplicate_or_overlapping"),
    ("missing", "missing_slices_or_nonuniform"), ("nonuniform", "missing_slices_or_nonuniform"),
    ("orientation", "inconsistent_slice_orientation"), ("spacing", "inconsistent_pixel_spacing"),
    ("frame", "mixed_ct_identity"), ("declared_gap", "declared_slice_spacing_mismatch"),
    ("missing_iop", "missing_dicom_attribute"), ("multiframe", "unsupported_multiframe"),
    ("nan_iop", "invalid_image_orientation")])
def test_bad_ct_geometry(config, mutation, reason):
    headers = ct_headers()
    if mutation == "duplicate_uid": headers[1].SOPInstanceUID = headers[0].SOPInstanceUID
    if mutation == "duplicate_position": headers[1].ImagePositionPatient = headers[0].ImagePositionPatient
    if mutation == "missing": headers.pop(1)
    if mutation == "nonuniform": headers[-1].ImagePositionPatient[2] += 1
    if mutation == "orientation": headers[1].ImageOrientationPatient = [0,1,0,1,0,0]
    if mutation == "spacing": headers[1].PixelSpacing = [2., 3.]
    if mutation == "frame": headers[1].FrameOfReferenceUID = "1.2.999"
    if mutation == "declared_gap": headers[0].SpacingBetweenSlices = 6
    if mutation == "missing_iop": del headers[0].ImageOrientationPatient
    if mutation == "multiframe": headers[0].NumberOfFrames = 2
    if mutation == "nan_iop": headers[0].ImageOrientationPatient[0] = float("nan")
    with pytest.raises(DataIssue, match=reason): build_ct_geometry(headers, config)


def test_rt_selection_roi_and_references(config):
    geometry = build_ct_geometry(ct_headers(), config)
    rt = rtstruct(geometry)
    assert choose_referenced_series(rt, {SERIES: [1], "1.9": list(range(99))}) == (SERIES, [1])
    assert select_primary_roi(rt, ["gtv-1"])["number"] == 1
    with pytest.raises(DataIssue, match="referenced_ct_series_unavailable"): choose_referenced_series(rt, {})
    with pytest.raises(DataIssue, match="ambiguous_or_missing_rtstruct"): choose_rtstruct([rt, rt])
    with pytest.raises(DataIssue, match="primary_tumor_roi_not_identified"): select_primary_roi(rt, ["missing"])
    rt.StructureSetROISequence.append(item(ROINumber=3, ROIName="gtv-1", ReferencedFrameOfReferenceUID=FRAME))
    with pytest.raises(DataIssue, match="ambiguous_primary"): select_primary_roi(rt, ["GTV-1"])
    assert select_primary_roi(rt, ["GTV-1"], override=1)["number"] == 1
    rt.RTROIObservationsSequence[0].RTROIInterpretedType = "ORGAN"
    with pytest.raises(DataIssue, match="interpreted_type_conflict"): select_primary_roi(rt, [], override=1)
    assert select_primary_roi(rt, [], override=1, accepted_interpreted_types=["ORGAN"])["number"] == 1


@pytest.mark.parametrize("mutation,reason", [("frame", "rt_ct_frame_mismatch"), ("series", "rt_ct_series_mismatch"),
    ("patient", "rt_ct_patient_mismatch"), ("study", "rt_ct_study_mismatch"),
    ("sop", "contour_sop_reference_mismatch"), ("global_sop", "rt_references_missing_ct_sop"),
    ("plane", "contour_does_not_match_slice_plane"), ("nonplanar", "nonplanar_contour"),
    ("open", "unsupported_or_mixed_contour_types"), ("count", "contour_point_count_mismatch"),
    ("slab", "unsupported_contour_slab"), ("source_grid", "unsupported_source_pixel_planes")])
def test_invalid_rt_rejected(config, mutation, reason):
    geometry = build_ct_geometry(ct_headers(), config)
    rt = rtstruct(geometry)
    contour = rt.ROIContourSequence[0].ContourSequence[0]
    if mutation == "frame": rt.ReferencedFrameOfReferenceSequence[0].FrameOfReferenceUID = "1.9"
    if mutation == "series": rt.ReferencedFrameOfReferenceSequence[0].RTReferencedStudySequence[0].RTReferencedSeriesSequence[0].SeriesInstanceUID = "1.9"
    if mutation == "patient": rt.PatientID = "LUNG1-002"
    if mutation == "study": rt.StudyInstanceUID = "1.9"
    if mutation == "sop": contour.ContourImageSequence[0].ReferencedSOPInstanceUID = geometry.sop_uids[2]
    if mutation == "global_sop": rt.ReferencedFrameOfReferenceSequence[0].RTReferencedStudySequence[0].RTReferencedSeriesSequence[0].ContourImageSequence[0].ReferencedSOPInstanceUID = "1.9"
    if mutation in {"plane", "nonplanar"}:
        for i in (range(2,12,3) if mutation == "plane" else [2]): contour.ContourData[i] += 1
    if mutation == "open": contour.ContourGeometricType = "OPEN_PLANAR"
    if mutation == "count": contour.NumberOfContourPoints = 99
    if mutation == "slab": contour.ContourSlabThickness = 1
    if mutation == "source_grid": rt.ROIContourSequence[0].SourcePixelPlanesCharacteristicsSequence = [Dataset()]
    with pytest.raises(DataIssue, match=reason): rasterize_roi(rt, geometry, roi_catalog(rt)[0], config)


def test_rasterize_multiple_contours_xor_and_volume(config):
    geometry = build_ct_geometry(ct_headers(oblique=True), config)
    a = np.array([[1.,1.],[3.,1.],[3.,3.],[1.,3.]])
    b = a + 5
    mask, _ = rasterize_roi(rtstruct(geometry, [a,b]), geometry, {"number":1,"frame_uid":FRAME}, config)
    assert mask.sum() == 18
    assert mask.sum() * abs(np.linalg.det(geometry.affine_ras[:3,:3])) == pytest.approx(162)
    outer = np.array([[1.,1.],[9.,1.],[9.,9.],[1.,9.]])
    inner = np.array([[4.,4.],[6.,4.],[6.,6.],[4.,6.]])
    xor, _ = rasterize_roi(rtstruct(geometry, [outer,inner], "CLOSEDPLANAR_XOR"), geometry, {"number":1,"frame_uid":FRAME}, config)
    assert xor.sum() == 72
    assert xor[5,5,1] == 0 and xor[2,2,1] == 1
    with pytest.raises(DataIssue, match="ambiguous_nested"): rasterize_roi(rtstruct(geometry,[outer,inner]), geometry, {"number":1,"frame_uid":FRAME}, config)


def test_keyhole_and_invalid_polygons():
    keyhole = np.array([[1,1],[9,1],[9,9],[1,9],[1,1],[4,4],[4,6],[6,6],[6,4],[4,4],[1,1]], float)
    mask = polygon_mask(keyhole, (12,12))
    assert not mask[5,5] and mask[2,2] and mask[4,4] and mask[8,8]
    for invalid in (np.array([[1,1],[2,2],[3,3]]), np.array([[-1,0],[2,0],[2,2]]), np.array([[0,0],[1,np.nan],[1,2]])):
        with pytest.raises(DataIssue): polygon_mask(invalid, (12,12))


def test_conversion_manifest_determinism_and_raw_preservation(config):
    headers = ct_headers()
    write_sources(config, headers, rtstruct(build_ct_geometry(headers, config)))
    raw_before = {p: file_sha256(p) for p in Path(config.raw_root).rglob("*") if p.is_file()}
    result = convert_sample(config, synthetic=True)
    assert not result["real_data"] and result["converted_cases"] == 1
    manifest = Path(config.output_dir) / "manifest_nsclc.csv"
    before = manifest.read_bytes()
    convert_sample(config, synthetic=True)
    assert manifest.read_bytes() == before
    ct = nib.load(Path(config.converted_root) / "LUNG1-001/ct.nii.gz")
    mask = nib.load(Path(config.converted_root) / "LUNG1-001/mask.nii.gz")
    np.testing.assert_allclose(ct.affine, mask.affine)
    assert np.asanyarray(mask.dataobj).sum() == 9
    assert result["tumor_volume_mm3"]["min"] == pytest.approx(81)
    assert {p: file_sha256(p) for p in raw_before} == raw_before
    assert survey(config, synthetic=True)["roi_name_counts"]["GTV-1"] == 1
    # Fixtures cannot be exported as real acquisition evidence.
    unverified = convert_sample(config)
    assert unverified["converted_cases"] == 0 and unverified["real_data"] is None
    assert survey(config)["real_data"] is None


def test_missing_primary_no_fake_empty_mask(config):
    headers = ct_headers()
    write_sources(config, headers, rtstruct(build_ct_geometry(headers, config), names=["gtv-pre-op"]))
    result = convert_sample(config, synthetic=True)
    assert result["quarantined_cases"] == 1
    assert not list(Path(config.converted_root).rglob("*.nii.gz"))


def test_tampered_raw_quarantined(config):
    headers = ct_headers()
    write_sources(config, headers, rtstruct(build_ct_geometry(headers, config)))
    next(Path(config.raw_root).rglob("*.dcm")).write_bytes(b"tampered")
    report = convert_sample(config, synthetic=True)
    assert report["quarantined_cases"] == 1
    assert "raw_checksum_mismatch" in report["quarantine"][0]["reasons"]


def test_capacity_catalog_and_archive_safety(config, monkeypatch):
    import lungseg.data.nsclc_acquire as module
    rows = [{"Collection":"NSCLC-Radiomics", "LicenseURI":LICENSE_URL, "PatientID":"LUNG1-001",
             "StudyInstanceUID":STUDY, "SeriesInstanceUID":SERIES, "Modality":"CT", "FileSize":10**10, "ImageCount":20}]
    catalog = validate_catalog(rows)
    monkeypatch.setattr(module, "require_space", lambda *args: 45 * 1024**3)
    plan = capacity_plan(config, catalog)
    assert not plan["full_capacity_pass"] and plan["full_download_status"] == "BLOCKED_STORAGE"
    with pytest.raises(ValueError, match="Duplicate"): validate_catalog(rows*2)
    rows[0]["LicenseURI"] = "other"
    with pytest.raises(ValueError, match="license changed"): validate_catalog(rows)
    for filename in ("../escape.dcm", "/absolute.dcm", "C:/escape.dcm", "a\\b.dcm"):
        data = BytesIO()
        entry = zipfile.ZipInfo("placeholder")
        entry.filename = filename  # preserve hostile backslashes, including on Windows
        with zipfile.ZipFile(data,"w") as archive: archive.writestr(entry,b"x")
        with zipfile.ZipFile(data) as archive:
            with pytest.raises(ValueError, match="Unsafe"): safe_zip_members(archive,100)


def test_configuration_disjoint_paths(config):
    value = asdict(config)
    value["converted_root"] = value["raw_root"]
    with pytest.raises(ValueError, match="separate"): NsclcConfig.from_dict(value)


def test_modality_lut_intensity(config, tmp_path):
    headers = ct_headers()
    paths = []
    for i, ds in enumerate(headers):
        lut = item(LUTDescriptor=[5,0,16], ModalityLUTType="HU")
        lut.add_new((0x0028,0x3006), "US", [0,10,20,30,40])
        ds.ModalityLUTSequence = [lut]
        path = tmp_path / f"{i}.dcm"
        ds.save_as(path, enforce_file_format=True)
        paths.append(path)
    array, transforms = read_ct_pixels(paths, build_ct_geometry(headers, config))
    np.testing.assert_array_equal(array[0,0], [10,20,30,40])
    assert transforms[0]["kind"] == "ModalityLUTSequence"


def test_acquisition_insufficient_capacity_prevents_network_download(config, monkeypatch):
    import lungseg.data.nsclc_acquire as module
    rows = [{"PatientID":"LUNG1-001", "StudyInstanceUID":STUDY, "SeriesInstanceUID":SERIES,
             "Modality":"CT", "FileSize":100, "ImageCount":4}]
    monkeypatch.setattr(module, "fetch_catalog", lambda: rows)
    monkeypatch.setattr(module, "require_space", lambda *args: 0)
    def forbidden(*args): raise AssertionError("No DICOM request should occur")
    monkeypatch.setattr(module, "download_series", forbidden)
    with pytest.raises(OSError, match="capacity check failed"): module.acquire_sample(config, download=True)


def test_safe_idc_listing_rejects_unofficial_hosts():
    from lungseg.data.nsclc_idc import list_objects
    for url in ("https://evil.invalid/data", "s3://unofficial/123/*", "s3://idc-open-data/../../secret/*"):
        with pytest.raises(ValueError, match="official IDC"): list_objects(url)


def test_real_origin_cannot_accept_untrusted_idc_catalog(tmp_path):
    from lungseg.data.nsclc_idc import load_idc_catalog
    path = tmp_path / "mirror.json"
    write_json(path, {"source":"unofficial", "index_sha256":"a"*64, "series":[]})
    with pytest.raises(ValueError, match="official IDC"): load_idc_catalog(path)


def test_shear_preserved_without_approximated_qform(config, tmp_path):
    from lungseg.data.nsclc import save_nifti
    headers = ct_headers()
    for i, ds in enumerate(headers): ds.ImagePositionPatient[0] += i * .5
    geometry = build_ct_geometry(headers, config)
    path = tmp_path / "shear.nii.gz"
    save_nifti(path, np.zeros(geometry.shape, np.uint8), geometry.affine_ras)
    image = nib.load(path)
    np.testing.assert_allclose(image.affine, geometry.affine_ras)
    assert image.header["qform_code"] == 0 and image.header["sform_code"] == 1


@pytest.mark.parametrize("failure", [None, "md5", "header", "count", "size"])
def test_idc_object_integrity_and_safe_failure(config, monkeypatch, failure):
    import lungseg.data.nsclc_idc as module
    ds = ct_headers()[0]
    if failure == "header": ds.PatientID = "LUNG1-002"
    buffer = BytesIO()
    ds.save_as(buffer, enforce_file_format=True)
    raw = buffer.getvalue()
    record = {"PatientID":"LUNG1-001", "StudyInstanceUID":STUDY, "SeriesInstanceUID":SERIES,
              "Modality":"CT", "FileSize":len(raw), "ImageCount":1}
    mirror = {SERIES:{**record, "instanceCount":1, "series_aws_url":"s3://idc-open-data/unused/*", "source_DOI":"test_fixture"}}
    objects = [{"key":"fixture.dcm", "bytes":len(raw), "md5":hashlib.md5(raw).hexdigest()}]
    if failure == "md5": objects[0]["md5"] = "0"*32
    if failure == "size": objects[0]["bytes"] = len(raw)+1
    if failure == "count": objects = []
    monkeypatch.setattr(module, "list_objects", lambda url:("https://fixture.invalid/", objects))
    monkeypatch.setattr(module, "urlopen", lambda *a,**kw:BytesIO(raw))
    root = Path(config.raw_root)
    if failure:
        with pytest.raises(ValueError): module.download_idc_series(record, mirror, root)
        assert not (root / "dicom/LUNG1-001" / SERIES).exists()
    else:
        result = module.download_idc_series(record, mirror, root)
        assert result["objects"][0]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert module.download_idc_series(record, mirror, root) == result
        # Verified existing raw cannot be silently replaced after tampering.
        path = root / "dicom/LUNG1-001" / SERIES / f"{ds.SOPInstanceUID}.dcm"
        path.write_bytes(b"changed")
        with pytest.raises(ValueError, match="hash mismatch"): module.download_idc_series(record, mirror, root)


def test_fixed_axis_spacing_affine_not_just_roundtrip(config):
    geometry = build_ct_geometry(ct_headers(), config)
    np.testing.assert_array_equal(geometry.affine_lps, [[1.5,0,0,10],[0,2,0,20],[0,0,3,30],[0,0,0,1]])
    np.testing.assert_array_equal(geometry.affine_ras, [[-1.5,0,0,-10],[0,-2,0,-20],[0,0,3,30],[0,0,0,1]])
