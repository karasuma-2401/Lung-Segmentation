# P1.3.1 — Lung-PET-CT-Dx technical hardening

Ngày24/11/2026. Baseline được review: dev `ac21467351340bc58369eda76ac4977f0691ec11`. **Hardening và real sample revalidation PASS; sample vẫn VALIDATED_WITH_REVIEW_FINDINGS, XML equivalence OPEN/BLOCKED_SOURCE, full corpus BLOCKED_STORAGE/NOT_VALIDATED.** Dừng sau P1.3.1. Không training clearance, không expert approval.

## Task A — Source completeness và đơn vị đếm

Finding cũ: evidence failures chỉ nằm trong JSON list, không nhất thiết có CSV row; `quarantined_cases` cộng annotation failures vào CT-case count. Scan dừng cả patient ở lỗi đầu tiên, có thể không kiểm các SR/file còn lại.

Đã tách source ledger và failure ledger trong `weak_sources.py`; scan tiếp tục từng object/folder sau lỗi và giữ hash/path/header nếu đọc được. Missing expected objects cũng có record; thiếu toàn bộ patient ghi acquisition failure. Không có fabricated CT UID hoặc unresolved-acquisition CT row.

| Artifact | Đơn vị / quy tắc |
|---|---|
|manifest_weak.csv / quarantine.csv / exclusion_log.csv|Unique patient/study/CT-series case; có thể từ verified SR reference đến CT chưa có raw. Quarantine count chỉ bằng số CT-case rows tương ứng|
|annotation_records.csv / annotation_failures.csv|Mỗi source SR object; failures là subset. Giữ configured/observed PatientID, observed/declared SR SOP và SeriesUID tách biệt, source path/hash, reason, observed CT references và CT-case results|
|acquisition_failures.csv|Mỗi requested patient có acquisition error, nested object failures với path/hash/reason; không cộng vào CT-case count|
|source_objects.csv|Mỗi discovered hoặc expected-but-missing DICOM object, identity/verification status|
|reconciliation.json|Requested patient coverage, source=verified+failed, annotation=parsed+failed, observed/missing counts và liên kết CT cases|

Reference chưa qua validation chỉ được giữ để truy vết. SR `parsed` không đồng nghĩa CT conversion pass; case-level reasons giữ riêng. Một patient có thể xuất hiện trong nhiều loại ledger, không cộng các ledger thành số bệnh nhân.

Real reconciliation: **10 requested patients,10 CT cases,430/430 observed and verified objects=420CT+10SR,10parsed SR,0missing objects,0annotation failures,0acquisition failures,0CT quarantine/exclusions**. CSV/JSON reconciled, không bỏ patient. Synthetic regressions tạo malformed/unreadable SR, missing/unsupported references, annotation-only và mixed2invalid+1valid annotations trên cùng CT case.

## Task B — Exit contract

`0`: command thành công trong scope đã định; `2`: partial hoặc actionable findings đã có report; `1`: fatal exception. [Acquisition guide](weak_acquisition.md) định nghĩa riêng từng command, kể cả plan-only/annotations-only. Survey0 chỉ chứng minh source parsing, không chứng minh exhaustive coverage hoặc training clearance.

Survey có parse errors nay exit2. Audit bao gồm warnings/review findings, không chỉ quarantine. QA lưu index khi không có converted cases và exit2; stale/corrupt inputs vẫn fatal1. Exceptions sau khi config hợp lệ giữ `<command>_fatal.json`; invalid config chưa xác định output root thì stderr/exit1. Acquisition partial giữ report và stage thay vì báo success. CLI regressions kiểm cả0/2/1 và error artifacts.

Real execution: survey0; audit2 ở cả hai lần; QA2. Đây là expected review status do unknown acquisition semantics, coverage exhaustiveness và XML verification còn mở; không phải conversion failure.

## Task C — Acquisition identity

Wrapper weak-only kiểm `AcquisitionNumber`, `TemporalPositionIdentifier`, `ImageType`, `NumberOfTemporalPositions`; lưu observed values, missing counts, findings và status trong manifest/provenance. `verified` chỉ là metadata consistency, geometry vẫn kiểm độc lập.

- Thiếu/null/empty metadata: `unknown`, không coi là verified.
- Mixed temporal IDs hoặc khai báo nhiều temporal positions: `suspicious`, quarantine; không ghép hoặc resample.
- Nhiều AcquisitionNumbers hoặc ImageTypes: `suspicious`, cần review; AcquisitionNumber khác nhau đơn lẻ không bị blanket reject. Native geometry và existing eligibility checks vẫn áp dụng; weak_eligible=false.

