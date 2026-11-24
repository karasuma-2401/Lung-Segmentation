"""Synthetic extraction and session guards; no actual cloud session attestation."""
import importlib.util
from io import BytesIO
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location("restore_cell", Path(__file__).parents[1] / "docs/evidence/p1_r_1/notebook_cells/06_restore_in_new_session.py")
cell = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cell)


def fixture_tar(tmp_path, names=("result/artifact", "result/RESULT_ROOT.json")):
    archive = tmp_path / "synthetic.bin"
    with tarfile.open(archive, "x") as handle:
        for name in names:
            value = b"SYNTHETIC_ONLY"
            info = tarfile.TarInfo(name)
            info.size = len(value)
            handle.addfile(info, BytesIO(value))
    return archive


def test_extract_result_from_mounted_transfer_without_prior_cache(tmp_path):
    archive = fixture_tar(tmp_path)
    before = cell.file_sha(archive)
    stage = tmp_path / "new_session_stage"
    result = cell.extract_result(archive, stage, before, archive.stat().st_size, 2)
    assert result == stage / "result"
    assert (result / "artifact").read_bytes() == b"SYNTHETIC_ONLY"
    assert cell.file_sha(archive) == before


def test_corrupted_result_transfer_rejected_before_writes(tmp_path):
    archive = fixture_tar(tmp_path)
    stage = tmp_path / "new_session_stage"
    with pytest.raises(AssertionError, match="corruption"):
        cell.extract_result(archive, stage, "0" * 64, archive.stat().st_size, 2)
    assert not stage.exists()


@pytest.mark.parametrize("name", ["result/../escape", "/result/absolute", "code/not_result.py"])
def test_unsafe_or_wrong_namespace_result_rejected(tmp_path, name):
    archive = fixture_tar(tmp_path, [name])
    stage = tmp_path / "new_session_stage"
    with pytest.raises(AssertionError):
        cell.extract_result(archive, stage, cell.file_sha(archive), archive.stat().st_size, 1)
    assert not stage.exists()


def test_user_attestation_is_required_before_any_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(cell, "FRESH_SESSION_ATTESTED", False)
    with pytest.raises(AssertionError, match="Confirm you ended"):
        cell.main(tmp_path / "nonexistent_context.json")


def test_old_cache_blocks_false_fresh_session_claim(tmp_path, monkeypatch):
    monkeypatch.setattr(cell, "FRESH_SESSION_ATTESTED", True)
    monkeypatch.setattr(cell.platform, "system", lambda: "Linux")
    monkeypatch.setattr(cell, "OLD_WORK", tmp_path)
    with pytest.raises(AssertionError, match="Original session cache"):
        cell.main(tmp_path / "nonexistent_context.json")
