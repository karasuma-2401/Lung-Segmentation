# NSCLC-Radiomics acquisition — T05

> Snapshot acquisition P1.2. Raw sample đã có; P1.2.1 không download thêm. Các commands dùng `configs/nsclc.yaml` bên dưới mô tả phiên P1.2. Cache legacy thiếu implementation identity nay bị từ chối; để revalidate dùng `scripts/revalidate_nsclc_sample.py --baseline-config configs/nsclc.yaml --config configs/nsclc_p1_2_1.yaml`, giữ outputs cũ. Xem [hardening report](nsclc_hardening_report.md) và README hiện tại; không chạy lại verifier cũ để ghi đè evidence baseline.

Nguồn chính thức: [TCIA NSCLC-Radiomics](https://www.cancerimagingarchive.net/collection/nsclc-radiomics/), [TCIA collection wiki/v4](https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=16056854). Public/de-identified, license [CC BY-NC 3.0](https://creativecommons.org/licenses/by-nc/3.0/): attribution, noncommercial; giữ thông tin license/citation và mô tả các thay đổi khi chia sẻ bản dẫn xuất. Không coi là quyền dùng thương mại. Lượt này dùng cho nghiên cứu/môn học, không đăng dữ liệu lên Git.

Citation dữ liệu: Aerts et al. (2014), *NSCLC-Radiomics*, version4, [DOI 10.7937/K9/TCIA.2015.PF0M9REI](https://doi.org/10.7937/K9/TCIA.2015.PF0M9REI). Bài nghiên cứu: [Aerts et al., Nature Communications 2014](https://doi.org/10.1038/ncomms5006). TCIA: [Clark et al., 2013](https://doi.org/10.1007/s10278-013-9622-7).

## Metadata và capacity trước download

[NBIA REST API](https://wiki.cancerimagingarchive.net/display/Public/NBIA+Search+REST+API+Guide) cung cấp `getSeries` và `getImageWithMD5Hash` cho public collections. Catalog thực ngày24/11/2026:422 patients/studies,1265 series:422 CT/51,230 objects/26,952,556,162 bytes;422 RTSTRUCT/422 objects/585,876,108 bytes;421 SEG/421 objects/8,237,157,616 bytes. Tổng52,073 objects. T05 chỉ lấy CT+RTSTRUCT gốc, không lấy SEG analysis results thay annotation.

CT+RTSTRUCT: **27,538,432,270 bytes**. Planning với ZIP+raw+conversion allowance2.5×CT+4GiB reserve: **126,753,222,241 bytes (~118.05GiB)**; qua IDC không cần ZIP vẫn khoảng99.21GB (~92.40GiB). Đây là allowance để lập kế hoạch, không phải kích thước NIfTI gzip đã đo hoặc bảo đảm cho transfer syntax khác. Máy8,215,101,440 bytes RAM (~7.65GiB); C lúc preflight48,282,382,336 bytes (~44.97GiB). Người dùng xác nhận không có ổ khác. **Full acquisition/conversion BLOCKED_STORAGE.** Không xóa MSD/archive hoặc giảm còn một dataset.

```powershell
.\.venv\Scripts\python.exe -m lungseg.cli acquire-nsclc --config configs/nsclc.yaml
# Offline dùng catalog TCIA công khai đã lưu, có hash input trong report:
.\.venv\Scripts\python.exe -m lungseg.cli acquire-nsclc --config configs/nsclc.yaml --catalog data/manifests/nsclc/public_catalog.json
```

Không có `--download` thì chỉ lập kế hoạch. `configs/nsclc.yaml` giới hạn1–20 public IDs, mặc định001–008,014,128. Catalog dung lượng mẫu592,987,154 bytes, planning6,928,571,729 bytes gồm reserve; đủ chỗ. File `capacity_plan.json` là snapshot mới nhất; `acquisition.json` giữ snapshot lần tải. Trước khi tải ở máy khác, chạy lại capacity/RAM checks.

## Download TCIA và fallback IDC chính thức

```powershell
# NBIA: chỉ tập mẫu, kiểm expanded ZIP paths, SOP MD5 và DICOM identity.
.\.venv\Scripts\python.exe -m lungseg.cli acquire-nsclc --config configs/nsclc.yaml --download --rt-only
```

Trong phiên này `getSeries` thành công một lần; các lần gọi metadata/ZIP sau timeout. **NBIA ZIP adapter chưa được kiểm chứng với ZIP thật**; unknown CSV schema fail closed, không bỏ MD5 check. Không có ZIP NSCLC tải thành công từ NBIA. Đã dùng bản sao chính thức [IDC collection](https://portal.imaging.datacommons.cancer.gov/collections/nsclc_radiomics/), theo [IDC data organization](https://learn.canceridc.dev/data/organization-of-data/files-and-metadata) và [idc-index](https://github.com/ImagingDataCommons/idc-index).

Fallback yêu cầu từng SeriesInstanceUID, StudyInstanceUID, PatientID, Modality và object count **khớp catalog TCIA**; source DOI gốc và CC BY-NC3.0. Không nhận analysis SEG mới hoặc mirror bên thứ ba. Public unsigned HTTPS S3 objects; không cần account/token cho các objects đã tải. Lưu S3 URL, ETag MD5, bytes, SHA256 và source DOI trong `source.json`; mọi header đối chiếu lại với catalog. Dữ liệu thật đã đi qua adapter IDC này.

Metadata index chính thức khoảng74MB trong phiên này. Có thể chuẩn bị như sau (DuckDB chỉ là công cụ đọc metadata, không phải dependency runtime/lock của dự án):

```powershell
New-Item -ItemType Directory -Path .reference/nsclc -Force
Invoke-WebRequest -Uri 'https://storage.googleapis.com/idc-index-data-artifacts/current/release_artifacts/idc_index.parquet' -OutFile .reference/nsclc/idc_index.parquet
.\.venv\Scripts\python.exe -m pip install --target .reference/idc_tools duckdb==2.0.1
.\.venv\Scripts\python.exe scripts/prepare_nsclc_idc.py --index .reference/nsclc/idc_index.parquet --duckdb-path .reference/idc_tools --output data/manifests/nsclc/idc_catalog.json
# Khảo sát RTSTRUCT trước khi chốt ROI policy; chỉ tải RT:
.\.venv\Scripts\python.exe -m lungseg.cli acquire-nsclc --config configs/nsclc.yaml --catalog data/manifests/nsclc/public_catalog.json --idc-catalog data/manifests/nsclc/idc_catalog.json --download --rt-only
.\.venv\Scripts\python.exe -m lungseg.cli survey-nsclc --config configs/nsclc.yaml
# Sau review ROI thực, lấy CT của cùng sample:
.\.venv\Scripts\python.exe -m lungseg.cli acquire-nsclc --config configs/nsclc.yaml --catalog data/manifests/nsclc/public_catalog.json --idc-catalog data/manifests/nsclc/idc_catalog.json --download
```

Script prepare chỉ xuất các trường public tối thiểu và SHA256 index; hash catalog nằm trong acquisition report. `current` có thể thay đổi: để tái lập phiên này, giữ index/hash/catalog đã dùng; nếu UID/count/license thay đổi, dừng review. Không suy ra v4 từ tên thư mục; bằng chứng là catalog TCIA và exact UID/header matching, source DOI.

## Storage, retries và conversion

`raw_root`, `converted_root`, `output_dir`, `qa_dir`, `evidence_dir` trong YAML phải tách rời, không lồng nhau. Hỗ trợ đường dẫn absolute ngoài C/repository. CLI có `--raw-root`/`--converted-root`; dùng nhất quán cho toàn pipeline. Giữ `.dcm`, `.nii.gz`, raw/cache/converted/montage ngoài Git kể cả khi dùng root ngoài repo. Source.json không chứa PatientName, demographics hoặc clinical dates.

Raw hoàn tất ở `raw_root/dicom/<public PatientID>/<SeriesUID>/`. Failed acquisition stages được giữ ở `raw_root/staging/`, không tự xóa. Các lần download lại xác minh hash và từ chối overwrite nguồn khác; partial ZIP chưa được xem là hoàn tất. Nếu lỗi, đọc report/source hashes, kiểm free space; chỉ dọn staging sau khi người dùng review đường dẫn. Không nạp một folder DICOM thủ công không provenance như verified TCIA; cần catalog và checksum acquisition đúng schema.

```powershell
.\.venv\Scripts\python.exe scripts/verify_nsclc_sample.py --config configs/nsclc.yaml --check-repeat
```

Verifier trên **không download**, lặp conversion để kiểm manifest byte-identical với cùng raw markers/config/versions, hash toàn raw tree trước/sau và tạo montage. `convert-nsclc` exit2 là có quarantine; exit1 là lỗi chạy. `qa-nsclc` chỉ render ca converted không errors. Generated montage/index chưa phải visual acceptance: xem ảnh và ghi findings riêng. Không mở rộng full conversion trước sample geometry + visual QA và đủ storage.
