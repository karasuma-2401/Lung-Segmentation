# Dữ liệu

Chưa tải dataset ở P0. Ba nguồn dự kiến: MSD-Lung, NSCLC-Radiomics và Lung-PET-CT-Dx.

- P1 mới tải/kiểm định và tạo manifests/splits; chưa có split IDs hoặc thống kê số ca thực.
- `raw/` giữ nguyên nguồn; `processed/`, `cache/`, `pseudo/` là output tái tạo được, tất cả gitignored.
- Không đưa CT, RTSTRUCT, weights hoặc định danh bệnh nhân vào Git. Manifest chia sẻ cần pseudo-ID và metadata được phép; bảng liên kết gốc giữ riêng.
- Patient-level split trước mọi crop/augmentation. Khoảng 15% bệnh nhân test mỗi nguồn strong; validation target 20 ca, Scarce train target 40 ca, cùng bệnh nhân không xuất hiện ở nhiều tập.
- Target là thiết kế, không ép số ca bằng cách bỏ qua QC. Quy tắc ROI/UID/bbox phải xác minh trên dữ liệu thực.