Real sample **10unknown,0verified,0suspicious**: TemporalPositionIdentifier thiếu toàn bộ; AcquisitionNumber null ở A0001/A0006/G0002, các ca còn lại một giá trị mỗi series. Không tìm thấy bằng chứng mixed temporal group từ các tags hiện có; metadata thiếu cũng không chứng minh series chắc chắn đồng nhất acquisition. Geometry consistency không loại trừ mọi khả năng concatenation nếu source không cung cấp semantics.

Không sửa shared geometry/rasterizer/NIfTI writer của NSCLC. Fingerprint NSCLC trước/sau giữ `87bac7926b4ab377dbbd978ecdbac5bfa0e4497319f8ae9ed097abc1dd2847bb`. Weak version mới `weak-sr-native-v2`, fingerprint `9ab8f20775370cbbddcb86d38002c93d6c260f1fff56f7b36c946bc7735adb35`, bổ sung weak_sources.py; legacy cache không compatible.

## Task D — Hard byte budget

Trước **mỗi** SR/CT payload: actual listing count/positive object bytes phải hợp lệ và vừa remaining cap; verified cache cũng chiếm selected raw budget. Estimate chỉ để planning. Không tạo/publish stage khi admission thất bại. Chunk reads bị chặn bằng bytes đã reserve; kiểm Content-Length khi có, exact bytes/MD5/header/SHA256 trước publish. Cache kiểm identity/DOI/license/transport, file set/count/size/hash/header. Không xóa raw hoặc interrupted stages.

Report tách selected raw, existing verified cache, network payload và từng admission decision. Failed-transfer bytes nhận trong run được tính; không tính HTTP/TLS/listing overhead. Failed stages của run trước không được xem là verified cache; vẫn chiếm disk và được giữ nguyên.

Real offline cache verification (network/listing bị khóa): **20series,221,804,220verified cache bytes,0network payload bytes**, cap2,147,483,648bytes. Synthetic tests chứng minh actual>estimate chỉ được tải nếu vừa cap; không gọi payload khi remaining thiếu ở cả SR/CT; short transfer giữ stage, không publish; partial failure report exit2.

## Task E — Original XML: BLOCKED_SOURCE

