"""Repeat offline sample inventory/conversion/QA and record real execution evidence.

Requires a prior verified acquisition. Does not download data or claim visual QA.
Exit 2 from convert-nsclc means findings were recorded, not silently discarded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from lungseg.data.msd_acquire import file_sha256
from lungseg.data.nsclc_config import load_nsclc_config
from lungseg.runs import utc_now, write_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--config", type=Path, required=True)
parser.add_argument("--check-repeat", action="store_true")
args = parser.parse_args()
config = load_nsclc_config(args.config)
evidence = Path(config.evidence_dir)
evidence.mkdir(parents=True, exist_ok=True)


def raw_snapshot():
    root = Path(config.raw_root)
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    if not paths:
        raise ValueError("No acquired raw files; this verifier cannot validate an empty sample")
    digests = {path.relative_to(root).as_posix(): file_sha256(path) for path in paths}
    return {"files": len(paths), "bytes": sum(p.stat().st_size for p in paths),
            "tree_sha256": hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()}


commands = []


def run(name, *options):
    command = [sys.executable, "-m", "lungseg.cli", name, "--config", str(args.config), *map(str, options)]
    stamp = utc_now()
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = evidence / f"sample_{len(commands):02d}_{name}.txt"
    log.write_text(f"timestamp_utc: {stamp}\ncommand_argv: {json.dumps(command)}\nexit_code: {result.returncode}\n"
                   + result.stdout + result.stderr, encoding="utf-8")
    record = {"command_argv": command, "exit_code": result.returncode, "log": log.name, "timestamp_utc": stamp}
    commands.append(record)
    write_json(evidence / "sample_execution.json", {"commands": commands, "status": "running"})
    if result.returncode not in ({0, 2} if name == "convert-nsclc" else {0}):
        write_json(evidence / "sample_execution.json", {"commands": commands, "status": "failed"})
        raise RuntimeError(f"{name} failed; inspect {log}")
    print(f"{name}: exit {result.returncode}", flush=True)


before = raw_snapshot()
run("acquire-nsclc", "--catalog", Path(config.output_dir) / "public_catalog.json")
run("survey-nsclc")
run("convert-nsclc")
manifest = Path(config.output_dir) / "manifest_nsclc.csv"
first = file_sha256(manifest)
if args.check_repeat:
    run("convert-nsclc")
second = file_sha256(manifest)
after = raw_snapshot()
result = {"timestamp_utc": utc_now(), "real_data": True, "config_sha256": config.sha256,
          "raw_before": before, "raw_after": after, "raw_preserved": before == after,
          "repeat_requested": args.check_repeat, "manifest_sha256_first": first,
          "manifest_sha256_second": second, "manifest_repeat_identical": first == second if args.check_repeat else None}
write_json(evidence / "repeat_and_preservation.json", result)
if before != after or first != second:
    raise RuntimeError("Raw preservation or deterministic manifest check failed")
run("qa-nsclc")
write_json(evidence / "sample_execution.json", {"commands": commands, "status": "checks_passed_with_quarantine_findings",
                                               "visual_qa_acceptance": "separate human/agent review required"})
