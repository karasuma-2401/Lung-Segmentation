# Kaggle Python cell: package the reviewed result in temporary notebook cache.
# No upload, Save Version, cleanup or session termination is performed.
from pathlib import Path
import hashlib, importlib.util, json, shutil, tarfile

RESULT_SHA = "8da1ebd95caac4551160cfcdfc9e8e749fec7f82d13a3bb6f1a836d6c670687a"
KIT_SHA = "7e017276b086afeb646c6c7e17aceed797cd93a12086868a0308cfd1e59be8d0"
CONTEXT = Path("/kaggle/working/pilot_cpu_20261124T103900Z_a9054907/runtime_context.json")
RESULT = Path("/kaggle/working/pilot_cpu_20261124T103900Z_a9054907/result_20261124T104648Z_39a1c42c")


def pack_result(pilot, result, destination, expected_sha=RESULT_SHA, expected_files=27):
    result, destination = Path(result), Path(destination)
    assert not destination.exists(), "Transfer already exists; preserve it and send its prior output"
    inventory = pilot.verify(result, "RESULT_ROOT.json", expected_sha)
    assert len(inventory) == expected_files, "Unexpected artifact inventory"
    expected = {**inventory, "RESULT_ROOT.json": {
        "bytes": (result / "RESULT_ROOT.json").stat().st_size, "sha256": expected_sha}}
    payload_bytes = sum(entry["bytes"] for entry in expected.values())
    assert payload_bytes <= 256 * 1024**2, "Result exceeds bounded 256 MiB pilot transfer"
    assert shutil.disk_usage(destination.parent).free >= payload_bytes + 1024**3, "Need payload plus 1 GiB disk reserve"
    with destination.open("xb") as output:
        with tarfile.open(fileobj=output, mode="w") as archive:
            for name in sorted(expected):
                path = result / name
                assert path.is_file() and not path.is_symlink()
                archive.add(path, arcname="result/" + name, recursive=False)
    # Read back every archived payload byte against the pinned result receipt.
    with tarfile.open(destination, "r:") as archive:
        members = archive.getmembers()
        assert len(members) == len(expected) and {m.name for m in members} == {"result/" + name for name in expected}
        for member in members:
            assert member.isfile()
            entry = expected[member.name[len("result/"):]]
            assert member.size == entry["bytes"]
            digest = hashlib.sha256()
            with archive.extractfile(member) as handle:
                for block in iter(lambda: handle.read(1024**2), b""): digest.update(block)
            assert digest.hexdigest() == entry["sha256"], member.name
    pilot.verify(result, "RESULT_ROOT.json", expected_sha)
    return {"status": "RESULT_TRANSFER_PREPARED_AND_READBACK_VERIFIED",
            "transfer_file": str(destination), "transfer_bytes": destination.stat().st_size,
            "transfer_sha256": pilot.sha(destination), "result_root_sha256": expected_sha,
            "result_files": len(inventory), "archive_files_including_receipt": len(expected),
            "payload_bytes": payload_bytes, "upload_performed": False,
            "cross_session_persistence": "NOT_RUN", "training_clearance": False}


def main():
    assert CONTEXT.is_file() and RESULT.is_dir(), "Keep the successful pilot session open; cache is required"
    context = json.loads(CONTEXT.read_text())
    kit = Path(context["kit"])
    assert hashlib.sha256(kit.read_bytes()).hexdigest() == KIT_SHA, "Pilot kit changed"
    spec = importlib.util.spec_from_file_location("verified_result_packager", kit)
    pilot = importlib.util.module_from_spec(spec); spec.loader.exec_module(pilot)
    destination = Path("/kaggle/working/se374-pilot-result-8da1ebd95caa.bin")
    report = pack_result(pilot, RESULT, destination)
    with destination.with_suffix(".receipt.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print("RESULT_TRANSFER_READY_NO_UPLOAD")
    print(json.dumps(report, indent=2))
    print("Keep the session open and send this receipt before uploading or ending the session.")


if __name__ == "__main__":
    main()
