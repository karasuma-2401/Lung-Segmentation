# Paste into a NEW Kaggle Python cell after EXTRACT_AND_INPUT_VERIFY_PASS.
from pathlib import Path
import hashlib, json, os, platform, subprocess

stage = Path("/kaggle/working/se374_pilot_stage_v1")
work = Path("/kaggle/working/pilot_session_01")
bootstrap = stage / "code/bootstrap_cloud_pilot.sh"
kit = stage / "code/cloud_pilot.py"
setup_log = work.with_name(work.name + ".setup.log")
assert platform.system() == "Linux", "Run this setup cell in Kaggle Linux"
assert not work.exists() and not setup_log.exists(), "Setup output exists; stop and send the output, do not delete it"
assert hashlib.sha256(bootstrap.read_bytes()).hexdigest() == "1bcb18ce3c2085945ae1d7a588e60f9f02fcefaf4329cbe95d40f215e4a574e9"
assert hashlib.sha256(kit.read_bytes()).hexdigest() == "7e017276b086afeb646c6c7e17aceed797cd93a12086868a0308cfd1e59be8d0"
assert hashlib.sha256((stage / "pilot_input/INPUT_ROOT.json").read_bytes()).hexdigest() == "c97683893715b34fbb7cdf7193134220625169021acb39aae00f6243ce9c4f6f"

env = dict(os.environ)
env.update(PILOT_WORK_ROOT=str(work), PILOT_KIT=str(kit),
           CUDA_VISIBLE_DEVICES="", GIT_TERMINAL_PROMPT="0", PIP_DISABLE_PIP_VERSION_CHECK="1")
with setup_log.open("x", encoding="utf-8") as log:
    process = subprocess.Popen(["bash", str(bootstrap)], env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace")
    for line in process.stdout:
        print(line, end="", flush=True)
        log.write(line)
        log.flush()
    code = process.wait()
assert code == 0, f"Setup failed (exit {code}); log retained at {setup_log}"

PROBE_CODE = r'''
from datetime import datetime, timezone
from importlib.metadata import version
import json, platform, subprocess, sys
from pathlib import Path
import numpy, nibabel, pydicom, yaml
from lungseg.data.nsclc_version import conversion_implementation
from lungseg.data.weak import implementation

spec = json.loads(Path(sys.argv[1]).read_text())
revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
assert revision == spec["revision"], "Production Git revision mismatch"
weak, nsclc = implementation(), conversion_implementation()
expected = spec["production_implementation"]
assert weak["sources"] == expected["weak"]["sources"], "Weak source fingerprint mismatch"
assert nsclc["source_sha256"] == expected["nsclc"]["source_sha256"], "NSCLC source fingerprint mismatch"
report = {
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PACKAGE_SOURCE_IMPORT_CHECK_PASS", "platform": platform.system(),
    "python": platform.python_version(), "production_revision": revision,
    "packages": {name: version(name) for name in ("numpy", "nibabel", "pydicom", "PyYAML")},
    "production_source_hashes_match": True,
    "weak_runtime_fingerprint": weak["sha256"],
    "nsclc_runtime_fingerprint": nsclc["fingerprint_sha256"],
    "runtime_identity_equals_local": {"weak": weak == expected["weak"], "nsclc": nsclc == expected["nsclc"]},
    "cache_policy": "fresh output; no reuse of local-runtime conversion cache",
    "native_conversion": "NOT_RUN", "persistence_restore": "NOT_RUN"
}
destination = Path(sys.argv[2])
with destination.open("x", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2)
print(json.dumps(report, indent=2))
'''

env["PYTHONPATH"] = str(work / "repo/src")
report_file = work / "environment_probe.json"
probe = subprocess.run([str(work / "venv/bin/python"), "-c", PROBE_CODE,
                        str(stage / "pilot_input/spec.json"), str(report_file)],
                       cwd=work / "repo", env=env, capture_output=True, text=True)
with (work / "environment_probe.log").open("x", encoding="utf-8") as log:
    log.write(probe.stdout + probe.stderr)
print(probe.stdout)
if probe.stderr:
    print(probe.stderr)
assert probe.returncode == 0, "Environment probe failed; send the output, logs retained"
environment_report = json.loads(report_file.read_text())
assert environment_report["platform"] == "Linux"
print("LINUX_ENVIRONMENT_READY_NO_CONVERSION")
