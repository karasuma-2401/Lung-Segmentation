# P1.2 / T05 — NSCLC-Radiomics report — 24/11/2026

**T05 PARTIAL. SAMPLE_VALIDATED_WITH_REVIEW_FINDINGS; FULL_CORPUS_NOT_VALIDATED / BLOCKED_STORAGE.** Đã kiểm workflow trên10 ca thực, không gọi422 patients là đã acquisition/validation xong. Người dùng chỉ có khoảng45GiB trên C, không có ổ khác. Dừng sau P1.2 để review; giữ phạm vi ba dataset.

## Implementation và files

- `src/lungseg/data/nsclc_acquire.py`, `nsclc_idc.py`: TCIA catalog/license/capacity, sample-only NBIA/IDC download, bounded bytes, UID/header/count/checksum verification, safe stages và refusal overwrite.
- `dicom_geometry.py`: per-PatientID/Study/Series/FoR grouping checks, physical ordering, duplicate/missing/nonuniform slices, IOP/IPP affine, LUT/rescale CT intensity, LPS→RAS native geometry.
- `rtstruct.py`: ROI survey/selection, UID/FoR/SOP references, supported contour semantics, physical→voxel rasterization, quarantine on ambiguity/unsupported data.
- `nsclc.py`, `nsclc_config.py`, `configs/nsclc.yaml`, `src/lungseg/cli.py`: inventory/manifest/provenance/report/QA; configurable external roots; không split/resample/train. CT float32 và binary mask uint8.
- Tái sử dụng `msd.inspect_nifti`, `statistics`, checksum/disk/run JSON helpers và renderer. `msd.write_manifest` chỉ thêm optional fields; `msd_qa.render_case` chỉ thêm optional attribution. Defaults MSD giữ nguyên. `.gitignore` bổ sung converted root.
- `scripts/prepare_nsclc_idc.py`, `verify_nsclc_sample.py`, `tests/test_nsclc.py`; guides/card/schema/report, `AGENTS.md`, `README.md`, progress/decisions/matrix; sample metadata/evidence dưới `data/manifests/nsclc/` và `docs/evidence/p1_2/`. Không thêm runtime dependency; DuckDB metadata helper nằm riêng `.reference/idc_tools`, không sửa lock/venv dependencies.

Danh sách từng file nằm ở [files_changed.txt](evidence/p1_2/files_changed.txt), gồm source, config, docs và metadata/execution logs; raw/converted/medical PNG không nằm trong danh sách Git.

## Nguồn, license, metadata, storage

