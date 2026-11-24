"""Public NBIA metadata, capacity planning and bounded sample downloads only."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from urllib.parse import urlencode
from urllib.request import urlopen
import zipfile

import pydicom

from lungseg.data.msd_acquire import file_sha256, require_space
from lungseg.runs import utc_now, write_json

API_BASE = "https://services.cancerimagingarchive.net/nbia-api/services/v1/"
COLLECTION_URL = "https://www.cancerimagingarchive.net/collection/nsclc-radiomics/"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc/3.0/"
CATALOG_FIELDS = ("PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Modality", "ImageCount", "FileSize",
                  "Collection", "CollectionURI", "LicenseName", "LicenseURI", "DateReleased")


def api_url(endpoint: str, **parameters) -> str:
    if endpoint not in {"getSeries", "getImageWithMD5Hash", "getSeriesSize"}:
        raise ValueError("Unsupported NBIA endpoint")
    return API_BASE + endpoint + "?" + urlencode(parameters)


def fetch_catalog() -> list[dict]:
    with urlopen(api_url("getSeries", Collection="NSCLC-Radiomics", format="json"), timeout=60) as response:
        data = json.load(response)
    return validate_catalog(data)


def validate_catalog(data) -> list[dict]:
    if not isinstance(data, list) or not data:
        raise ValueError("NBIA returned no NSCLC series")
    result = []
    for entry in data:
        if entry.get("Collection") != "NSCLC-Radiomics" or entry.get("LicenseURI") != LICENSE_URL:
            raise ValueError("Catalog collection/license changed; review source before download")
        if not re.fullmatch(r"LUNG1-\d{3}", entry.get("PatientID", "")):
            raise ValueError("Unexpected non-public patient identifier in catalog; do not export")
        for key in ("SeriesInstanceUID", "StudyInstanceUID"):
            if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", entry.get(key, "")):
                raise ValueError("Catalog has invalid UIDs")
        item = {key: entry.get(key) for key in CATALOG_FIELDS}
        for key in ("FileSize", "ImageCount"):
            item[key] = int(item[key])
            if item[key] <= 0:
                raise ValueError("Catalog must provide positive size and image count")
        result.append(item)
    if len({r["SeriesInstanceUID"] for r in result}) != len(result):
        raise ValueError("Duplicate series UIDs in catalog")
    return sorted(result, key=lambda row: (row["PatientID"], row["Modality"], row["SeriesInstanceUID"]))


def capacity_plan(config, catalog: list[dict]) -> dict:
    modalities = {m: {"series": sum(r["Modality"] == m for r in catalog),
                      "bytes": sum(r["FileSize"] for r in catalog if r["Modality"] == m),
                      "objects": sum(r["ImageCount"] for r in catalog if r["Modality"] == m)}
                  for m in sorted({r["Modality"] for r in catalog})}
    sample = [r for r in catalog if r["PatientID"] in config.sample_patient_ids and r["Modality"] in {"CT", "RTSTRUCT"}]
    found = {r["PatientID"] for r in sample}
    if found != set(config.sample_patient_ids):
        raise ValueError("A requested sample patient is absent from current catalog")
    full_raw = sum(r["FileSize"] for r in catalog if r["Modality"] in {"CT", "RTSTRUCT"})
    sample_raw = sum(r["FileSize"] for r in sample)
    full_ct = modalities.get("CT", {}).get("bytes", 0)
    sample_ct = sum(r["FileSize"] for r in sample if r["Modality"] == "CT")
    # Keep archives + raw. Conversion allowance estimates float32 CT + uint8 masks
    # versus usual 16-bit CT, plus metadata; not a measured compressed-output size.
    full_required = 2 * full_raw + int(2.5 * full_ct) + config.reserve_bytes
    sample_required = 2 * sample_raw + int(2.5 * sample_ct) + config.reserve_bytes
    free = require_space(Path(config.raw_root), 0)
    converted_free = require_space(Path(config.converted_root), 0)
    same_device = Path(config.raw_root).resolve().anchor.lower() == Path(config.converted_root).resolve().anchor.lower()
    sample_ok = free >= sample_required if same_device else free >= 2 * sample_raw + config.reserve_bytes and converted_free >= int(2.5 * sample_ct) + config.reserve_bytes
    full_ok = free >= full_required if same_device else free >= 2 * full_raw + config.reserve_bytes and converted_free >= int(2.5 * full_ct) + config.reserve_bytes
    report = {"timestamp_utc": utc_now(), "collection": "NSCLC-Radiomics", "source": COLLECTION_URL,
              "api_url": api_url("getSeries", Collection="NSCLC-Radiomics", format="json"),
              "license": "CC-BY-NC-3.0", "license_url": LICENSE_URL,
              "catalog_patients": len({r["PatientID"] for r in catalog}),
              "catalog_studies": len({r["StudyInstanceUID"] for r in catalog}), "catalog_series": len(catalog),
              "modalities": modalities, "full_ct_rtstruct_raw_bytes": full_raw,
              "sample_patient_ids": config.sample_patient_ids, "sample_series": len(sample), "sample_raw_bytes": sample_raw,
              "full_planning_bytes": full_required, "sample_planning_bytes": sample_required,
              "full_idc_without_zip_planning_bytes": full_raw + int(2.5 * full_ct) + config.reserve_bytes,
              "raw_disk_free_bytes": free, "converted_disk_free_bytes": converted_free,
              "same_volume": same_device, "sample_capacity_pass": sample_ok,
              "full_capacity_pass": full_ok, "full_download_status": "not_authorized_before_sample_QA" if full_ok else "BLOCKED_STORAGE",
              "conversion_estimate": "planning allowance 2.5x CT DICOM bytes, not measured gzip size or a guarantee for other transfer syntaxes",
              "config_sha256": config.sha256, "scope": "sample only; full collection metadata is not full corpus validation"}
    output = Path(config.output_dir)
    write_json(output / "public_catalog.json", {"source": report["api_url"], "license_url": LICENSE_URL,
                                               "recorded_at": report["timestamp_utc"], "series": catalog})
    write_json(Path(config.evidence_dir) / "capacity_plan.json", report)
    return report


def safe_zip_members(archive: zipfile.ZipFile, maximum_bytes: int) -> list[zipfile.ZipInfo]:
    members = []
    seen = set()
    for info in archive.infolist():
        original = getattr(info, "orig_filename", info.filename)
        path = PurePosixPath(original)
        if path.is_absolute() or ".." in path.parts or "\\" in original or ":" in original:
            raise ValueError("Unsafe ZIP path")
        if info.filename.casefold() in seen or (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("Duplicate ZIP member or symbolic link")
        seen.add(info.filename.casefold())
        if not info.is_dir():
            members.append(info)
    if sum(info.file_size for info in members) > maximum_bytes:
        raise ValueError("ZIP expanded size exceeds catalog planning limit")
    return members


def md5_map(archive: zipfile.ZipFile, members: list[zipfile.ZipInfo]) -> dict[str, str]:
    csv_names = [info.filename for info in members if info.filename.lower().endswith(".csv")]
    if len(csv_names) != 1:
        raise ValueError("Expected exactly one NBIA MD5 CSV; inspect archive schema")
    rows = list(csv.DictReader(StringIO(archive.read(csv_names[0]).decode("utf-8-sig"))))
    if not rows:
        raise ValueError("Empty NBIA MD5 manifest")
    columns = {key.strip().lower(): key for key in rows[0]}
    # Fail closed on unknown CSV schemas; this NBIA adapter has not yet passed a real ZIP test.
    if "sopinstanceuid" not in columns or "md5hash" not in columns:
        raise ValueError(f"Unsupported NBIA MD5 columns: {sorted(columns)}")
    result = {}
    for row in rows:
        uid, digest = row[columns["sopinstanceuid"]].strip(), row[columns["md5hash"]].strip().lower()
        if uid in result or not re.fullmatch(r"[a-f0-9]{32}", digest):
            raise ValueError("Duplicate/invalid NBIA MD5 entry")
        result[uid] = digest
    return result


def download_series(record: dict, raw_root: Path) -> dict:
    uid = record["SeriesInstanceUID"]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", uid) or not re.fullmatch(r"LUNG1-\d{3}", record["PatientID"]):
        raise ValueError("Only verified public TCIA identifiers are accepted")
    destination = raw_root / "dicom" / record["PatientID"] / uid
    marker = destination / "source.json"
    if destination.exists():
        if not marker.exists():
            raise FileExistsError("Existing raw directory has no acquisition provenance")
        result = json.loads(marker.read_text())
        if (result.get("series_uid") != uid or result.get("study_uid") != record["StudyInstanceUID"]
                or result.get("public_patient_id") != record["PatientID"] or result.get("modality") != record["Modality"]
                or result.get("license_url") != LICENSE_URL or len(result["objects"]) != record["ImageCount"]):
            raise ValueError("Existing raw provenance disagrees with selected catalog")
        for item in result["objects"]:
            if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", item["sop_uid"]):
                raise ValueError("Invalid raw SOP UID")
            path = destination / (item["sop_uid"] + ".dcm")
            if file_sha256(path) != item["sha256"]:
                raise ValueError("Existing raw DICOM checksum mismatch; refusing overwrite")
        return result
    archives = raw_root / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    archive_path = archives / f"{uid}.zip"
    bound = int(record["FileSize"] * 1.05) + 2 * 1024**2
    url = api_url("getImageWithMD5Hash", SeriesInstanceUID=uid)
    if not archive_path.exists():
        temporary = archive_path.with_suffix(".zip.partial")
        with urlopen(url, timeout=120) as response, temporary.open("wb") as handle:
            while block := response.read(1024**2):
                if handle.tell() + len(block) > bound:
                    raise ValueError("Download exceeds bounded catalog size")
                handle.write(block)
        os.replace(temporary, archive_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    from uuid import uuid4
    stage = raw_root / "staging" / record["PatientID"] / (uid + ".extracting-" + uuid4().hex[:8])
    stage.mkdir(parents=True, exist_ok=False)
    objects = []
    with zipfile.ZipFile(archive_path) as archive:
        members = safe_zip_members(archive, bound)
        hashes = md5_map(archive, members)
        for member in members:
            if member.filename.lower().endswith((".csv", ".txt")):
                continue
            raw = archive.read(member)
            dataset = pydicom.dcmread(BytesIO(raw), stop_before_pixels=True)
            expected = {"PatientID": record["PatientID"], "StudyInstanceUID": record["StudyInstanceUID"],
                        "SeriesInstanceUID": uid, "Modality": record["Modality"]}
            if any(str(getattr(dataset, key, "")) != value for key, value in expected.items()):
                raise ValueError("Downloaded DICOM identifiers disagree with TCIA catalog")
            sop = str(dataset.SOPInstanceUID)
            if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", sop) or sop not in hashes:
                raise ValueError("DICOM SOP UID missing from MD5 manifest")
            if hashlib.md5(raw).hexdigest() != hashes[sop]:
                raise ValueError("DICOM MD5 does not match NBIA manifest")
            path = stage / f"{sop}.dcm"
            if path.exists():
                raise ValueError("Duplicate DICOM SOPInstanceUID in ZIP")
            path.write_bytes(raw)
            objects.append({"sop_uid": sop, "sha256": hashlib.sha256(raw).hexdigest(), "md5": hashes[sop]})
    if len(objects) != record["ImageCount"] or set(hashes) != {item["sop_uid"] for item in objects}:
        raise ValueError("ZIP object count/SOPs do not match catalog/MD5 manifest")
    result = {"series_uid": uid, "study_uid": record["StudyInstanceUID"], "public_patient_id": record["PatientID"],
              "modality": record["Modality"], "source_url": url, "license_url": LICENSE_URL,
              "transport": "NBIA_getImageWithMD5Hash",
              "archive_sha256": file_sha256(archive_path), "downloaded_zip_bytes": archive_path.stat().st_size,
              "objects": sorted(objects, key=lambda item: item["sop_uid"]), "timestamp_utc": utc_now()}
    write_json(stage / "source.json", result)
    os.rename(stage, destination)
    return result


def acquire_sample(config, *, download: bool = False, rt_only: bool = False,
                   catalog_path: Path | None = None, idc_catalog_path: Path | None = None) -> dict:
    cached = json.loads(catalog_path.read_text()) if catalog_path else None
    catalog = validate_catalog(cached.get("series", cached) if isinstance(cached, dict) else cached) if cached is not None else fetch_catalog()
    report = capacity_plan(config, catalog)
    report["catalog_input_sha256"] = file_sha256(catalog_path) if catalog_path else None
    report["catalog_is_cached"] = catalog_path is not None
    if not download:
        return report
    if not report["sample_capacity_pass"]:
        raise OSError("Sample capacity check failed; no DICOM download performed")
    selected = [r for r in catalog if r["PatientID"] in config.sample_patient_ids
                and r["Modality"] in ({"RTSTRUCT"} if rt_only else {"CT", "RTSTRUCT"})]
    report.update(status="running_sample_download", downloaded=[])
    target = Path(config.evidence_dir) / "acquisition.json"
    write_json(target, report)
    try:
        if idc_catalog_path:
            from lungseg.data.nsclc_idc import download_idc_series, load_idc_catalog
            mirror = load_idc_catalog(idc_catalog_path)
            downloader = lambda item: download_idc_series(item, mirror, Path(config.raw_root))
            report["transport"] = "official_IDC_S3_UID_matched_to_TCIA"
            report["idc_catalog_sha256"] = file_sha256(idc_catalog_path)
        else:
            downloader = lambda item: download_series(item, Path(config.raw_root))
            report["transport"] = "NBIA_getImageWithMD5Hash"
        # Bounded concurrency; raw DICOM headers will determine referenced CT matching.
        with ThreadPoolExecutor(max_workers=3) as executor:
            for result in executor.map(downloader, selected):
                report["downloaded"].append({key: result.get(key) for key in ("public_patient_id", "series_uid", "modality", "archive_sha256", "downloaded_zip_bytes", "downloaded_object_bytes")})
                write_json(target, report)
        report.update(status="sample_acquired_not_converted", scope="RTSTRUCT_survey" if rt_only else "sample_CT_RTSTRUCT")
    except Exception as exc:
        report.update(status="failed_partial_sample", error=f"{type(exc).__name__}: {exc}")
        write_json(target, report)
        raise
    write_json(target, report)
    return report
