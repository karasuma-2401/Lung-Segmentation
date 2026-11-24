# P1.2.1 — NSCLC technical hardening — 24/11/2026

**Technical acceptance PASS trên sample; T05 vẫn PARTIAL / SAMPLE_VALIDATED_WITH_REVIEW_FINDINGS, full corpus BLOCKED_STORAGE.** Baseline được review: nhánh dev, commit `1429bb14996beded92cafa128e0d827787f55f5e`. Không full download/cloud execution, không đổi ROI/quarantine/Scarce–Vast policy, không P1.3/T07/T08/training. Dừng sau P1.2.1 để review.

## A — Empty-polygon detection

`rtstruct.polygon_mask()` trước đây chỉ reject khi bounding rectangle không chứa integer center. Sau khi áp dụng cùng thuật toán even-odd + inclusive boundary, code nay kiểm `output.any()`; không có foreground thì raise `DataIssue("contour_has_no_voxel_centers")`. Không đổi sampling, union/XOR/keyhole, không supersample/fill hay skip contour để ép006pass.

Regression triangle `[(0.1,0.1),(1.1,0.1),(0.1,1.1)]` có bbox chứa `(1,1)` nhưng polygon không chứa voxel center. Có test trực tiếp và end-to-end: một contour hợp lệ trước contour rỗng, cho cả CLOSED_PLANAR/CLOSEDPLANAR_XOR; toàn ca quarantine, không xuất partial mask. Các tests union, XOR hole và keyhole hiện có vẫn pass.

`DataIssue.context` bổ sung structured diagnostics. Quarantine CSV/report giữ reason, contour index, slice index, ROI number, contour type, point count, SOP references, plane error cùng source digests và RTSTRUCT/ROI IDs. Source contour coordinates vẫn ở raw, không đưa vào Git hoặc tự sửa annotation.

## B — Conversion cache identity

Module mới `nsclc_version.py` tạo `conversion_implementation`: algorithm `nsclc-native-v2`, source SHA256 của7modules và versions Python/NumPy/NiBabel/pydicom, rồi hash canonical toàn identity. Modules bao quát geometry/intensity, ROI/reference/rasterizer, orchestration/cache/NIfTI writing, config validation, converted validation, checksum helper và identity code. Normalize source LF/CRLF; không chỉ dùng Git HEAD vì working tree có thể dirty. Hash toàn module là conservative: comment edit cũng có thể invalidate cache.

Fingerprint thực: `87bac7926b4ab377dbbd978ecdbac5bfa0e4497319f8ae9ed097abc1dd2847bb`. Full identity nằm trong provenance từng converted case, conversion report và QA index; manifest thêm algorithm version/fingerprint. Cache chỉ hit khi full implementation identity, source/full config digests, origin flag và CT/mask hashes khớp. Legacy thiếu identity hoặc implementation khác → `stale_conversion_cache`, yêu cầu explicit reconversion vào root/version mới. Missing/unreadable provenance hoặc hash mismatch bị từ chối; không tự migrate, xóa hoặc overwrite.

Tests kiểm source/config giữ nguyên nhưng algorithm version đổi, source module/dependency version đổi, valid cache hit tránh decode CT lại, corrupted CT/mask/JSON và missing provenance. [Real legacy probe](evidence/p1_2_1/legacy_cache_probe.json) xác nhận artifact P1.2 thật bị từ chối dù dùng source/config cũ không đổi. QA cũng từ chối stale identity.

Dependency coverage hiện phù hợp uncompressed CT sample; optional decoder/transfer syntax mới cần pilot và identity coverage trước dùng, không tự cài/chỉnh code giữa batch. Fingerprint là cache identity, không phải chữ ký chống giả mạo local.

## C — Revalidation thực và before/after

Config mới `configs/nsclc_p1_2_1.yaml` giữ raw root,10IDs và mọi ROI/geometry/QC policy, chỉ đổi output/evidence roots. [Preflight](evidence/p1_2_1/revalidation_preflight.json):47,174,094,848bytes free, output allowance1,447,630,125bytes +4,294,967,296bytes reserve. Máy8.2GB RAM installed, snapshot khoảng0.42GiB free physical. Sample chạy thực hoàn tất; chưa đo peak RSS hoặc chứng minh RAM admission cho full corpus.

| Artifact | Baseline giữ nguyên | Output mới |
|---|---|---|
| CT/mask/provenance |`data/converted/nsclc/`|`data/converted/nsclc_p1_2_1_v2/`|
| Manifest/survey/report/quarantine |`data/manifests/nsclc/`|`data/manifests/nsclc_p1_2_1/`|
| QA |`data/qa/nsclc/`|`data/qa/nsclc_p1_2_1/`|
| Evidence |`docs/evidence/p1_2/`|`docs/evidence/p1_2_1/`|

Scan lại10patients thật/10CTseries/1,101headers và10RTSTRUCT; convert mới7pairs,3quarantine. Không tải thêm. Script so decoded arrays theo slab, không chỉ file SHA, cùng shape/affine/spacing/units/dtype/qform/sform và physical volume. [Before/after đầy đủ](evidence/p1_2_1/before_after_comparison.json).

