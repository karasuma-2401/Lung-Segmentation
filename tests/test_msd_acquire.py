"""No network or real MSD data: tiny tar fixtures and mocked HTTP responses."""

import io
import json
from pathlib import Path
import tarfile
from types import SimpleNamespace

import pytest

from lungseg.data import msd_acquire as acquire


def member(name, data=b"{}", kind=tarfile.REGTYPE):
    result = tarfile.TarInfo(name)
    result.size = len(data)
    result.type = kind
    return result, data


@pytest.mark.parametrize("name,kind", [("../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
    ("Task06_Lung/../../outside", tarfile.REGTYPE), ("Task06_Lung/link", tarfile.SYMTYPE),
    ("Task06_Lung/hardlink", tarfile.LNKTYPE), ("C:/escape", tarfile.REGTYPE),
    ("Task06_Lung\\escape", tarfile.REGTYPE)])
def test_tar_traversal_links_and_unexpected_paths_rejected(name, kind):
    with pytest.raises(ValueError):
        acquire.validate_members([member(name, kind=kind)[0]])


def test_tar_duplicate_paths_rejected():
    info = member("Task06_Lung/dataset.json")[0]
    with pytest.raises(ValueError, match="Duplicate"):
        acquire.validate_members([info, info])


def test_safe_extraction_skips_appledouble_and_preserves_existing_raw(tmp_path):
    archive = tmp_path / "tiny.tar"
    with tarfile.open(archive, "w") as handle:
        for item, data in [member("Task06_Lung/dataset.json"), member("Task06_Lung/._dataset.json", b"mac metadata")]:
            handle.addfile(item, io.BytesIO(data))
    root = tmp_path / "raw/Task06_Lung"
    result = acquire.extract_archive(archive, root, "synthetic-hash", 100)
    assert result["status"] == "extracted"
    assert (root / "dataset.json").read_bytes() == b"{}"
    assert not (root / "._dataset.json").exists()
    assert acquire.extract_archive(archive, root, "synthetic-hash", 100)["status"] == "already_extracted"
    with pytest.raises(FileExistsError):
        acquire.extract_archive(archive, root, "other-hash", 100)


def test_preflight_refuses_insufficient_space(tmp_path, monkeypatch):
    monkeypatch.setattr(acquire.shutil, "disk_usage", lambda _: SimpleNamespace(free=10))
    with pytest.raises(OSError, match="Insufficient"):
        acquire.require_space(tmp_path, 11)


class Response(io.BytesIO):
    def __init__(self, data, begin, end, total, etag='"fixture"', status=206):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Range": f"bytes {begin}-{end}/{total}", "ETag": etag}


def test_range_download_and_resume_existing_partial(tmp_path, monkeypatch):
    data = b"synthetic archive bytes"
    report = {"url": acquire.SOURCE_URL, "content_length_bytes": len(data), "etag": '"fixture"', "version_id": "v1"}
    def fetch(request, timeout):
        begin, end = map(int, request.headers["Range"].split("=")[1].split("-"))
        return Response(data[begin:end+1], begin, end, len(data))
    monkeypatch.setattr(acquire, "urlopen", fetch)
    archive = tmp_path / "Task06_Lung.tar"
    partial = archive.with_suffix(".tar.part")
    partial.write_bytes(data[:4])
    partial.with_suffix(".part.json").write_text(json.dumps(report))
    digest = acquire.download_archive(report, archive)
    assert archive.read_bytes() == data
    assert digest == acquire.file_sha256(archive)
    assert acquire.download_archive(report, archive) == digest
    archive.write_bytes(b"changed")
    with pytest.raises(ValueError, match="mismatch"):
        acquire.download_archive(report, archive)


@pytest.mark.parametrize("status,etag", [(200, '"fixture"'), (206, '"changed"')])
def test_bad_http_range_or_changed_etag_rejected(tmp_path, monkeypatch, status, etag):
    report = {"url": acquire.SOURCE_URL, "content_length_bytes": 3, "etag": '"fixture"'}
    monkeypatch.setattr(acquire, "urlopen", lambda *args, **kwargs: Response(b"abc", 0, 2, 3, etag, status))
    with pytest.raises(ValueError):
        acquire.download_range(report, tmp_path, 0, 2)


def test_resume_refuses_unknown_source_identity(tmp_path):
    archive = tmp_path / "Task06_Lung.tar"
    archive.with_suffix(".tar.part").write_bytes(b"existing")
    report = {"url": acquire.SOURCE_URL, "content_length_bytes": 100, "etag": '"fixture"', "version_id": "v1"}
    with pytest.raises(ValueError, match="unknown source"):
        acquire.download_archive(report, archive)
