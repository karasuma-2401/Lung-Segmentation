# Data card — MSD Task06_Lung

## Định danh, nguồn và license

- Tên metadata: `Lung`; description: `Lung and cancer segmentation`; reference: `The Cancer Imaging Archive`.
- Release metadata nguyên văn: `1.0 04/05/2018`, field nguồn viết `relase`; không diễn giải ngày/tháng theo định dạng khác.
- [Medical Segmentation Decathlon](https://medicaldecathlon.com/index.html); phân phối chính thức [AWS Open Data Registry](https://registry.opendata.aws/msd/), bucket `msd-for-monai`, region `us-west-2`, Task06_Lung.tar.
- License **CC-BY-SA 4.0**, khớp registry và `dataset.json`. Attribution/citation, link license, chỉ rõ thay đổi và ShareAlike cho dữ liệu phái sinh khi phân phối; không tự upload/publication trong P1.1. [License](https://creativecommons.org/licenses/by-sa/4.0/).
- Cite Simpson et al., [arXiv:1902.09063](https://arxiv.org/abs/1902.09063), và Antonelli et al., [Nature Communications2022](https://doi.org/10.1038/s41467-022-30695-9). Hướng dẫn và source identity/checksum: [acquisition guide](../msd_acquisition.md), `docs/evidence/p1_1/acquisition.json`.

## Nội dung và annotation

CT 3D, một channel. Label mapping trong metadata: `0=background`, `1=cancer`. Strong annotation là expert segmentation mask của vùng tumor được nguồn cung cấp, không phải mask hai phổi. Volume tumor là tổng voxel label1 trong cả mask ca; không tự suy diễn số lesion, stage hoặc subtype lâm sàng từ mask.

Archive metadata ghi **63 training images +63 tương ứng masks**, **32 official test images không có public masks**. Đây là95 CT cases, không mặc định95 bệnh nhân. Mốc64 training trong trang giới thiệu/handoff/paper là số tham khảo khác bản archive đã lấy; lý do khác biệt chưa xác minh. Không bổ sung dữ liệu giả hoặc tùy ý bỏ ca để khớp số tham khảo.

Case IDs lấy từ tên NIfTI public `lung_###`. `dataset.json` không có patient ID, UID hoặc mapping case→patient đã kiểm chứng. Manifest để `patient_id=null`; không tạo patient ID từ case ID và không khẳng định patient independence. Metadata không đủ để đối chiếu mọi ca với raw TCIA hoặc cross-dataset duplicates; T07 cần giải quyết trước chia dữ liệu.

## Hình học và kiểm định

Kết quả đo thật của T04: **95/95 CT và63/63 masks đọc được**,95 auto-QC pass,0 errors/warnings. Shape native512×512×112–636; spacing i/j0.597656–0.976562mm, k0.625–2.5mm; units mm, orientation LAS cho95 CT. Labels{0,1};63/63 image–mask aligned trong tolerance0.001mm. Tumor volumes min/median/max0.737738/5.220032/370.384113cm³. CT float32, masks uint8. Không có empty masks hoặc duplicate fingerprints trong corpus đã kiểm.

Đã xem10 montage thật. `lung_022` cần review annotation riêng dù auto geometry pass; `lung_018` có intensity max20349, chưa xác định nguyên nhân. Không sửa/loại chúng. Selected-slice QA không thay thế expert annotation adjudication; xem report để biết phạm vi và giới hạn.

Các volume giữ native shape/spacing/orientation và active affine. Không canonicalize hoặc resample raw. CT/mask được kiểm shape, affine/spacing theo mm, units, qform/sform, finite voxels, binary labels, foreground, physical volume và exact duplicate fingerprints. Chi tiết ở [manifest schema](../msd_manifest_schema.md).

Trạng thái kiểm định và các thống kê thực nằm ở `data/manifests/msd/summary.json` và [QA report](../msd_qa_report.md). Data card không dùng số paper làm số đo của nhóm. Manifest bao gồm cả ca có/không có GT; `strong_eligible` chỉ là chỉ báo QA tự động, không phải assignment vào train hoặc quyết định tự động loại annotation.

Công thức volume: `N(label=1) × abs(det(mask_affine_mm[0:3,0:3]))`, mm³. Unknown spatial units → null volume và lỗi QC; không gán đơn vị mm mặc định. Empty GT vẫn là annotation có thật, được cảnh báo và giữ nguyên.

## Vai trò trong dự án và hạn chế

- Một trong **hai strong sources** của phương án ba dataset. NSCLC-Radiomics và weak Lung-PET-CT-Dx vẫn thuộc scope; chưa triển khai chúng ở P1.1.
- Official partition của MSD không phải split nghiên cứu. Chưa chia train/validation/test nội bộ, chưa chọn40/20 hoặc chạy training. Official test không có mask nên không dùng cho local Dice với GT giả.
- QA xem nhiều kích thước u trên axial/coronal/sagittal; chỉ CT display window/permutation/flip/overlay/zoom, không thay raw. Cùng grid không đảm bảo annotation đúng giải phẫu; các ca nghi ngờ phải review riêng, không tự sửa expert mask.
- Label availability không chứng minh annotation đầy đủ cho mọi lesion hay mọi bệnh lý. Không mặc định các vùng ngoài tumor là bằng chứng âm tính cho tác vụ khác.
- Đây là dữ liệu nghiên cứu đã được nguồn công bố; không phải pipeline chẩn đoán lâm sàng và không có kết quả model của nhóm ở T04.

## Artifact và lưu trữ

- Raw: `data/raw/Task06_Lung/{imagesTr,labelsTr,imagesTs,dataset.json}`; archive và provenance cùng dưới `data/raw/`, gitignored.
- Manifest/summary/run provenance: `data/manifests/msd/`.
- Montage có attribution/license + index: `data/qa/msd/`, gitignored medical slices.
- Acquisition/test/execution evidence: `docs/evidence/p1_1/`.
- Source files chỉ đọc; mọi QC finding giữ trong report và manifest. Không có blacklist tự động, mask correction hoặc preprocessing production ở T04.
