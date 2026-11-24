# Tiến độ hiện tại — P1.3/T06 — 24/11/2026

**SAMPLE_VALIDATED_WITH_REVIEW_FINDINGS cho official expert-SR representation; full corpus BLOCKED_STORAGE/NOT_VALIDATED.** XML gốc timeout, local equivalence chưa verified. User duyệt T06 sau P1.2.1 tại dev commit `a3712db3ecea5607b878c76f40de967004d3eee8`. Giữ3datasets, không full NSCLC/cloud/cleanup/splits/T08/Teacher/pseudo/Student/training; dừng sau P1.3 để review.

| Hạng mục | Kết quả thực /evidence |
|---|---|
|Official source/license |Original TCIA v5/CC BY4.0, expert XML→SR harmonization IDC/Zenodo2025/CC BY4.0; không AI SEG. XML URL timeout, không giả parser XML đã verified |
|Catalog |355patients/436studies/1,295original series=1,162CT+133PT;251,135objects. SR1,091series/354patients, không mặc định bằng annotated CT count |
|Acquisition/sample |10patients/studies/CTseries,420CTslices+10SR,221,804,220bytes payload, UID/header/MD5/SHA256 checked. Final raw450files |
|Bbox/coverage |77bbox/75positive slices,345missing/unknown,0explicit negatives;2multibox slices ởA0003 giữ đầy đủ. GT=false/weak_eligible=false toàn bộ |
|Native conversion |10/10CT+bbox aligned, shape512²×23–64, spacingZ5/8/10mm; edge FOV230–320mm, closed[160,600]mm pass.0real exclusions/quarantine |
|QA |10montage đã xem, A0003 overlaps/A0005single-slice/G0001separated positives/A0006central context cần review. Không expert approval hoặc source edits |
|Verification |**177passed**=126cũ+51T06; CPU smoke/env/pip check pass. Manifest repeat byte-identical/raw unchanged;1,436oldMSD/NSCLC files19.47GB checked,0changes; NSCLC cache fingerprint unchanged |
|Full/storage |Weak fullCT+SR/output allowance≈436.04GB, vượt~53GBfree. Combined known planning3datasets≈553.58GB trước margin/versions/checkpoints; storage/cloud pilot chưa thực hiện |

[Report T06](weak_qa_report.md), [manifest](../data/manifests/weak/manifest_weak.csv), [survey](weak_annotation_survey.md), [tests](evidence/p1_3/verification/verification.json), [preservation](evidence/p1_3/msd_nsclc_preservation.json). Final roots `data/converted/weak_v1_1`, `data/manifests/weak`, `data/qa/weak`; initial interruptedweak_v1 giữ riêng, không merge hoặc xóa. Không thêm runtime dependencies, commit/push.

OPEN trước giai đoạn tiếp: original XML access/equivalence, annotation completeness/multibox semantics, actual665paper subset chưa reproduce, full storage/persistence cho3nguồn. Giữ MSD patient mapping/lung_022/lung_018 và NSCLC002/006/014/128. Không tự chuyển P1-R/T07/T08/research training.

---

# P1.2.1 technical hardening — snapshot đã nghiệm thu

**P1.2.1 technical acceptance PASS; T05 vẫn PARTIAL / SAMPLE_VALIDATED_WITH_REVIEW_FINDINGS, full corpus BLOCKED_STORAGE.** P1.2 được review có điều kiện tại dev commit `1429bb14996beded92cafa128e0d827787f55f5e`. Đã sửa hardening/revalidate sample, dừng sau P1.2.1 để review; không P1.3/T07/T08/training hoặc full download.

