# NEW Kaggle Python cell after the ensurepip failure. Keep the failed venv/log.
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, platform, re, shutil, subprocess, sys

stage = Path("/kaggle/working/se374_pilot_stage_v1")
work = Path("/kaggle/working/pilot_session_01")
repo = work / "repo"
new_venv = work / "venv_external_pip_01"
log_path = work / "recovery_external_pip_01.log"
report_path = work / "environment_recovery_01.json"
assert platform.system() == "Linux" and (3, 11) <= sys.version_info[:2] < (3, 14)
assert repo.is_dir(), "Pinned repo missing; stop and send the output"
assert shutil.disk_usage(work).free >= 4 * 1024**3, "Insufficient disk reserve for environment setup"
assert not new_venv.exists() and not log_path.exists() and not report_path.exists(), "Recovery output exists; stop, do not delete it"
assert hashlib.sha256((stage / "pilot_input/INPUT_ROOT.json").read_bytes()).hexdigest() == "c97683893715b34fbb7cdf7193134220625169021acb39aae00f6243ce9c4f6f"
assert hashlib.sha256((stage / "code/cloud_pilot.py").read_bytes()).hexdigest() == "7e017276b086afeb646c6c7e17aceed797cd93a12086868a0308cfd1e59be8d0"

expected = json.loads((stage / "pilot_input/spec.json").read_text())
revision = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
assert revision == expected["revision"], "Git revision mismatch"
for name, field in (("weak", "sources"), ("nsclc", "source_sha256")):
    for relative, checksum in expected["production_implementation"][name][field].items():
        source = (repo / "src/lungseg" / relative).read_text(encoding="utf-8")
        assert hashlib.sha256(source.encode()).hexdigest() == checksum, relative

# Drop inherited install destinations/constraints without editing the notebook environment.
env = {k: v for k, v in os.environ.items()
       if not k.startswith("PIP_") and k not in ("PYTHONHOME", "PYTHONPATH")}
env.update(PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK="1", CUDA_VISIBLE_DEVICES="")
with log_path.open("x", encoding="utf-8") as log:
    def run_logged(argv):
        print("RUN:", " ".join(map(str, argv)), flush=True)
        log.write("argv: " + json.dumps(list(map(str, argv))) + "\n")
        output = []
        process = subprocess.Popen(list(map(str, argv)), cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                   encoding="utf-8", errors="replace")
        for line in process.stdout:
            output.append(line); print(line, end="", flush=True); log.write(line); log.flush()
        code = process.wait()
        log.write(f"exit_code: {code}\n"); log.flush()
        assert code == 0, f"Command failed ({code}); send output. Log retained: {log_path}"
        return "".join(output)

    pip_version = run_logged([sys.executable, "-m", "pip", "--version"])
    match = re.search(r"pip (\d+)\.(\d+)", pip_version)
    assert match and tuple(map(int, match.groups())) >= (22, 3), "Base pip>=22.3 required; do not upgrade notebook base automatically"
    run_logged([sys.executable, "-I", "-m", "venv", "--without-pip", new_venv])
    target_python = new_venv / "bin/python"
    # Parent pip manages ONLY this fresh target. Install pip there for the pilot's freeze step.
    run_logged([sys.executable, "-m", "pip", "--python", target_python, "install",
                "--index-url", "https://pypi.org/simple", "--only-binary=:all:",
                "pip>=22.3,<27", "numpy>=2,<3", "nibabel>=5,<6", "pydicom>=3,<4", "PyYAML>=6,<7"])
    run_logged([target_python, "-I", "-m", "pip", "check"])
    frozen = run_logged([target_python, "-I", "-m", "pip", "freeze", "--all"])
    with (work / "recovery_resolved_linux.freeze.txt").open("x", encoding="utf-8") as handle:
        handle.write(frozen)

PROBE_CODE = r'''
from datetime import datetime, timezone
from importlib.metadata import version
import json, platform, sys
from pathlib import Path
spec = json.loads(Path(sys.argv[1]).read_text())
sys.path.insert(0, str(Path(sys.argv[3]) / "src"))
assert Path(sys.prefix).resolve() == Path(sys.argv[4]).resolve()
assert sys.prefix != sys.base_prefix, "Not isolated from base Python"
import numpy, nibabel, pydicom, yaml, pip
from lungseg.data.nsclc_version import conversion_implementation
from lungseg.data.weak import implementation
weak, nsclc = implementation(), conversion_implementation()
baseline = spec["production_implementation"]
assert weak["sources"] == baseline["weak"]["sources"]
assert nsclc["source_sha256"] == baseline["nsclc"]["source_sha256"]
report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PACKAGE_SOURCE_IMPORT_CHECK_PASS", "platform": platform.system(),
    "python": platform.python_version(), "production_revision": spec["revision"],
    "packages": {name: version(name) for name in ("pip", "numpy", "nibabel", "pydicom", "PyYAML")},
    "production_source_hashes_match": True, "isolated_target_venv": True,
    "weak_runtime_fingerprint": weak["sha256"], "nsclc_runtime_fingerprint": nsclc["fingerprint_sha256"],
    "runtime_identity_equals_local": {"weak": weak == baseline["weak"], "nsclc": nsclc == baseline["nsclc"]},
    "native_conversion": "NOT_RUN", "persistence_restore": "NOT_RUN"}
with Path(sys.argv[2]).open("x", encoding="utf-8") as handle:json.dump(report, handle, indent=2)
print(json.dumps(report, indent=2))
'''
probe = subprocess.run([str(target_python), "-I", "-c", PROBE_CODE,
                        str(stage / "pilot_input/spec.json"), str(report_path), str(repo), str(new_venv)],
                       cwd=repo, env=env, capture_output=True, text=True)
with (work / "recovery_environment_probe.log").open("x", encoding="utf-8") as handle:
    handle.write(probe.stdout + probe.stderr)
print(probe.stdout)
if probe.stderr:print(probe.stderr)
assert probe.returncode == 0, "Recovery probe failed; send the output, keep logs"
report = json.loads(report_path.read_text())
assert report["platform"] == "Linux" and report["isolated_target_venv"]
context = {"stage": str(stage), "work": str(work), "repo": str(repo),
           "python": str(target_python), "venv": str(new_venv),
           "environment_report": str(report_path), "bootstrap_method": "venv_without_pip_plus_parent_pip_python",
           "failed_venv_preserved": True, "native_conversion": "NOT_RUN"}
with (work / "runtime_context_recovery_01.json").open("x", encoding="utf-8") as handle:
    json.dump(context, handle, indent=2)
print("LINUX_ENVIRONMENT_READY_NO_CONVERSION")
print("Recovery context:", work / "runtime_context_recovery_01.json")
