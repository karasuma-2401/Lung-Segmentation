# Lung-PET-CT-Dx acquisition — P1.3/T06 và P1.3.1

**Cập nhật P1.3.1:** dùng `configs/weak_p1_3_1.yaml` và output namespace mới. Các command `configs/weak.yaml` bên dưới là lịch sử P1.3; không chạy audit mới vào baseline. Tái kiểm offline bằng `.venv\Scripts\python.exe scripts/revalidate_weak_sample.py`; kết quả trong [hardening report](weak_hardening_report.md).

Hard byte cap được áp trước từng SR/CT payload: actual S3 object listing hoặc verified cache bytes phải vừa remaining selected-byte budget. Catalog estimate chỉ để dự trù; không nới cap khi estimate thấp. Tổng selected raw = cache đã verify + payload mới được reserve. Report tách `existing_verified_cache_bytes`, `network_payload_bytes_this_run`, `selected_raw_bytes`, remaining và từng admission decision. Network counter tính cả bytes nhận trong transfer lỗi, không gồm HTTP/TLS/listing overhead. Read chunks có giới hạn bằng object bytes đã reserve; kiểm Content-Length nếu có, MD5/SHA256/header trước publish. Reserve thất bại không tạo/publish stage; transfer lỗi giữ stage, không tự xóa raw. Counter theo run, không cộng payload của failed stages phiên trước; disk free check vẫn tính chúng đang chiếm chỗ.

Exit contract hiện tại (tests trong `test_weak_hardening.py`):

| Command | Exit0 | Exit2 | Exit1 |
|---|---|---|---|
|acquire-weak|Plan chạy xong và sample capacity pass, hoặc toàn bộ requested acquisition scope pass; annotations-only là scope SR|Plan thiếu sample capacity hoặc acquisition partial/failure có report|Fatal config/catalog/preflight; không thể chạy operation|
|survey-weak|Tất cả acquired SR sources parse được, không acquisition errors; coverage unverified vẫn được báo rõ|Annotation/source/acquisition errors có partial report|Không đọc được root hoặc fatal operation|
|audit-weak|Inventory/reconciliation hoàn thành, không actionable warnings/errors|Quarantine/exclusion/source failures hoặc coverage/acquisition/XML findings cần review|Fatal operation, không tạo được inventory đáng tin cậy|
|qa-weak|Rendering scope hoàn thành, upstream không actionable findings|QA có review findings hoặc không có converted cases; vẫn ghi index|Stale/corrupt inputs hoặc fatal rendering/operation|

Exit0 của survey/acquisition không là clearance dữ liệu. Audit/QA sample hiện exit2 vì coverage, XML và acquisition semantics chưa verified. Các exceptions sau khi config hợp lệ ghi `<command>_fatal.json` trong evidence_dir; config không đọc được chỉ có stderr/exit1 vì chưa có output root đáng tin cậy. Partial acquisition giữ `acquisition.json`. Caller phải đọc report, không coi exit2 là fatal hoặc success sạch.

Bounded XML investigation: `.venv\Scripts\python.exe scripts/investigate_weak_xml.py`; tối đa3official pages (2MiB/page,20s timeout), một archive link xác định từ trang (24MiB cap; không đoán ZIP URL). Archive chỉ lưu ignored `data/cache/weak_xml_investigation`, không đụng raw/baseline. Chưa tải được thì giữ BLOCKED_SOURCE và XML/SR equivalence OPEN, không đổi parser/policy.

