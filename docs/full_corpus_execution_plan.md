# Full-corpus execution plan — NSCLC-Radiomics

**DESIGN_ONLY — 24/11/2026. Chưa được duyệt full download, chưa có cloud pilot hoặc persistent storage của nhóm.** P1.2.1 chỉ sửa và revalidate sample. Kế hoạch này không mở T06–T08, không tạo experiment splits, không thay primary ROI/quarantine policy, không train và không giảm scope MSD-Lung + NSCLC-Radiomics + Lung-PET-CT-Dx.

## Phương án và điều kiện khả thi

Đề xuất xử lý tuần tự các batch nhỏ bằng CPU; giữ raw/source annotations và converted artifacts trong persistent storage riêng. C local chỉ là scratch có giới hạn khi có đủ RAM trống. Batching giảm lượng dữ liệu **đang xử lý**, không làm mất nhu cầu lưu corpus và các version lâu dài. Chưa có nơi lưu này thì full corpus vẫn **BLOCKED_STORAGE**, kể cả disk hiện tại đủ cho một batch. Không tự xóa MSD, archive, sample hoặc output cũ để lấy chỗ.

Ưu tiên thiết kế: CPU worker + private object storage do nhóm kiểm soát, hoặc ổ ngoài có đủ chỗ. Máy/cloud account, billing, IAM, quota, Internet và persistence phải được người dùng chấp thuận và kiểm thực tế trước thực thi. Không tạo bucket, upload, mua tài nguyên hoặc chạy full download trong P1.2.1. Kaggle chỉ là ứng viên compute theo batch sau pilot, chưa được coi là persistent archive khả dụng.

## Dữ liệu đầu vào và ngân sách

Nguồn metadata là catalog TCIA đã pin trong `data/manifests/nsclc/public_catalog.json`, SHA256 trong evidence. Đây là thống kê metadata, không phải kết quả đọc toàn bộ422ca:422patients/studies,422CT/51,230slices,422RTSTRUCT. **26,952,556,162bytes** CT và **585,876,108bytes** RTSTRUCT; cộng **27,538,432,270bytes** (~25.65GiB). Không tải421SEG analysis results thay contour gốc.

CT catalog75–297slices/series; CT+RT mỗi patient khoảng40.51–157.97MB, trung bình65.26MB. FileSize/ImageCount không xác nhận Rows/Columns, transfer syntax, decode memory hoặc annotation geometry. Phải probe header thực từng series trước allocation. Không suy ra mọi CT đều512×512 từ sample.

| Thành phần | Budget thiết kế / điều kiện |
|---|---|
| Batch membership |Tối đa10patients **và** tổng CT+RT catalog ≤1GiB; đóng batch trước khi chạm một ngưỡng. Một patient vượt budget: batch riêng, phải replan trước tải |
| Số batch |Ít nhất43 cho422patients; giới hạn bytes có thể làm tăng số batch. Không coi đây là experiment split |
| Scratch/batch IDC |Source bound1GiB + output allowance2.5×CT ≤2.5GiB + staging/upload/retry ≤2GiB + QA/metadata ≤0.5GiB + reserve4GiB: **10GiB free** trước nhận batch; kiểm lại trước mỗi series/case |
| ZIP fallback |Thêm ít nhất1GiB ZIP allowance và expanded-size/header checks; budget **12GiB free**. NBIA ZIP adapter vẫn cần pilot thật trước dùng rộng |
| RAM/worker |Một conversion process, không song song nhiều ca. Đặt working budget khoảng2GiB/worker **cần đo peak RSS pilot**; yêu cầu available RAM ≥ước lượng peak+1GiB margin. Không coi8GiB installed là8GiB available |
| Native-array estimate |Với N=Rows×Columns×Slices: CTfloat32+maskuint8 ít nhất5Nbytes; cộng slabs, contour polygons, pydicom headers/pixels, compression và Python/QA. Ví dụ512²×297:5N≈389MB, chưa phải peak RSS |
| Memory guard |Probe N, contour count và raw RT bytes; nếu ước lượng/peak vượt budget thì dừng/replan worker lớn hơn, không downsample/crop/sửa ROI để vừa RAM. Chạy QA sau conversion thay vì đồng thời |
| Sample observed |P1.2 raw khoảng593MB,7pairs+provenance270MB; không lấy tỉ lệ gzip của7ca này làm bảo đảm cho422ca |

