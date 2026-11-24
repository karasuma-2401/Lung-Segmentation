# Weak manifest schema v1

`data/manifests/weak/manifest_weak.csv`: một row cho CT series được sample acquisition/annotation evidence tham chiếu; patient/study/series group độc lập. Case ID ghép public PatientID và full SeriesUID, không tự dựng patient identity. Unresolved acquisition có row suffix `__unresolved_acquisition`, patient_id_source đánh dấu chưa source-verified. Không dùng những IDs này để tạo split.

CSV UTF-8, bool/list/dict bằng JSON, missing scalar ô rỗng; paths tương đối POSIX. CT/source annotation paths tương đối raw_root; output paths tương đối converted_root. Không export PatientName, demographics, clinical dates hoặc raw pixels. Common fields hợp lý với MSD/NSCLC nhưng **không có mask_path hoặc segmentation-strong label**.

| Fields | Semantics |
|---|---|
|case_id,patient_id,patient_id_source,study_uid,series_uid,sr_sop_uid,sr_series_uid|Public/de-identified DICOM identity từ verified source; không giả mapping giữa datasets |
|modality,image_type,ct_eligible,paper_filter_eligible|Diagnostic-type/geometry checks và extent rule; catalog CT chưa đồng nghĩa đủ eligibility |
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

`exclusion_log.csv` là sample rows excluded bởi technical/paper rules; sample hiện0. `quarantine.csv` và conversion_report.json giữ lỗi/mapping/source-read failures; sample hiện0. `catalog_exclusion_log.csv` ghi133PT metadata-only non-CT exclusions, **không phải133images đã decode/QC**. Annotation failures ngoài CT mapping và raw acquisition errors còn có trong report, không bị coi là negative. `conversion_report.json`/`annotation_survey.json`/QA index nối qua manifest/config/implementation hashes; timestamp ở run report không làm đổi CSV khi rerun cùng source/config/implementation.
