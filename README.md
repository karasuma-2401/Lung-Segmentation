# Lung Tumor Segmentation — SE374.R11

Dự án nghiên cứu mixed supervision Teacher–Student trên CT 3D. Phương án chính dùng MSD-Lung và NSCLC-Radiomics có mask, cùng Lung-PET-CT-Dx có axial bbox. Chạy Scarce trước Vast; Student cuối cùng nhận CT và xuất mask, không cần bbox.

Hiện có công cụ **P0**: kiểm tra môi trường, synthetic smoke, kiểm thử và audit paper/source. Chưa có dataset, split thực, model nghiên cứu, pseudo masks hay kết quả thực nghiệm. Xem [tiến độ](docs/progress.md), [quyết định](docs/decisions.md) và [bảng paper–code](docs/paper_to_code_matrix.md).

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
- `src/lungseg/`: chỉ chứa chức năng P0 đã hiện thực. Chưa expose `train`, `split`, `preprocess`, `evaluate` hoặc `generate-pseudo`.
- `data/README.md`: quy tắc lưu dữ liệu. Raw/cache/pseudo/checkpoints/virtualenv/reference clone đều gitignored.

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

[Fredriksen et al. (2022), PLOS ONE](https://doi.org/10.1371/journal.pone.0266147), CC BY; bảng đối chiếu và bảng số liệu tham chiếu có attribution, không phải số của nhóm. Source upstream giữ nguyên cùng LICENSE trong clone; P0 dùng MONAI API và code tooling viết mới, không copy thân model upstream. Chưa chọn license cho code mới của nhóm. License/quyền truy cập dataset và weights cần xác minh riêng ở P1. Không push, publish, train full hoặc mở P1 ở lượt P0.
