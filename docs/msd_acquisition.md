# MSD Task06_Lung — thu thập và kiểm định P1.1/T04

## Nguồn và điều kiện sử dụng

- Trang dự án: [Medical Segmentation Decathlon](https://medicaldecathlon.com/index.html), [trang tải AWS](https://medicaldecathlon.com/dataaws/).
- Nguồn phân phối đã xác minh: [AWS Open Data Registry — MSD](https://registry.opendata.aws/msd/), bucket `msd-for-monai`, region `us-west-2`, do MONAI Development Team quản lý. Registry nói rõ không cần tài khoản AWS; dùng HTTPS công khai, không cần access key.
- Archive: `https://msd-for-monai.s3.us-west-2.amazonaws.com/Task06_Lung.tar`. HEAD đo được **9,163,696,640 bytes**; đây là tar không nén, chứa các volume `.nii.gz`, không phải `tar.gz`.
- License: **CC-BY-SA 4.0**, xác nhận ở registry và field `licence` của `dataset.json` trong archive. Giữ attribution, link license và ghi thay đổi; khi phân phối bản dữ liệu phái sinh, tuân thủ ShareAlike. [License](https://creativecommons.org/licenses/by-sa/4.0/). Công cụ không upload/publish dữ liệu.
- Citation: Simpson et al., *A large annotated medical image dataset for the development and evaluation of segmentation algorithms*, [arXiv:1902.09063](https://arxiv.org/abs/1902.09063); Antonelli et al., *The Medical Segmentation Decathlon*, [Nature Communications (2022)](https://doi.org/10.1038/s41467-022-30695-9). Các montage dùng CT/mask MSD có attribution và notice CC-BY-SA 4.0.

`dataset.json` phân phối release `1.0 04/05/2018` (field gốc viết `relase`) ghi **63 training và 32 test**. Trang giới thiệu/paper có mốc64 training; không tự tạo ca thứ64 hoặc giả lý do khác biệt. Số thực được kiểm chứng bằng inventory, không bằng con số tham khảo.

## Dung lượng và tải có thể chạy lại

Từ thư mục gốc dự án, dùng virtualenv P0 đã có dependency data:

```powershell
# Chỉ HEAD và kiểm tra dung lượng; chưa tải archive:
.\.venv\Scripts\python.exe -m lungseg.cli acquire-msd --config configs/msd.yaml
# Tải và giải nén sau resource check:
.\.venv\Scripts\python.exe -m lungseg.cli acquire-msd --config configs/msd.yaml --download --extract
```

Config `configs/msd.yaml` lưu source, đường dẫn tương đối và reserve2 GiB. Preflight yêu cầu bảo thủ `2 × Content-Length + reserve` = **20,474,876,928 bytes** còn trống: giữ cả archive và payload giải nén. Lần đầu ổ C còn khoảng65.5 GB, đủ yêu cầu này. Trước extraction kiểm tra lại tổng member bytes và free space thực; tar payload chưa được giải nén NIfTI sang file lớn.

- Download có bốn range64 MiB, mỗi worker chỉ đọc buffer4 MiB, merge đúng thứ tự; giữ `.part` và identity để resume.
- Pin ETag/version/Content-Length từ HEAD, gửi `If-Match`, kiểm `206 Content-Range` và ETag; SHA256 cuối lưu trong sidecar/report. **Multipart ETag không phải MD5**; SHA256 là checksum đo của bản đã tải, không phải official published checksum độc lập.
- Không overwrite archive hoặc raw folder có provenance khác/không rõ. Nếu nguồn đổi hoặc partial không có identity, dừng với lỗi để người dùng kiểm tra, không append tùy tiện.
- Tar validation từ chối path traversal, absolute paths, symlink/hardlink, special file và duplicate path. Python data-filter là lớp kiểm tra bổ sung. AppleDouble `._*` và `.DS_Store` là metadata hệ điều hành, không phải medical volumes, được bỏ qua và không sửa NIfTI.
- Extraction vào staging rồi rename raw folder khi xong. Staging hỏng giữ lại để kiểm tra; không xóa raw để tự chữa lỗi.

Artifact acquisition ở `docs/evidence/p1_1/acquisition.json`; source sidecar/archive/raw đều trong `data/raw/` gitignored. NIfTI CT/mask chỉ được đọc sau khi tải/giải nén hoàn tất. Không commit raw CT, labels, weights hoặc archive.

## Inventory và manifest

```powershell
.\.venv\Scripts\python.exe -m lungseg.cli audit-msd --config configs/msd.yaml
```

Đọc metadata gốc, tất cả CT được liệt kê, training masks và kiểm file không được liệt kê. Phân biệt `official_training`/`official_test` của nhà phát hành với **experiment train/validation/test chưa được chia**. Test chính thức chỉ có CT; thiếu mask ở training là lỗi, không đổi thành negative hay test.

Output mặc định:

- `data/manifests/msd/manifest_msd.csv`: từng ca, path tương đối dataset root, geometry/hash/QC/annotation; [schema](msd_manifest_schema.md).
- `summary.json`: count/shape/spacing/orientation/labels/foreground/tumor volumes và lỗi/cảnh báo.
- `inventory_run.json`: config/hash, metadata/manifest hashes, timestamp/revision và provenance acquisition. CSV ổn định byte-for-byte khi nguồn/config không đổi; timestamp không đặt vào từng row.

Kiểm native 3D shape, finite data, spacing dương, affine khả nghịch/homogeneous, units, qform/sform disagreement, image-mask shape/affine/spacing cùng đơn vị mm, label chỉ0/1, foreground và thể tích `foreground_count × abs(det(mask_affine_mm[:3,:3]))`. Units không rõ thì báo lỗi và không giả định mm. CT được đọc theo z-slabs, không load cả corpus vào RAM.

Duplicate: case ID, path và normalized voxel fingerprint. Fingerprint đọc cùng thứ tự z-slice, float64; không phải bằng chứng patient identity và không phát hiện mọi dạng scan trùng đã resample. Giữ mọi row và flags; không tự xóa/loại expert annotations. `strong_eligible` chỉ là QA indicator, không tạo training split.

**Patient ID để null**: metadata phân phối không cung cấp mapping case→patient. Không suy luận `lung_###` là patient identity; T07 phải xử lý bằng chứng grouping sau inventory cả ba nguồn.

Exit codes:0 = inventory xong, không có QC errors/dataset findings;2 = inventory đã xuất nhưng có lỗi cần review;1 = không thể thực hiện command (root/metadata/config/read failure cấp dataset). Warnings như empty masks/qform disagreement nằm trong report; không tự sửa dữ liệu.

## QA ba mặt phẳng

```powershell
.\.venv\Scripts\python.exe -m lungseg.cli qa-msd --config configs/msd.yaml
# Lựa chọn minh bạch khi cần xem một ca cụ thể:
.\.venv\Scripts\python.exe -m lungseg.cli qa-msd --config configs/msd.yaml --case-ids <case_id_1> <case_id_2>
```

Chọn mặc định8 ca theo các rank cách đều của thể tích u, gồm hai extremes; không dùng score mô hình. Mỗi ca có axial/coronal/sagittal, full-plane và zoom chỉ phục vụ QA. CT display window[-1000,400], mask đỏ; reorient bằng permutation/flip sang RAS, **không resample**, raw không đổi. Với oblique affine, mặt phẳng là voxel planes gần canonical axes, không phải world-plane reslicing.

Đọc CT streaming một lượt, giữ ba planes; chỉ giữ mask uint8 để chọn slice có diện tích foreground lớn nhất mỗi hướng. Đối chiếu manifest SHA256 với inventory_run và kiểm lại CT/mask hashes để từ chối metadata hoặc input bị thay sau inventory. NIfTI geometry matching không chứng minh expert mask đúng giải phẫu: phải xem ảnh và ghi nhận nhận xét thủ công riêng.

Ảnh và `qa_index.json` ở `data/qa/msd/`, gitignored để tránh đưa medical slices vào Git. Index có case IDs, vị trí slice, hashes, selection rule, license và `manual_review: pending`. Người review ghi nhận trong `docs/msd_qa_report.md`; không tự đổi pending thành pass. Synthetic tests có nhãn ảnh **SYNTHETIC NIfTI FIXTURE — NOT MSD DATA** và không đưa vào QA corpus thật.

## Kiểm thử / phạm vi

```powershell
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_1/verification
```

Chạy toàn bộ tests P0 và P1.1, smoke CPU, env và pip check; giữ bằng chứng P0 cũ. Các unit tests chỉ dùng fixtures synthetic và HTTP mocks, không tải dữ liệu trong pytest. Bằng chứng MSD thật nằm trong acquisition/inventory/QA report riêng.

Không thực hiện T05–T08, split, production preprocessing, bbox generation hoặc model training ở P1.1. Dừng sau báo cáo T04 để người dùng review.
