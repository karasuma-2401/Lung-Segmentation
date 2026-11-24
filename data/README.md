# Dữ liệu

Ba nguồn của dự án: MSD-Lung, NSCLC-Radiomics và Lung-PET-CT-Dx. P0 chưa tải data; P1.1 chỉ thực hiện MSD-Lung, xem [tiến độ](../docs/progress.md), [data card](../docs/data_cards/msd_lung.md) và [QA report](../docs/msd_qa_report.md).

- `manifests/msd/` giữ inventory/summary/provenance T04 và path tương đối; `qa/msd/` giữ montage/index, gitignored medical slices. Không gộp dữ liệu synthetic tests vào inventory thật.
- `official_training`/`official_test` trong manifest là partition nhà phát hành; chưa tạo experiment train/validation/test IDs. Official test không có public GT.
- `raw/` giữ nguyên nguồn; `processed/`, `cache/`, `pseudo/` là output tái tạo được, tất cả gitignored.
- Không đưa CT, RTSTRUCT, weights hoặc định danh bệnh nhân vào Git. Manifest chia sẻ cần pseudo-ID và metadata được phép; bảng liên kết gốc giữ riêng.
- Patient-level split trước mọi crop/augmentation. Khoảng 15% bệnh nhân test mỗi nguồn strong; validation target 20 ca, Scarce train target 40 ca, cùng bệnh nhân không xuất hiện ở nhiều tập.
- Target là thiết kế, không ép số ca bằng cách bỏ qua QC. Quy tắc ROI/UID/bbox phải xác minh trên dữ liệu thực.
- MSD case ID `lung_###` không được mặc định là patient ID; patient_id null khi chưa có mapping có bằng chứng. License nguồn MSD CC-BY-SA4.0 và attribution/notice cho QA ở acquisition guide; không publish raw/QA tự động.
