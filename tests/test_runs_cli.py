import json

import pytest
import torch

from lungseg.cli import main
from lungseg.runs import RunRecord


def test_run_collision_preserves_previous_metadata(tmp_path):
    record = RunRecord(tmp_path, "same", {"seed": 42}, "hash", {})
    record.finish("completed")
    original = (record.directory / "metadata.json").read_bytes()
    with pytest.raises(FileExistsError):
        RunRecord(tmp_path, "same", {"seed": 7}, "other", {})
    assert (record.directory / "metadata.json").read_bytes() == original
    with pytest.raises(ValueError):
        record.finish("failed")


@pytest.mark.parametrize("run_id", ["../escape", "a/b", "", "..", "a" * 81])
def test_run_id_cannot_escape_directory(tmp_path, run_id):
    with pytest.raises(ValueError):
        RunRecord(tmp_path, run_id, {}, "hash", {})


def test_cli_writes_resolved_config_and_completed_record(tmp_path):
    assert main(["smoke-test", "--config", "configs/smoke.yaml", "--device", "cpu",
                 "--output-dir", str(tmp_path), "--run-id", "cpu_success"]) == 0
    folder = tmp_path / "cpu_success"
    metadata = json.loads((folder / "metadata.json").read_text())
    config = json.loads((folder / "config.json").read_text())
    result = json.loads((folder / "result.json").read_text())
    assert metadata["status"] == "completed"
    assert metadata["finished_at"]
    assert len(metadata["config_sha256"]) == 64
    assert config["output_dir"] == str(tmp_path)
    assert config["device"] == result["device_used"] == "cpu"
    assert metadata["research_result"] is False


def test_cli_records_failure_without_success_result(tmp_path, monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert main(["smoke-test", "--config", "configs/smoke.yaml", "--device", "cuda",
                 "--output-dir", str(tmp_path), "--run-id", "cuda_missing"]) == 1
    folder = tmp_path / "cuda_missing"
    metadata = json.loads((folder / "metadata.json").read_text())
    assert metadata["status"] == "failed"
    assert metadata["error"]["type"] == "RuntimeError"
    assert not (folder / "result.json").exists()
