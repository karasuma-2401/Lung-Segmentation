# P1-R.1 — Resource feasibility & cloud pilot

Khảo sát bắt đầu24/11/2026, cập nhật review25/11/2026; reviewed production revision `dc6e179087737621b69d538ef200436c644a7687`. **P1-R.1 DELIVERED_FOR_REVIEW_WITH_OPEN_ITEMS. Kaggle bounded CPU native2sample pilot và cross-session result restore27artifacts PASS theo user-run evidence/user attestation.** P1.3.1 và XML investigation giữ nghiệm thu. Full NSCLC/weak corpus vẫn BLOCKED_STORAGE. Exact pilot input/result Private destinations đã duyệt/upload/read-back; không costs/provisioning/full download hoặc training. R2 real pilot chưa chạy, account quota/privacy/version chưa independently verified.

**Architecture decision update:** chọn [Hybrid B](hybrid_storage_architecture.md): Kaggle CPU/GPU, Private Datasets primary180GBtarget, R2 Standard checkpoints/overflow8GBtarget/10GBappcap, boto3. Budget ưu tiên0VND, dự phòng mục tiêu50,000VND không là quyền chi. Những options/cloud costs khảo sát trước quyết định bên dưới giữ làm context, không tiếp tục khảo sát sâu hoặc đề xuất provider khác. R2 synthetic kit READY_FOR_USER_EXECUTION, real R2 NOT_RUN; full optimized plan chưa chứng minh vừa188GBtarget.

**User-run resource follow-up:** [screenshot transcription](evidence/p1_r_1/kaggle_user_probe.json) ghi4logical CPUs, OS-visible31.35GiBtotal/30.13GiBavailable; cgroup limit32,212,254,720bytes=30GiB và current823,054,336bytes, conservative cgroup headroom≈29.23GiB tại snapshot. Working free19.5GiB; IDC/TCIA200 với729/1,024bytes reads. Probe chạy bởi người dùng, chưa có exact measurement timestamp hoặc conversion metrics; đây là resource/connectivity evidence, không cloud conversion/restore PASS. Small pilot resources đủ theo estimate; Kaggle total private quota/version usage vẫn chưa xác minh.

**User-run Linux setup follow-up:** [log02c](evidence/p1_r_1/kaggle_setup_user_success.json) tại2026-11-24T10:39:18Z xác nhận pinned production revision/source hashes, isolated venv, data imports và pip check PASS trên Linux/Python3.13.18. Runtime fingerprints khác local3.13.15 được giữ riêng; không reuse cache. Startup warning sitecustomize/missingwrapt còn OPEN, root cause chưa điều tra. Native2case conversion đã PASS theo update phầnC; cảnh báo chưa được chứng minh đã biến mất.

## A — Resources thực đo

[Local assessment](evidence/p1_r_1/local_assessment.json) đo bằng runtime/OS và filesystem stat; không suy từ installed RAM hoặc gzip ratios. CPU count là logical processors.

| Resource | Measured local snapshot |
|---|---:|
|RAM total /available|8,215,101,440 /926,130,176bytes|
|Disk total /free|500,865,953,792 /52,062,769,152bytes|
|CPU /Python|8logical processors /3.13.15, Windows|
|Official source probes|IDC HTTP200/729bytes, TCIA HTTP200/1,024bytes; local connectivity only|
|Kaggle account quota/runtime|NOT_VERIFIED; không có actual Kaggle session evidence|

| Tree | Files | Measured bytes |
|---|---:|---:|
|MSD raw NIfTI +metadata|160|9,163,406,616|
|MSD archive directory|2|9,163,697,007|
|NSCLC raw sample|1,131|593,390,653|
|NSCLC current converted7pairs|21|269,534,384|
|NSCLC previous converted baseline|21|269,526,838|
|Weak raw sample|450|221,968,468|
|Weak current converted10pairs|50|166,887,982|
|Weak prior final /interrupted versions|50 /30|166,879,618 /97,035,420|
|Original XML ZIP|1|17,304,054; SHA256 pin/CRC trong accepted XML evidence|

