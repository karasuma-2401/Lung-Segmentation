# Kaggle Python cell: run only after successful cell02c, in the same session.
# Existing approved samples only. No upload, acquisition, cleanup or training.
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import hashlib, importlib.util, json, os, platform, subprocess

INPUT_SHA = "c97683893715b34fbb7cdf7193134220625169021acb39aae00f6243ce9c4f6f"
KIT_SHA = "7e017276b086afeb646c6c7e17aceed797cd93a12086868a0308cfd1e59be8d0"
REVISION = "dc6e179087737621b69d538ef200436c644a7687"
# Explicit fallback from the successful user-provided setup log; no ambiguous glob.
LATEST_CONTEXT = Path("/kaggle/working/pilot_cpu_20261124T103900Z_a9054907/runtime_context.json")


def load_verified_context(context_path):
    context_path = Path(context_path)
    assert context_path.is_file(), "Setup context absent; run cell02c in this session first"
    context = json.loads(context_path.read_text())
    work, stage = Path(context["work"]), Path(context["stage"])
    repo, python, kit = (Path(context[name]) for name in ("repo", "python", "kit"))
    assert work.resolve() == context_path.parent.resolve()
    assert repo.resolve() == (work / "repo").resolve() and python.resolve().is_file()
    assert kit.resolve() == (stage / "code/cloud_pilot.py").resolve()
    assert hashlib.sha256(kit.read_bytes()).hexdigest() == KIT_SHA, "Pilot kit changed"
    assert context["input_root_sha256"] == INPUT_SHA
    report = json.loads(Path(context["environment_report"]).read_text())
    assert report["status"] == "PACKAGE_SOURCE_IMPORT_CHECK_PASS" and report["platform"] == "Linux"
    assert report["isolated_target_venv"] and report["production_source_hashes_match"]
    assert report["production_revision"] == REVISION
    spec = importlib.util.spec_from_file_location("verified_native_pilot", kit)
    pilot = importlib.util.module_from_spec(spec); spec.loader.exec_module(pilot)
    pilot.verify(stage / "pilot_input", "INPUT_ROOT.json", INPUT_SHA)
    return context, pilot


def main(context_path):
    assert platform.system() == "Linux", "Run this cell on Kaggle CPU"
    context, pilot = load_verified_context(context_path)
    work, stage, repo, python, kit = (Path(context[name]) for name in ("work", "stage", "repo", "python", "kit"))
    assert work.resolve().is_relative_to(Path("/kaggle/working").resolve())
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    output, log_path = work / ("result_" + run_id), work / ("native_" + run_id + ".log")
    assert not output.exists() and not log_path.exists(), "Fresh output required"
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PIP_") and key not in ("PYTHONHOME", "PYTHONPATH")}
    env.update(PYTHONPATH=str(repo / "src"), CUDA_VISIBLE_DEVICES="",
               PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONUNBUFFERED="1")
    command = [str(python), str(kit), "run", "--input", str(stage / "pilot_input"),
               "--output", str(output), "--expected-root-sha256", INPUT_SHA,
               "--execution-kind", "kaggle", "--probe-connectivity"]
    print("Bounded CPU native pilot: 1 NSCLC + 1 weak case; no training", flush=True)
    print("Result:", output, "\nLog:", log_path, flush=True)
    with log_path.open("x", encoding="utf-8") as log:
        log.write("argv: " + json.dumps(command) + "\n")
        process = subprocess.Popen(command, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace")
        for line in process.stdout:
            print(line, end="", flush=True); log.write(line); log.flush()
        code = process.wait(); log.write(f"exit_code: {code}\n")
    if code:
        for name in ("failure.json", "preflight.json", "nsclc_worker.log", "weak_worker.log"):
            path = output / name
            if path.is_file():
                print("RETAINED:", path)
                print(path.read_text(encoding="utf-8", errors="replace")[-6000:])
        raise RuntimeError(f"Pilot failed ({code}); preserve outputs/logs and send the error")
    report = json.loads((output / "run.json").read_text())
    assert report["status"] == "KAGGLE_CPU_PILOT_PASS" and report["revision"] == REVISION
    assert report["input_root_sha256"] == INPUT_SHA and report["input_preserved"]
    digest = pilot.sha(output / "RESULT_ROOT.json")
    inventory = pilot.verify(output, "RESULT_ROOT.json", digest)
    pilot.verify(stage / "pilot_input", "INPUT_ROOT.json", INPUT_SHA)
    summary = {"status": report["status"], "result_path": str(output),
               "result_root_sha256": digest, "result_files_verified": len(inventory),
               "runtime": report["runtime"], "checks": report["checks"],
               "source_connectivity": report["source_connectivity"],
               "persistence_restore": "NOT_RUN", "training_clearance": False}
    # Keep the summary outside the sealed result tree.
    with (work / ("summary_" + run_id + ".json")).open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print("NATIVE_PILOT_RESULT_SUMMARY")
    print(json.dumps(summary, indent=2))
    print("Keep this session open; send the summary for review before persistence steps.")
    return output


if __name__ == "__main__":
    PILOT_RESULT = main(globals().get("PILOT_CONTEXT", LATEST_CONTEXT))
