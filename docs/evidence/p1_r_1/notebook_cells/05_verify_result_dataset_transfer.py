# Kaggle Python cell: read back the approved uploaded result container.
# No extraction, conversion, upload, cleanup or session termination.
from pathlib import Path
import hashlib

TRANSFER_BYTES = 57477120
TRANSFER_SHA = "a7285babe7d1c0fa5a24fef48f064b2fc558113ba75aa1b2e948d493c1b4f3dc"


def verify_transfer(path, expected_bytes=TRANSFER_BYTES, expected_sha=TRANSFER_SHA):
    path = Path(path)
    assert path.stat().st_size == expected_bytes, "Uploaded result size mismatch"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024**2), b""): digest.update(chunk)
    assert digest.hexdigest() == expected_sha, "Uploaded result SHA256 mismatch"
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def main():
    matches = list(Path("/kaggle/input").rglob("se374-pilot-result-8da1ebd95caa.bin"))
    assert len(matches) == 1, f"Attach the approved Result Dataset first; found {len(matches)} result containers"
    report = verify_transfer(matches[0])
    print("RESULT_DATASET_TRANSFER_SHA256_PASS")
    print("Mounted file:", matches[0])
    print("Bytes:", report["bytes"])
    print("SHA256:", report["sha256"])
    print("Cross-session restore: NOT_RUN. Send this output before ending the current session.")


if __name__ == "__main__":
    main()
