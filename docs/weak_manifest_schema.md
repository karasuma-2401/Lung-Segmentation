# Weak manifest schema v2 — P1.3.1

`data/manifests/weak_p1_3_1/manifest_weak.csv`: một `record_type=ct_case` cho mỗi patient/study/CT-series group quan sát hoặc CT reference hợp lệ từ SR. Case ID ghép public PatientID và full SeriesUID. Không tạo CT UID hoặc CT-case row khi reference chưa xác định. Acquisition lỗi không còn dùng suffix `__unresolved_acquisition`; được ghi riêng. Bản v1 tại `data/manifests/weak` là baseline bất biến.

CSV UTF-8, bool/list/dict bằng JSON, missing scalar ô rỗng; paths tương đối POSIX. CT/source annotation paths tương đối raw_root; output paths tương đối converted_root. Không export PatientName, demographics, clinical dates hoặc raw pixels. Common fields hợp lý với MSD/NSCLC nhưng **không có mask_path hoặc segmentation-strong label**.

| Fields | Semantics |
|---|---|
|case_id,patient_id,patient_id_source,study_uid,series_uid,sr_sop_uid,sr_series_uid|Public/de-identified DICOM identity từ verified source; không giả mapping giữa datasets |
|modality,image_type,ct_eligible,paper_filter_eligible|Diagnostic-type/geometry checks và extent rule; catalog CT chưa đồng nghĩa đủ eligibility |
|record_type,acquisition_semantics|CT-case record; observed AcquisitionNumber, TemporalPositionIdentifier, ImageType, NumberOfTemporalPositions, số object thiếu tags, findings và verified/suspicious/unknown. Verified chỉ là metadata consistency, không phải expert clearance |
|ct_source_paths,annotation_source_paths,source_files,source_sha256|Relative DICOM paths, SHA256 và source marker hashes; source digest canonical |
|native_geometry,image_shape,image_spacing_mm,image_affine,image_orientation|Native IJK/IOP/IPP-derived LPS/RAS affine, spatial SOP order/frame/spacing; no resample |
|slice_center_span_mm,physical_z_extent_mm,anatomical_si_extent_mm,physical_extent_convention|Primary filter dùng slice-normal voxel-edge FOV span+gap; anatomical S/I world edge extent được lưu riêng cho oblique/shear |
|annotation_kind,ground_truth_available|weak_expert_bbox_SR_not_segmentation_GT; GT=false toàn bộ, kể cả bbox geometry pass |
|box_count,annotated_slice_count,missing_slice_count,explicit_negative_slice_count,multiple_box_slice_count|Giữ mọi source bbox, positive count khác annotation completeness; missing không phải negative |
|annotation_coverage_status,coordinate_convention,finding_codes,duplicate_box_geometry_count|Actual SR semantics/coverage, no implicit VOC origin, duplicates retained/review |
|image_path,bbox_path,boxes_path,coverage_path,provenance_path và SHA256 tương ứng|CTfloat32, bbox-envelopeuint8 native grid, all individual bbox records, per-SOP coverage và provenance riêng |
|label_values,bbox_foreground_voxels,bbox_envelope_volume_mm3,geometry_aligned|Geometry/union-box measurements, **không phải tumor segmentation volume** |
|conversion_status,qc_errors,qc_warnings|converted/excluded/quarantined; errors không silently skip, source giữ nguyên |
|weak_eligible,weak_eligibility_status|False trong T06; bbox_geometry_valid_coverage_review_required không phải train clearance |
|config_sha256,implementation_fingerprint_sha256|Full resolved config và code/dependency identity; không reuse legacy/mismatched cache |

Provenance chứa config/implementation full identity, source hashes/UIDs, native matrices, intensity transforms, annotation evidence references, output hashes và source_annotation_changed=false. Weak fingerprint bao quát weak acquisition/parser/inventory/QA/config và reused geometry/NIfTI writer/validation helpers, cùng Python/NumPy/NiBabel/pydicom versions; normalize source LF/CRLF. Existing outputs khác source/config/identity/hash phải explicit versioned reconversion, không overwrite/xóa.

Các artifacts v2 có đơn vị đếm riêng:

- `manifest_weak.csv`, `quarantine.csv`, `exclusion_log.csv`: CT-case rows; `quarantined_cases` chỉ đếm CT cases, không cộng annotation failures.
- `annotation_records.csv`: mỗi source SR một record, kể cả unreadable/malformed; `annotation_failures.csv` là subset `status=failed`. Giữ configured/observed PatientID, observed SR SOP/Series UID, declared UID riêng khi header chưa đọc được, relative source path/SHA256, observed evidence references, reason và liên kết CT-case/results khi có. Observed references phục vụ truy vết, không tự được coi là validated mapping. `parsed` chỉ nghĩa parser thành công; conversion/mapping còn có thể quarantine ở CT-case results.
- `acquisition_failures.csv`: mỗi requested patient bị acquisition error một record; object-level paths/hash/reasons được lồng trong `source_failures`. Một patient có thể đồng thời có CT-case và acquisition failure; không cộng hai đơn vị này thành số bệnh nhân.
- `source_objects.csv`: mỗi discovered DICOM hoặc expected object bị thiếu một record; `exists`, verification status và declared identity rõ ràng. `source_dicom_objects` đếm file thực có; `source_object_records` bao gồm expected-but-missing.
- `reconciliation.json`: requested patients cùng CT-case IDs, source/annotation counts và acquisition errors; source records = verified + failed; annotation records = parsed + failed; requested patient luôn có CT-case, annotation record hoặc acquisition error. Missing CT reference không làm biến mất annotation-only patient.

`conversion_report.patient_count` là số patient có CT-case row, không phải toàn bộ requested patient count; số requested lấy từ reconciliation. `annotation_SR_objects` là số annotation source records, có thể gồm expected-but-missing; dùng `source_objects.csv`/observed counts để phân biệt file có thật và file chưa có. Không suy ra payload đã đọc từ số declared objects.

Manifest/config/implementation/output SHA256 nối report với QA; CSV deterministic khi source/config/implementation không đổi. `catalog_exclusion_log.csv` tại baseline ghi133PT metadata-only exclusions, không phải133images đã decode/QC. Fingerprint v2 bổ sung `weak_sources.py`; legacy output cần versioned reconversion, không overwrite.
