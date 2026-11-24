# Standalone Kaggle Python cell. Works with an empty notebook cache after restart.
# Replaces setup cells 02/02b. No conversion, cleanup, upload or global installs.
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from uuid import uuid4
import hashlib, importlib.util, json, os, platform, re, shutil, subprocess, sys, tarfile

TRANSFER_SHA = "f70a2120cb28ce2712e86953669838115c41b658a374ed749645585e6e6454b9"
INPUT_SHA = "c97683893715b34fbb7cdf7193134220625169021acb39aae00f6243ce9c4f6f"
KIT_SHA = "7e017276b086afeb646c6c7e17aceed797cd93a12086868a0308cfd1e59be8d0"
REVISION = "dc6e179087737621b69d538ef200436c644a7687"


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024**2), b""):
            result.update(block)
    return result.hexdigest()


def extract_verified(archive, stage, expected_sha=TRANSFER_SHA,
                     expected_bytes=161341440, expected_members=184):
    archive, stage = Path(archive), Path(stage)
    assert not stage.exists(), "Fresh stage required; nothing will be overwritten"
    assert archive.stat().st_size == expected_bytes and file_sha(archive) == expected_sha, "Transfer integrity mismatch"
    assert hasattr(tarfile, "data_filter"), "Python tar data filter unavailable"
    with tarfile.open(archive, "r:") as handle:
        members = handle.getmembers()
        assert len(members) == expected_members and len({m.name for m in members}) == expected_members
        for member in members:
            name = PurePosixPath(member.name)
            assert member.isfile() and not name.is_absolute() and ".." not in name.parts, "Unsafe tar member"
            assert name.parts[0] in ("pilot_input", "code") and "\\" not in member.name and ":" not in member.name, "Unsafe tar path"
        size = sum(m.size for m in members)
        assert size <= 2 * 1024**3, "Expanded pilot exceeds 2 GiB"
        assert shutil.disk_usage(stage.parent).free >= size + 4 * 1024**3, "Insufficient disk reserve"
        stage.mkdir()
        handle.extractall(stage, filter="data")


def run_logged(argv, cwd, env, log):
    argv = list(map(str, argv))
    print("RUN:", " ".join(argv), flush=True)
    log.write("argv: " + json.dumps(argv) + "\n")
    output = []
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace")
    for line in process.stdout:
        output.append(line); print(line, end="", flush=True); log.write(line); log.flush()
    code = process.wait()
    log.write(f"exit_code: {code}\n"); log.flush()
    assert code == 0, f"Command failed ({code}); log retained at {log.name}"
    return "".join(output)