Đã thử [official alternate page](https://www.cancerimagingarchive.net/tcia-downloads/lung-pet-ct-dx-da-other/lung-pet-ct-dx-annotations-xml-files-rev12222020/), [collection page](https://www.cancerimagingarchive.net/collection/lung-pet-ct-dx/) và official uploads directory. Web fetch trả HTTP500; ba direct urllib GET timeout20s/request. Chi tiết actual attempts trong [xml_source_investigation.json](evidence/p1_3_1/xml_source_investigation.json).

Search index của official TCIA hiển thị archive title `Lung-PET-CT-Dx-Annotations-XML-Files-rev12222020`, mô tả LabelImg/PASCAL VOC; collection page hiển thị16.5MB ở current row, wiki17.26MB. Đây là published labels từ index, **không phải Content-Length hoặc ZIP bytes đã verify**. Bounded script giới hạn2MiB/page và24MiB/archive, chỉ theo ZIP link quan sát từ official page; không đoán direct ZIP URL. Không thu được download link/ZIP response có thể kiểm định trong run này.

**Archive identity/actual size/hash chưa verified;0XML objects đã đọc; object counts/SOP mapping/class codes/coordinate bounds/XML–SR equivalence chưa đối chiếu.** Giữ OPEN/BLOCKED_SOURCE, không suy ra VOC origin, không đổi parser production hoặc ROI policy. Original CT/XML và expert SR vẫn giữ source/license metadata CC BY4.0, không dùng AI SEG. Không bỏ dataset.

## Task F — Real before/after

Config mới `configs/weak_p1_3_1.yaml`, raw/sample/policy không đổi; chỉ thay output roots. Offline script kiểm overlap, disk reserve và snapshot trước conversion. Free disk preflight đủ output allowance khoảng0.668GB cộng4GiB reserve; không acquisition mới. New outputs:

- `data/converted/weak_p1_3_1_v2`:10CT/bbox pairs cùng boxes/coverage/provenance.
- `data/manifests/weak_p1_3_1`:schema v2, source/failure ledgers và reconciliation.
- `data/qa/weak_p1_3_1`:10three-plane montage và QA index.
- `docs/evidence/p1_3_1`:execution, verification, cache admission và comparisons.

| Measurement | P1.3 → P1.3.1 |
|---|---|
|Patients / CT series / CT slices / SR|10 /10 /420 /10 → giống nhau|
|Converted / quarantined / excluded|10 /0 /0 → giống nhau|
|Bboxes / positive slices / unknown slices / explicit negatives|77 /75 /345 /0 → giống nhau|
|CT và bbox voxel arrays|10/10 pairs exact equal; **0different voxels**, max absolute difference0|
|Shape, affine, spacing, units, dtype, qform/sform|Tất cả exact equal; CT/bbox file SHA256 giống baseline|
|boxes.json và coverage.json|10/10 exact records và file hashes equal; unknown không đổi thành negative|
|QA montage|10/10 PNG hashes verified và bytes giống baseline; QA index vẫn manual review pending|
|Bbox foreground và envelope volumes|Giống baseline; không phải tumor segmentation volumes|
|Provenance / manifest|Provenance hash đổi do config roots, implementation v2 và acquisition findings; manifest đổi schema/fields/warnings. Source digest không đổi|
|Repeat manifest|Hai lần audit byte-identical; SHA256 `79195790d230febf50a5e6137c0c7981e6fe067b51b1b6445c0e9d95ad36adf7`|
|Raw + baseline preservation|**570files /492,231,485bytes**, gồm raw, final/interrupted converted, manifests, QA và P1.3 evidence; aggregate SHA256 trước/sau giống nhau|
|NSCLC fingerprint|Không đổi; không invalidation cache strong ngoài dự kiến|
|Training clearance|GT=false và weak_eligible=false toàn bộ; không manual/expert approval|

[Before/after evidence](evidence/p1_3_1/before_after_comparison.json) chứa từng ca/array/geometry/JSON/hash và QA PNG comparison. Đã xem lại montage A0003: hai overlapping boxes được giữ; không sửa annotation. Các findings P1.3 A0003/A0005/G0001/A0006 vẫn cần review, không có expert clearance mới.

## Commands và actual verification

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_weak.py tests/test_weak_hardening.py
.venv\Scripts\python.exe scripts/investigate_weak_xml.py
.venv\Scripts\python.exe scripts/revalidate_weak_sample.py
.venv\Scripts\python.exe scripts/verify_weak_sample.py --config configs/weak_p1_3_1.yaml
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_3_1/verification
git diff --check
```

Targeted **91passed**. Full suite **217passed in23.42s =177prior+40new synthetic tests**, no regression. Environment/import checks, CPU smoke forward/backward/update và `pip check` exit0. Smoke là fixture MONAI nhỏ, không phải research training/result. Verifier phân biệt exit2 review warnings với partial sample: chỉ công bố machine checks pass khi reconciliation/converted count/QA coverage đủ và không có source/quarantine errors. Actual command argv/timestamps/exit codes trong [verification logs](evidence/p1_3_1/verification/verification.json), [revalidation logs](evidence/p1_3_1/revalidation_execution.json) và [sample verifier logs](evidence/p1_3_1/sample_execution.json). XML script exit0 nghĩa investigation được ghi, không có nghĩa XML acquisition thành công; report BLOCKED_SOURCE.

## File changes

- Code: `src/lungseg/data/weak.py`, `weak_sources.py` (mới), `weak_acquire.py`, `weak_qa.py`, `src/lungseg/cli.py`.
- Config/tests: `configs/weak_p1_3_1.yaml`, `tests/test_weak_hardening.py` (mới).
- Scripts: `scripts/revalidate_weak_sample.py`, `investigate_weak_xml.py` (mới), `verify_weak_sample.py` (exit2 support).
- Docs: báo cáo này, `AGENTS.md`, `README.md`, `docs/weak_manifest_schema.md`, `weak_acquisition.md`, `progress.md`, `decisions.md`.
- Metadata/evidence mới: `data/manifests/weak_p1_3_1/*`, `docs/evidence/p1_3_1/*`. Raw/NIfTI/PNG vẫn gitignored. Không commit/push hoặc thêm dependency.

## Acceptance và remaining blockers

| Tiêu chí | Kết quả |
|---|---|
|A — Source/annotation failures không bỏ sót, CT count không double-count, reconciliation|PASS — real counts và synthetic regressions|
|B — Exit contracts và error artifacts|PASS — CLI regressions + actual0/2 execution|
|C — verified/suspicious/unknown, findings persisted, không blanket reject AcquisitionNumber|PASS —10real unknown được giữ rõ|
|D — Actual per-series admission trước payload, cache/network riêng|PASS — synthetic network guards + real cache-only validation|
|E — Bounded official XML investigation|PASS investigation; equivalence **OPEN/BLOCKED_SOURCE**|
|F — Real revalidation / regressions / preservation|PASS —10pairs exact,217tests,570baseline files preserved|
|Protocol và scope|PASS —3datasets, Scarce/Vast unchanged; không full download/cloud/splits/preprocessing/training/cleanup|

Cần source XML chính thức truy cập được hoặc archive có provenance đáng tin cậy để mở tiếp equivalence investigation; không yêu cầu giải quyết blocker này để review hardening. Cần annotation/coverage review và acquisition semantics evidence trước clearance; persistent storage vẫn thiếu cho full corpus cả3nguồn. MSD patient mapping/lung_022/lung_018 và NSCLC002/006/014/128 giữ nguyên. **Chờ người dùng review P1.3.1; chưa triển khai P1-R/T07/T08 hoặc giai đoạn nghiên cứu tiếp theo.**