Nguồn: [TCIA collection](https://www.cancerimagingarchive.net/collection/lung-pet-ct-dx/), [collection wiki](https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=70224216), Li et al.(2020), [DOI10.7937/TCIA.2020.NNC2-0461](https://doi.org/10.7937/TCIA.2020.NNC2-0461), v5 ngày22/12/2020. Images và XML được công bố với [CC BY4.0](https://creativecommons.org/licenses/by/4.0/): attribution, link license, nêu conversion/display modifications. Cite TCIA [Clark et al.2013](https://doi.org/10.1007/s10278-013-9622-7). Không tải clinical XLSX và không đưa medical images/annotations vào Git.

## Annotation source và giới hạn truy cập

XML chính thức: `https://wiki.cancerimagingarchive.net/download/attachments/70224216/Lung-PET-CT-Dx-Annotations-XML-Files-rev12222020.zip?api=v2&modificationDate=1609346850424&version=1`. Các attempts ban đầu timeout được giữ trong historical evidence. **Trạng thái hiện tại: ACCESS_RESOLVED** sau user browser download/VPN; archive17,304,054bytes, CRC pass, SHA256 pinned trong [XML report](weak_xml_comparison.md).31,561XML parse được/1binary member; XML coordinate/full equivalence vẫn REVIEW_REQUIRED, không production XML parser. Giữ ZIP immutable reference và SR production. VisualizationTools ZIP chưa được dùng như code thực thi.

Sample thực dùng [Lung-PET-CT-Dx-Annotations trên IDC](https://portal.imaging.datacommons.cancer.gov/analysis_results/Lung-PET-CT-Dx-Annotations/), [Zenodo record16989820](https://zenodo.org/records/16989820), concept DOI10.5281/zenodo.16989819, version1/2025, Krishnaswamy, Clunie và Fedorov. Publisher xác nhận expert XML harmonized thành SR, không AI SEG. Catalog/headers/region structure đã đọc thực trước viết parser. SR tiếp tục production theo quyết định addendum; chưa claim exact XML/paper reproduction hoặc complete equivalence dù access đã resolved.

## Catalog và capacity

Official [IDC collection](https://portal.imaging.datacommons.cancer.gov/collections/lung_pet_ct_dx/), index URL `https://storage.googleapis.com/idc-index-data-artifacts/current/release_artifacts/idc_index.parquet`. Dùng index đã tải trong P1.2, giữ SHA256; export chỉ public IDs/UIDs/modality/count/size/DOI/license/S3 URL, không demographics/dates. Chỉ nhận original image DOI và expert SR DOI; loại SEG/BAMF AI analysis.

| Metadata, chưa phải full image validation | Số liệu từ pinned index |
|---|---:|
|Original patients/studies/series |355 /436 /1,295 |
|CT series /single-frame objects |1,162 /205,459 |
|PT series /objects |133 /45,676 |
|Original CT+PT objects |251,135 |
|CT bytes |123,339,382,584 |
|PT bytes |3,845,551,812 |
|Expert SR series/objects /patients |1,091 /354 |
|Expert SR bytes |53,127,838 |

SR count không mặc định bằng số CT được annotation: phải đọc evidence UIDs từng SR.355subjects không chứng minh355 unique persons giữa các collections. V2 nguồn đã sửa A0266→A0251; không tự tạo mapping khác hoặc tái dùng bản release cũ.1,295 trong paper đối chiếu ở mức series/volumes đầu vào, không phải slices;665 là curated count của tác giả, chưa tái lập trên toàn corpus hiện tại.

Preflight thực: khoảng53.0GB disk free và8.215GB RAM installed; một snapshot737,920KiB free physical. Full CT+SR raw≈123.39GB, output allowance2.5×CT≈308.35GB +4GiBreserve: **436,035,934,178bytes (~406.09GiB)**, không ZIP. Không đủ chỗ, **BLOCKED_STORAGE**. Allowance không phải measured gzip size hoặc peak RSS guarantee. Không tải PT pixels/SEG hoặc full CT.

Sample giới hạn10patients, tối đa2GiB raw; preflight yêu cầu3.5×maxraw+4GiBreserve=11GiB nếu cùng volume, kiểm riêng raw/converted nếu khác ổ. Actual CT+SR payload221,804,220bytes. Raw kèm source markers221,968,468bytes; converted final166,879,618bytes; QA≈4.35MB. Chạy tuần tự từng volume, cap80million voxels trước allocation; không resize để vượt budget. Config hỗ trợ absolute/external roots tách rời, không lồng raw/derived/evidence.

## Commands tái tạo

Chạy tại repo root. DuckDB chỉ là optional metadata tool ngoài venv dependencies, không phải runtime parser requirement. Giữ index/catalog bytes đã pin; `current` URL có thể đổi trong tương lai.

```powershell
# Nếu chưa có helper, chỉ cài vào thư mục tool riêng:
.venv\Scripts\python.exe -m pip install --target .reference/idc_tools duckdb==2.0.1
.venv\Scripts\python.exe scripts/prepare_weak_catalog.py --index .reference/nsclc/idc_index.parquet --duckdb-path .reference/idc_tools --output data/manifests/weak/public_catalog.json
# Chỉ plan, không download:
.venv\Scripts\python.exe -m lungseg.cli acquire-weak --config configs/weak.yaml
# Bounded sample; --annotations-only để chỉ khảo sát SR trước CT:
.venv\Scripts\python.exe -m lungseg.cli acquire-weak --config configs/weak.yaml --download --annotations-only
.venv\Scripts\python.exe -m lungseg.cli survey-weak --config configs/weak.yaml
.venv\Scripts\python.exe -m lungseg.cli acquire-weak --config configs/weak.yaml --download
.venv\Scripts\python.exe scripts/verify_weak_sample.py --config configs/weak.yaml
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_3/verification
```

Sample lấy deterministic một SR/patient theo study/series UID, rồi **chỉ CT được evidence tham chiếu**, không chọn largest series. S3 list/count/bytes/ETag MD5, từng DICOM header identity và SHA256 được kiểm. Public unsigned HTTPS; không credentials. Existing raw phải khớp source provenance/hash, không overwrite. `actual_downloaded_bytes` là tổng payload đã acquisition kể cả khi reuse; `network_payload_bytes_this_run` tách lần kiểm lại cache (phiên cuối0bytes, không download lại).

Raw ở `data/raw/Lung-PET-CT-Dx/dicom/`; staging thất bại giữ riêng. Final output `data/converted/weak_v1_1/`; phiên kiểm tra gián đoạn trước đó ở `weak_v1/` được giữ, không merge vào manifest cuối. Đổi implementation/config cần root version mới, không xóa hoặc reuse cache cũ ngầm. `audit-weak` exit2 khi có quarantine, exit1 nếu operation không chạy được; đọc report. `qa-weak` chỉ render converted rows và kiểm source/config/implementation/output hashes.

Không thực hiện cloud provisioning/full download/cleanup. Đề xuất storage cả3nguồn nằm trong [QA report](weak_qa_report.md); NSCLC full blocker, MSD mapping/review findings giữ nguyên. Dừng sau T06 để review.
