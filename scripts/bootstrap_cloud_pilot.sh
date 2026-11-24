#!/usr/bin/env bash
# Run explicitly by the user in a Kaggle CPU session. No dataset transfer/upload.
set -euo pipefail
: "${PILOT_WORK_ROOT:?Set a fresh work root outside the mounted input bundle}"
: "${PILOT_KIT:?Set path to the reviewed scripts/cloud_pilot.py file}"
PILOT_REVISION=dc6e179087737621b69d538ef200436c644a7687
PILOT_REPO_URL=https://github.com/karasuma-2401/Lung-Segmentation.git
test ! -e "$PILOT_WORK_ROOT"
mkdir -p "$PILOT_WORK_ROOT"
python -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14), "Python 3.11-3.13 required"'
git clone --filter=blob:none --no-checkout "$PILOT_REPO_URL" "$PILOT_WORK_ROOT/repo"
git -C "$PILOT_WORK_ROOT/repo" fetch origin "$PILOT_REVISION"
git -C "$PILOT_WORK_ROOT/repo" checkout --detach "$PILOT_REVISION"
test "$(git -C "$PILOT_WORK_ROOT/repo" rev-parse HEAD)" = "$PILOT_REVISION"
python -m venv "$PILOT_WORK_ROOT/venv"
"$PILOT_WORK_ROOT/venv/bin/python" -m pip install 'numpy>=2,<3' 'nibabel>=5,<6' 'pydicom>=3,<4' 'PyYAML>=6,<7'
"$PILOT_WORK_ROOT/venv/bin/python" -m pip check
"$PILOT_WORK_ROOT/venv/bin/python" -m pip freeze > "$PILOT_WORK_ROOT/resolved-linux.freeze.txt"
sha256sum "$PILOT_KIT" > "$PILOT_WORK_ROOT/pilot-kit.sha256"
printf 'Bootstrap prepared. cd to the pinned repo; set PYTHONPATH to its src directory. Use venv/bin/python and the reviewed pilot kit. No cloud conversion has run yet.\n'
