# P1.3/T06 — Lung-PET-CT-Dx report — 24/11/2026

**SAMPLE_VALIDATED_WITH_REVIEW_FINDINGS cho official expert-SR representation. Full corpus NOT_VALIDATED/BLOCKED_STORAGE; XML gốc access/equivalence còn OPEN.** Baseline P1.2.1 được người dùng nghiệm thu tại dev commit `a3712db3ecea5607b878c76f40de967004d3eee8`. Chỉ T06, giữ cả3datasets; không full NSCLC download/cloud provisioning/cleanup, splitting/T08/Teacher/pseudo/Student/training.

## Implementation và file changes

- `weak_acquire.py`, `weak_config.py`, `configs/weak.yaml`, CLI: official IDC metadata/license/DOI checks, bounded sample download≤2GiB, capacity preflight, UID/count/bytes/MD5/SHA256/header checks, source provenance và safe cache/retry behavior.
- `weak_boxes.py`: surveyed TID1500 SR parser, Measurement Group/TrackingUID/Finding, evidence Study/Series/SOP matching, tất cả bbox records, explicit edge-coordinate conversion, native physical corners/coverage, không clip/sửa/skip invalid boxes.
- `weak.py`, `weak_qa.py`: CT type/geometry/extent checks, native CT+bbox union volume/records/coverage, manifest/exclusion/quarantine, implementation cache identity, axial individual rectangle + coronal/sagittal envelope QA. Bbox không là segmentation GT.
- `prepare_weak_catalog.py`, `verify_weak_sample.py`,51synthetic tests, guides/card/survey/schema, metadata/evidence; README/progress/decisions/AGENTS cập nhật. [Danh sách đầy đủ](evidence/p1_3/files_changed.txt).

Reuse frozen `dicom_geometry.build_ct_geometry/read_ct_pixels`, NIfTI writer, `inspect_nifti`, manifest/hash/run helpers và streamed QA planes. Không sửa7modules thuộc NSCLC conversion identity; fingerprint NSCLC trước/sau vẫn `87bac7926b4ab377dbbd978ecdbac5bfa0e4497319f8ae9ed097abc1dd2847bb`. Không thêm runtime dependency; DuckDB dùng ngoài venv chỉ chuẩn bị metadata. Actual negative handling không copy upstream zeros-on-error/first-box behavior.

## Official sources và annotation adaptation

