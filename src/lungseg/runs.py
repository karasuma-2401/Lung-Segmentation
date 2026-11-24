"""A local run registry: one exclusive directory and atomic metadata per run."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class RunRecord:
    def __init__(self, output_dir: str | Path, run_id: str, config: dict, config_hash: str, environment: dict):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_id):
            raise ValueError("run_id must be 1-80 safe filename characters, starting with a letter/digit")
        self.directory = Path(output_dir) / run_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.metadata = {"schema_version": 1, "run_id": run_id, "kind": "synthetic_smoke",
                         "status": "running", "started_at": utc_now(), "finished_at": None,
                         "config_sha256": config_hash, "environment": environment,
                         "research_result": False}
        write_json(self.directory / "config.json", config)
        write_json(self.directory / "metadata.json", self.metadata)

    def finish(self, status: str, **details) -> None:
        if status not in {"completed", "failed"} or self.metadata["status"] != "running":
            raise ValueError("A running record can finish once as completed or failed")
        self.metadata.update(status=status, finished_at=utc_now(), **details)
        write_json(self.directory / "metadata.json", self.metadata)