| So sánh | Kết quả đo |
|---|---|
|7CT arrays và7mask arrays|**0voxels khác**, max abs difference0 |
|Converted geometry|Shape,affine,spacing,units,qform/sform giống baseline; fresh conversion cũng check native RAS affine |
|Tumor volume|Chênh lệch **0mm³** từng ca; min/median/max12.494/83.548/359.469cm³ giữ nguyên |
|CT/mask compressed files|Hashes cũng giống baseline; không có thay đổi serialization thực |
|Case status/quarantine reason|Giữ nguyên7converted,006/014/128quarantine, cùng reason strings |
|006diagnostics|Contour_has_no_voxel_centers, contour16/slice65, ROI15,4points, plane_error0mm; thêm structured context/source identifiers |
|014/128|Nonuniform gaps3/6mm; primary ROI không xác định. Không nội suy/map pre-op |
|Source/ROI identity|Source digests và selected ROI names/numbers giữ nguyên |
|Repeat/cache hit|Hai lần cùng CSV SHA256 `1711192f59df62a90246a57e639b493d2ecdf031f2f8c7be6102fea3cf16e61f` |
|Raw/baseline preservation|Hash trước/sau **1,189files/868,193,002bytes**, gồm NSCLC raw và toàn bộ output/QA/manifest/evidence P1.2 cũ, giống hệt |
|QA mới|7montage render lại; PNG bytes/hashes giống baseline. Không cấp manual/expert approval mới;002 REVIEW_REQUIRED, all strong_eligible=false |

Lỗi TaskA được fixture synthetic mới tái hiện; trong sample thực không converted pair nào bị ảnh hưởng.006 đã fail bbox check ở cùng contour16 nên vẫn quarantine. Manifest/provenance/report đổi hash vì output config/paths, version identity và diagnostic fields mới, không do sửa voxel/annotation. New converted folder269,534,384bytes, hơn baseline7,546bytes chỉ do provenance JSON. QA folder tăng1,052bytes do index metadata,7PNG không đổi.

[Preservation](evidence/p1_2_1/preservation.json), [artifact audit](evidence/p1_2_1/artifact_audit.json), [QA revalidation](evidence/p1_2_1/qa_revalidation.json). Finding002 không được coi resolved bởi geometry/PNG giống nhau. Synthetic tests không được tính vào10real patients.

## D — Full-corpus execution plan

[full_corpus_execution_plan.md](full_corpus_execution_plan.md) là **DESIGN_ONLY**: tối đa10patients/≤1GiB source mỗi batch, một CPU worker, scratch10GiB IDC/12GiB ZIP, memory admission theo actual headers/contours và measured peak+margin. Persistent NSCLC một version planning≈99.21GB không ZIP; đề xuất quota≥120GiB riêng NSCLC, additional versions và ba dataset có budget riêng.

Có thiết kế batch IDs, manifest merge/dedup/coverage, source/config/implementation identity, resume states, upload preconditions/read-back hashes/commit receipts và cleanup chỉ sau restore verification. Đã tra primary sources Kaggle/Cloud Storage; account/quota, upload/restore và billing **chưa kiểm thực tế**. Chưa triển khai scheduler/merge/uploader/cleaner hoặc upload dữ liệu. Thiết kế không tự giải quyết blocker storage.

## Commands và tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_nsclc.py -q
.\.venv\Scripts\python.exe scripts/revalidate_nsclc_sample.py --baseline-config configs/nsclc.yaml --config configs/nsclc_p1_2_1.yaml
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_2_1/verification
```

Targeted NSCLC **58passed** (43P1.2+15hardening). Full suite **126passed** (111existing+15new); env-check, CPU smoke và pip check đều exit0. [Verification logs](evidence/p1_2_1/verification/verification.json). GPU/Kaggle/cloud NOT RUN; smoke không phải research training.

[Revalidation logs](evidence/p1_2_1/revalidation_execution.json): survey0, conversion2 hai lần (quarantine expected), QA0. Package source hash khớp environment cuối, xem artifact audit. Không commit/push. [Danh sách từng file thay đổi](evidence/p1_2_1/files_changed.txt).

## Acceptance và việc còn mở

| Tiêu chí | Kết quả |
|---|---|
|Empty polygon/regression, union/XOR/keyhole |PASS |
|Stale/legacy/versioned/corrupted cache |PASS, không overwrite/delete |
|P0/P1.1/P1.2 regression |PASS126tests, CPU smoke/env/pip check |
|10real-case revalidation/array-geometry-volume comparison |PASS;7pairs unchanged,3quarantine |
|New artifacts và raw/baseline preservation |PASS, versioned output và hash evidence |
|Full-corpus plan |PASS thiết kế có budget/gates; cloud/runtime feasibility chưa được nghiệm thu |
|Full acquisition/validation |BLOCKED_STORAGE / NOT_VALIDATED |
|Expert annotation clearance |OPEN002/006/014/128, không cấp approval mới |
|Scope/policies/ba datasets |PASS; không full download/P1.3/T07/T08/training |

Sau review cần nhóm adjudicate annotation/discretization riêng và duyệt storage/pilot trước mở rộng. MSD patient mapping, lung_022 review và lung_018 intensity finding giữ nguyên. P1.2.1 hoàn tất phạm vi technical hardening; điều này không đổi T05 tổng thể thành DONE.
