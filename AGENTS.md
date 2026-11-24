# Hướng dẫn dự án

- Giao tiếp và tài liệu tiếng Việt; code, identifiers và commands tiếng Anh.
- Đọc `docs/decisions.md` và `docs/progress.md` trước khi làm việc. Quyết định mới của người dùng ưu tiên hơn bản handoff gốc.
- Phạm vi lượt triển khai đầu tiên: P0/T01–T03. Dừng sau P0; P1+ cần yêu cầu tiếp của người dùng.
- Giữ phương án ba dataset, Scarce trước Vast; không tự giảm phạm vi.
- Không sửa raw data, không dùng test để tune, không công bố kết quả chưa đo.
- Không import/chạy code trong `.reference/` tùy tiện: có lỗi loader, geometry và external logger. Tham chiếu pinned commit trong `configs/references/upstream.yaml`.
- Smoke model là fixture MONAI nhỏ, không phải architecture tái hiện paper. Không ghi smoke loss vào bảng kết quả nghiên cứu.
- Chạy `python -m pytest -q` và smoke theo README sau thay đổi liên quan; ghi bằng chứng thật. Không commit/push nếu chưa được yêu cầu.
