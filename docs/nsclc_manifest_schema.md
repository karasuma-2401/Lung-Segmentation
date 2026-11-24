# Manifest NSCLC v1

Artifact: `data/manifests/nsclc/manifest_nsclc.csv`. Một row/public sample patient, sắp theo ID; nhiều RTSTRUCT/series/primary candidates phải resolve explicit hoặc quarantine, không chọn series lớn nhất. Public `LUNG1-###` xác minh từ catalog và DICOM PatientID, không phải danh tính thật. Không tái dùng case→patient assumption của MSD.

CSV UTF-8, newline LF, bool/list/dict bằng JSON, scalar missing để ô rỗng. Paths POSIX tương đối, không chứa raw clinical metadata. `image_path`, `mask_path`, `provenance_path` tương đối `converted_root`; `source_files[].path` tương đối `raw_root`. Full roots nằm trong resolved config/run report, cho phép chuyển ổ bằng config.

| Nhóm | Fields và ý nghĩa |
|---|---|
| Chung MSD | schema_version,dataset,source_version,case_id,patient_id,patient_id_source,source_partition; cùng semantics geometry/labels/volume/hash/QC với MSD |
| DICOM identity | study_uid,ct_series_uid,rtstruct_series_uid,rtstruct_sop_uid,frame_of_reference_uid; lấy từ nguồn đã kiểm, không dựng UID |
| Sources | source_files: relative path,SHA256,source marker SHA256; source_sha256: digest danh sách sắp ổn định |
| ROI | available_rois: number,name,frame_uid,interpreted_types; roi_number/roi_name chỉ primary đã chọn; giữ ROI khác trong survey |
| Native | native_geometry: shape_ijk,spacing_ijk_mm,affine_lps,affine_ras,slice positions/normal spacing, SOPs spatial order; null nếu native geometry không xác nhận được |
| Converted | image/mask shape,spacing_mm,affine/affine_mm,spatial_unit,orientation,qform/sform_code,dtype,readable,hashes; chỉ có khi convert được |
| Mask | label_values,foreground_voxels,voxel_volume_mm3,tumor_volume_mm3; volume=foreground×abs(det(native affine 3×3)), đơn vị mm³; cm³=mm³/1000 |
| Annotation | annotation_kind mô tả expert RTSTRUCT/primary unresolved; ground_truth_available=true chỉ sau rasterization primary thành công; false không có nghĩa healthy/negative hoặc không có bất cứ RTSTRUCT nào |
| Status | conversion_status=converted/quarantined; qc_errors/warnings là danh sách; geometry_aligned không là anatomical correctness |
| Training | strong_eligible=false toàn bộ T05: chưa adjudicate annotation, chưa T07 splits; source_partition=acquisition_sample_not_experiment_split |
| Provenance | provenance_path,SHA256,config_sha256; JSON per converted case chứa source hashes/UIDs, selected ROI/references, từng contour slice/error, native matrices, intensity transforms, config và source_annotation_edited=false |

`quarantine.csv` là subset giữ nguyên rows lỗi, không phải exclusion vĩnh viễn. `roi_survey.json` có toàn bộ ROI names/numbers/types/references kể cả ca không convert. `conversion_report.json` thống kê **sample**, không tổng quát ra422 patients. `qa_index.json` đối chiếu manifest/CT/mask hashes trước render; visual review nằm riêng trong `docs/evidence/p1_2/qa_visual_review.json`. Không tự sửa CSV để clearance training.

LPS→RAS: affine_RAS=diag(-1,-1,1,1)×affine_LPS; array `[column,row,slice]`, không đổi voxel indices hoặc resample. PixelSpacing DICOM `[row,column]` được đổi đúng cột affine. Constant gantry shear giữ trong sform, qform_code=0 nếu qform không biểu diễn được; không ghi qform xấp xỉ. SliceThickness không thay slice-position gaps. Khoảng cách đều không đủ chứng minh không mất nguyên một nhóm slices nếu thiếu metadata độc lập.

Rasterization tại integer voxel centers, even-odd interior và inclusive boundary; CLOSED_PLANAR polygons rời dùng union, CLOSEDPLANAR_XOR dùng XOR. Keyhole giữ đường nối theo [DICOM C.8.8.6.3](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.8.6.3.html). Nested rings CLOSED_PLANAR riêng biệt, unsupported/mixed contour types, source-grid/slab/offset, nonplanar/off-plane/missing-SOP hoặc polygon không có voxel center phải quarantine, không tự fill lỗ/interpolate/skip contour. Không có supersampling/subvoxel area weighting; đây là limitation cần review, không kết luận annotation chuyên gia sai.
