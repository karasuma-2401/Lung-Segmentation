"""Synthetic result-transfer integrity checks; no cloud storage or real medical data."""
import importlib.util
from pathlib import Path
import tarfile

import pytest


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


pilot = module("transfer_test_pilot", "scripts/cloud_pilot.py")
cell = module("transfer_test_cell", "docs/evidence/p1_r_1/notebook_cells/04_package_verified_result.py")


def synthetic_result(tmp_path):
    root = tmp_path / "synthetic_result"
    root.mkdir()
    (root / "artifact.json").write_bytes(b'{"SYNTHETIC_ONLY":true}')
    return root, pilot.seal(root, "RESULT_ROOT.json")


def test_result_transfer_readback_and_source_preservation(tmp_path):
    result, digest = synthetic_result(tmp_path)
    before = pilot.files(result)
    destination = tmp_path / "synthetic.bin"
    report = cell.pack_result(pilot, result, destination, digest, 1)
    assert report["status"] == "RESULT_TRANSFER_PREPARED_AND_READBACK_VERIFIED"
    assert report["archive_files_including_receipt"] == 2
    assert report["transfer_sha256"] == pilot.sha(destination)
    assert report["upload_performed"] is False
    assert report["cross_session_persistence"] == "NOT_RUN"
    assert pilot.files(result) == before
    with tarfile.open(destination, "r:") as archive:
        assert archive.extractfile("result/artifact.json").read() == (result / "artifact.json").read_bytes()
        assert archive.extractfile("result/RESULT_ROOT.json").read() == (result / "RESULT_ROOT.json").read_bytes()


def test_corrupt_source_rejected_before_transfer_creation(tmp_path):
    result, digest = synthetic_result(tmp_path)
    (result / "artifact.json").write_bytes(b"corrupt")
    destination = tmp_path / "synthetic.bin"
    with pytest.raises(ValueError, match="corrupt"):
        cell.pack_result(pilot, result, destination, digest, 1)
    assert not destination.exists()


def test_existing_transfer_never_overwritten(tmp_path):
    result, digest = synthetic_result(tmp_path)
    destination = tmp_path / "existing.bin"
    destination.write_bytes(b"preserve prior artifact")
    with pytest.raises(AssertionError, match="already exists"):
        cell.pack_result(pilot, result, destination, digest, 1)
    assert destination.read_bytes() == b"preserve prior artifact"