[TCIA collection](https://www.cancerimagingarchive.net/collection/nsclc-radiomics/), [v4 collection wiki](https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=16056854), dữ liệu Aerts et al.2014 [DOI](https://doi.org/10.7937/K9/TCIA.2015.PF0M9REI), **[CC BY-NC3.0](https://creativecommons.org/licenses/by-nc/3.0/)**. Academic/noncommercial use, giữ attribution và nêu các thay đổi dẫn xuất. Xem [acquisition guide](nsclc_acquisition.md) cho citations, official access/API và commands đầy đủ.

Catalog NBIA thật:422 public patients,422 studies,1265series;422CT/51,230objects,422RTSTRUCT,421SEG. CT+RT27,538,432,270bytes; không tải SEG. Catalog/metadata không đồng nghĩa đọc toàn corpus. NBIA metadata thành công một lần, lần tải ZIP timeout; dùng [IDC chính thức](https://portal.imaging.datacommons.cancer.gov/collections/nsclc_radiomics/) exact TCIA UID/DOI/license matching. Public unsigned S3 download hoạt động,1,111 objects kiểm ETag MD5, SHA256 và header identity. NBIA ZIP adapter vẫn chưa real-ZIP validated.

| Tài nguyên | Đã đo / planning |
|---|---|
| RAM physical |8,215,101,440bytes (~7.65GiB); free physical chỉ khoảng0.53GiB tại một snapshot khi kiểm định; chạy sample theo ca, không full corpus trong RAM |
| C trước acquisition |48,282,382,336bytes (~44.97GiB) |
| Full ZIP+raw+conversion+reserve |126,753,222,241bytes (~118.05GiB), allowance chứ chưa đo compressed NIfTI |
| IDC không giữ ZIP |~99.21GB (~92.40GiB) vẫn vượt free; không chứng minh full storage đủ |
| Sample DICOM tải |592,987,154bytes (~0.55GiB),10CT+10RTSTRUCT |
| Raw gồm source markers |593,390,653bytes /1,131files |
| Converted sample |269,526,838bytes /21files (7CT,7masks,7provenance JSON) |
| QA |7PNG+index, khoảng2.91MB, gitignored |
| C sau sample |Khoảng47.56GB (~44.30GiB), số tức thời trong [inventory summary](evidence/p1_2/sample_inventory_summary.json) |

Không xóa/tái nén/chuyển MSD archive hoặc raw để lấy chỗ. `raw_root`/`converted_root` hỗ trợ external path nhưng người dùng hiện không có storage đó. Full download không được thực hiện.

## Dữ liệu thực, ROI policy, conversion

Mẫu001–008,014,128: **10 public patients,10 studies,10CTseries/1,101 slice headers,10RTSTRUCT** đã kiểm header và source hashes. Pixel decode/intensity/full converted voxel validation thực hiện cho7CT convert thành công; không nói đã decode mọi voxel của10CT hoặc toàn corpus. Native geometry xác nhận9ca,014 fail nonuniform;7 converted pairs đối chiếu native RAS affine, shape,units,labels.

Survey ROI thực trước policy: [bản survey trước policy](evidence/p1_2/roi_survey_before_policy.json), [survey đầy đủ](../data/manifests/nsclc/roi_survey.json). GTV-1:9ca; Lung-Left/Right và Spinal-Cord:9; Heart:7; Esophagus:8; gtv-2:3; gtv-3:2; gtv-pre-op và gtv-pre-operat:mỗi tên1. Tất cả observation types trong mẫu là generic ORGAN. Theo survey và mô tả TCIA, match duy nhất tên GTV-1 trim/case-insensitive; ROI number thay đổi theo ca. Generic ORGAN được cho phép explicit với warning; không lựa chọn tumor dựa riêng vào tag này. Không gộp gtv-2/3/OAR/pre-op, không đoán vai trò cụ thể của ROI phụ. Missing/ambiguous primary phải quarantine;128 không bị coi healthy/negative.

CT matching dùng referenced Series UID trong đúng study, không chọn CT lớn nhất. Frame, PatientID,study/series/imageSOP checks đầy đủ. Mọi mask có provenance source SHA256, config, ROI number/name/references, từng contour slice và distance, native affine và LUT/rescale transforms. LPS→RAS đổi dấu world x/y, không hoán đổi voxel hoặc resample. SliceThickness không thay physical gap. Unsupported/mixed types/slab/grid semantics không được skip. [Schema và rasterization contract](nsclc_manifest_schema.md).

| Ca | Shape converted | Primary ROI number | Foreground voxels | Tumor cm³ | Kết quả |
|---|---|---:|---:|---:|---|
| LUNG1-001 |512×512×134|2|54,639|156.323|geometry pass |
| LUNG1-002 |512×512×111|6|125,531|359.469|geometry pass, visual REVIEW_REQUIRED |
| LUNG1-003 |512×512×107|15|12,159|34.818|geometry pass; nhiều GTV names khảo sát riêng |
| LUNG1-004 |512×512×114|12|29,521|84.460|geometry pass; near-boundary/complex ROI context |
| LUNG1-005 |512×512×91|16|29,176|83.548|geometry pass |
| LUNG1-006 |—|15|—|—|quarantine: contour_index16/slice65 không chứa voxel center |
| LUNG1-007 |512×512×129|24|4,367|12.494|geometry pass, nhỏ nhất trong7ca |
| LUNG1-008 |512×512×114|16|14,272|40.869|geometry pass, peripheral/near pleura |
| LUNG1-014 |—|chưa chốt do geometry fail|—|—|quarantine: slice gaps3/6mm |
| LUNG1-128 |—|không match|—|—|quarantine: pre-operative ROI only |

Spacing7 pairs: x/y0.9765625 hoặc khoảng0.977mm, z3mm; orientation LPS (NIfTI world RAS convention), labels{0,1}. Tumor min/median/max12.494/83.548/359.469cm³; physical volume=foreground×abs(det(affine)), không dùng number of slices×SliceThickness. Các số này chỉ mô tả7ca, không phải population422ca hoặc số paper.

## QA và quarantine

[Manifest](../data/manifests/nsclc/manifest_nsclc.csv), [conversion report](../data/manifests/nsclc/conversion_report.json), [quarantine log](../data/manifests/nsclc/quarantine.csv). Giữ tất cả10rows và source contours nguyên vẹn. GT availability phân biệt usable primary mask với RTSTRUCT có tồn tại; không đưa ca quarantine vào strong training. Toàn bộ strong_eligible=false vì T05 chưa training clearance/T07.

7montage thực trong `data/qa/nsclc/LUNG1-*_qa.png`, có axial/coronal/sagittal full context+zoom, window[-1000,400]HU, native grid axis permutation, source attribution. Đã mở xem đủ7ảnh: không thấy gross mirroring/displacement ở các planes đã chọn; không coi đây là xác nhận annotation đúng hoàn toàn. [Visual review có PNG/source hashes](evidence/p1_2/qa_visual_review.json).

- **LUNG1-002 REVIEW_REQUIRED:** inferior extent kết thúc khá phẳng trên coronal/sagittal montage; nhóm cần xem full volume và original contours trước training. Không kết luận nguồn sai, không tự sửa biên.
- **LUNG1-006:** contour nhỏ không chứa integer voxel center theo quy tắc đã công bố. Đây là limitation discretization cần review, không tự coi expert contour invalid. Không skip contour hoặc tạo partial/empty mask để tăng pass rate.
- **LUNG1-014:** physical gaps3/6mm; phù hợp cảnh báo missing slices của TCIA. Chưa nội suy hay điền các slices thiếu dù nguồn nói vùng thiếu ngoài GTV; cần policy review riêng.
- **LUNG1-128:** chỉ pre-op ROI; không tự map sang primary/post-op hoặc giả mask negative. TCIA cũng nêu trường hợp thiếu GTV-1 này.
- Native geometry pass không phải anatomy sign-off; sample chưa bao quát mọi tumor size/contour semantics của corpus.

## Commands, tests và evidence

Đã chạy chuẩn bị catalog TCIA và IDC, `acquire-nsclc --download --rt-only`, survey trước policy, rồi `acquire-nsclc --download` với exact UID matched IDC catalog. [Acquisition](evidence/p1_2/acquisition.json) có nguồn/license/dung lượng/hash catalog và20series tải thực.

```powershell
.\.venv\Scripts\python.exe scripts/prepare_nsclc_idc.py --index .reference/nsclc/idc_index.parquet --duckdb-path .reference/idc_tools --output data/manifests/nsclc/idc_catalog.json
.\.venv\Scripts\python.exe scripts/verify_nsclc_sample.py --config configs/nsclc.yaml --check-repeat
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_2/verification
```

[Sample execution logs](evidence/p1_2/sample_execution.json): capacity/survey exit0; conversion hai lần exit2 (3quarantine có báo cáo); QA exit0. [Repeat và preservation](evidence/p1_2/repeat_and_preservation.json): manifest SHA256 hai lần cùng `7362d1755b9e1273b69360c4d1b8e9e1a68afe066f47da0d36e1e0d4a7f8903f`; raw tree hash trước/sau giống nhau,1,131files không thay đổi. Timestamp nằm ở run report, không làm thay manifest của cùng raw/config/versions.

[Final artifact check](evidence/p1_2/final_artifact_check.json): chạy lại survey/conversion với code cuối,10 verified source patients, manifest giữ nguyên; conversion/QA/visual-review/repeat hashes cùng khớp,7PNG hashes khớp ảnh đã xem và package source SHA256 khớp environment cuối. Kiểm tra origin từ chối gắn real_data=true nếu toàn bộ acquisition bị từ chối hoặc là fixture sai mode. Auto conversion report vẫn giữ QA_PENDING; trạng thái visual acceptance có findings nằm ở visual-review/summary riêng, không sửa báo cáo máy để giả human clearance.

Synthetic tests phân biệt rõ với dữ liệu thật: ordering/InstanceNumber, fixed affine/oblique/shear, gaps/duplicates, LUT/rescale, LPS/RAS/world mapping, series/frame/SOP mismatch, ambiguous RT/ROI, rasterization/holes/keyhole, geometry/physical volume, deterministic manifest/raw preservation, capacity/download/hash safe failure. **111passed (68P0/P1.1+43T05)**; env-check, CPU smoke và pip check đều exit0. Xem [verification logs](evidence/p1_2/verification/verification.json). GPU/Kaggle NOT RUN; smoke không phải research model/results.

## Acceptance và việc còn mở

| Tiêu chí | Trạng thái |
|---|---|
| Official source/license/catalog/bytes |PASS |
| DICOM/RTSTRUCT workflow, exact UID matching, policy có real evidence |PASS trên sample, không blanket policy cho mọi patient |
| Native→NIfTI physical geometry, nonempty binary masks |PASS7pairs;3ca quarantine được ghi rõ |
| Manifest deterministic, raw preserved, GT/unresolved phân biệt |PASS sample |
| ≥5 real QA cases và report bất thường |PASS7montage, có review findings; anatomy clearance PARTIAL |
| Regression CPU/tests |PASS —111tests, env/CPU smoke/pip check exit0 |
| Full corpus acquisition/validation |BLOCKED_STORAGE; chưa tải/convert full |
| Không raw vào Git / không T06–T08 / giữ3datasets |PASS; chưa commit/push |
| T05 tổng thể |PARTIAL; SAMPLE_VALIDATED_WITH_REVIEW_FINDINGS |

Trước mở rộng: review002/006/014/128, bổ sung đủ storage hoặc một kế hoạch cloud được duyệt và kiểm persistence, khảo sát full-corpus ROI trước khi áp policy rộng. Người dùng đã xác nhận không có ổ khác; hiện không cần tải thêm hay cung cấp dữ liệu. Các OPEN MSD patient mapping, lung_022 và intensity lung_018 giữ nguyên. P1.3/T06 chỉ đề xuất khảo sát nguồn/license/annotation sample Lung-PET-CT-Dx với capacity plan mới sau review; chưa thực hiện. Không T07/T08/training cho tới khi inventory cả3nguồn và giải quyết blockers.
