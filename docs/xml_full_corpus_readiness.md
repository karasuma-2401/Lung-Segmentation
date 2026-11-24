# XML trong thiết kế full-corpus readiness — addendum P1-R.1

**DESIGN_ONLY.** Addendum được người dùng duyệt sau dev `dc6e179087737621b69d538ef200436c644a7687`. P1.3.1 và XML investigation đã nghiệm thu, không mở lại implementation phase. Prompt P1-R.1 gốc đã được người dùng gửi lại trong lượt này; tài liệu này bổ sung phần XML cho Task E, đi cùng resource assessment/storage plan/cloud pilot guide. Không coi hoàn thành tài liệu là full-corpus readiness đã pass.

## Quyết định representation và evidence

Tiếp tục **DICOM SR production representation hiện tại** cho P1-R.1. Original XML là immutable reference source phục vụ paper reproduction và annotation cross-validation. Không thay parser SR, xóa2SR-only boxes của A0003, normalize class lạ hoặc suy ra coordinate conventions. Full XML–SR equivalence **REVIEW_REQUIRED**; weak training clearance **false**.

Evidence đã đọc: [XML comparison report](weak_xml_comparison.md), [comparison.json](evidence/p1_3_1/xml_followup/comparison.json) và [investigation script](../scripts/compare_weak_xml_sample.py). Script chỉ khảo sát sample, không phải full reconciliation engine hoặc production XML loader. Một số catalog paths còn cố định trong script; thiết kế full corpus phải pin từng catalog/config, không suy ra identity từ working directory.

| Fact đã đo và được review | Giá trị |
|---|---|
|Archive bytes / integrity|17,304,054 / CRC PASS|
|Archive SHA256|74578564508a2c52c6046ef8065708c068b884711dd924d4eaf3db298914d377|
|XML-named / parsed / malformed members|31,562 /31,561 /1|
|Parsed objects / patient folders|31,659 /357; folder count không phải validated patient count|
|Sample|10real CT/SR cases;75XML boxes match75/77SR boxes by exact SOP/numerical bounds|
|Case equality / positive SOP sets|9/10raw bbox multisets equal;10/10positive SOP sets equal|
|Coverage|345missing/unknown slices giữ unknown;0inferred negatives|

## Storage và immutable provenance

Thêm **một ZIP gốc** vào persistent inventory, không nhân toàn archive cho mỗi batch hoặc mỗi conversion version. Content-addressed key đề xuất: `sources/Lung-PET-CT-Dx/xml/sha256/<full_archive_sha256>/Lung-PET-CT-Dx-Annotations-XML-Files-rev12222020.zip`. Key là thiết kế; chưa copy/upload hoặc tạo storage mới. Versioned manifests tham chiếu cùng digest; backend dedup phải verify bytes, không chỉ tên file. Một backup độc lập thêm17,304,054bytes và có checksum/restore receipt riêng.

| Thành phần | Budget thiết kế |
|---|---:|
|Persistent original XML ZIP, một copy|**17,304,054bytes** thêm vào CT+SR budget|
|Weak full plan cũ CT+SR+conversion allowance+reserve|436,035,934,178bytes|
|Weak full plan gồm XML ZIP|**436,053,238,232bytes**; chưa gồm thêm backup/version/metadata margin|
|Full weak CT+SR+XML source payload|123,409,814,476bytes; catalog estimates cho DICOM, measured ZIP bytes cho XML|
|Nếu giữ thêm toàn bộ XML extracted|Thêm17,997,486bytes payload, cộng filesystem overhead; mặc định đọc member từ ZIP, không cần persistent extraction|
|XML scratch allowance đề xuất|128MiB ngoài batch budget hiện có:24MiB ZIP allowance+64MiB bounded expanded scan+32MiB metadata staging, làm tròn; chưa đo peak RAM/ledger size full-run|
|Combined known planning3datasets|Mốc cũ≈553.58GB cộng0.017304054GB≈**553.60GB**; số tổng đã làm tròn, chưa đủ margin/versions/checkpoints|

Batching không giải quyết persistent capacity. Full corpus vẫn BLOCKED_STORAGE; quota/persistence/restore/peak memory chưa verified, không provision hoặc tải full trong phase này. Dừng trước allocation nếu listing, decoded shape, source bytes hoặc metadata ledger vượt budget; không crop/drop annotations để vừa RAM. Giữ MSD-Lung và NSCLC-Radiomics trong scope và license riêng.

