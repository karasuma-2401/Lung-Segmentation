# Manifest MSD v1 — data dictionary

`manifest_msd.csv` dùng UTF-8, header cố định, row sort theo case ID/source partition/path. Path POSIX tương đối `dataset_root`; không chứa absolute paths. Giá trị null là ô trống; list/matrix dùng JSON trong ô CSV; booleans `true`/`false`.

| Field(s) | Ý nghĩa / quy tắc |
|---|---|
| `schema_version`, `dataset` | Version1, `MSD-Task06_Lung`; case IDs là ID ca public của nguồn. |
| `source_version` | Release nguyên văn từ metadata (`relase`/`release`); null khi nguồn không khai báo. |
| `case_id` | Tên file NIfTI bỏ `.nii.gz`/`.nii`, không suy luận patient identity. |
| `patient_id`, `patient_id_source` | Null khi không có mapping đã xác minh; `not_provided_in_dataset_json`. Không tự hash/copy case ID thành patient ID. |
| `source_partition` | `official_training`, `official_test`, `unlisted`; chỉ phân vùng nhà phát hành, không phải experiment split. Không có field experiment `split` ở T04. |
| `image_path`, `mask_path` | Path tương đối; mask_path trống cho official test, vẫn ghi expected path nếu training mask thiếu. |
| `annotation_kind` | `strong_mask` khi có file mask, `missing_mask` khi expected GT thiếu, `none` khi nguồn không cung cấp GT. Có file không đồng nghĩa annotation hợp lệ. |
| `ground_truth_available` | File GT được liệt kê có thực sự tồn tại. Official test luôn false. |
| `strong_eligible` | QA indicator: CT/mask đọc được, mask nonempty/binary, native grid khớp, không QC errors. Không tự đưa ca vào train và không xóa ca fail khỏi manifest. |
| `image_readable`, `mask_readable` | Header và dữ liệu3D đọc xong toàn volume, kể cả cuối gzip; không chỉ header load pass. |
| `image_shape`, `mask_shape` | Shape array NIfTI theo thứ tự native `(i,j,k)`, chưa đổi thành tensor D/H/W. |
| `*_spacing_mm` | Header zooms chuyển sang mm dựa `xyzt_units`; null nếu units không rõ/spacing không hợp lệ. |
| `*_spatial_unit` | Unit gốc trong header: mm/meter/micron/unknown. |
| `*_affine` | Affine gốc4×4 (unit gốc), hoặc null nếu không hợp lệ. |
| `*_affine_mm` | Affine4×4 với ba hàng đầu đổi sang mm; null nếu không xác minh được units. |
| `*_orientation` | Axis codes từ active affine, ví dụ LAS/RAS; không tự đổi raw orientation. |
| `*_qform_code`, `*_sform_code` | Codes nguyên bản. qform/sform cùng tồn tại nhưng khác quá tolerance được cảnh báo. |
| `*_dtype` | NIfTI storage dtype. Voxel reads dùng slope/intercept của NiBabel, không sửa file. |
| `image_sha256`, `mask_sha256` | SHA256 toàn file nén, phát hiện thay đổi bytes. |
| `image_voxel_sha256` | Fingerprint shape + voxel values float64, z-first order; độc lập slab size/gzip header; không phải patient ID. |
| `image_affine_sha256` | SHA256 affine gốc dạng little-endian float64. |
| `ct_min`, `ct_max` | Min/max đọc từ finite slabs; ca có nonfinite voxel vẫn fail, không dùng range này để khẳng định CT hợp lệ. |
| `label_values`, `label_values_truncated` | Nhãn thực đọc; tối đa64 unique values được lưu để giới hạn memory. Nonfinite hoặc giá trị ngoài{0,1} đều fail. |
| `foreground_voxels` | Tổng số voxel label1. Không gọi mọi nonzero value là cancer. |
| `voxel_volume_mm3` | `abs(det(mask_affine_mm[0:3,0:3]))`; hỗ trợ shear tốt hơn tích spacing. |
| `tumor_volume_mm3` | Foreground × voxel volume; null nếu nhãn sai/units chưa rõ;0 nếu mask thật rỗng. Tổng foreground của mask ca, không phải volume mỗi lesion. |
| `geometry_aligned` | Shape bằng nhau và active affine/spacing khớp theo tolerance0.001mm sau đổi đơn vị. Chưa xác minh correctness giải phẫu. |
| `qc_status` | `fail` khi có errors; `warn` khi chỉ warnings; `pass` khi không lỗi/cảnh báo tự động. Không phải kết luận manual QA. |
| `qc_errors`, `qc_warnings` | Danh sách reason codes sorted: missing, unreadable, dimensions, units/spacing/affine, shape/affine/spacing mismatch, label values, duplicates, unlisted, empty mask... |

`summary.json` không thay thế manifest. `real_data=false` là fixture synthetic; `null` là nguồn cung cấp thủ công chưa xác minh; `true` dùng khi có provenance acquisition. SHA256 archive trong provenance là hash đo, chưa có checksum độc lập nhà phát hành để đối chiếu.

Các QC flags không tự sửa/loại annotation chuyên gia. T04 chỉ báo và giữ nguồn nguyên vẹn; quyết định sử dụng cần review trước các phase training sau.
