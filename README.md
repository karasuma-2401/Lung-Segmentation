# Lung Tumor Segmentation — SE374.R11

Dự án nghiên cứu mixed supervision Teacher–Student trên CT 3D. Phương án chính dùng MSD-Lung và NSCLC-Radiomics có mask, cùng Lung-PET-CT-Dx có axial bbox. Chạy Scarce trước Vast; Student cuối cùng nhận CT và xuất mask, không cần bbox.

Hiện có tooling P0, MSD T04, NSCLC T05/P1.2.1 và **Lung-PET-CT-Dx T06/P1.3**. Hai nguồn sau mới validated sample, full corpus bị chặn storage. T06 dùng expert bbox SR chính thức IDC; XML gốc chưa local-verified. Chưa có splits, production preprocessing hoặc research training. Xem [tiến độ](docs/progress.md), [quyết định](docs/decisions.md), [paper–code matrix](docs/paper_to_code_matrix.md).

## Cài đặt CPU trên Windows

Chạy từ thư mục gốc dự án với Python 3.11–3.13. Môi trường P0 đã đo dùng Python 3.13.15; `python` chưa có trên PATH của máy ban đầu nên có thể dùng launcher `py`.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-cpu.lock.txt
.\.venv\Scripts\python.exe -m pip install -e ".[dev,data]" --no-build-isolation
.\.venv\Scripts\python.exe -m lungseg.cli env-check --output docs/evidence/environment.json
.\.venv\Scripts\python.exe -m lungseg.cli smoke-test --config configs/smoke.yaml
.\.venv\Scripts\python.exe -m pytest -q
```

`requirements-cpu.lock.txt` khóa toàn bộ dependency đã thực chạy trên Windows CPU/Python 3.13; không áp nguyên lock này cho Kaggle CUDA. `pyproject.toml` mô tả khoảng tương thích, không thay thế bản khóa của một run. Không downgrade Python hệ thống để cài stack năm 2022.

Một lệnh chạy env-check, smoke, tests và dependency check, ghi command/timestamp/exit code vào `docs/evidence/`:

```powershell
.\scripts\verify.ps1
```

Script dừng với lỗi nếu một check thất bại. Nếu PowerShell chặn script theo policy máy, chạy bốn lệnh tương ứng trực tiếp; không cần đổi policy hệ thống.

## Smoke và artifact

Fixture MONAI U-Net nhỏ: CT synthetic `[1,1,16,16,16]`, target binary có foreground, channels `[4,8,16]`, hai downsamplings, Dice Loss trên logits với sigmoid đúng một lần, Adam hai updates. Kiểm tra shape, finite output/loss/gradients, gradient khác 0 và parameter thay đổi. Đây **chưa phải architecture Teacher/Student của paper** và loss synthetic không phải kết quả nghiên cứu.

```powershell
.\.venv\Scripts\python.exe -m lungseg.cli smoke-test --config configs/smoke.yaml --device cpu
# Chỉ dùng khi đã có CUDA build/device:
.\.venv\Scripts\python.exe -m lungseg.cli smoke-test --config configs/smoke.yaml --device cuda
```

Mỗi lần tạo `experiments/P0_smoke_<timestamp>_<id>/` với `config.json`, `metadata.json`, `result.json`. Config đã resolve được hash; metadata có versions/hardware, source hash, Git state, timestamp và `research_result: false`. Run ID trùng bị từ chối, không ghi đè. Run lỗi có status `failed`, không có result pass. Yêu cầu `cuda` khi không khả dụng trả exit 1, không tự đổi thành CPU; `auto` ghi rõ thiết bị được chọn. Chưa có checkpoint/resume production ở P0.

`env-check` trả exit 0 khi import dependency tối thiểu thành công; thư viện data tùy chọn và CUDA được báo riêng. CUDA unavailable không chứng minh máy không có phần cứng GPU. CPU pass không phải CUDA pass.

## Tài liệu và configs

- `docs/PROJECT_HANDOFF.md`: bản handoff gốc giữ nguyên; cập nhật đã thống nhất nằm ở `docs/decisions.md`.
- `configs/protocol.yaml`: ý định protocol đã duyệt — 40 strong train + 20 strong validation, test khoảng 15% bệnh nhân mỗi nguồn strong; chưa có ID nào được chọn.
- `configs/references/paper.yaml`: thông số bài báo, có đánh dấu chưa rõ.
- `configs/references/upstream.yaml`: thông số source và pinned commit, không phải config training chạy được.
- `configs/smoke.yaml`: config thực chạy cho P0. CLI từ chối config reference/protocol.
- `src/lungseg/`: công cụ P0 và data adapters T04–T06 cho native acquisition/inventory/QA. Chưa expose `train`, `split`, `preprocess`, `evaluate` hoặc `generate-pseudo`.
- `data/README.md`: quy tắc lưu dữ liệu. Raw/cache/pseudo/checkpoints/virtualenv/reference clone đều gitignored.

## MSD-Lung — P1.1/T04

[Hướng dẫn acquisition](docs/msd_acquisition.md), [schema manifest](docs/msd_manifest_schema.md), [data card](docs/data_cards/msd_lung.md), [QA report](docs/msd_qa_report.md).

```powershell
# Preflight: HEAD + disk check, không tải CT:
.\.venv\Scripts\python.exe -m lungseg.cli acquire-msd --config configs/msd.yaml
# Tải khoảng9.16 GB, giải nén khi đủ chỗ và giữ provenance:
.\.venv\Scripts\python.exe -m lungseg.cli acquire-msd --config configs/msd.yaml --download --extract
.\.venv\Scripts\python.exe -m lungseg.cli audit-msd --config configs/msd.yaml
.\.venv\Scripts\python.exe -m lungseg.cli qa-msd --config configs/msd.yaml
# Full P0+T04 checks, giữ riêng evidence P0:
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_1/verification
```

Manifest/summary/run metadata: `data/manifests/msd/`. Montage/index: `data/qa/msd/` (gitignored medical slices). Official test CT không có mask; `patient_id` để null nếu không có mapping nguồn, không suy luận từ case ID. Các findings MSD giữ nguyên khi triển khai T05.

## NSCLC-Radiomics — P1.2.1 hardening, sample only

Xem [acquisition guide](docs/nsclc_acquisition.md), [data card](docs/nsclc_data_card.md), [schema](docs/nsclc_manifest_schema.md), [P1.2 report](docs/nsclc_qa_report.md) và [P1.2.1 report](docs/nsclc_hardening_report.md). Nguồn TCIA/IDC chính thức, **CC BY-NC 3.0**. Chỉ10ca mẫu; full corpus vẫn BLOCKED_STORAGE. [Full-corpus execution plan](docs/full_corpus_execution_plan.md) chỉ là thiết kế, chưa thực thi.

```powershell
# Kiểm metadata/capacity; chưa tải DICOM:
.\.venv\Scripts\python.exe -m lungseg.cli acquire-nsclc --config configs/nsclc_p1_2_1.yaml --catalog data/manifests/nsclc/public_catalog.json
# Pipeline offline sau verified acquisition:
.\.venv\Scripts\python.exe -m lungseg.cli survey-nsclc --config configs/nsclc_p1_2_1.yaml
.\.venv\Scripts\python.exe -m lungseg.cli convert-nsclc --config configs/nsclc_p1_2_1.yaml
.\.venv\Scripts\python.exe -m lungseg.cli qa-nsclc --config configs/nsclc_p1_2_1.yaml
# Kiểm repeat manifest/raw hashes và regression, evidence riêng:
.\.venv\Scripts\python.exe scripts/revalidate_nsclc_sample.py --baseline-config configs/nsclc.yaml --config configs/nsclc_p1_2_1.yaml
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_2_1/verification
```

`convert-nsclc` exit2 khi có quarantine findings, exit1 khi thao tác không chạy được; đọc report trước khi tiếp tục. P1.2 artifacts thiếu implementation identity là **legacy/stale**, không được tự reuse. `configs/nsclc.yaml` giữ làm baseline; dùng output mới trong `configs/nsclc_p1_2_1.yaml` cho explicit reconversion, không xóa/overwrite baseline. Đổi algorithm/modules/dependency versions làm fingerprint khác; đổi source/full config cũng từ chối cache. QA kiểm identity trước render. Config hỗ trợ external roots; dùng cùng cấu hình cho toàn pipeline. Full download/conversion không được CLI này hỗ trợ; sample giới hạn1–20IDs. Raw/converted/montage gitignored. Dừng sau P1.2.1 để review.

## Lung-PET-CT-Dx — P1.3/T06, sample only

[Acquisition guide](docs/weak_acquisition.md), [data card](docs/weak_data_card.md), [annotation survey](docs/weak_annotation_survey.md), [manifest schema](docs/weak_manifest_schema.md), [QA report](docs/weak_qa_report.md). Official CT + expert XML harmonized to DICOM SR (IDC), CC BY4.0; không AI SEG.10sample CT/SR,77bbox/75positive slices;345missing/unknown không phải negative. Bbox volume không là segmentation GT/pseudo mask; không training clearance.

```powershell
# Metadata/capacity only:
.venv\Scripts\python.exe -m lungseg.cli acquire-weak --config configs/weak_p1_3_1.yaml
# Sau bounded acquisition theo guide, chạy offline:
.venv\Scripts\python.exe scripts/revalidate_weak_sample.py
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_3_1/verification
```

P1.3.1 dùng `configs/weak_p1_3_1.yaml`, output `data/converted/weak_p1_3_1_v2`, manifest `data/manifests/weak_p1_3_1`, QA `data/qa/weak_p1_3_1`. [Hardening report](docs/weak_hardening_report.md) ghi reconciliation, exit contract và before/after. `configs/weak.yaml`, `weak_v1_1`, `data/manifests/weak`, `data/qa/weak` là baseline P1.3: giữ nguyên, không chạy audit mới vào đó. `weak_v1` là interrupted output giữ riêng. Raw/derived images/annotations/PNG gitignored. Same source/config/implementation mới reuse cache; mismatch cần versioned output mới. CLI exit0 = scope command thành công; exit2 = partial/actionable review; exit1 = fatal. Survey parse thành công chưa là training clearance. Offline revalidation khóa network và kiểm preservation. Giữ3datasets, dừng sau P1.3.1; không full download/training.

## Tái tạo audit tham chiếu

Upstream MIT: [VemundFredriksen/LungTumorMask](https://github.com/VemundFredriksen/LungTumorMask), commit `d1bca4b8dec8f3fe623b58d35be78055b954428c`. Clone chỉ dùng đọc source, không cài package upstream và không chạy các scripts có logger ngoài máy.

```powershell
git clone https://github.com/VemundFredriksen/LungTumorMask.git .reference/LungTumorMask
git -C .reference/LungTumorMask checkout --detach d1bca4b8dec8f3fe623b58d35be78055b954428c
New-Item -ItemType Directory -Path .reference/paper -Force
Invoke-WebRequest -Uri 'https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0266147&type=manuscript' -OutFile .reference/paper/article.xml
.\.venv\Scripts\python.exe scripts/audit_reference.py
```

Audit dùng XML open access và kiểm tra SHA/clean worktree; không import code upstream. Output có hashes source, độ dài danh sách YAML (không có ID bệnh nhân) và bảng paper, không chứng minh các split gốc ánh xạ đúng raw dataset. Figure 2 đã xem từ nguồn PLOS; các ảnh nguồn giữ trong `.reference/paper/`.

## Kaggle: dùng lại package

Upload source package được phép vào một Kaggle Dataset riêng tư (có `pyproject.toml`, `src/`, `configs/`, `tests/`; không kèm `.venv`, CT hoặc checkpoint). Đây chỉ là hướng dẫn, chưa thực hiện upload. Trong notebook:

```python
from pathlib import Path
import shutil
import subprocess
import sys