Archive receipt dự kiến ghi: dataset/release label, official landing page, observed download origin, license/attribution, bytes, local SHA256, CRC result, member counts, receipt timestamp, checksum trust level và evidence references. Nguồn hiện tại là user browser download từ official TCIA, chưa có independent publisher checksum. Browser HostUrl trong evidence chứa trailing NUL: giữ observed value như historical evidence nhưng flag invalid URL; không dùng chuỗi đó trực tiếp làm executable URL hoặc âm thầm sửa thành verified source. Validated landing page và raw observed origin là hai fields riêng.

Mỗi member: archive digest + exact member path + member SHA256/bytes/CRC + parse status/reason + parser identity. Raw XML text/pixels không đưa vào Git. Artifact URI trong shared reports dùng logical key hoặc đường dẫn tương đối; local location chỉ ở runtime config/private mapping. Không ghi absolute home/Downloads paths, credentials hoặc signed URLs trong reports mới. Historical timeout/comparison logs giữ nguyên; dẫn link thay vì chép đường dẫn máy từ log cũ sang báo cáo mới.

## 1. Catalog-backed XML/SR/CT reconciliation

Freeze metadata snapshots (original CT/PT catalog, expert SR catalog, archive receipt), full hashes, DOI/license/version và identities của parser/production converter. Không gộp số XML folders357, original catalog patients355 hay expert SR patients354 thành cùng denominator. Không yêu cầu số XML files bằng CT slices vì XML chỉ có positive records và còn release/mapping findings.

Thiết kế các ledgers riêng, tất cả có dataset/source/version, status/reason và evidence hash:

| Ledger | Key và reconciliation |
|---|---|
|Requested catalog entities|Catalog snapshot + public Patient/Study/CT-Series UID; mọi entry phải có outcome pending/converted/excluded/quarantined/missing; PT metadata exclusions riêng|
|CT objects|Catalog + exact Study/Series/SOP UID + frame/class identity, source digest, acquisition/geometry status; catalog metadata chưa là pixel validation|
|SR sources/records|SR SOP UID/source hash, evidence CT refs và TrackingUID/group index, finding code, coordinates; giữ unmapped/parse failures|
|XML members/objects|Archive digest + member path + XML object index; patient folder và filename SOP là observed claims, không verified CT identity|
|Mapping/differences|Các source keys đầy đủ, candidate/verified/conflict/unresolved mapping, exact comparisons và reviewer decision; giữ XML-only/SR-only outcomes|

Reconcile từng denominator:31,562XML-named members =31,561parsed+1malformed trong archive đã pin;31,659parsed objects phải xuất hiện đủ trong object/mapping ledger. Full run sau này reconcile lại từ source, không hardcode counts làm success target. CT-case count không cộng annotation errors; một case có nhiều failure/difference records vẫn chỉ một CT case. Member/record duplicate được flag, không last-writer-wins. Batch manifests merge deterministic theo source keys+digest, giữ mọi contributing batch IDs, conflict nếu cùng key khác content; chỉ nhận completion receipts đã verify integrity. Full reconciliation chưa triển khai/chạy ở đây.

## 2. Patient folder và SOP UID mapping

Exact candidate map: archive folder `A0001` → public-ID candidate `Lung_Dx-A0001`, filename stem → SOP UID candidate. Verify against pinned catalog và acquired CT headers (Patient/Study/Series/SOP/FoR/SOPClass), rồi đối chiếu SR evidence. Không match substring, InstanceNumber hoặc nearest coordinates; không tạo patient identity giả. UID malformed, missing catalog, ambiguous source versions và patient conflict được giữ unresolved.

Observed XML-only folders: A0060/A0067/A0076/A0266; catalog A0058/A0251 chưa có parsed XML. Không tự đổi A0266→A0251 từ mô tả lịch sử nếu chưa có source-level SOP/version proof và adjudication. XML positive SOP không có selected CT sample không đồng nghĩa absent toàn corpus; phân biệt `outside_selected_batch`, `catalog_reference_unresolved`, `CT_not_acquired` và `source_missing_confirmed`.

## 3. Malformed XML member tracking

Giữ record cho member `Annotation/A0024/1.3.6.1.4.1.14519.5.2.1.6655.2359.148117780944430339778694852523.xml`,4096bytes, SHA256 `ce28617cbc3f2cc66f6934cb13ce72a69122c16cb88bae2938cc63605481ceac`. Binary header/parse error trong comparison evidence; CRC pass không biến file này thành XML hợp lệ.

Không skip/error-to-zero hoặc tự sửa. Mapping status unresolved cho annotation đó, giữ source bytes trong ZIP. Sau khi xác định ảnh hưởng CT/SR, ghi review outcome có provenance; valid SR không bị thay bằng fake empty XML label. Các malformed/failure records được persist/restore cùng batch receipts, không chỉ nằm trong stdout.

