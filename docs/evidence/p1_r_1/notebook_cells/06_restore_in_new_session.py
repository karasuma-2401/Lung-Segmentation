# Kaggle Python cell: run after cell02c in a separate NEW notebook/session.
# Do not rerun conversion. Mounted datasets remain read-only.
from pathlib import Path, PurePosixPath
from uuid import uuid4
import hashlib, importlib.util, json, os, platform, shutil, subprocess, tarfile

# Set True ONLY after ending the original session and starting the new notebook.
FRESH_SESSION_ATTESTED = False
OLD_WORK = Path("/kaggle/working/pilot_cpu_20261124T103900Z_a9054907")
TRANSFER_SHA = "a7285babe7d1c0fa5a24fef48f064b2fc558113ba75aa1b2e948d493c1b4f3dc"
RESULT_SHA = "8da1ebd95caac4551160cfcdfc9e8e749fec7f82d13a3bb6f1a836d6c670687a"
INPUT_SHA = "c97683893715b34fbb7cdf7193134220625169021acb39aae00f6243ce9c4f6f"
KIT_SHA = "7e017276b086afeb646c6c7e17aceed797cd93a12086868a0308cfd1e59be8d0"


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024**2), b""): digest.update(chunk)
    return digest.hexdigest()


def extract_result(archive, stage, expected_sha=TRANSFER_SHA, expected_bytes=57477120, expected_members=28):
    archive, stage = Path(archive), Path(stage)
    assert not stage.exists(), "Fresh restore stage required; do not overwrite old artifacts"
    assert archive.stat().st_size == expected_bytes and file_sha(archive) == expected_sha, "Result transfer corruption"
    with tarfile.open(archive, "r:") as handle:
        members = handle.getmembers()
        assert len(members) == expected_members and len({m.name for m in members}) == expected_members
        for member in members:
            path = PurePosixPath(member.name)
            assert member.isfile() and not path.is_absolute() and ".." not in path.parts, "Unsafe result member"
            assert len(path.parts) >= 2 and path.parts[0] == "result" and "\\" not in member.name and ":" not in member.name, "Unsafe result path"
        size = sum(m.size for m in members)
        assert size <= 256 * 1024**2 and shutil.disk_usage(stage.parent).free >= size + 1024**3, "Restore disk budget exceeded"
        stage.mkdir()
        handle.extractall(stage, filter="data")
    return stage / "result"


RESTORE_CODE = r'''
from pathlib import Path
import importlib.util,json,sys
repo,kit,result,expected,report_path=map(str,sys.argv[1:6])
sys.path.insert(0,str(Path(repo)/"src"))
from lungseg.data.weak import implementation
from lungseg.data.nsclc_version import conversion_implementation
producer=json.loads((Path(result)/"run.json").read_text())
assert implementation()==producer["implementation"]["weak"], "Weak restore implementation/runtime differs from producer; preserve logs and review environment"
assert conversion_implementation()==producer["implementation"]["nsclc"], "NSCLC restore implementation/runtime differs from producer; preserve logs and review environment"
spec=importlib.util.spec_from_file_location("restore_pilot",kit)
pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)
report=pilot.restore(Path(result),expected,True)
report.update(restore_implementation_equal_to_producer=True,old_work_directory_absent=True,
    input_bundle_readback_verified=True,session_evidence_review="REQUIRED_FROM_USER_NOTEBOOK_URL_AND_ATTESTATION")
assert report["session_restore_status"]=="USER_ATTESTED_FRESH_SESSION_CONTENT_PASS"
with Path(report_path).open("x",encoding="utf-8") as handle:json.dump(report,handle,indent=2)
print(json.dumps(report,indent=2))
'''


def main(context_path):
    assert FRESH_SESSION_ATTESTED, "Confirm you ended the original session and started a new notebook before setting FRESH_SESSION_ATTESTED=True"
    assert platform.system() == "Linux" and not OLD_WORK.exists(), "Original session cache is present; stop and use a fresh notebook/session"
    context_path = Path(context_path)
    context = json.loads(context_path.read_text())
    work, repo, python, kit, source_stage = (Path(context[k]) for k in ("work", "repo", "python", "kit", "stage"))
    assert work.resolve() == context_path.parent.resolve() and work.resolve().is_relative_to(Path("/kaggle/working").resolve())
    assert file_sha(kit) == KIT_SHA and context["input_root_sha256"] == INPUT_SHA
    spec = importlib.util.spec_from_file_location("verified_restore_kit", kit)
    pilot = importlib.util.module_from_spec(spec); spec.loader.exec_module(pilot)
    pilot.verify(source_stage / "pilot_input", "INPUT_ROOT.json", INPUT_SHA)
    matches = list(Path("/kaggle/input").rglob("se374-pilot-result-8da1ebd95caa.bin"))
    assert len(matches) == 1, "Attach exactly one approved Result Dataset"
    run_id = uuid4().hex[:12]
    result = extract_result(matches[0], work / ("restored_" + run_id))
    inventory = pilot.verify(result, "RESULT_ROOT.json", RESULT_SHA)
    assert len(inventory) == 27, "Unexpected restored artifact set"
    assert subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip() == "dc6e179087737621b69d538ef200436c644a7687"
    report_path, log_path = work / ("restore_" + run_id + ".json"), work / ("restore_" + run_id + ".log")
    env = {key: value for key, value in os.environ.items() if not key.startswith("PIP_") and key not in ("PYTHONHOME", "PYTHONPATH")}
    env.update(CUDA_VISIBLE_DEVICES="", PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK="1")
    command = [str(python), "-I", "-c", RESTORE_CODE, str(repo), str(kit), str(result), RESULT_SHA, str(report_path)]
    process = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True)
    with log_path.open("x", encoding="utf-8") as handle:handle.write(process.stdout + process.stderr)
    if process.stderr:print(process.stderr)
    print(process.stdout)
    assert process.returncode == 0, f"Restore failed; preserve artifacts/log: {log_path}"
    report = json.loads(report_path.read_text())
    print("RESTORE_RESULT_SUMMARY")
    print(json.dumps({"restore": report, "report_path": str(report_path),
                      "original_session_work_absent": True, "new_setup_work": str(work),
                      "result_dataset_mount": str(matches[0]), "training_clearance": False}, indent=2))
    print("Send this summary plus the NEW notebook URL and confirmation that the original session ended.")


if __name__ == "__main__":
    assert "PILOT_CONTEXT" in globals(), "Run cell02c only in the new session first; do not run cell03/04"
    main(PILOT_CONTEXT)