MSD không có converted root riêng: inventory đọc native NIfTI. Native data/QA/metadata cũ giữ nguyên; measurements trên không cộng pilot copy vào dataset counts. Original XML access RESOLVED; full equivalence REVIEW_REQUIRED, không là source-access blocker nữa. Probes thành công không chứng minh Internet của Kaggle, full payload availability, archive authenticity hoặc permission upload.

## Published limits và actual account limits

Đã tra cứu official sources ngày24/11/2026:

| Published/documented | Actual account/runtime |
|---|---|
|[Kaggle Notebooks](https://www.kaggle.com/docs/notebooks): CPU4cores/30GB RAM,12h CPU/GPU session;20GB saved working output; scratch ngoài working không persist|Chưa đo account/session; kit đo lại OS RAM/disk/CPU trước conversion, CPU accelerator None|
|[Kaggle Datasets](https://www.kaggle.com/docs/datasets):200GB/dataset,200GB tổng private datasets, tối đa50top-level files; archive uploads được unpack|Used/remaining quota, visibility, collaborators, version accounting, file limits và restore chưa verified|
|[GPU tips](https://www.kaggle.com/page/GPU-tips-and-tricks):30h/week và9h session; khác12h trên notebook docs|Không coi một con số là quota bảo đảm; kiểm UI quota/runtime thực. Pilot không dùng GPU|
|Kaggle saved output có thể được add input trong notebook khác; Save & Run All là separate execution session theo docs|Chưa có read-back/session restore thực; notebook được tạo hoặc filename xuất hiện chưa là persistence PASS|

Các limits là published reference, không phải tài nguyên đã cấp cho nhóm. GPU models/availability, concurrency, internet toggle/verification và remaining account quota cần người dùng xác nhận. Không lấy docs/spec cũ làm benchmark.

## B — Capacity cho cả ba nguồn

Budget là **conservative design**, không phải measured full-corpus converted bytes:

| Dataset | Budget đã cập nhật |
|---|---:|
|MSD raw +archive đang giữ|18,327,103,623bytes|
|NSCLC CT+RT +2.5×CT allowance +4GiB reserve|99,214,789,971bytes|
|Weak CT+SR+XML +2.5×CT allowance +4GiB reserve|436,053,238,232bytes|
|Combined known planning|**553,595,131,826bytes≈553.60GB**|

Không đủ trên local≈52GBfree hoặc Kaggle200GB private quota theo current conservative design. Không suy ra không thể có optimized plan dưới quota: raw-only one-copy theoretical floor≈160.11GB (một MSD tar, NSCLC CT+RT, weak CT+SR, XML) nhưng cần policy/restore/metadata và không chứa derived outputs, redundancy hoặc future preprocessing. Floor không là pipeline đã feasible, không cho phép xóa local duplicates.

Capacity reference **0.75–1TiB** cho monolithic conservative plan không còn là proposed deployment của kiến trúc B; target được duyệt180GBKaggle+8GBR2 vẫn cần optimized lifecycle proof. Budget checkpoints/preprocessing/version riêng. Scratch NSCLC10GiB, ZIP fallback12GiB từ plan cũ; XML metadata allowance128MiB. Pilot cần8GiBfree, estimated RAM `max(1GiB,12×max_reference_voxels+768MiB)`, một CPU worker tuần tự; cần measured cloud RSS để calibrate. Không production resampling.

Future preprocessing chưa có resolved shape/spacing/crop policy nên chưa có exact budget. Formula theo voxel counts: CTfloat32 +one uint8 target tối thiểu5Nbytes trước compression, staging/worker/augmentation. Ví dụ512²×300 là393,216,000bytes; resampling tăngN không thể lấy ratio sample để bảo đảm. Giới hạn riêng cache versions/checkpoints; không giả định1TiB đủ mọi research run.

## Các phương án

| Option | Vai trò khả thi | Storage/persistence | Trạng thái |
|---|---|---|---|
|Local CPU hiện tại|Code/tests/metadata và bounded pilot khi đủ free RAM|≈52GBfree, không full corpus|Measured; pilot RAM guard chặn|
|Kaggle CPU|Bounded2sample native conversion PASS; future batches/GPU cần profiling riêng|Published20GB saved output/200GBprivate; không chứa current553.60GBplan|CPU pilot PASS theo user evidence; account quota/restore chưa verified|
|Colab CPU +approved persistent destination|Compute thay thế nếu runtime phù hợp|Không tự thay thế archive; [official FAQ](https://research.google.com/colaboratory/faq.html) nói limits/hardware động, free session tối đa12h tùy availability|Chưa account/pilot/restore; không guarantee free resources|
|Private persistent object storage +CPU worker/Kaggle|Tách archive khỏi compute scratch, content-addressed shards/receipts|Quota/cost/permissions/read-back/restore cần kiểm thật|DESIGN_ONLY; chưa provision/upload|
|Ổ ngoài/NAS được duyệt|Persistent source/derived archive; có thể restore local batches|Cần capacity/backup/IO/chi phí thực|Người dùng hiện không có ổ khác; chưa khả dụng|

### Chi phí paid cloud — estimate, không phát sinh chi phí

[Google Cloud Storage pricing](https://cloud.google.com/storage/pricing) tại default Iowa/us-central1 hiển thị Standard `$0.000027397/GiB-hour`. Scenario730h:768GiB≈**$15.36/tháng**,1,024GiB≈**$20.48/tháng**, chỉ storage. Đây là phép tính từ published rate, không quote account/region cuối và không giả free credits. Cộng operations, network/egress/read-back, compute, extra versions/soft-deleted objects, thuế/FX và retention. Source cùng trang liệt kê Standard ClassA$0.005/1,000, ClassB$0.0004/1,000 cho flat regional namespace; actual request pattern chưa đo. Chưa có VM SKU/region/runtime được chọn nên compute/total TCO UNVERIFIED; công thức `storage_GiB×hours×rate + CPU_hours×SKU_rate +requests+egress+backup`. Không tạo billing account/bucket hoặc paid instance.

## C — Pilot đã chuẩn bị và phần thực sự chạy

[Python pilot](../scripts/cloud_pilot.py), [Linux bootstrap](../scripts/bootstrap_cloud_pilot.sh), [guide](cloud_pilot_guide.md). Bootstrap clone/fetch/detach exact reviewed SHA, isolate Linux venv và freeze dependencies; không áp Windows CPU lock. Python kit pin source hashes, verify externally pinned receipt, compare native CT/mask/bbox arrays/geometry, annotation/coverage/provenance và report per-worker peakRSS/time/bytes. Không reuse local-runtime cache trong Linux; full runtime fingerprints khác phải fresh output, source implementation vẫn phải khớp.

Đã tạo bundle160,929,353bytes payload,176source/reference files +spec/receipt, gồm NSCLC LUNG1-001 và weak Lung_Dx-A0003, local references và XML ZIP. Receipt SHA256 `c97683893715b34fbb7cdf7193134220625169021acb39aae00f6243ce9c4f6f`. [Preparation evidence](evidence/p1_r_1/preparation.txt) là snapshot local trước upload. User đã duyệt/upload transfer161,341,440bytes vào exact Private Dataset và verify hashes177files trên Kaggle; original ZIP/input được bảo toàn theo kit checks.

Actual [local pilot attempt](evidence/p1_r_1/local_pilot.json): **BLOCKED_LOCAL_RAM_OR_DISK do RAM**, available731,955,200bytes, yêu cầu1,226,833,920bytes; free disk51,900,919,808bytes đủ8GiBguard. Không local conversion worker nào chạy; cloud measurements bên dưới là user execution mới, không thay hoặc che blocker local. Preflight giữ trong ignored output; không giảm guard hoặc đóng app người dùng để ép chạy.

**Actual Kaggle CPU conversion:** [user summary](evidence/p1_r_1/kaggle_native_user_summary.json), [review](evidence/p1_r_1/kaggle_native_review.json) cho bounded PASS,1case/source,0quarantine. Agent đã so cả4reported voxel hashes/geometry signatures với pinned local spec; đều khớp. Agent chưa trực tiếp fetch cloud artifact bytes. Weak boxes/coverage và selected source/annotation provenance equality lấy từ kit output; NSCLC mask equality là NIfTI comparison, không diễn giải boolean default annotation-record field thành independent RTSTRUCT record audit.

|Sample|Shape /spacing mm|Worker wall seconds|Peak RSS bytes (MiB)|Raw input bytes|Reference bytes|Output bytes trước metrics|
|---|---|---:|---:|---:|---:|---:|
|NSCLC LUNG1-001|512×512×134 /0.9765625,0.9765625,3|9.635|358,244,352 (341.65)|72,071,380|45,444,759|45,506,541|
|Weak Lung_Dx-A0003|512×512×27 /0.62109375,0.62109375,10|2.171|191,258,624 (182.40)|14,257,379|11,851,781|11,896,103|

Tổng11.807s là thời gian2conversion workers, không end-to-end setup/compare/hash/network. PeakRSS là per-worker high-water mark, không total notebook/cgroup peak hoặc full-corpus bound. Output57,402,644bytes trước metrics không là exact persistent size gồm receipts/logs; cell04 sẽ đo toàn gói. Runtime4CPUs/Python3.13.18; preflight OS RAM32,245,391,360available bytes và disk20,492,337,152free bytes. Đây là OS-visible RAM snapshot, không cgroup headroom mới. IDC200/729bytes và TCIA200/1,024bytes chỉ là bounded connectivity probes, không full download throughput.

Result receipt `8da1ebd95caac4551160cfcdfc9e8e749fec7f82d13a3bb6f1a836d6c670687a`,27artifacts verified theo user-run output. Native arrays/affines/spacing/qform/sform/dtypes và selected provenance giữ nguyên; runtime fingerprints mới được version riêng. Account limits/full corpus chưa verified. XML reference và A0003SR4boxes/2positive slices giữ, không inference XML semantics hoặc expert/training approval.

## D — Persistence/restore

**PASS_BOUNDED_RESTORE_WITH_USER_ATTESTATION** — [user output và review](evidence/p1_r_1/kaggle_session2_restore_user_verified.json). User đã duyệt/upload result vào “SE374 LungSeg Pilot Result v1”, Private/personal owner-only theo [approval](evidence/p1_r_1/kaggle_result_destination_approval.json). Cell04 actual transfer57,477,120bytes, payload57,421,134bytes/28members, outer SHA256 `a7285babe7d1c0fa5a24fef48f064b2fc558113ba75aa1b2e948d493c1b4f3dc`; cell05 mounted read-back khớp. Chỉ exact result được upload, không toàn workingdir. [Packaging receipt](evidence/p1_r_1/kaggle_result_package_user_verified.json), [upload receipt](evidence/p1_r_1/kaggle_result_upload_user_verified.json).

Original notebook `notebook1923ef4210`; user cung cấp notebook mới `notebooka1b5088c00`, setup25/11trong namespace mới với source/packages và2runtime fingerprints khớp producer ([setup evidence](evidence/p1_r_1/kaggle_session2_setup_user_verified.json)). Cell06 xác nhận old work absent, actual Kaggle runtime, fresh-session attestation=true và previous session ID `a0492d9112114e029f3c1590599b0d5a`. Restored result receipt giữ đúng trusted digest `8da1ebd95caac4551160cfcdfc9e8e749fec7f82d13a3bb6f1a836d6c670687a`;27artifact bytes/hashes,4decoded NIfTI arrays/geometry và annotation/provenance hashes đều verified. Original input bundle read-back cũng verified, bao gồm immutable XML ZIP.

Đây là user-run content/lifecycle attestation evidence với notebook URL đã cung cấp; agent không independently quan sát host shutdown hoặc đọc account. Không suy actual quota/private collaborators/version accounting từ restore. Cảnh báo sitecustomize thiếuwrapt vẫn xuất hiện nhưng restore thành công; root cause OPEN, không suppression/global package changes. Không expert/training clearance, không chứng minh full-corpus durability/capacity, không cleanup raw/baselines/failed stages. Không dùng cùng-session visibility hoặc synthetic tests để thay evidence này.

## E — Full-corpus readiness

[Execution plan](full_corpus_execution_plan.md) bổ sung all expected CT/SR/RT entities, multiple-SR ambiguity/missing expected SR, memory admission, batch gates, merge/dedup/resume và read-back. [XML design](xml_full_corpus_readiness.md) bao gồm7items của addendum. Đây là design, không full scheduler. Không chỉ chọn một SR/patient trong full-corpus mode. SR production hiện tại không thay đổi; training clearance vẫnfalse/345unknown vẫnunknown.

## Acceptance và next review

| Tiêu chí | Trạng thái |
|---|---|
|Measured vs published vs account vs assumptions|PASS assessment, account NOT_VERIFIED|
|Capacity3datasets +XML immutable source|PASS design/measured local; full storage BLOCKED|
|Storage duplication plan không giảm scope|PASS design; chưa cleanup|
|Reproducible pilot kit|PASS bounded Linux CPU execution trên2sample +user-attested new-notebook restore|
|Actual execution evidence|PASS user-run2case conversion/array comparison, resource metrics và pinned result receipt; agent đối chiếu reported signatures với local reference|
|Persistence/session2 restore|PASS_BOUNDED_RESTORE_WITH_USER_ATTESTATION —27artifact hashes, arrays/geometry/annotation-provenance +input read-back; independent host/account inspection chưa có|
|Hybrid B /R2 pricing, synthetic SDK kit, routing/guard|DESIGN/PREPARATION updated; real R2 credentials/upload/retry/throughput/session2 NOT_RUN|
|No unauthorized cost/upload/provision/full download|PASS phạm vi thực hiện|
|Regression P0–P1.3.1|PASS **263tests =217prior+13native-pilot+14R2 fake-transport+1setup-recovery integration+8restart staging+3result transfer+7restore guards**, CPU smoke/env/pip check pass; [latest logs](evidence/p1_r_1/verification_restore_cell/verification.json), không thay production converter/config/protocol|

Files mới/chính: resource/storage/cloud guide, XML readiness và hybrid architecture reports; cloud CPU/bootstrap +R2 synthetic scripts, hybrid budget JSON, optional R2 requirements và synthetic tests; cập nhật full plan/progress/decisions/README/current XML status docs. [Kit manifest](evidence/p1_r_1/kit_manifest.json) pin exact code/metadata hashes; [final audit](evidence/p1_r_1/final_audit.json) verify176copied source/reference/XML originals160,929,353bytes unchanged và frozen fingerprints. `src/lungseg` và protocol/converter configs giữ nguyên. Historical timeout/comparison logs không chỉnh; reports mới dùng relative/logical paths.

[Closing review](evidence/p1_r_1/closing_review.json) kiểm106changed/untracked Git candidates, parse43JSON; không thay protected production code/config/protocol, không raw medical containers/model artifacts hoặc strong credential-signature matches trong tập kiểm. Sole user-directory pattern là synthetic traversal test fixture, không actual user path. Pattern scan không bảo đảm phát hiện mọi secret. `git diff --check` PASS; latest executed fullsuite263/CPU smoke/env/pip check vẫn ở linked logs, không rerun cho documentation-only closure. Chưa stage/commit/push, không thêm cloud writes/cleanup.

**Dừng để review P1-R.1.** Bounded Kaggle conversion/restore đã có evidence; không cần rerun chỉ để commit. Snapshot code/config/tests/docs/metadata có thể commit khi user yêu cầu; raw medical data/transfer containers/credentials giữ ngoàiGit. Các OPEN còn lại: actual Kaggle quota/privacy/version accounting, full target188GB feasibility, real R2 synthetic roundtrip/retry/throughput/session2 và sitecustomize warning. R2 kit READY_FOR_USER_EXECUTION với existing approved Standard bucket, Secrets và zero-cost headroom prerequisites, actual remote work NOT_RUN; không bắt buộc giả PASS để bàn giao P1-R.1. Đề xuất **P1-R.2 sau review riêng**: đo thêm bounded case/codec sizes và giải quyết measured retention/capacity/account blockers, thực thi R2 synthetic khi đủ quyền/setup; không full acquisition, T07/T08 hoặc training ở lượt này.