## 4. XML-only và SR-only differences

So raw records như **multiset** theo validated SOP UID + raw numerical bounds, rồi báo class association/coordinate-policy status riêng; không gọi numerical equality là semantic/rasterized equivalence. XML object index và SR TrackingUID/group index giữ multiplicity. Duplicate geometry không bị collapse hoặc tự xóa.

Sample:75exact matched XML boxes,0XML-only,2SR-only tại A0003; hai SOP/bounds cụ thể trong comparison report. Giữ cả77production SR boxes và75reference XML boxes. Diff ledger cần source digests, case/record keys, raw values, finding codes, difference kind và adjudication status. Future version thay đổi source hoặc policy tạo namespace mới, không overwrite existing conversions. Nguyên nhân A0003 còn OPEN; không chọn nguồn để ép match.

## 5. Class label review

Giữ exact strings/casing A/a/B/b/E/G/g/Q/A0192 và raw SR coding scheme/value/meaning. Observed associations A/B/E/G trên sample không đủ để normalize full corpus hoặc infer diagnosis từ folder. Review matrix cần source label→proposed coded concept, supporting evidence, unresolved exceptions, reviewer/date và version. Class label chưa hiểu vẫn có source record; không chuyển thành background hoặc tự loại. XML `verified=yes/no` không tự trở thành expert approval.

## 6. Explicit coordinate policy

SR production giữ DICOM SCOORD pixel-edge column/row, center=i+.5 và current rasterizer/native geometry policy. XML raw numbers giữ nguyên; **XML convention UNSPECIFIED/REVIEW_REQUIRED**. Chỉ bật XML rasterization sau bằng chứng về origin/inclusive endpoints, width/height semantics, SOP/image orientation và off-by-one edge tests. Không mặc định VOC zero/one-based hoặc suy ra từ75matching bounds. `size.depth=1/3` không được tự diễn giải thành số CT slices.

Future approved policy phải có version, evidence/reviewer, mathematical mapping và tests cho boundary/single-pixel/multiple-box/oblique cases, rồi revalidate vào output mới nếu ảnh hưởng production. Thiết kế này không implement XML production preprocessing hoặc đổi converter fingerprints.

## 7. Coverage và canonical representation trước training

Canonical **production source representation** hiện được người dùng chốt là SR; XML là immutable comparison reference. Đây chưa là canonical **training supervision policy** đã cleared. Trước training phải có quyết định versioned về source precedence, A0003/multiplicity/class conflicts, XML coordinate policy khi sử dụng XML, exhaustive annotation evidence, positive/missing/negative semantics và sample/full review coverage.

345missing/unknown sample slices giữ unknown; outside bbox không mặc định background, bbox không segmentation GT, không interpolate pseudo masks. Expert/anatomy approval và training eligibility là gates riêng, không suy ra từ completion receipts/CRC/tests. Chỉ mở clearance khi reviewer quyết định rõ unresolved findings được xử lý hoặc tiếp tục giữ như thế nào; không auto-set weak_eligible=true. Scarce/Vast và3dataset protocol giữ nguyên.

## Checklist addendum và phần còn thiếu

| Yêu cầu addendum | Thiết kế/bằng chứng | Trạng thái |
|---|---|---|
|SR production, XML immutable reference|Quyết định representation + content-addressed archive receipt|DESIGN_UPDATED|
|Storage/provenance bao gồm XML|Measured ZIP bytes cộng đúng một lần; paths portable; integrity/restore receipt|DESIGN_UPDATED; persistence chưa chạy|
|7readiness items|Các mục1–7, ledgers/gates và observed findings|DESIGN_UPDATED; full reconciliation chưa chạy|
|Access status|RESOLVED; equivalence REVIEW_REQUIRED; historical logs không sửa|PASS cập nhật tài liệu|
|Review P1.3.1 không mở lại|Không sửa production code/config/data/fingerprints|PASS phạm vi addendum|
|Prompt P1-R.1 gốc và acceptance criteria|Người dùng đã gửi lại; assessment/pilot/restore status được báo riêng|Scope đã xác nhận; xem resource_feasibility_report.md|

Chưa download full corpus, provision resources, cleanup, split, production preprocessing hoặc research training. Full-corpus scheduler/merge/reconciliation components là thiết kế; pilot receipts/checks chỉ kiểm bounded samples. Dừng sau P1-R.1 để review, không tự chuyển P1-R.2.