Local hiện có khoảng44GiB free,8.2GB RAM installed; một snapshot khi hardening chỉ khoảng0.42GiB free physical. Vì vậy scratch của một batch có thể đủ nhưng **RAM headroom chưa được bảo đảm**. Phải đo lại trước worker, không cố chạy bằng swap để tuyên bố feasibility. Worker CPU16GiB RAM với ≥10GiB scratch là cấu hình pilot đề xuất, chưa benchmark, chưa provision.

Persistent storage cho một version NSCLC: raw27.54GB + conversion allowance2.5×CT≈67.38GB +4GiBreserve≈**99.21GB (~92.40GiB)**. Đề xuất namespace/quota ít nhất120GiB, theo dõi dung lượng thực và dừng trước hết quota. Nếu giữ ZIP toàn corpus cần126.75GB (~118.05GiB) **chưa có headroom thích hợp** trong120GiB; IDC object download tránh ZIP. Version conversion thứ hai cần budget thêm tới khoảng62.75GiB theo allowance; không tự overwrite version cũ.

Đây chỉ là budget NSCLC. Tổng dự án còn MSD raw+archive≈18.33GB đang giữ, Lung-PET-CT-Dx **chưa xác minh size ở T06**, cùng preprocessing/checkpoints sau này chưa budget. Không tuyên bố120GiB đủ cho ba dataset. Không giảm số nguồn khi chưa có chỗ; giữ blocker và tách kế hoạch storage của từng nguồn.

## Cloud/Kaggle — bằng chứng tài liệu và gates chưa chạy