source = Path("/kaggle/input/<your-code-dataset>/lungseg")  # đổi theo mount thực
project = Path("/kaggle/working/lungseg-code")
shutil.copytree(source, project, dirs_exist_ok=True)  # input mount chỉ đọc
subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps",
                "--no-build-isolation", str(project)], check=True)
subprocess.run([sys.executable, "-m", "lungseg.cli", "env-check",
                "--output", "/kaggle/working/environment.json"], check=True)
subprocess.run([sys.executable, "-m", "lungseg.cli", "smoke-test",
                "--config", str(project / "configs/smoke.yaml"), "--device", "cuda",
                "--output-dir", "/kaggle/working/experiments"], check=True)
```

Trước bước trên cần cài dependency còn thiếu từ `pyproject.toml` vào môi trường notebook, giữ torch CUDA tương thích thiết bị. Không cài bản torch CPU từ lock Windows. Lưu `pip freeze`, report môi trường và smoke GPU riêng sau khi chạy thật. `/kaggle/working` chưa đảm bảo persistence qua session: phải lưu notebook outputs và kiểm tra đọc lại ở phiên mới trước full training. Kaggle chưa được kiểm thử trong P0 local.

## Nguồn và quyền sử dụng

[Fredriksen et al. (2022), PLOS ONE](https://doi.org/10.1371/journal.pone.0266147), CC BY; số paper không phải kết quả nhóm. Source upstream giữ LICENSE riêng, không chạy/copy loader lỗi. Chưa chọn license cho code mới. MSD: CC BY-SA4.0; NSCLC: CC BY-NC3.0; Lung-PET-CT-Dx và expert SR: CC BY4.0, xem acquisition guides. Không relabel toàn project data theo license một nguồn. Weights chưa xác minh. Chưa push/publish hoặc train nghiên cứu.
