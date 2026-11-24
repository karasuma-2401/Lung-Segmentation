"""Download the public MSD archive with resource checks and safe extraction."""

from pathlib import Path, PurePosixPath
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import shutil
import sys
import tarfile
import time
from urllib.request import Request, urlopen

from lungseg.runs import utc_now, write_json

SOURCE_URL = "https://msd-for-monai.s3.us-west-2.amazonaws.com/Task06_Lung.tar"
REGISTRY_URL = "https://registry.opendata.aws/msd/"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_space(directory: Path, required: int) -> int:
    probe = directory.resolve()
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < required:
        raise OSError(f"Insufficient disk space: need {required} bytes, available {free} on {probe}")
    return free


def probe_source(url: str, archive: Path, reserve_bytes: int) -> dict:
    if url != SOURCE_URL:
        raise ValueError("Only the verified public MSD Task06_Lung source URL is supported")
    with urlopen(Request(url, method="HEAD"), timeout=30) as response:
        length = int(response.headers["Content-Length"])
        if length <= 0:
            raise ValueError("Source Content-Length must be positive")
        report = {"url": url, "content_length_bytes": length, "etag": response.headers.get("ETag"),
                  "last_modified": response.headers.get("Last-Modified"),
                  "version_id": response.headers.get("x-amz-version-id"), "http_status": response.status}
    # This is an uncompressed tar containing .nii.gz files: extracted members cannot
    # occupy more payload bytes than the archive. Filesystem overhead is reserved separately.
    required = 2 * length + reserve_bytes
    report.update(timestamp_utc=utc_now(), license="CC-BY-SA-4.0", license_url=LICENSE_URL,
                  source_registry=REGISTRY_URL, no_aws_account_required=True,
                  reserve_bytes=reserve_bytes, conservative_download_and_extract_bytes=required,
                  free_bytes=require_space(archive.parent, required))
    return report


def download_archive(report: dict, archive: Path) -> str:
    archive.parent.mkdir(parents=True, exist_ok=True)
    sidecar = archive.with_suffix(archive.suffix + ".source.json")
    identity = {key: report[key] for key in ("url", "etag", "content_length_bytes", "version_id")}
    if archive.exists():
        if not sidecar.exists():
            raise FileExistsError(f"Unverified existing archive; preserve and inspect {archive}")
        previous = json.loads(sidecar.read_text(encoding="utf-8"))
        digest = file_sha256(archive)
        if any(previous.get(k) != v for k, v in identity.items()) or previous.get("sha256") != digest:
            raise ValueError("Existing archive source/checksum mismatch; refusing overwrite")
        if archive.stat().st_size != identity["content_length_bytes"]:
            raise ValueError("Existing archive has the wrong length")
        return digest
    partial = archive.with_suffix(archive.suffix + ".part")
    partial_meta = partial.with_suffix(partial.suffix + ".json")
    if partial.exists():
        if not partial_meta.exists() or json.loads(partial_meta.read_text(encoding="utf-8")) != identity:
            raise ValueError("Partial archive has different/unknown source identity; refusing to append")
    else:
        write_json(partial_meta, identity)
    start = partial.stat().st_size if partial.exists() else 0
    length = identity["content_length_bytes"]
    if start > length:
        raise ValueError("Partial archive is larger than the remote source")
    if start < length:
        # Four bounded ranges hide long-distance S3 latency without buffering whole
        # volumes in RAM. Merge in byte order; the contiguous .part remains resumable.
        segment_dir = archive.with_suffix(archive.suffix + ".parts")
        segment_dir.mkdir(exist_ok=True)
        chunk_source = segment_dir / "source.json"
        if chunk_source.exists():
            if json.loads(chunk_source.read_text(encoding="utf-8")) != identity:
                raise ValueError("Cached download chunks have a different source identity")
        elif any(segment_dir.iterdir()):
            raise ValueError("Cached download chunks have no source identity; preserve for inspection")
        else:
            write_json(chunk_source, identity)
        spans = iter((begin, min(begin + 64 * 1024 * 1024, length) - 1)
                     for begin in range(start, length, 64 * 1024 * 1024))
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending = deque()
            for span in spans:
                pending.append(pool.submit(download_range, report, segment_dir, *span))
                if len(pending) == 4:
                    break
            with partial.open("ab" if start else "wb") as handle:
                last_progress = time.monotonic()
                while pending:
                    segment = pending.popleft().result()
                    with segment.open("rb") as source:
                        shutil.copyfileobj(source, handle, length=4 * 1024 * 1024)
                    handle.flush()
                    segment.unlink()  # only this downloader's merged temporary chunk
                    if time.monotonic() - last_progress >= 25:
                        print(f"MSD download: {handle.tell()}/{length} bytes ({100*handle.tell()/length:.1f}%)", file=sys.stderr, flush=True)
                        last_progress = time.monotonic()
                    span = next(spans, None)
                    if span:
                        pending.append(pool.submit(download_range, report, segment_dir, *span))
    if partial.stat().st_size != length:
        raise OSError("Incomplete download; rerun with the same config to resume")
    digest = file_sha256(partial)
    # Record a complete source sidecar before rename; a process interruption cannot
    # make an unverified existing archive look successfully acquired.
    write_json(sidecar, {**identity, "sha256": digest, "completed_at": utc_now()})
    os.replace(partial, archive)
    partial_meta.unlink(missing_ok=True)
    return digest


