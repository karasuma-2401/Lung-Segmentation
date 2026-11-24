# Paste into a NEW Kaggle notebook cell after TRANSFER_SHA256_PASS.
from pathlib import Path, PurePosixPath
import hashlib, importlib.util, json, shutil, tarfile

def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

matches = list(Path("/kaggle/input").rglob("se374-pilot-transfer-v1.bin"))
assert len(matches) == 1, f"Expected one transfer file, found {len(matches)}"
archive = matches[0]
assert archive.stat().st_size == 161341440, "Transfer size mismatch"
assert sha256_file(archive) == "f70a2120cb28ce2712e86953669838115c41b658a374ed749645585e6e6454b9", "Transfer SHA256 mismatch"

stage = Path("/kaggle/working/se374_pilot_stage_v1")
assert not stage.exists(), "Stage already exists; stop and send the output, do not delete it"
assert hasattr(tarfile, "data_filter"), "Python tar data filter unavailable; stop and report Python version"
with tarfile.open(archive, "r:") as handle:
    members = handle.getmembers()
    assert len(members) == 184 and len({m.name for m in members}) == 184
    for member in members:
        name = PurePosixPath(member.name)
        assert member.isfile() and not name.is_absolute() and ".." not in name.parts
        assert name.parts[0] in ("pilot_input", "code") and "\\" not in member.name and ":" not in member.name
    total = sum(m.size for m in members)
    assert total <= 2 * 1024**3, "Extraction exceeds bounded pilot limit"
    assert shutil.disk_usage(stage.parent).free >= total + 4 * 1024**3, "Insufficient disk reserve"
    stage.mkdir()
    handle.extractall(stage, filter="data")

kit_manifest = json.loads((stage / "code/kit_manifest.json").read_text())
for relative, entry in kit_manifest["files"].items():
    path = stage / "code" / Path(relative).name
    assert path.stat().st_size == entry["bytes"] and sha256_file(path) == entry["sha256"], relative

code = stage / "code/cloud_pilot.py"
assert sha256_file(code) == "7e017276b086afeb646c6c7e17aceed797cd93a12086868a0308cfd1e59be8d0"
spec = importlib.util.spec_from_file_location("verified_pilot_kit", code)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
inventory = pilot.verify(stage / "pilot_input", "INPUT_ROOT.json",
    "c97683893715b34fbb7cdf7193134220625169021acb39aae00f6243ce9c4f6f")

print("EXTRACT_AND_INPUT_VERIFY_PASS")
print("Verified input files:", len(inventory))
print("Stage:", stage)
print("Conversion has not started")
