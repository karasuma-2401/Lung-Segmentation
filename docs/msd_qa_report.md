# P1.1 / T04 — báo cáo MSD-Lung acquisition và validation

**Kết quả: hoàn tất T04 trong phạm vi acquisition/native inventory/QA, có một finding cần nhóm review về annotation.** Đã kiểm dữ liệu MSD thật; không chỉ fixtures. Chưa chia experiment splits, preprocessing production hoặc train. Ba dataset vẫn là scope tổng thể; T05–T08 chưa thực hiện.

## 1. Nguồn, license và tài nguyên

Nguồn công khai do MSD/MONAI phân phối trên [AWS Open Data Registry](https://registry.opendata.aws/msd/), bucket `msd-for-monai`, region `us-west-2`. Không cần AWS account/credentials. License **CC-BY-SA4.0**, xác nhận ở registry và `dataset.json`; attribution, link license và ShareAlike cho bản dữ liệu phái sinh khi phân phối. [License](https://creativecommons.org/licenses/by-sa/4.0/), [acquisition guide](msd_acquisition.md).

Archive9,163,696,640 bytes (~8.53 GiB). Preflight reserve2 GiB, yêu cầu bảo thủ20,474,876,928 bytes; lần resume đo free64,301,944,832 bytes. Payload extract9,163,406,370 bytes,162 members sau bỏ metadata AppleDouble/DS_Store. SHA256 archive đo được:

`f782cd09da9cf7a3128475d4a53650d371db10f0427aa76e166fccfcb2654161`

ETag multipart không dùng như MD5, chưa có published SHA256 độc lập để đối chiếu. HTTPS public source, ETag/version/range/length và observed SHA được ghi trong [acquisition.json](evidence/p1_1/acquisition.json). Tải tuần tự ban đầu được ngắt có chủ đích rồi resume bằng bốn ranges có giới hạn RAM; partial identity giữ nguyên. Lần tải/giải nén cuối exit0. Acquisition status `acquired_not_yet_validated` là snapshot trước inventory; validation hoàn tất ở `inventory_run.json` thời điểm sau đó.

Raw và archive giữ trong `data/raw/` gitignored; montage trong `data/qa/` gitignored. Còn khoảng46.2 GB (~43.0 GiB) free sau các bước này, là số tức thời, chưa xác nhận đủ chỗ cho hai nguồn tiếp theo.

## 2. Corpus thật đã kiểm

| Hạng mục | Kết quả thực |
|---|---|
| CT đọc hết voxel data | **95/95** |
| Training masks đọc hết voxel data | **63/63** |
| Official partitions | 63 official_training có GT;32 official_test không có public GT |
| Unique case IDs | 95; không có duplicate ID/path/voxel fingerprint trong run |
| Patient identity | Không có mapping đã xác minh;95 patient_id null; không tuyên bố95 bệnh nhân |
| Shape native CT `(i,j,k)` | `512×512×112` đến `512×512×636`, toàn bộ3D |
| Spacing native i/j | 0.597656–0.976562 mm |
| Spacing native k | 0.625–2.5 mm |
| Spatial units / orientation CT | mm95/95; LAS95/95 |
| Dtype | CT float32 (95); mask uint8 (63) |
| Label values thực | `{0,1}`, background/cancer theo source metadata |
| CT intensity finite range | −1024 đến20349; maximum20349 ở `lung_018`; chưa kết luận nguyên nhân |
| Foreground voxels / mask | min756; median7050; max338475 |
| Tumor volume / mask | min0.737738 cm³; median5.220032 cm³; max370.384113 cm³ |
| Q25 / Q75 tumor volume | 2.725717 /15.874925 cm³ |
| CT–mask native geometry | 63/63 cùng shape/active affine/spacing trong tolerance0.001mm |
| QC errors / warnings tự động | 0/0;95 rows pass |
| Missing/unreadable/invalid labels/nonfinite/empty masks | Không phát hiện trong corpus đã đọc |
| Dataset findings/unlisted files | Không phát hiện |

Thể tích là tổng voxel label1 × trị tuyệt đối determinant affine theo mm, không phải đo từng lesion. Các thống kê foreground/volume dùng cả63 masks, **bao gồm lung_022**, không âm thầm loại để thay đổi thống kê. Intensity cao chỉ được ghi nhận; không clip/reject raw ở T04. Window ảnh QA là biến đổi hiển thị, không thay dữ liệu.

Metadata archive release `1.0 04/05/2018` ghi63 training/32 test, khác mốc64 training trong trang giới thiệu/handoff/paper. Chưa có bằng chứng giải thích chênh lệch, không tự bổ sung hoặc bỏ ca.

## 3. Manifest và tái tạo

[manifest_msd.csv](../data/manifests/msd/manifest_msd.csv) có95 rows,100,016 bytes; paths tương đối dataset root, geometry/hash/annotation/QC đầy đủ. [summary.json](../data/manifests/msd/summary.json) và [inventory_run.json](../data/manifests/msd/inventory_run.json) chứa actual counts, config/hash, source metadata hash, acquisition SHA, timestamp và Git revision/dirty state.

Manifest SHA256: `ecdb0c960d197a9ba4b4595209beaff199f669eba4912cdea1f8f95d3e84de5b`.

`official_training`/`official_test` là partition của nguồn, không phải experiment splits. Test rows có `annotation_kind=none`, `ground_truth_available=false`, `strong_eligible=false`. Patient IDs null vì `dataset.json` không cung cấp mapping; không gán case IDs thành patient IDs. `strong_eligible=63` chỉ là kết quả QA tự động, không phải quyết định duyệt toàn bộ annotation để training.

CSV deterministic không chứa timestamp từng row; unit test chạy inventory hai lần trên cùng NIfTI fixtures xác nhận byte-identical. Hướng dẫn chạy lại corpus thật có sẵn; chưa chạy lại toàn bộ9 GB chỉ để lặp phép đo không có thay đổi. [Schema](msd_manifest_schema.md).

## 4. QA trực quan —10 ca thật

Đã tạo và **Codex đã xem trực tiếp** tất cả10 montage dưới đây: axial/coronal/sagittal, full-plane và zoom. Tám ca đầu lấy các rank thể tích cách đều gồm min/max, hai ca cuối là targeted review. Tất cả ảnh có source hashes, slice indices, attribution/license và notice display modifications. Không resample raw. Trục mm trong ảnh là khoảng cách tương đối trên canonical voxel grid, không phải tọa độ DICOM tuyệt đối.

| Case | Volume cm³ | Montage | Nhận xét ở các lát đã xem |
|---|---:|---|---|
| lung_096 | 0.738 | [ảnh](../data/qa/msd/lung_096_qa.png) | U nhỏ; không thấy dịch chuyển/lật trục lớn trong mẫu ảnh |
| lung_083 | 1.395 | [ảnh](../data/qa/msd/lung_083_qa.png) | Gần rìa phổi; không thấy lệch grid lớn trong mẫu ảnh |
| lung_043 | 2.831 | [ảnh](../data/qa/msd/lung_043_qa.png) | Mask bất quy tắc; ba hướng hiển thị nhất quán |
| lung_049 | 4.852 | [ảnh](../data/qa/msd/lung_049_qa.png) | Biên mask bất quy tắc; không thấy translation/flip lớn |
| lung_054 | 6.578 | [ảnh](../data/qa/msd/lung_054_qa.png) | Mask có các nhánh/rìa nhỏ; không thấy lệch grid lớn |
| lung_010 | 12.194 | [ảnh](../data/qa/msd/lung_010_qa.png) | Sát thành ngực; cần lưu ý coverage lung crop ở T08, chưa triển khai crop |
| lung_086 | 31.272 | [ảnh](../data/qa/msd/lung_086_qa.png) | Mask lớn/bất quy tắc; không thấy lệch trục lớn |
| lung_053 | 370.384 | [ảnh](../data/qa/msd/lung_053_qa.png) | Extreme lớn nhất; cần kiểm crop coverage ở T08, không tự loại outlier |
| lung_022 | 59.106 | [ảnh](../data/qa/msd_diagnostic/lung_022_qa.png) | **REVIEW_REQUIRED**: ranh giới mask mở rộng không đều sang vùng lân cận trên một số lát; cần xem toàn volume/nguồn trước kết luận annotation |
| lung_018 | 8.529 | [ảnh](../data/qa/msd_intensity/lung_018_qa.png) | CT max20349, có vùng rất sáng trong full-plane; ở lát mask đã xem không thấy lệch grid lớn. Chưa xác định nguyên nhân intensity outlier |

Finding `lung_022` là nhận xét QA hỗ trợ, **không phải kết luận chuyên gia rằng mask sai**. Không dịch/chỉnh mask, không sửa affine, không blacklist và không loại case khỏi manifest/statistics. Cần nhóm review trước khi quyết định cách sử dụng trong training. Các ảnh còn lại cũng chỉ là selected-slice visual screening, không đảm bảo biên annotation đúng ở mọi voxel hoặc đủ nhãn mọi lesion.

Các `qa_index.json` tự động giữ `manual_review=pending` để chờ human review. Kết quả Codex visual QA được ghi riêng ở [qa_visual_review.json](evidence/p1_1/qa_visual_review.json), không đổi pending thành expert approval. Human expert adjudication chưa được thực hiện.

## 5. Kiểm thử và commands

| Command thực / tương đương | Kết quả |
|---|---|
| `.venv\Scripts\python.exe -m lungseg.cli acquire-msd --config configs/msd.yaml --download --extract` | Exit0,9.16 GB tải và giải nén có provenance |
| `.venv\Scripts\python.exe -m lungseg.cli audit-msd --config configs/msd.yaml` | Exit0,95 CT/63 masks đọc và kiểm định đầy đủ |
| `.venv\Scripts\python.exe -m lungseg.cli qa-msd --config configs/msd.yaml` | Exit0,8 montage theo volume ranks |
| `generate_qa` với config QA dir riêng và caseIDs `lung_022`, `lung_018` | Mỗi call exit0; thêm2 montage targeted, giữ index riêng |
| `.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_1/verification` | Exit0 toàn bộ env/smoke/pytest/pip checks |
| `.venv\Scripts\python.exe -m pytest -q` | **68 passed**:27 P0 +41 tests T04 |
| `.venv\Scripts\python.exe -m pip check` | No broken requirements found |

Logs có command/timestamp/exit status trong `docs/evidence/p1_1/*_execution.txt` và `verification/verify_*.txt`. New tests dùng **synthetic NIfTI fixtures và mocked HTTP**, tách khỏi corpus thật. Coverage: valid CT/mask, missing mask/image, shape/affine mismatch, invalid labels/NaN, empty mask, unreadable NIfTI, invalid dimensions/units, duplicates, determinant volume/shear/unit conversion, deterministic manifest, no fake patient/split, axis permutation/flip của QA planes, stale input, modified-manifest rejection, safe tar, range/ETag/resume và disk checks.

Không có GPU/Kaggle test ở T04; CPU validation và smoke không được gọi là GPU pass hoặc training nghiên cứu.

## 6. File changes / bàn giao

- Mới: `src/lungseg/data/{__init__,msd_config,msd_acquire,msd,msd_qa}.py`; `configs/msd.yaml`; `tests/test_msd.py`, `tests/test_msd_acquire.py`.
- Sửa: `src/lungseg/cli.py`, `__init__.py`, `environment.py` (source hash gồm subpackages); `scripts/verify.ps1` (evidence directory riêng); `.gitignore`; `pyproject.toml` description.
- Tài liệu: README, AGENTS, data/README, progress, decisions; mới acquisition guide, schema, data card và report này.
- Artifact: manifest/summary/inventory_run thật; acquisition/test/execution/visual-review evidence;10 montage/index trong `data/qa/` không đưa vào Git. Dependency versions không đổi; không thêm thư viện ngoài venv P0.

## 7. Acceptance criteria

| Tiêu chí T04 | Trạng thái | Bằng chứng |
|---|---|---|
| Đọc CT/mask hợp lệ | PASS | 95 CT +63 masks thật đọc đủ voxel data |
| Phát hiện geometry mismatch và lỗi dữ liệu | PASS | Synthetic regression tests cho lỗi đã định nghĩa; real source không phát hiện lỗi tự động |
| Manifest tái tạo được | PASS | CLI/config/schema + deterministic fixture test, source/config/manifest hashes |
| Phân biệt GT/no GT | PASS | 63 strong_mask,32 none; official test không strong eligible |
| Tests mới pass/P0 không regression | PASS | 68 passed, CPU smoke và pip check pass |
| Bằng chứng dữ liệu thật | PASS | Public archive provenance, inventory/manifest/hash,10 ảnh thật đã xem |
| Raw và expert annotation giữ nguyên; scope T04 | PASS | Không resample, không split/train, không exclusions/corrections |

Không có blocker acquisition/engineering T04 còn lại. Annotation adjudication cho lung_022 và patient mapping là OPEN, không được coi là đã giải quyết chỉ vì automated QC pass.

## 8. Việc cần người dùng / P1.2 đề xuất

Người dùng review finding lung_022 và montage; nếu có mapping case→patient hoặc nguồn gốc tương ứng, cung cấp trước T07. Chưa cần thao tác nào để cứu acquisition MSD. Không tự chốt loại/sửa annotation hoặc giả patient independence.

P1.2 đề xuất chỉ **T05 NSCLC-Radiomics**: xác minh nguồn/license và capacity trước bulk download; kiểm một CT series + RTSTRUCT mẫu, referenced UIDs, primary-tumor ROI semantics; sau đó inventory/QA tương tự với provenance. Chưa thực hiện các bước này, chưa mở T06–T08. **Dừng sau P1.1 để người dùng review.**