def download_range(report: dict, directory: Path, begin: int, end: int) -> Path:
    destination = directory / f"{begin:012d}-{end:012d}.chunk"
    if destination.is_file() and destination.stat().st_size == end - begin + 1:
        return destination
    temporary = destination.with_suffix(".downloading")
    headers = {"Range": f"bytes={begin}-{end}"}
    if report["etag"]:
        headers["If-Match"] = report["etag"]
    for attempt in range(3):
        try:
            with urlopen(Request(report["url"], headers=headers), timeout=60) as response:
                expected = f"bytes {begin}-{end}/{report['content_length_bytes']}"
                if response.status != 206 or response.headers.get("Content-Range") != expected:
                    raise ValueError("Server did not honor the exact requested byte range")
                if response.headers.get("ETag") != report["etag"]:
                    raise ValueError("Source ETag changed after preflight")
                with temporary.open("wb") as handle:
                    while block := response.read(4 * 1024 * 1024):
                        if handle.tell() + len(block) > end - begin + 1:
                            raise ValueError("Range body exceeds declared span")
                        handle.write(block)
            if temporary.stat().st_size != end - begin + 1:
                raise OSError("Incomplete range body")
            os.replace(temporary, destination)
            return destination
        except OSError:
            if attempt == 2:
                raise
    raise RuntimeError("Unreachable range retry state")


def validate_members(members: list[tarfile.TarInfo]) -> list[tarfile.TarInfo]:
    safe = []
    seen = set()
    for member in members:
        name = member.name.rstrip("/")
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
                or path.parts[0] != "Task06_Lung" or not (member.isdir() or member.isfile())):
            raise ValueError(f"Unsafe or unexpected tar member: {member.name!r}")
        if name in seen:
            raise ValueError(f"Duplicate tar member: {name}")
        seen.add(name)
        if any(part.startswith("._") or part == ".DS_Store" for part in path.parts):
            continue
        safe.append(member)
    return safe


def extract_archive(archive: Path, dataset_root: Path, digest: str, reserve_bytes: int) -> dict:
    if dataset_root.name != "Task06_Lung":
        raise ValueError("dataset_root must end in Task06_Lung")
    marker = dataset_root / ".acquisition.json"
    if dataset_root.exists():
        if marker.exists() and json.loads(marker.read_text(encoding="utf-8")).get("archive_sha256") == digest:
            return {"status": "already_extracted", "marker": str(marker)}
        raise FileExistsError(f"Dataset destination exists without matching provenance: {dataset_root}")
    with tarfile.open(archive, "r:") as handle:
        members = validate_members(handle.getmembers())
        extracted_bytes = sum(member.size for member in members if member.isfile())
        free = require_space(dataset_root.parent, extracted_bytes + reserve_bytes)
        stage = dataset_root.parent / ".extracting_Task06_Lung"
        stage.mkdir(parents=True, exist_ok=False)
        # Python's data filter additionally rejects links, traversal and special files.
        # A failed extraction stays staged for inspection; never overwrite existing raw.
        handle.extractall(stage, members=members, filter="data")
    extracted = stage / "Task06_Lung"
    if not (extracted / "dataset.json").is_file():
        raise ValueError("Archive did not contain Task06_Lung/dataset.json")
    record = {"archive_sha256": digest, "timestamp_utc": utc_now(),
              "payload_bytes": extracted_bytes, "members": len(members), "free_bytes_before_extract": free}
    write_json(extracted / ".acquisition.json", record)
    os.rename(extracted, dataset_root)
    stage.rmdir()
    return {"status": "extracted", **record}


def acquire(config, *, download: bool = False, extract: bool = False) -> dict:
    archive = Path(config.acquisition["archive_path"])
    report_path = Path(config.acquisition["report_path"])
    report = probe_source(config.acquisition["url"], archive, config.acquisition["reserve_bytes"])
    report.update(status="preflight_pass", archive_path=str(archive), dataset_root=config.dataset_root)
    write_json(report_path, report)
    try:
        if download:
            report["archive_sha256"] = download_archive(report, archive)
            report["status"] = "downloaded"
            write_json(report_path, report)
        if extract:
            if not archive.is_file():
                raise FileNotFoundError(f"Download archive before extraction: {archive}")
            digest = report.get("archive_sha256") or file_sha256(archive)
            sidecar = json.loads(archive.with_suffix(archive.suffix + ".source.json").read_text(encoding="utf-8"))
            if sidecar.get("sha256") != digest or archive.stat().st_size != report["content_length_bytes"]:
                raise ValueError("Archive does not match download provenance")
            report["extraction"] = extract_archive(archive, Path(config.dataset_root), digest, config.acquisition["reserve_bytes"])
            report.update(status="acquired_not_yet_validated", archive_sha256=digest)
        write_json(report_path, report)
        return report
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        write_json(report_path, report)
        raise
