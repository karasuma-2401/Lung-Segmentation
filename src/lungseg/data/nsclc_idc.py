"""Unsigned official IDC S3 mirror, exact TCIA UID matching, bounded object reads."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen
import xml.etree.ElementTree as ET

import pydicom

from lungseg.data.msd_acquire import file_sha256, require_space
from lungseg.data.nsclc_acquire import LICENSE_URL
from lungseg.runs import utc_now, write_json

INDEX_URL = "https://storage.googleapis.com/idc-index-data-artifacts/current/release_artifacts/idc_index.parquet"


def load_idc_catalog(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get("source") != INDEX_URL or not re.fullmatch(r"[a-f0-9]{64}", data.get("index_sha256", "")):
        raise ValueError("Expected official IDC index source/hash")
    result = {}
    for item in data["series"]:
        if (item["collection_id"] != "nsclc_radiomics" or item["license_short_name"] != "CC BY-NC 3.0"
                or item["source_DOI"].lower() != "10.7937/k9/tcia.2015.pf0m9rei"):
            raise ValueError("IDC collection/source/license differs from original TCIA data")
        uid = item["SeriesInstanceUID"]
        if uid in result:
            raise ValueError("Duplicate IDC series")
        result[uid] = item
    return result


def list_objects(series_url: str) -> tuple[str, list[dict]]:
    match = re.fullmatch(r"s3://(idc-open-data(?:-cr)?)/([a-f0-9-]{36})/\*", series_url)
    if not match:
        raise ValueError("Only official IDC public buckets and series UUID prefixes supported")
    bucket, prefix = match.group(1), match.group(2) + "/"
    base = f"https://{bucket}.s3.amazonaws.com/"
    url = base + "?" + urlencode({"list-type": "2", "prefix": prefix})
    with urlopen(url, timeout=45) as response:
        raw = response.read(4 * 1024**2 + 1)
    if len(raw) > 4 * 1024**2:
        raise ValueError("S3 listing exceeds limit")
    root = ET.fromstring(raw)
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    if root.findtext("s:IsTruncated", namespaces=ns) != "false":
        raise ValueError("Truncated S3 listing; refuse incomplete acquisition")
    objects = []
    for item in root.findall("s:Contents", ns):
        key = item.findtext("s:Key", namespaces=ns)
        if not re.fullmatch(re.escape(prefix) + r"[a-f0-9-]{36}\.dcm", key or ""):
            raise ValueError("Unexpected S3 object path")
        etag = item.findtext("s:ETag", namespaces=ns).strip('"')
        if not re.fullmatch(r"[a-f0-9]{32}", etag):
            raise ValueError("Multipart/non-MD5 S3 ETag requires separate checksum policy")
        objects.append({"key": key, "bytes": int(item.findtext("s:Size", namespaces=ns)), "md5": etag})
    if len({item["key"] for item in objects}) != len(objects):
        raise ValueError("Duplicate S3 object key")
    return base, sorted(objects, key=lambda item: item["key"])


def download_idc_series(record: dict, mirror: dict, raw_root: Path) -> dict:
    uid = record["SeriesInstanceUID"]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", uid) or not re.fullmatch(r"LUNG1-\d{3}", record["PatientID"]):
        raise ValueError("Expected verified public TCIA identifiers")
    item = mirror.get(uid)
    if not item or any(item[key] != record[key] for key in ("PatientID", "StudyInstanceUID", "Modality")) or item["instanceCount"] != record["ImageCount"]:
        raise ValueError("IDC identifiers/count disagree with original NBIA catalog")
    destination = raw_root / "dicom" / record["PatientID"] / uid
    marker = destination / "source.json"
    if destination.exists():
        result = json.loads(marker.read_text())
        if (result.get("series_uid") != uid or result.get("public_patient_id") != record["PatientID"]
                or result.get("study_uid") != record["StudyInstanceUID"] or result.get("modality") != record["Modality"]
                or result.get("license_url") != LICENSE_URL):
            raise ValueError("Existing raw provenance disagrees with selected source")
        if len(result["objects"]) != record["ImageCount"]:
            raise ValueError("Existing raw count differs")
        for obj in result["objects"]:
            if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", obj["sop_uid"]) or file_sha256(destination / (obj["sop_uid"] + ".dcm")) != obj["sha256"]:
                raise ValueError("Existing raw hash mismatch; refuse overwrite")
        return result
    base, objects = list_objects(item["series_aws_url"])
    total = sum(obj["bytes"] for obj in objects)
    if len(objects) != record["ImageCount"] or total > record["FileSize"] * 1.1 + 2 * 1024**2:
        raise ValueError("IDC object count or size disagrees with TCIA planning bound")
    require_space(raw_root, total + 2 * 1024**3)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Preserve failed stages for investigation. A retry uses a new stage; never deletes raw.
    from uuid import uuid4
    stage = raw_root / "staging" / record["PatientID"] / (uid + ".partial-" + uuid4().hex[:8])
    stage.mkdir(parents=True)

    def fetch(obj):
        with urlopen(base + obj["key"], timeout=60) as response:
            raw = response.read(obj["bytes"] + 1)
        if len(raw) != obj["bytes"] or hashlib.md5(raw).hexdigest() != obj["md5"]:
            raise ValueError("IDC object byte count/ETag MD5 mismatch")
        ds = pydicom.dcmread(BytesIO(raw), stop_before_pixels=True)
        if any(str(getattr(ds, key, "")) != record[key] for key in ("PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Modality")):
            raise ValueError("IDC DICOM header identity disagrees with TCIA UID matched catalog")
        sop = str(ds.SOPInstanceUID)
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", sop):
            raise ValueError("Invalid DICOM SOPInstanceUID")
        # Exclusive creation detects duplicate SOPs even with parallel object reads.
        with (stage / (sop + ".dcm")).open("xb") as handle:
            handle.write(raw)
        return {"sop_uid": sop, "key": obj["key"], "bytes": len(raw), "md5": obj["md5"], "sha256": hashlib.sha256(raw).hexdigest()}

    with ThreadPoolExecutor(max_workers=4) as executor:
        verified = list(executor.map(fetch, objects))
    result = {"series_uid": uid, "study_uid": record["StudyInstanceUID"], "public_patient_id": record["PatientID"],
              "modality": record["Modality"], "license_url": LICENSE_URL, "source_url": item["series_aws_url"],
              "source_doi": item["source_DOI"], "transport": "official_IDC_S3", "downloaded_object_bytes": total,
              "timestamp_utc": utc_now(), "objects": sorted(verified, key=lambda obj: obj["sop_uid"])}
    write_json(stage / "source.json", result)
    os.rename(stage, destination)
    return result