| Hạng mục | Kết quả thực / evidence |
|---|---|
|Rasterizer |Reject polygon không có foreground sau rasterization, giữ reason/context; triangle bbox regression, union/XOR/keyhole pass; không đổi phương pháp để006pass |
|Cache identity |`nsclc-native-v2` + SHA2567implementation modules + Python/NumPy/NiBabel/pydicom; legacy/stale/corrupt bị từ chối, không tự overwrite/delete. Real legacy probe PASS |
|Tests |**126passed** =111cũ+15mới, targeted NSCLC58passed; env/CPU smoke/pip check exit0. [Logs](evidence/p1_2_1/verification/verification.json) |
|Revalidation |10real patients,7pairs converted vào root mới,3quarantine006/014/128 giữ cùng reasons.7CT+7mask arrays **0voxels khác**, geometry và volumes giống baseline |
|Integrity |Manifest repeat byte-identical; raw và toàn bộ artifacts P1.2 cũ1,189files hash trước/sau giống nhau; source package khớp env verified |
|QA |7montage mới có PNG bytes giống baseline; không cấp approval mới.002 REVIEW_REQUIRED giữ nguyên, all strong_eligible=false |
|Full-corpus plan |[Thiết kế](full_corpus_execution_plan.md): batch≤10patients/≤1GiB source, scratch10–12GiB, measured RAM gate, persistent NSCLC quota đề xuất≥120GiB. Cloud/Kaggle/restore chưa chạy; storage blocker vẫn còn |

[Báo cáo P1.2.1](nsclc_hardening_report.md), [before/after](evidence/p1_2_1/before_after_comparison.json), [preservation](evidence/p1_2_1/preservation.json), [artifact audit](evidence/p1_2_1/artifact_audit.json). Output mới: `data/converted/nsclc_p1_2_1_v2`, `data/manifests/nsclc_p1_2_1`, `data/qa/nsclc_p1_2_1`; config `configs/nsclc_p1_2_1.yaml`. `configs/nsclc.yaml` và artifacts P1.2 gốc giữ làm baseline, không coi cache thiếu version là compatible.

Giữ ba dataset, ROI/quarantine policy và Scarce/Vast protocol. OPEN002/006/014/128, MSD patient mapping/lung_022/lung_018 vẫn giữ nguyên. Không download thêm, không dọn dữ liệu, không commit/push. Trước mở rộng cần annotation review và storage/persistence pilot được duyệt; không tự triển khai giai đoạn sau.

---

# P1.2 / T05 — snapshot được review có điều kiện

**T05 PARTIAL — SAMPLE_VALIDATED_WITH_REVIEW_FINDINGS; FULL_CORPUS_NOT_VALIDATED / BLOCKED_STORAGE.** Người dùng đã duyệt T05 sau P1.1 tại commit `fef32f1932df3e6e0644b937fdd775f953cd3cae`. Người dùng xác nhận chỉ có khoảng45GiB trên C và không có ổ khác; không tải full corpus, không xóa MSD/archive. Giữ3dataset, không T06–T08/splits/preprocessing production/training. Dừng sau P1.2 để review.

| Hạng mục P1.2 | Trạng thái / evidence |
|---|---|
| Official source/license/catalog |PASS — TCIA v4, CC BY-NC3.0,422patients/studies,422CT+422RTSTRUCT+421SEG catalog; chỉ sample CT/RT được tải |
| Capacity |BLOCKED full — CT+RT27.54GB; ZIP/raw/conversion planning126.75GB hoặc IDC không ZIP99.21GB, vượt khoảng45GiB free. RAM7.65GiB |
| Real sample |10public patients/10CTseries/1,101slice headers và10RTSTRUCT;592,987,154bytes, official IDC exact UID/DOI/license matching TCIA, ETag MD5/SHA256/header verification |
| ROI và conversion |Survey thật trước policy;9/10GTV-1, varied ROI numbers, generic ORGAN tags explicit warning.7converted pairs aligned native geometry, labels0/1;3quarantine006/014/128 |
| Real QA |7three-plane montage đã xem, LUNG1-002 inferior extent REVIEW_REQUIRED; không tự chỉnh annotation. [Visual review](evidence/p1_2/qa_visual_review.json) |
| Determinism/preservation |PASS — manifest byte-identical hai lần, raw tree1,131files hash trước/sau giống nhau. [Evidence](evidence/p1_2/repeat_and_preservation.json) |
| Regression |**111passed** =68P0/P1.1+43T05 synthetic tests; CPU smoke/env/pip check PASS. [Logs](evidence/p1_2/verification/verification.json). GPU/Kaggle NOT RUN |
| Scope và Git |Không raw/converted medical images/montage vào Git, không commit/push, không training hoặc splits |