[Kaggle Notebooks documentation](https://www.kaggle.com/docs/notebooks) được tra cứu ngày24/11/2026; phần nội dung index nêu20GB saved output ở `/kaggle/working`. Trang dùng JavaScript và không trả readable body trong browser text tool; đây là mốc tham khảo tài liệu, **không phải quota account đã đo**. Không dùng mốc này để chứa cả NSCLC. [Kaggle Datasets documentation](https://www.kaggle.com/docs/datasets) mô tả public/private datasets và quyền collaborators; cần kiểm account/terms/quota hiện tại, không giả định private dataset đã tồn tại hoặc đủ chỗ.

Phần technical specifications được search index trả đầy đủ còn nêu CPU4cores/30GBRAM, session CPU/GPU12giờ; datasets nêu200GB/dataset và200GBprivate quota. Suy luận thiết kế: một batch10GiB scratch và một worker2GiB có thể vừa cấu hình tham khảo; một NSCLC version khoảng99GB có thể vừa private quota nếu còn đủ, nhưng versions/archives/dữ liệu đã có và cả3nguồn có thể vượt. Phải xác minh runtime/quota/UI/account và session mới restore, không coi các con số tài liệu là resource đã cấp hay persistence đã pass.

Pilot cần người dùng duyệt riêng sau review này, giới hạn1–2ca **đã có sample**, không full download:

1. Ghi account/runtime, actual RAM/disk, Internet/source reachability, credentials mechanism, time limits và measured peak RSS/time/bytes. CPU conversion không cần GPU.
2. Pin source commit+fingerprint, Python/dependency lock/container. Chuyển môi trường có thể đổi fingerprint; tạo namespace mới, không trộn cache local/cloud mặc định. Optional DICOM decoder plugins/transfer syntax mới phải được kiểm và bổ sung identity trước khi dùng, không tự cài plugin giữa batch.
3. Xác minh CT/mask arrays, affine và volume khớp sample reference; giữ quarantine/002 review. Test interrupted transfer, interrupted conversion, restart và failed checksum.
4. Lưu một batch vào persistent destination được duyệt, đóng session, mở **session mới** đọc lại đầy đủ object bytes/hashes, manifests và ROI provenance. Notebook save thành công hoặc thấy filename chưa đủ.
5. Chỉ khi restore pass mới cho phép dùng scratch cleanup và xin duyệt kế hoạch full. Nếu account thiếu quota/Internet/persistence thì ghi BLOCKED, chọn storage/worker khác sau người dùng duyệt.

Cloud Storage là ví dụ có cơ chế [resumable upload](https://docs.cloud.google.com/storage/docs/resumable-uploads), [CRC32C integrity checks](https://docs.cloud.google.com/storage/docs/data-validation) và [generation preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions). Các cơ chế có trong tài liệu không chứng minh nhóm đã cấu hình hay kiểm thử chúng. Chi phí storage, read-back/egress, requests và worker phải được ước tính theo account/region/retention thực trước khi duyệt; chưa có chi phí hoặc hạn mức miễn phí được xác nhận.

## Batch identity, manifests và deduplication

Freeze catalog bytes+SHA256, source DOI/license/version, code fingerprint, dependency environment và ROI/QC policy. Sắp public IDs theo thứ tự lexical, tạo danh sách batch deterministic với hai giới hạn ở trên. `batch_id` đề xuất: `nsclc-v4-<catalog_sha12>-<policy_sha12>-<implementation_sha12>-B0001-<members_sha12>`. Lưu full hashes và exact Patient/Study/Series/RT SOP requests trong batch specification; short hashes chỉ để đặt tên, không dùng làm integrity check.

Policy hash bổ sung là hash canonical của các tham số hình học/ROI hiện được duyệt; **không thay** full resolved config SHA256 đang dùng cho cache. Batch config bao gồm membership/output roots, được freeze. Đổi membership/root/config làm cache strict không tương thích; dùng batch/version namespace mới, không tự bỏ qua config check.

Mỗi batch có manifest cùng schema/version, conversion/quarantine report, full config, ROI survey, source/checksum catalog, implementation identity và execution logs. Không sửa global CSV in-place từ nhiều workers. Merge tool tương lai phải:

- Chỉ nhận batch có completion receipt và đã kiểm tất cả artifacts; kiểm schema, source catalog, semantic policy, implementation fingerprint và data-origin flags khớp. Giữ full config hashes từng batch trong provenance.
- Key định danh tối thiểu: dataset + publicPatientID + StudyUID + CTSeriesUID + RTSOPUID + primaryROInumber, kèm version namespace. Không coi CT khác Study là duplicate chỉ vì cùng publicPatientID; không coi cùng public IDs giữa hai dataset là cùng bệnh nhân.
- Duplicate key với cùng source/output hashes: merge idempotent và giữ tất cả contributing batch IDs. Khác source, mask hoặc policy: conflict/review, không last-writer-wins. Detect duplicate SOP/source hashes và voxel duplicates như findings để review, không tự xóa annotation.
- Giữ cả quarantined/missing/unresolved rows, không chỉ concat ca converted. Coverage phải reconcile đủ422 requested patients với catalog; không gọi full validation hoàn tất khi còn batch missing/incomplete hoặc failure chưa phân loại.
- Sort deterministic, ghi manifest mới atomically và hash; không tạo train/val/test. Patient grouping/duplicate adjudication của cả3nguồn vẫn thuộc T07 sau inventory.

## Resume, idempotency và artifact integrity

State machine đề xuất: `PLANNED → SOURCE_VERIFIED → CONVERTED_OR_QUARANTINED → QA_RECORDED → PERSISTED_VERIFIED → BATCH_COMMITTED → SCRATCH_CLEANABLE`. Trạng thái machine checks và annotation review tách biệt; REVIEW_REQUIRED không bị đổi thành expert-approved bởi receipt. Quarantine là kết quả có provenance cần lưu, không phải ca bị âm thầm bỏ.

Giữ raw DICOM bytes, source markers và whole annotation RTSTRUCT; lưu exact public source URL/IDC UUID, TCIA study/series/SOP/count, license/DOI, bytes, publisher ETag MD5 phù hợp và local SHA256. Không dùng multipart ETag như MD5. Raw UID/count/header/hash mismatch dừng stage, không rename sang complete. Acquisition stages chưa complete không được merge.

Cache chỉ hit khi raw source digest, full config digest, complete `conversion_implementation` identity và output hashes đều khớp. Legacy/mismatched identity là stale, yêu cầu explicit reconversion/versioned output. Thiếu/hỏng provenance hoặc output hash phải giữ artifact và báo lỗi, không xóa/tạo lại ngầm. Staging directory theo UUID; publish local bằng same-volume rename sau khi đủ artifact/provenance. Một worker sở hữu một batch/case; dùng lease/exclusive creation để tránh hai writers.

Uploads theo immutable keys cho raw digest và algorithm/config version, có resumable state ngoài Git/secrets store được duyệt. Cloud example dùng generation-match0 cho create-only và exact generation khi kiểm/restore; HTTP412 là conflict cần kiểm identity/hash, không retry overwrite. Chỉ retry idempotent operations có preconditions, bounded backoff; không log token/session URI chứa credentials. CRC32C kiểm transfer, local SHA256 lưu trong manifest; **read-back remote bytes và tính SHA256**, không chỉ so custom metadata đã tự upload.

Sau khi read-back đủ raw+derived+provenance+quarantine+QA và hash tất cả objects: ghi commit receipt immutable gồm full hashes/object generations/counts/source/license/config/implementation. `_SUCCESS` được ghi cuối với precondition create-only; không suy ra completeness từ sự tồn tại của directory/prefix. Restart kiểm receipt và content, skip verified stages; partial state tiếp tục trong scratch mới hoặc resume upload tương thích. Đổi code giữa batch bị cấm; code/environment là immutable trong một run.

## License, distribution và cleanup policy

NSCLC gốc và các dẫn xuất giữ [CC BY-NC3.0](https://creativecommons.org/licenses/by-nc/3.0/): attribution, noncommercial, link license và chỉ rõ conversion/overlay modifications; không đổi thành CC BY4.0 chỉ vì mirror/analysis khác có license đó. License cho phép chia sẻ theo điều kiện, không yêu cầu public upload. Project mặc định private destination và collaborators được duyệt; trước redistribution phải kiểm điều kiện nguồn/platform và attribution, không áp thêm điều kiện trái license. Không gửi raw/medical overlays vào Git. MSD có license riêng; Lung-PET-CT-Dx chưa xác minh ở T06. Không áp một license chung thay tất cả nguồn.

Không dọn dữ liệu trong P1.2.1. Cleaner tương lai chỉ được bật sau pilot persistence pass và người dùng duyệt policy cụ thể. Chỉ xóa scratch do batch đó sở hữu sau `PERSISTED_VERIFIED/BATCH_COMMITTED`, có remote read-back hashes, exact generation IDs và restore test. Raw sample, P1.2 baseline, source annotations chưa có persistent copy, artifacts review chưa lưu đủ và corrupt/conflicting stage cần điều tra không được tự dọn.

Cleanup phải có dry-run danh sách paths/bytes/hash/receipt, kiểm absolute resolved path nằm trong scratch batch được chỉ định, từ chối roots/symlinks/junction escape. Windows dùng native PowerShell với `-LiteralPath`, không ghép `cmd /c` để xóa. Ghi deletion audit; không xóa remote version bằng cleanup local. Chưa có receipt hoặc storage không đọc lại được: giữ scratch, dừng nhận batch mới khi thiếu chỗ, không tăng rate bằng cách bỏ raw.

## Việc cần triển khai sau khi được duyệt

Hiện đã có sample acquisition/config giới hạn1–20IDs, conversion cache identity, integrity checks và revalidation script. **Chưa có** full scheduler, cross-batch merge/coverage validator, memory-aware admission, remote upload/receipts, distributed locks hoặc cleaner. Cần implement/tests failure recovery cho các thành phần này, rồi pilot được duyệt. Không lặp CLI sample422lần để lách full-download approval. Full corpus và cả3dataset vẫn giữ nguyên mục tiêu; blocker storage/RAM/cloud persistence chưa được giải quyết bằng tài liệu thiết kế.

## Cập nhật metadata sau T06/P1.3

Weak dataset nay đã khảo sát official catalog và10CT/SR sample: fullCT+expertSR+conversion allowance/reserve≈436.04GB, combined known planning3nguồn≈553.58GB trước margin/versions/checkpoints. Xem [T06 storage assessment](weak_qa_report.md). Phần NSCLC ở trên vẫn là snapshot DESIGN_ONLY, không là bằng chứng cloud/persistence đã triển khai; không tự mở rộng full corpus hoặc dọn data.
