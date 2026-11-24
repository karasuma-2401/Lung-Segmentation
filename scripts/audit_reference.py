"""Inspect pinned upstream statically; never import or execute its source."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import yaml


def audit(upstream: Path, paper: Path) -> dict:
    reference = yaml.safe_load(Path("configs/references/upstream.yaml").read_text(encoding="utf-8"))
    revision = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
    if revision != reference["commit"]:
        raise ValueError(f"Upstream revision mismatch: expected {reference['commit']}, found {revision}")
    dirty = subprocess.run(["git", "-C", str(upstream), "status", "--porcelain"],
                           check=True, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise ValueError("Upstream working tree is modified; audit the pinned clean reference")
    files = {}
    for path in sorted((upstream / "training").rglob("*.py")):
        raw = path.read_bytes()
        files[path.relative_to(upstream).as_posix()] = {
            "sha256": hashlib.sha256(raw).hexdigest(), "lines": len(raw.splitlines())}
    splits = {}
    for path in sorted((upstream / "training/Resources").rglob("*.yaml")):
        name = path.relative_to(upstream).as_posix()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            counts = {k: len(v) for k, v in data.items() if isinstance(v, list)} if isinstance(data, dict) else {}
            splits[name] = {"parsed": True, "list_lengths": counts}
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            splits[name] = {"parsed": False, "error": type(exc).__name__,
                            "line": mark.line + 1 if mark else None,
                            "column": mark.column + 1 if mark else None}
    tables = {}
    root = ET.parse(paper).getroot()
    for table in root.iter("table-wrap"):
        rows = []
        for row in table.findall(".//tbody/tr"):
            rows.append([" ".join("".join(cell.itertext()).split()) for cell in row])
        tables[table.get("id")] = rows
    return {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "upstream_commit": revision,
            "upstream_worktree": "clean", "scope": "static inspection, not an upstream execution test",
            "python_files": files, "yaml_summaries_no_patient_ids": splits,
            "paper_xml_sha256": hashlib.sha256(paper.read_bytes()).hexdigest(),
            "paper_tables": tables,
            "paper_attribution": "Fredriksen et al. (2022), PLOS ONE, doi:10.1371/journal.pone.0266147, CC BY"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=Path(".reference/LungTumorMask"))
    parser.add_argument("--paper", type=Path, default=Path(".reference/paper/article.xml"))
    parser.add_argument("--output", type=Path, default=Path("docs/evidence/upstream_audit.json"))
    args = parser.parse_args()
    report = audit(args.upstream, args.paper)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"commit": report["upstream_commit"], "python_files": len(report["python_files"]),
                      "yaml_files": len(report["yaml_summaries_no_patient_ids"]), "output": str(args.output)}))