[Báo cáo P1.2](nsclc_qa_report.md), [manifest](../data/manifests/nsclc/manifest_nsclc.csv), [quarantine](../data/manifests/nsclc/quarantine.csv), [acquisition guide](nsclc_acquisition.md), [data card](nsclc_data_card.md), [schema](nsclc_manifest_schema.md). Converted/QA sample khoảng272MB; C sau sample khoảng44.3GiB free. NBIA ZIP download timeout, adapter chưa real-ZIP validated; actual sample qua IDC chính thức. Code/CLI hỗ trợ external roots nhưng chưa có storage ngoài C.

OPEN: review NSCLC002/006/014/128 và phương án lưu trữ trước full T05; primary policy chưa được khảo sát toàn422ca. Giữ MSD patient mapping unknown, lung_022 annotation review và lung_018 intensity finding nguyên vẹn. Đề xuất P1.3 chỉ khảo sát source/license/annotation sample Lung-PET-CT-Dx và capacity sau review; chưa triển khai.

---

# P1.1 / T04 — snapshot đã được review/chấp thuận

**T04 hoàn tất trong phạm vi acquisition/inventory/QA; dừng để người dùng review.** Có annotation finding OPEN ở lung_022, không tự sửa/loại mask. P0 CPU đã được người dùng chấp thuận trước lượt này. Phần P0 bên dưới là snapshot lịch sử, không mô tả trạng thái dataset hiện tại.

| Hạng mục P1.1 | Trạng thái / evidence |
|---|---|
| Source/license/resource | PASS — AWS MSD public/no-account, CC-BY-SA4.0, archive9,163,696,640 bytes; disk checked trước tải/giải nén; [acquisition](evidence/p1_1/acquisition.json) |
| Real inventory | PASS —95/95 CT,63/63 masks đọc hết voxel;95 unique case IDs;0 auto errors/warnings; [manifest](../data/manifests/msd/manifest_msd.csv), [summary](../data/manifests/msd/summary.json) |
| GT/no GT / identity |63 strong_mask,32 official test không GT,95 patient_id null; không tạo experiment splits hoặc giả patient IDs |
| Geometry/labels/volume |63/63 pairs aligned, LAS95/95, labels0/1, volume min/median/max0.738/5.220/370.384cm³; shape512×512×112–636 |
| Visual QA |10 montage thật đã xem:8 volume-rank samples +lung_022 +lung_018. Lung_022 REVIEW_REQUIRED; không đổi data. [QA report](msd_qa_report.md), [visual review](evidence/p1_1/qa_visual_review.json) |
| Regression/testing | **68 passed** (27 P0 +41 T04), CPU smoke/env/pip check pass; [verification](evidence/p1_1/verification/verification.json). GPU/Kaggle NOT RUN |
| Scope | Chỉ T04; không T05–T08, preprocessing production, split hoặc research training; giữ ba dataset |

Các CLI mới: `acquire-msd`, `audit-msd`, `qa-msd` với `configs/msd.yaml`. Source/hash, schema, guides, data card, changes, commands/exit status và acceptance checklist được tổng hợp trong [báo cáo đầy đủ P1.1](msd_qa_report.md). Raw9.16 GB + archive9.16 GB và medical montage gitignored; còn khoảng46.2 GB free lúc report. Không thêm dependency, commit hoặc push.

Những việc OPEN trước giai đoạn sau: human/source adjudication lung_022, mapping MSD case→patient trước T07, nguồn/license/capacity/CT–RTSTRUCT UID cho NSCLC. **Đề xuất P1.2/T05, chưa thực hiện; chờ người dùng review P1.1.**

---

# Tiến độ P0 — 24/11/2026 (snapshot trước P1.1)

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
