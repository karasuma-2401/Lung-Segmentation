# Lung-PET-CT-Dx acquisition — P1.3/T06

Nguồn: [TCIA collection](https://www.cancerimagingarchive.net/collection/lung-pet-ct-dx/), [collection wiki](https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=70224216), Li et al.(2020), [DOI10.7937/TCIA.2020.NNC2-0461](https://doi.org/10.7937/TCIA.2020.NNC2-0461), v5 ngày22/12/2020. Images và XML được công bố với [CC BY4.0](https://creativecommons.org/licenses/by/4.0/): attribution, link license, nêu conversion/display modifications. Cite TCIA [Clark et al.2013](https://doi.org/10.1007/s10278-013-9622-7). Không tải clinical XLSX và không đưa medical images/annotations vào Git.

## Annotation source và giới hạn truy cập

XML chính thức: `https://wiki.cancerimagingarchive.net/download/attachments/70224216/Lung-PET-CT-Dx-Annotations-XML-Files-rev12222020.zip?api=v2&modificationDate=1609346850424&version=1`. TCIA mô tả PASCAL VOC/LabelImg, khoảng17MB. Attempt từ môi trường này bị connection timeout; **chưa đọc được XML archive, chưa xác minh coordinate convention hoặc equivalence XML tại local**. Không dựng parser production XML từ giả định upstream. VisualizationTools ZIP cũng là tài nguyên tham chiếu nguồn, chưa dùng như code thực thi.

Sample thực dùng [Lung-PET-CT-Dx-Annotations trên IDC](https://portal.imaging.datacommons.cancer.gov/analysis_results/Lung-PET-CT-Dx-Annotations/), [Zenodo record16989820](https://zenodo.org/records/16989820), concept DOI10.5281/zenodo.16989819, version1/2025, Krishnaswamy, Clunie và Fedorov. Publisher xác nhận đây là XML expert bbox harmonized thành DICOM SR, không phải AI SEG. Catalog/headers/region structure đã đọc thực trước viết parser. Đây là adaptation về representation, không được gọi là đã tái tạo chính xác XML pipeline paper. XML access/equivalence giữ OPEN.

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