[TCIA original collection](https://www.cancerimagingarchive.net/collection/lung-pet-ct-dx/), Li et al.2020 [DOI10.7937/TCIA.2020.NNC2-0461](https://doi.org/10.7937/TCIA.2020.NNC2-0461), v5/CC BY4.0. Metadata verified từ official IDC index + source page:355patients,436studies,1,295original series,251,135objects. Các đơn vị này khác CT volume, slice và bbox count. [Acquisition guide](weak_acquisition.md) có citations/license/URLs/commands đầy đủ.

XML gốc được TCIA mô tả PASCAL VOC nhưng download từ môi trường này bị timeout; chưa khảo sát XML bytes, không đoán convention từ upstream. Đã survey actual official [IDC expert SR](https://portal.imaging.datacommons.cancer.gov/analysis_results/Lung-PET-CT-Dx-Annotations/), [Zenodo16989820](https://zenodo.org/records/16989820): publisher harmonization từ expert XML, không AI segmentation. Đây là format adaptation được ghi rõ, không claim XML-equivalence đã local-verified. SR DOI/license và source/image IDs khớp catalog; raw bytes và every object SHA256/ETag MD5 được giữ.

Coordinate contract lấy từ [DICOM C.18.6](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.18.6.html), pixel-edge(column,row), center=i+.5. Không áp one-based inclusive VOC conversion lên SR. Source finding codes/TrackingUID được giữ; không suy diễn class hoặc negative từ patient name. [Format/coverage survey](weak_annotation_survey.md), [manifest schema](weak_manifest_schema.md).

## CT selection và paper filtering

Paper Fredriksen et al.2022 [Data section](https://doi.org/10.1371/journal.pone.0266147) báo1,295input images và665sau bỏ non-CT/Z length ngoài[16,60]cm. Current catalog cũng có1,295**series** gồm1,162CT+133PT, không phải1,295axial slices/patients. Metadata count trùng không chứng minh665eligible hiện tại; chưa đọc toàn1,162CT để tái lập curated count.

Group PatientID/StudyUID/SeriesUID, chọn exact CT trong SR evidence; sort IOP/IPP physical coordinates, kiểm FoR/SOP uniqueness, duplicate positions, uniform gaps/orientation và declared spacing. Localizer/scout/fused/secondary capture/derived-review series không được mặc định diagnostic CT.133PT metadata-only exclusions ở catalog log; không tải/decode PET. Sample10CT là original primary axial, không có duplicate positions/nonuniform spacing; acquisition/temporal/InstanceNumber survey ở [native header assessment](evidence/p1_3/native_header_assessment.json). Uniform concatenation không có metadata độc lập vẫn không thể loại trừ tuyệt đối chỉ bằng geometry; acquisition-number thiếu không được coi là bằng chứng chỉ một scan.

Declared convention: primary physical Z extent là **slice-normal voxel-edge FOV = projected IPP center span + median normal gap**, gate **closed[160,600]mm**. Lưu anatomical S/I voxel-edge extent riêng để không nhầm oblique normal với worldZ. SliceThickness không dùng đơn lẻ. Upstream utility dùngN×SliceThickness, strict(16,60) cho CT và strict(20,60) cho bbox writer, khác prose và khác native physical contract này. Đây là explicit adaptation theo paper prose, không ép counts bằng665. Boundary160/600pass,159.999/600.001fail đã test; không resample để qua filter.

Sample measured Zspacing5/8/10mm và thickness tương ứng, rộng hơn mô tả spacing≤5mm ở trang nguồn; giữ measured values, không sửa/đánh rớt chỉ vì metadata description khác. Source CT DICOM Implicit/Explicit VR Little Endian được khảo sát ở header evidence; không cài decoder mới để ép pass.

## Real sample và conversion

10public patients/10studies/10CTseries,420CTslice objects +10SR =430DICOMobjects,221,804,220bytes payload. Mỗi SR được chọn deterministic trong patient, sample gồm A0001–A0006/B0001/E0001/G0001–G0002. Actual10nativeCT +10bbox volumes convert, geometry10/10aligned, bbox values0/1; không tạo segmentation GT/pseudo mask hoặc experiment splits.

| Patient suffix | CT shape | zspacing/extent(mm) | Bboxes /positive slices | Unknown slices |
|---|---|---|---:|---:|
|A0001|512×512×64|5 /320|11 /11|53|
|A0002|512×512×30|8 /240|10 /10|20|
|A0003|512×512×27|10 /270|4 /2|25|
|A0004|512×512×29|8 /232|4 /4|25|
|A0005|512×512×29|10 /290|1 /1|28|
|A0006|512×512×54|5 /270|7 /7|47|
|B0001|512×512×56|5 /280|16 /16|40|
|E0001|512×512×57|5 /285|14 /14|43|
|G0001|512×512×23|10 /230|4 /4|19|
|G0002|512×512×51|5 /255|6 /6|45|

77boxes,75positive slices,345missing/unknown,0explicit negatives. A0003 có hai overlapping boxes mỗi positive slice, cả4records được giữ; không silently merge như một tumor. Source bbox 2D area min/median/max≈115.57/2858.72/7284.61mm², không phải ground-truth tumor area/volume. In-plane spacing0.5859375–0.841796875mm, native shape/affine/orientation trong manifest.

Source/config/implementation fingerprints và output hashes trong provenance; coordinate/physical records ở boxes.json, per-SOP coverage.json tách khỏi bbox volume. Missing/zero outside boxes không được dùng như negative. All `ground_truth_available=false`, `weak_eligible=false`, status bbox_geometry_valid_coverage_review_required. Full coverage, XML equivalence và future training policy cần review.

Final outputs: `data/converted/weak_v1_1`, `data/manifests/weak`, `data/qa/weak`.6case outputs ở interrupted initial `weak_v1` được giữ riêng (≈97MB), không reuse/merge sau ImageType-VM1 regression fix. Baseline medical data không bị dọn. [Manifest](../data/manifests/weak/manifest_weak.csv), [conversion report](../data/manifests/weak/conversion_report.json).

## QA, exclusions và findings

10montage thực đã mở xem, axial giữ từng source rectangle, coronal/sagittal là native axis-permutation envelope, không true oblique reslicing/interpolation.10PNG/index gitignored. [Visual review kèm PNG/source hashes](evidence/p1_3/qa_visual_review.json). Không thấy gross coordinate displacement trên selected planes; đây không là expert anatomy approval.

- A0003: overlapping distinct source boxes ở2slices; adjudicate object/duplicate semantics trước training, không tự merge/drop.
- A0005:1/29positive slice,28unknown; thin native10mm slab không chứng minh lesion chỉ ở một slice.
- G0001: positive regions rời theoZ; khoảng trống ở giữa không là negative, không nội suy annotation.
- A0006: central/perimediastinal context, bbox coarse localization không là anatomical boundary.
- Zspacing8/10mm làm sagittal/coronal bậc thang; preserve native acquisition. XML/coverage completeness chưa verified.

Sample `exclusion_log.csv`0rows, `quarantine.csv`0rows; kỹ thuật SR/nativebbox passes không có nghĩa không còn findings. `catalog_exclusion_log.csv`133PT rows chỉ metadata; không claim CT filtering của cả corpus xong. Synthetic invalid data là tests riêng, không cộng vào real quarantine/sample counts.

## Resources và storage cho ba dataset

Preflight disk khoảng53GBfree, RAM8.215GBinstalled/freephysical khoảng0.70GiB tại snapshot; finite-volume budget và sample thực hoàn tất, **peak RSS/cloud capacity chưa benchmark**. [Capacity evidence](evidence/p1_3/capacity_plan.json), [sample summary](evidence/p1_3/sample_summary.json).

| Storage | Bytes /budget |
|---|---:|
|Weak raw payload /raw kèm markers |221,804,220 /221,968,468|
|Final converted50files /QA11files |166,879,618 /4,354,059|
|Full weak CT+expert SR raw |123,392,510,422|
|Full weak native conversion allowance+reserve |436,035,934,178 (~406.09GiB), noZIP |
|NSCLC single-version plan, noZIP |≈99.21GB, vẫn blocked |
|MSD raw+archive đang giữ |≈18.33GB |
|Combined known planning |≈553.58GB trước margin/additional versions/T08 caches/T10 checkpoints |

2.5×CT là allowance, không measured full gzip output hoặc guarantee cho transfer syntax khác. Với giữ cả3nguồn, đề xuất lập budget persistent storage riêng **khoảng0.75–1TiB** cho data-stage/margin, rồi xác minh actual quotas, costs, retention và restore; chưa provision/mua/upload. Checkpoints/additional versions cần thêm budget. Có thể dùng CPU batch nhỏ theo [DESIGN_ONLY plan](full_corpus_execution_plan.md) nhưng batching không bỏ nhu cầu persistent raw/annotation/outputs; không xóa MSD/NSCLC hoặc giảm scope để vừa C. NSCLC CC BY-NC3.0 phải giữ license riêng, không relabel theo CC BY4.0 của weak dataset.

## Commands, tests, integrity

```powershell
.venv\Scripts\python.exe scripts/prepare_weak_catalog.py --index .reference/nsclc/idc_index.parquet --duckdb-path .reference/idc_tools --output data/manifests/weak/public_catalog.json
.venv\Scripts\python.exe -m lungseg.cli acquire-weak --config configs/weak.yaml --download
.venv\Scripts\python.exe scripts/verify_weak_sample.py --config configs/weak.yaml --baseline-snapshot .reference/weak/baseline_before.json
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_3/verification
```

**177tests pass =126existing+51T06**, env/CPU smoke/pip check exit0. New tests: actual SR schema/SOP matching, multibox, zero/one-based explicit math/off-by-one, flips/swaps, invalid/out-of-bounds, coverage, modality, physical extent/boundaries, duplicate/mismatched records, native alignment, cache/source/config corruption, deterministic manifest/raw preservation/capacity failure. [Verification logs](evidence/p1_3/verification/verification.json). No GPU/cloud/research training.

[Sample commands/exit logs](evidence/p1_3/sample_execution.json): survey0, audit0 hai lần, QA0. Manifest byte-identical SHA256 `b5bbb6dd1895511e23b7531cd60c7871796ea70cb16a33695391b3df58c9d76b`. Weak raw450files SHA trước/sau giống nhau. [MSD/NSCLC preservation](evidence/p1_3/msd_nsclc_preservation.json):1,436preexisting files/19,473,696,473bytes hash checked,0changed. NSCLC implementation fingerprint vẫn khớp đã nghiệm thu. Source/package/QA/manifest audit [PASS](evidence/p1_3/artifact_audit.json). Không commit/push.

## Acceptance và điểm còn mở

| Tiêu chí | Trạng thái |
|---|---|
|Official source/license/metadata |PASS, original + expert SR representation rõ DOI; XML bytes chưa verified |
|Real CT/annotation/SOP mapping/native geometry |PASS sample10 |
|Multiple bbox retention/missing≠negative |PASS77records,0negative inferred; coverage completeness OPEN |
|Paper filtering đối chiếu/convention/boundaries |PASS implementation/sample; full665curated count NOT_REPRODUCED |
|Manifest/QA/source hashes/negative controls |PASS actual sample + synthetic failures; no real invalid-case count invented |
|Regression/baseline preservation |PASS177tests, raw/old artifacts intact, NSCLC cache identity unchanged |
|Training eligibility/expert clearance |REVIEW_REQUIRED, không được cấp |
|XML original local validation |BLOCKED_SOURCE_TIMEOUT /OPEN equivalence |
|Full weak/NSCLC corpus |BLOCKED_STORAGE, NOT_VALIDATED |
|Scope |PASS, ba datasets giữ nguyên; dừng sau P1.3 |

Trước T07/T08 cần storage/persistence pilot được duyệt, full inventory/duplicates/patient mapping và coverage/object policy được chốt; XML gốc cần kiểm thêm nếu muốn claim exact XML/paper preprocessing equivalence. MSD patient mapping/lung_022/lung_018 và NSCLC002/006/014/128 vẫn OPEN. Không tự chuyển P1-R/T07/T08 hoặc training.
