"""Implemented P0/T04/T05 tooling; no research training commands."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

from lungseg.config import load_smoke_config
from lungseg.environment import collect_environment
from lungseg.runs import RunRecord, write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lung segmentation research tooling")
    commands = parser.add_subparsers(dest="command", required=True)
    env = commands.add_parser("env-check", help="Report real package imports and CPU/CUDA capability")
    env.add_argument("--output", type=Path)
    smoke = commands.add_parser("smoke-test", help="Run a synthetic fixture; not a research experiment")
    smoke.add_argument("--config", type=Path, required=True)
    smoke.add_argument("--device", choices=("cpu", "cuda", "auto"))
    smoke.add_argument("--output-dir")
    smoke.add_argument("--run-id")
    acquisition = commands.add_parser("acquire-msd", help="Probe public MSD source; download/extract only with flags")
    acquisition.add_argument("--config", type=Path, required=True)
    acquisition.add_argument("--download", action="store_true")
    acquisition.add_argument("--extract", action="store_true")
    audit = commands.add_parser("audit-msd", help="Inventory native CT/masks; no split or preprocessing")
    audit.add_argument("--config", type=Path, required=True)
    qa = commands.add_parser("qa-msd", help="Render three-plane CT/mask QA from a validated manifest")
    qa.add_argument("--config", type=Path, required=True)
    qa.add_argument("--case-ids", nargs="+")
    for name in ("acquire-nsclc", "survey-nsclc", "convert-nsclc", "qa-nsclc"):
        command = commands.add_parser(name, help="Bounded NSCLC sample acquisition / native geometry QA")
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--raw-root")
        command.add_argument("--converted-root")
        if name == "acquire-nsclc":
            command.add_argument("--download", action="store_true")
            command.add_argument("--rt-only", action="store_true")
            command.add_argument("--catalog", type=Path)
            command.add_argument("--idc-catalog", type=Path)
    args = parser.parse_args(argv)
    record = None
    try:
        if args.command.endswith("-nsclc"):
            from lungseg.data.nsclc_config import load_nsclc_config
            config = load_nsclc_config(args.config, raw_root=args.raw_root, converted_root=args.converted_root)
            if args.command == "acquire-nsclc":
                from lungseg.data.nsclc_acquire import acquire_sample
                result = acquire_sample(config, download=args.download, rt_only=args.rt_only,
                                        catalog_path=args.catalog, idc_catalog_path=args.idc_catalog)
            else:
                from lungseg.data.nsclc import survey, convert_sample, generate_qa
                result = {"survey-nsclc": survey, "convert-nsclc": convert_sample, "qa-nsclc": generate_qa}[args.command](config)
            print(json.dumps(result, indent=2))
            return 2 if result.get("quarantined_cases") else 0
        if args.command in {"audit-msd", "qa-msd"}:
            from lungseg.data.msd_config import load_msd_config

            config = load_msd_config(args.config)
            if args.command == "audit-msd":
                from lungseg.data.msd import inventory

                result = inventory(config)
                print(json.dumps(result, indent=2))
                return 2 if result["error_counts"] or result["dataset_findings"] else 0
            from lungseg.data.msd_qa import generate_qa

            print(json.dumps(generate_qa(config, args.case_ids), indent=2))
            return 0
        if args.command == "acquire-msd":
            from lungseg.data.msd_acquire import acquire
            from lungseg.data.msd_config import load_msd_config

            print(json.dumps(acquire(load_msd_config(args.config), download=args.download, extract=args.extract), indent=2))
            return 0
        if args.command == "env-check":
            report = collect_environment()
            if args.output:
                write_json(args.output, report)
            print(json.dumps(report, indent=2))
            return 0 if report["required_imports_pass"] else 1
        config = load_smoke_config(args.config)
        # Overrides are part of the resolved config/hash, rather than hidden runtime settings.
        config = replace(config, device=args.device or config.device,
                         output_dir=args.output_dir or config.output_dir)
        run_id = args.run_id or f"P0_smoke_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
        record = RunRecord(config.output_dir, run_id, config.to_dict(), config.sha256, collect_environment())
        from lungseg.smoke import run_smoke

        result = run_smoke(config)
        write_json(record.directory / "result.json", result)
        record.finish("completed", result_path="result.json")
        print(json.dumps({"run_directory": str(record.directory), **result}, indent=2))
        return 0
    except Exception as exc:
        if record is not None:
            record.finish("failed", error={"type": type(exc).__name__, "message": str(exc)})
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
