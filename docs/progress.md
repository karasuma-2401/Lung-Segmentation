# Tiến độ P0 — 24/11/2026

Phạm vi: **P0 / T01–T03**. Dự án mới; chưa có dataset, split thực, run E01–E08 hoặc kết quả nghiên cứu. Dừng ở P0 theo phạm vi đã thống nhất; P1 chưa bắt đầu.

## Trạng thái task

| Task | Trạng thái | Bằng chứng |
|---|---|---|
| T01: paper/source audit | DONE với câu hỏi OPEN đã ghi nhận | [Matrix](paper_to_code_matrix.md), [static audit JSON](evidence/upstream_audit.json), pinned upstream `d1bca4b8dec8f3fe623b58d35be78055b954428c`. Đã đọc Methods, Algorithm1, Fig2, Tables2–5, Discussion và source paths chính. |
| T02: environment / smoke | DONE trên CPU; GPU NOT RUN | [env_check.txt](evidence/env_check.txt), [environment.json](evidence/environment.json), [smoke CPU output](evidence/smoke_cpu.txt), [verification log](evidence/verification.json). |
| T03: repo conventions / tooling / tests | DONE trong phạm vi P0 | README, pyproject, CPU lock, reference/protocol/smoke configs, CLI thật, local run registry, 27 tests, decision/progress docs. |

T01 hoàn thành việc **audit và ghi gaps**; không có nghĩa model/method gốc đã tái hiện. T02 CPU pass không thay thế yêu cầu profile GPU và resume ở T10. Các câu hỏi source không trả lời được được giữ OPEN trong [decisions.md](decisions.md).

## Đã hiện thực và vì sao

- `src/lungseg/config.py`: config smoke typed/strict, từ chối thiếu/thừa key, shape không hợp lệ, NaN/Inf, bool thay integer và config research/reference; giới hạn smoke tối đa 10 updates.
- `src/lungseg/environment.py`: import/versions thực, RAM/disk, torch CUDA/device; hash source để trace khi chưa có commit.
- `src/lungseg/smoke.py`: MONAI fixture 3D nhỏ, binary foreground, forward → scalar finite DiceLoss → backward → finite/nonzero gradients → Adam update. Seed/config lặp lại cho kết quả CPU giống nhau.
- `src/lungseg/runs.py`, `cli.py`: per-run directory độc quyền, resolved config/hash, timestamp/environment, metadata atomic, trạng thái completed/failed. Không ghi success khi yêu cầu CUDA thất bại, không ghi đè run cũ.
- `scripts/verify.ps1`: env/smoke/pytest/pip check bằng một lệnh, có actual command/exit status/output; fail sớm khi check lỗi.
- `scripts/audit_reference.py`: audit tĩnh pin SHA và clean worktree, hash source, parse 47 YAML, trích tables XML có attribution; không import source upstream hoặc xuất patient IDs.
- `configs/protocol.yaml`, `docs/decisions.md`: giữ ba dataset, Scarce target40 train +20 validation, ngân sách nhãn phát triển60, test riêng. Chưa chọn ID hoặc áp các target vào raw data chưa có.

Không tạo module training/data/evaluation rỗng, không expose CLI giả, không tạo metrics/checkpoints nghiên cứu giả. Handoff gốc được copy giữ nguyên, thay đổi đã duyệt ghi riêng ở decisions.

## Những phát hiện ảnh hưởng triển khai

1. `Engine.train.initiate` dùng key `train` cho cả train/validation; cấu trúc config cũng không tương thích loader/factory hiện tại. Không dùng trực tiếp cho đối chứng.
2. `optimizer.step()` mỗi batch và `zero_grad()` chỉ trước loop, khác accumulation8 paper; checkpoint chỉ model weights. Cần loop và resume contract mới ở T10.
3. UNet4 sample không phải architecture Fig2: MaxPool/BatchNorm/LeakyReLU, depth khác. Các biến thể MONAI gần hơn về blocks nhưng channels/depth/config chưa resolve đủ.
4. Utilities weak có rủi ro DICOM order/affine, filter CT và bbox dùng ngưỡng Z khác nhau; crop/box writer chưa preserve affine đầy đủ. Không sử dụng cho raw conversion khi chưa sửa và kiểm định.
5. Source có split YAML nhưng chưa truy được exact scarce weak pool/patient mapping; không thấy object-F1/DSC-TP matching implementation. Dùng adapted protocol minh bạch; giải quyết trước full training.
6. Đối chiếu Tables2–5: DSC means trong handoff khớp. Scarce MSD 71.00 là DO; prose SO/DO bất nhất như handoff đã cảnh báo.

Path:line, phạm vi search và validation dự kiến được ghi đầy đủ trong matrix.

## Commands và kết quả thực

