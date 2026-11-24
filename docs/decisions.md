# Quyết định và câu hỏi mở

Các quyết định dưới đây cập nhật handoff gốc theo hội thoại người dùng. Chưa tạo split hay train thực nghiệm.

| ID | Trạng thái | Quyết định / lý do |
|---|---|---|
| D01 | Người dùng xác nhận | Dự án mới hoàn toàn tại `C:\Projects\Lung-Segementation`, chưa có code hoặc dataset trước P0. |
| D02 | Người dùng xác nhận | Không dùng lịch 12 tuần làm deadline cứng; ưu tiên tiến độ nhanh, giữ kiểm định và đối chứng. |
| D03 | Người dùng đồng ý | Scarce target 40 CT train + 20 CT validation riêng, ưu tiên mỗi CT từ một bệnh nhân khác nhau. Ngân sách mask phát triển target 60 ca, nhãn test thống kê riêng. |
| D04 | Theo handoff đã duyệt triển khai | Ba dataset là mặc định; Scarce E01/E02/E03 trước Vast; không tự fallback một dataset. |
| D05 | Theo đề xuất đã được đồng ý | Validation và test cố định giữa Baseline/Teacher/Student và Scarce/Vast. Scarce train là subset của Vast train; cả hai nguồn strong có mặt trong train/val. Target số lượng khóa sau QC, trước training. |
| D06 | Theo handoff | Weak pool hợp lệ dùng chung giữa hai scenario. Strong train ngoài 40 ca không dùng trong Scarce; không tự chuyển thành simulated weak. Mỗi scenario có Teacher/pseudo riêng. |
| D07 | Theo handoff | So sánh chính theo cùng optimizer-update budget Baseline/SO; log riêng chi phí Teacher/pseudo. Ghi rõ adapted protocol, không gọi exact reproduction. |
| D08 | Triển khai P0 | Upstream pinned `d1bca4b8dec8f3fe623b58d35be78055b954428c`, clone read-only theo quy ước, không copy training loop có lỗi và không chạy external logger. |
| D09 | Triển khai P0 | Virtualenv riêng, stack hiện đại đo thực tế. MONAI smoke nhỏ độc lập, chưa phải model nghiên cứu. Không cài legacy stack vào Python hệ thống. |
| D10 | Giới hạn phạm vi | P0 chỉ audit/env/scaffold/tests; ngày 4–5 loader/crop trong lịch gợi ý handoff được hiểu là khảo sát ở P0, hiện thực ở T08/P1. |
| D11 | Chưa chọn phương pháp mới | Bbox channel/conditioning và model nghiên cứu phải resolve theo paper/source/shape test ở T12. File tên Teacher không chứng minh là đúng model paper. |
| D12 | Người dùng duyệt sau review P0 CPU | Triển khai **P1.1/T04 MSD-Lung acquisition/inventory/QA**; dừng trước T05–T08. Không split experiment, preprocessing production hoặc train. Giữ ba dataset. |
| D13 | Xác minh source MSD T04 | AWS Open Data MSD public/no-account, CC-BY-SA4.0; archive Task06_Lung có metadata63 training +32 test, khác số64 ở tài liệu tham khảo. Không tự bổ sung ca hoặc đoán lý do chênh lệch. |
| D14 | Quy ước inventory T04 | Case ID giữ tên public từ nguồn; patient_id null vì không có mapping trong dataset.json. Official test không GT; phân vùng nguồn không phải experiment split. |
| D15 | Bảo toàn annotation / giới hạn QA | QC flags và strong_eligible chỉ giúp review, không xóa/sửa expert mask. Montage dùng native grid permutation/flip, không resample, window/zoom chỉ hiển thị; giữ raw và ảnh y tế ngoài Git. |
| D16 | QA finding T04 — chưa adjudicate | `lung_022` cần nhóm xem toàn volume/source do ranh giới mask trên montage; giữ raw/manifest/statistics và không tự loại/sửa. `lung_018` intensity max20349 được ghi nhận, không clip/reject ở T04. |

Thứ tự split dự kiến ở P1: kiểm định và loại duplicate → giữ test khoảng 15% bệnh nhân mỗi nguồn strong → chọn validation target 20 CT từ bệnh nhân còn lại, phân bố nguồn/kích thước → phần còn lại là Vast train pool → lấy target 40 CT cho Scarce. Tất cả scan của một bệnh nhân đi cùng tập; số CT/patient báo riêng. Nếu điều kiện dữ liệu khiến target không khả thi, báo evidence trước khi đổi.

Tỷ lệ MSD:NSCLC trong 40/20 chưa khóa: cần inventory và phân bố kích thước thực. Hai mươi ca validation là ngân sách thực dụng, không phải cam kết tối ưu hoặc đảm bảo đại diện đầy đủ; hạn chế search hyperparameter và báo độ bất định.

| OPEN | Thời điểm giải quyết | Cách xử lý tiếp |
|---|---|---|
| O01: Exact split/weak-pool scarce của tác giả chưa tái dựng được | T07 | Source có `train2/val2` nhưng loader bỏ qua, không có seed/script patient split; adapted protocol giữ nguyên. Không suy diễn chuyển strong thành weak. |
| O02: Bbox thực có đầy đủ trên mọi axial slice/object không? | T06 | Kiểm annotation sample và UID overlay. Missing không đồng nghĩa negative; không gán nền bên ngoài vùng có nhãn nếu chưa xác minh annotation coverage. |
| O03: Teacher conditioning/depth/channels và exact Student blocks | T12 / trước full training | MONAI variant gần Fig2 hơn UNet4; chưa có config duy nhất chứng minh exact paper run. Shape/forward/backward tests bắt buộc. |
| O04: Z-score scope, loss smooth/empty cases, sampler ratio, normalization defaults | T08/T10 | Kiểm version gốc và chốt resolved config; ghi adaptation nếu thay đổi. |
| O05: DSC-TP/F1 overlap denominator, connectivity và matching | T09 | Không tìm được implementation trong source Python upstream. Viết spec có tests và declared adaptation. |
| O06: CT–RTSTRUCT referenced series và primary tumor ROI | T05 | Source chọn `GTV-1` nhưng không kiểm UID; cần xác minh trên từng ca, không áp tên ROI mù quáng. |
| O07: Dataset license/access/disk/GPU | T04–T06/T10 | MSD đã tải và kiểm95 CT/63 masks ở T04, CC-BY-SA4.0, raw/archive9.16 GB mỗi phần; còn khoảng46.2 GB free. Hai nguồn còn lại chưa kiểm. Máy local khoảng8 GB RAM; Kaggle/CUDA/persistence vẫn chưa chạy. |
| O08: Full-state checkpoint/resume | T10 | P0 chưa hiện thực. Test 10 steps so với 5+save/load+5 với optimizer/RNG/logs khi xây training loop. |
| O09: MSD patient identity | Trước T07 |95 case IDs không phải bằng chứng95 patients; patient_id null do metadata không có mapping. Cần source mapping/justified grouping trước patient-level split. |
| O10: Annotation review lung_022 | Trước training | Codex visual finding, không phải expert correction. Nhóm review full volume/source rồi quyết định minh bạch; T04 không blacklist hoặc sửa mask. |

Paper có correction ngày 13/02/2024, chỉ sửa Funding, không giải thích bất nhất prose SO/DO hoặc split: [correction](https://doi.org/10.1371/journal.pone.0298978). Số 71.00 theo Table 5 là DO, không SO.
