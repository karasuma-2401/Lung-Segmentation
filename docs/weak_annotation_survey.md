# Annotation format và coverage survey — T06

**Đã đọc thực:**10DICOM SR objects thuộc official IDC expert annotation collection, trước implementation parser;10referenced CT series. **Chưa đọc:** XML archive gốc vì timeout. Không suy ra XML zero/one-based từ tên PASCAL VOC. Synthetic VOC math helpers chỉ kiểm explicit coordinate conversion, không là XML production parser đã verified.

SR thực là Comprehensive3DSRStorage, TID1500; CONTAINER Measurement Group(DCM125007), Finding(DCM121071), Tracking UID(DCM112040), Image Region SCOORD/POLYLINE, IMAGE child SELECTED FROM. Closed rectangle có5(column,row)pairs, điểm cuối lặp điểm đầu. CurrentRequestedProcedureEvidenceSequence cho StudyUID→SeriesUID→SOPUIDs. Parser kiểm exact patient/study/series và mọi region SOP, không match substring/InstanceNumber/filename.

Theo [DICOM C.18.6, PS3.3 2026e](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.18.6.html), SCOORD là **continuous pixel-edge coordinates**: top-left pixel edge(0,0), bottom-right(Columns,Rows), order(column,row), mặc định FRAME. Voxel array `[column,row,slice]` có tâm `(i+.5,j+.5)` trong SCOORD. Không áp quy tắc one-based-inclusive của upstream lên SR này.

Conversion chọn voxel centers trong rectangle, không clip/supersample. Với integer edges `(xmin,ymin,xmax,ymax)` tương đương zero-based half-open indices `[xmin:xmax,ymin:ymax]`; ở subpixel boundaries dùng ceil(min−.5), floor(max−.5)+1. Chuyển physical corners bằng native affine LPS tại `(x_edge−.5,y_edge−.5,k)`, rồi NIfTI world RAS đổi dấu x/y. Native voxel indices không flip để sửa bbox. Unsupported SCOORD3D/VOLUME/multiframe/nonrectangle, open/crossed/degenerate/out-of-bounds hoặc no-center boxes bị quarantine, không tự clip/fix/skip.

Giữ từng measurement group, TrackingUID, finding code, original GraphicData, source SOP và physical corners trong `boxes.json` ở converted root gitignored. Bbox union volume chỉ là tiện ích hình học; overlapping rectangles vẫn giữ riêng trong records và QA axial. Duplicate tracking UID bị reject. Exact duplicate geometry với tracking UID khác được giữ và warning để review, không silently deduplicate.

| Patient | CT slices | Bboxes | Positive slices | Missing/unknown slices | Multiple-box slices |
|---|---:|---:|---:|---:|---:|
|A0001|64|11|11|53|0|
|A0002|30|10|10|20|0|
|A0003|27|4|2|25|2|
|A0004|29|4|4|25|0|
|A0005|29|1|1|28|0|
|A0006|54|7|7|47|0|
|B0001|56|16|16|40|0|
|E0001|57|14|14|43|0|
|G0001|23|4|4|19|0|
|G0002|51|6|6|45|0|
|Tổng|420|77|75|345|2|

Actual public IDs có prefix `Lung_Dx-`. Finding codes trong SR gồm Adenocarcinoma, Small cell/Large cell/Squamous cell carcinoma; giữ code system/value/meaning gốc, không tự sửa class dựa vào chữ trong PatientID. Các trang nguồn có mô tả letter codes không hoàn toàn đồng nhất; dùng actual SR codes làm annotation semantics, không dùng suy diễn chẩn đoán.

10SR có bbox không chứng minh labeling đầy đủ mọi slice/lesion. Không thấy assertion explicit-negative được parser hỗ trợ; **0 explicit negative**,345missing/unknown, không phải345negative. COMPLETE/FN verification flags trong SR không là exhaustive slice coverage. Positive bbox cũng không xác minh mọi tumor trong slice đã được gán nhãn. `coverage.json` ghi per-SOP status và `outside_boxes_is_background=false`; không dùng bbox volume như binary segmentation GT hoặc pseudo mask. Tất cả `ground_truth_available=false`, `weak_eligible=false` chờ coverage/training policy review.

Source metadata có354patients trong SR và355 trong original collection; chưa đọc toàn bộ1,091SR nên không khẳng định tất cả CT nào có/không có bbox.10sample chỉ là sample thuận tiện gồm4label groups, không phải random population đại diện. [Survey JSON](../data/manifests/weak/annotation_survey.json), [QA review](evidence/p1_3/qa_visual_review.json).
