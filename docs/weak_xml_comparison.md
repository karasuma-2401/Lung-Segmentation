# Kiểm tra XML người dùng tải sau khi đổi VPN — 24/11/2026

**XML access RESOLVED; XML–SR equivalence REVIEW_REQUIRED.** Đây là bounded follow-up cho Task E/P1.3.1, không thay production parser, ROI/coverage policy, conversion hoặc training clearance.

## Archive thực đã đọc

Archive basename: `Lung-PET-CT-Dx-Annotations-XML-Files-rev12222020.zip`; local location cấu hình riêng bằng `LUNGSEG_XML_ARCHIVE`, không đưa user directory vào shared reports. Historical comparison/execution evidence giữ nguyên.

- Dung lượng **17,304,054bytes**, khoảng16.50MiB, phù hợp số16.5MB trên download UI.
- SHA256 `74578564508a2c52c6046ef8065708c068b884711dd924d4eaf3db298914d377`.
- **CRC PASS**, không có duplicate ZIP member names; không giải nén hoặc sửa ZIP.
- 31,921members;31,562file đuôi`.xml`; tổng uncompressed17,997,486bytes.
- Browser `Zone.Identifier` ghi referrer đúng [official TCIA XML page](https://www.cancerimagingarchive.net/tcia-downloads/lung-pet-ct-dx-da-other/lung-pet-ct-dx-annotations-xml-files-rev12222020/), HostUrl thuộc official TCIA uploads. Giữ observed URL trong evidence, bỏ query khi ghi log. Đây là provenance từ download trên máy, không có independent publisher checksum để xác minh cryptographic authenticity.

## Findings trong archive

**31,561XML parse được**, chứa31,659object boxes. 31,463XML có1object;98XML có2objects. Một file không phải XML text đọc được:

`Annotation/A0024/1.3.6.1.4.1.14519.5.2.1.6655.2359.148117780944430339778694852523.xml`

File4096bytes, byte đầu `00051607000200004d6163204f532058`, có chuỗi`Mac OS X`; XML parser báo invalid token line1/column0. CRC hợp lệ chỉ xác nhận ZIP lưu đúng bytes, không chứng minh nội dung mỗi file là XML hợp lệ. Không sửa, bỏ hoặc diễn giải file này thành annotation rỗng.

Parsed XML nằm trong357patient folders; không phải bằng chứng357patients đã inventory CT. So với355original patients trong pinned catalog: XML có thêm A0060/A0067/A0076/A0266; catalog A0058/A0251 không có parsed XML. Cần review release/mapping trước full corpus, không tự rename/merge patient IDs.

Tên class giữ nguyên và phân biệt hoa/thường: A13,065; a7,911; B2,244; b860; E201; G5,270; g2,089; Q10; A0192 có9objects. Không tự normalize `Q`/`A0192` hoặc suy ra diagnosis từ folder. XML size width/height512×512; depth metadata là1ở20,969files và3ở10,592files. Không coi VOC depth là số axial slices. Thuộc tính`verified` có`no`30,943và`yes`618; không dùng cờ này để tự công bố expert approval/clearance.

## So sánh với 10 ca CT/SR thật

Chỉ đối chiếu XML có tên file trùng exact CT SOP UID và patient folder; xác minh width/height CT. Đọc lại raw SR và kiểm bbox records khớp existing boxes.json trước so sánh. XML ngoài selected10CTseries không bị gọi là đã validate CT.

| Patient | SR boxes | XML boxes trên selected CT | Exact raw bounds matches |
|---|---:|---:|---:|
|A0001|11|11|11|
|A0002|10|10|10|
|A0003|4|2|2|
|A0004|4|4|4|
|A0005|1|1|1|
|A0006|7|7|7|
|B0001|16|16|16|
|E0001|14|14|14|
|G0001|4|4|4|
|G0002|6|6|6|
|**Tổng**|**77**|**75**|**75**|

**9/10cases có raw bbox record multiset giống nhau; cả10có cùng positive SOP set (75positive slices).** XML75boxes là subset exact của SR77boxes trong sample; không có XML-only boxes. Cùng tọa độ số không chứng minh XML có cùng pixel-edge/center/inclusive semantics với DICOM SCOORD, nên chưa gọi voxel rasterization equivalent hoặc mặc định VOC one-based/zero-based.

Observed class associations trên75matched boxes: A→SCT1187332001 Adenocarcinoma; B→SCT74364000 Small cell carcinoma; E→SCT22687000 Large cell carcinoma; G→SCT1162767002 Squamous cell carcinoma. Chưa validate mapping cho a/b/g/Q/A0192 trên full corpus. [Publisher](https://zenodo.org/records/16989820) mô tả SR là expert XML annotations harmonized; finding thực cho thấy vẫn cần giải thích version/record differences.

Hai SR-only boxes ở **A0003**:

| CT SOP UID | SR bounds xmin,ymin,xmax,ymax |
|---|---|
|1.3.6.1.4.1.14519.5.2.1.6655.2359.178836002044492899997583802620|366,253,405,298|
|1.3.6.1.4.1.14519.5.2.1.6655.2359.386936544335940634104504855125|353,258,408,312|

Đã đọc trực tiếp XML tương ứng, mỗi file có1object/1bndbox; không phải bỏ sót second object bởi parser khảo sát. Chưa có bằng chứng để kết luận XML hay SR đúng hơn, hoặc nguyên nhân revision/duplication. Giữ cả nguồn và flag review, không drop2SR boxes để ép số lượng khớp.

## Evidence và preservation

```powershell
.venv\Scripts\python.exe scripts/compare_weak_xml_sample.py --archive $env:LUNGSEG_XML_ARCHIVE
```

[Comparison JSON](evidence/p1_3_1/xml_followup/comparison.json) giữ archive hash, source-member hashes, parse failure, per-case differences và class associations. [Execution log](evidence/p1_3_1/xml_followup/execution.txt) ghi command/timestamp/exit0. Exit0 nghĩa investigation chạy được; report vẫn REVIEW_REQUIRED, không success equivalence.

521files thuộc raw + current converted/manifest/QA được hash trước/sau giống nhau; ZIP người dùng và weak/NSCLC implementation fingerprints không đổi. Không sửa pipeline nên không chạy lại CPU smoke/full217tests chỉ để đọc archive; con số217pass là kết quả P1.3.1 trước đó. Không download thêm, không tạo masks/splits/training hoặc commit/push.

**Kết luận:** gỡ riêng source-access blocker. Full equivalence còn OPEN vì A0003 record discrepancy, coordinate-origin semantics chưa có bằng chứng độc lập, binary XML member và catalog/folder/class inconsistencies ngoài sample. 345missing/unknown slices vẫn unknown; toàn bộ weak_eligible=false. Full corpus BLOCKED_STORAGE và phạm vi3datasets giữ nguyên.
