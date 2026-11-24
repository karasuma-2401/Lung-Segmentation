# Hướng dẫn dự án

- Giao tiếp và tài liệu tiếng Việt; code, identifiers và commands tiếng Anh.
- Đọc `docs/decisions.md` và `docs/progress.md` trước khi làm việc. Quyết định mới của người dùng ưu tiên hơn bản handoff gốc.
- Phạm vi lượt triển khai đầu tiên: P0/T01–T03. Dừng sau P0; P1+ cần yêu cầu tiếp của người dùng.
- P0 CPU và P1.1/T04 (commit fef32f1932df3e6e0644b937fdd775f953cd3cae) đã được người dùng review/chấp thuận. Lượt hiện tại được duyệt P1.2/T05: NSCLC-Radiomics acquisition/conversion/validation, chỉ tập mẫu khi thiếu storage. Dừng sau P1.2; không T06–T08, experiment splits, preprocessing production hoặc training.
- Người dùng xác nhận chỉ còn khoảng45 GiB ở ổ C, không có ổ khác. Không tải full NSCLC; giữ BLOCKED_STORAGE, không tự xóa MSD/raw/archive để lấy chỗ. Phân biệt sample validation với full corpus validation.
- P1.2 được review có điều kiện tại commit `1429bb14996beded92cafa128e0d827787f55f5e`. Lượt hiện tại chỉ P1.2.1: fix empty-polygon detection, version conversion cache, revalidate10ca vào output mới và thiết kế full-corpus execution plan. Giữ nguyên ROI/quarantine/Scarce–Vast; dừng sau P1.2.1, không P1.3/T07/T08/research training hoặc full download.
- P1.2.1 đã nghiệm thu tại dev commit `a3712db3ecea5607b878c76f40de967004d3eee8`. Lượt hiện tại được duyệt P1.3/T06 Lung-PET-CT-Dx: source/capacity, actual annotation survey, bounded sample CT/bbox conversion/inventory/QA. Dừng sau P1.3; không full NSCLC/cloud provisioning/cleanup/P1-R/T07/T08/Teacher/pseudo/Student/training. Missing annotation không là negative; bbox không là segmentation GT.
- Giữ phương án ba dataset, Scarce trước Vast; không tự giảm phạm vi.
- Không sửa raw data, không dùng test để tune, không công bố kết quả chưa đo.
- Không import/chạy code trong `.reference/` tùy tiện: có lỗi loader, geometry và external logger. Tham chiếu pinned commit trong `configs/references/upstream.yaml`.
- Smoke model là fixture MONAI nhỏ, không phải architecture tái hiện paper. Không ghi smoke loss vào bảng kết quả nghiên cứu.
- Chạy `python -m pytest -q` và smoke theo README sau thay đổi liên quan; ghi bằng chứng thật. Không commit/push nếu chưa được yêu cầu.