| Command | Kết quả |
|---|---|
| `git clone --depth 1 https://github.com/VemundFredriksen/LungTumorMask.git .reference/LungTumorMask` | Sandbox network thất bại; chạy với quyền network được tool duyệt thành công. |
| `git -C .reference/LungTumorMask rev-parse HEAD` | `d1bca4b8dec8f3fe623b58d35be78055b954428c`; worktree upstream clean. |
| `py -3.13 -m venv .venv` + cài dependencies CPU trong venv | Thành công; không thay Python hệ thống hoặc cài legacy upstream. |
| `.venv\Scripts\python.exe -m pip install -e ".[dev,data]" --no-build-isolation` | Exit0, package editable cài thành công. |
| `.venv\Scripts\python.exe scripts/audit_reference.py` | Exit0, audit49 file Python /47 YAML; `data_test.yaml` lỗi syntax ghi trong report, không sửa source. |
| `.\scripts\verify.ps1` | Exit0; xem `verify_0.txt`…`verify_3.txt` và `verification.json`. |
| `python -m pytest -q` trong virtualenv | **27 passed**. Kiểm CPU forward/backward/update, reproducibility, invalid config, run collision/path traversal, completed/failed CLI. |
| `python -m pip check` trong virtualenv | **No broken requirements found.** |
| `python -m lungseg.cli env-check --output docs/evidence/environment.json` | Exit0, dependency imports pass; report cuối cập nhật sau khi sửa Git ownership. |
| `python -m lungseg.cli smoke-test --config configs/smoke.yaml --run-id P0_cpu_verified` | Exit0; artifact tại `experiments/P0_cpu_verified/`, output lưu `smoke_cpu.txt`; chỉ synthetic fixture. |

Lệnh trong bảng viết gọn; `verify_*.txt` chứa command thực với timestamp UTC và exit code. Kiểm thử CUDA-unavailable trong pytest là mô phỏng nhánh lỗi bằng monkeypatch, **không phải GPU run**.

Môi trường đo: Windows11 AMD64, Python3.13.15, torch2.15.0+cpu, MONAI1.6.2, NumPy2.5.5, PyYAML6.0.4, pytest9.2.0; SimpleITK2.5.8, NiBabel5.5.0, Matplotlib3.11.2, pydicom3.0.2 import pass. Toàn bộ versions pinned ở `requirements-cpu.lock.txt`.

RAM vật lý 8,215,101,440 bytes (~7.65 GiB); disk C còn khoảng61 GiB lúc env-check. Đây là số tức thời, chưa phải capacity plan cho ba dataset. CUDA unavailable với CPU build, compiled CUDA=null; GPU smoke/VRAM/profile/Kaggle đều NOT RUN. Không suy ra máy chắc chắn không có GPU vật lý từ kết quả này.

Git local đã init, chưa có commit/remote và chưa push. Git metadata rỗng ban đầu do sandbox sở hữu đã được giữ lại trong `.reference/p0-initial-git-metadata/`, khởi tạo lại bằng tài khoản người dùng để tránh dubious ownership; không đổi global `safe.directory`. `revision=null` là có chủ đích vì chưa commit; package source SHA256 nằm trong report/run metadata. Log verify đầu có lỗi ownership ở phần Git metadata (không ảnh hưởng imports/smoke/tests); báo cáo environment cuối ghi trạng thái mới trung thực.

## Acceptance checklist

| Tiêu chí P0 | Trạng thái | Bằng chứng |
|---|---|---|
| Working repo và upstream pinned | PASS | Git local + upstream SHA, static audit clean |
| Matrix có code paths/lines, differences và OPEN questions | PASS | paper_to_code_matrix.md / decisions.md |
| Setup/config/dependencies tái chạy, không dùng path máy tác giả | PASS | README, pyproject, CPU lock; sample runtime paths tương đối |
| Env versions/CPU/CUDA status thật | PASS | environment.json / env_check.txt |
| Synthetic3D forward/loss/backward/optimizer update | PASS CPU | smoke_cpu.txt / result.json |
| CUDA smoke | NOT RUN, không chặn CPU P0 | CPU torch build; không có CUDA runtime khả dụng |
| Tests đã chạy, có output thật | PASS | 27 passed; verify_2.txt |
| Progress/decisions/next steps | PASS | tài liệu này và decisions.md |
| Giữ scope3 datasets, không train full hoặc mở P1 | PASS | Chưa có data/run E01–E08; chỉ fixture |

## Đề xuất thứ tự P1 — chưa thực hiện

1. **T04**: MSD-Lung inventory trước để có một nguồn strong kiểm thử geometry, đồng thời xác minh license/metadata chính thức của cả ba nguồn.
2. **T05/T06**: NSCLC CT–RTSTRUCT conversion đúng UID/ROI và Lung-PET-CT-Dx annotation sample/UID/bbox; kiểm dung lượng trước tải bulk, giữ exclusion log.
3. **T07**: sau QC/duplicate checks, khóa test patient~15%/nguồn, validation20, Vast pool và Scarce subset40; version/hash mọi split, không overlap.
4. **T08**: crop/spacing/bbox/inverse và CT-only lung ROI QA; overlay thực và one-batch smoke. Chưa main training cho tới Gate A.

Các việc cần tài nguyên/người dùng ở giai đoạn sau: địa điểm lưu dữ liệu đủ chỗ, quyền tải dataset theo điều kiện nguồn, môi trường Kaggle GPU và cách lưu checkpoint giữa session. Chưa cần chúng để hoàn thành P0 CPU. Các OPEN methodology sẽ được resolve bằng source/data/tests trước training, không âm thầm default thành paper setting.