PROBE_CODE = r'''
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import json, platform, sys
spec = json.loads(Path(sys.argv[1]).read_text())
sys.path.insert(0, str(Path(sys.argv[3]) / "src"))
assert Path(sys.prefix).resolve() == Path(sys.argv[4]).resolve()
assert sys.prefix != sys.base_prefix
import numpy, nibabel, pydicom, yaml, pip
from lungseg.data.weak import implementation
from lungseg.data.nsclc_version import conversion_implementation
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


def main():
    assert platform.system() == "Linux" and (3, 11) <= sys.version_info[:2] < (3, 14), "Kaggle Python 3.11-3.13 required"
    mounted, cache = Path("/kaggle/input"), Path("/kaggle/working")
    matches = list(mounted.rglob("se374-pilot-transfer-v1.bin"))
    assert len(matches) == 1, f"Attach the approved pilot Dataset first; found {len(matches)} transfer files"
    assert shutil.disk_usage(cache).free >= 8 * 1024**3, "Need 8 GiB free for bounded setup/pilot"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    stage = cache / ("se374_stage_" + run_id)
    work = cache / ("pilot_cpu_" + run_id)
    print("Fresh stage:", stage, "\nFresh work:", work, flush=True)
    extract_verified(matches[0], stage)
    manifest = json.loads((stage / "code/kit_manifest.json").read_text())
    for relative, value in manifest["files"].items():
        path = stage / "code" / Path(relative).name
        assert path.stat().st_size == value["bytes"] and file_sha(path) == value["sha256"], relative
    kit = stage / "code/cloud_pilot.py"
    assert file_sha(kit) == KIT_SHA
    module_spec = importlib.util.spec_from_file_location("verified_pilot_kit", kit)
    pilot = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(pilot)
    pilot.verify(stage / "pilot_input", "INPUT_ROOT.json", INPUT_SHA)
    expected = json.loads((stage / "pilot_input/spec.json").read_text())
    assert expected["revision"] == REVISION
    print("EXTRACT_AND_INPUT_VERIFY_PASS", flush=True)
    work.mkdir()
    repo, venv = work / "repo", work / "venv"
    env = {k: v for k, v in os.environ.items() if not k.startswith("PIP_") and k not in ("PYTHONHOME", "PYTHONPATH")}
    env.update(PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK="1", CUDA_VISIBLE_DEVICES="", GIT_TERMINAL_PROMPT="0")
    with (work / "setup.log").open("x", encoding="utf-8") as log:
        invoke = lambda argv: run_logged(argv, work, env, log)
        version_text = invoke([sys.executable, "-m", "pip", "--version"])
        match = re.search(r"pip (\d+)\.(\d+)", version_text)
        assert match and tuple(map(int, match.groups())) >= (22, 3), "Base pip>=22.3 required; do not upgrade base automatically"
        invoke(["git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/karasuma-2401/Lung-Segmentation.git", repo])
        invoke(["git", "-C", repo, "fetch", "origin", REVISION])
        invoke(["git", "-C", repo, "checkout", "--detach", REVISION])
        actual = invoke(["git", "-C", repo, "rev-parse", "HEAD"]).strip()
        assert actual == REVISION, "Pinned checkout mismatch"
        for name, field in (("weak", "sources"), ("nsclc", "source_sha256")):
            for relative, checksum in expected["production_implementation"][name][field].items():
                text = (repo / "src/lungseg" / relative).read_text(encoding="utf-8")
                assert hashlib.sha256(text.encode()).hexdigest() == checksum, relative
        invoke([sys.executable, "-I", "-m", "venv", "--without-pip", venv])
        python = venv / "bin/python"
        invoke([sys.executable, "-m", "pip", "--python", python, "install", "--index-url", "https://pypi.org/simple",
                "--only-binary=:all:", "pip>=22.3,<27", "numpy>=2,<3", "nibabel>=5,<6", "pydicom>=3,<4", "PyYAML>=6,<7"])
        invoke([python, "-I", "-m", "pip", "check"])
        freeze = invoke([python, "-I", "-m", "pip", "freeze", "--all"])
        with (work / "resolved-linux.freeze.txt").open("x", encoding="utf-8") as handle:handle.write(freeze)
        report_path = work / "environment.json"
        invoke([python, "-I", "-c", PROBE_CODE, stage / "pilot_input/spec.json", report_path, repo, venv])
    report = json.loads(report_path.read_text())
    assert report["platform"] == "Linux" and report["isolated_target_venv"]
    pilot.verify(stage / "pilot_input", "INPUT_ROOT.json", INPUT_SHA)
    context = {"run_id": run_id, "stage": str(stage), "work": str(work), "repo": str(repo),
               "python": str(python), "venv": str(venv), "kit": str(kit), "environment_report": str(report_path),
               "input_root_sha256": INPUT_SHA, "bootstrap_method": "standalone_dataset_pip_external",
               "old_stages_deleted_or_overwritten": False, "native_conversion": "NOT_RUN"}
    context_path = work / "runtime_context.json"
    with context_path.open("x", encoding="utf-8") as handle:json.dump(context, handle, indent=2)
    print("LINUX_ENVIRONMENT_READY_NO_CONVERSION")
    print("PILOT_CONTEXT:", context_path)
    return context_path


if __name__ == "__main__":
    PILOT_CONTEXT = main()
