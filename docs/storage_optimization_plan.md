# P1-R.1 — Storage optimization plan

**DESIGN_ONLY, không cleanup.** Giữ MSD-Lung, NSCLC-Radiomics và Lung-PET-CT-Dx, current annotation/Scarce–Vast policy. [Assessment](resource_feasibility_report.md) phân biệt measured bytes và estimates; không downsample/cắt bớt ca/cast CT hoặc xóa expert annotation để giảm footprint.

**Kiến trúc B đã chọn:** [hybrid_storage_architecture.md](hybrid_storage_architecture.md) chốt Kaggle primary180GBtarget, R2 Standard8GBtarget/10GBappcap cho checkpoints/approved overflow,0VNDưu tiên/50,000VNDcontingency chưa authorize spend. Feasibility188GBtarget chưa verified; conservative/reference capacities bên dưới giữ làm evidence của gap, không tự tăng paid storage hoặc chọn provider khác.

Bounded evidence cập nhật25/11:2case Kaggle CPU conversion và27artifact cross-session result restore PASS theo [user-run evidence/attestation](evidence/p1_r_1/kaggle_session2_restore_user_verified.json). Exact opaque transfer57,477,120bytes bảo toàn result receipt/hashes/arrays/provenance. Đây là evidence cho small transfer/restore, không chứng minh compression/full-corpus capacity, actual version quota hoặc cho phép cleanup. Raw sources/baselines/XML/failed stages giữ nguyên.

## Capacity baseline

Known conservative design553,595,131,826bytes≈553.60GB, XML ZIP17,304,054bytes tính một lần. Raw-source one-copy theoretical floor≈160.11GB nếu chỉ giữ một MSD tar; không gồm derived/QA/metadata/backup/versions. Current raw/baselines giữ nguyên. Floor không chứng minh primary180GB đủ; R2ưu tiên checkpoint nên không assume cả8GBđều overflow cho data. Capacity reference0.75–1TiB của monolithic plan chỉ thể hiện gap; B cần measured compression/shards/version/retention/rehydration design và approval để có thể feasible trong targets.

## Các tối ưu đề xuất

| Option | Lợi ích / đánh đổi | Gate trước áp dụng |
|---|---|---|
|Compressed native CT/mask/bbox|Current NIfTI đã dùng gzip; giảm allowance bằng measured per-case quantiles/full pilot thay vì2.5× nếu có bằng chứng|Exact voxel/dtype/affine/units/SOP/record parity; không quantize hoặc đổi float32 silently|
|Immutable source reuse|CT DICOM/RT/SR và ZIP XML chỉ persist một lần theo content digest; multiple batches/config versions tham chiếu lại|Digest+bytes verification, source DOI/license/release, backup/restore receipts|
|Versioned artifact lifecycle|Logical namespace giữ config/implementation/provenance; physically identical output bytes có thể content-dedup|Không bỏ cache identity check chỉ vì arrays giống. Full source/config/runtime hashes vẫn riêng; old baselines protected|
|Batch temporary storage|Một CPU worker, bounded source/staging/output; không giữ cả corpus trên scratch|Actual listing/header/decoded-size memory admission; persist/read-back/restore trước cleanup được duyệt|
|Shards|Immutable small shards≤1GiB source hoặc bounded pilot≤2GiB, stable member inventories; giảm nhiều top-level files|No experiment splits; preserve source byte hashes và per-member identities; cross-shard merge/dedup/conflict ledger|
|MSD archive vs extracted copies|Future worker có thể extract batch từ immutable tar, tránh permanent duplicate extracted corpus|Không xóa bản hiện tại; audit đủ95CT/63GT, archive read-back và restore entire selected batch; patient mapping vẫn OPEN|
|Official source recovery|Có thể không giữ extra transfer archive nếu raw objects đã persist/restore và policy chấp thuận|Official URL/version/UID/hash/license pinned; prove reacquisition exact digest. Network access có thể mất, không dùng source availability như backup guarantee|
|Avoid redundant dataset versions|Publish immutable receipts chỉ khi source/algorithm thay đổi; identical byte objects reuse dưới versioned provenance|Account/platform version accounting phải đo; không assume deletion/overwrite frees quota ngay|

Observed current native outputs NSCLC269.53MB/7pairs và weak166.89MB/10pairs chỉ là sample; raw denominators còn quarantine/metadata và case selection bias. Không ngoại suy compression ratio thành full-corpus guarantee hoặc tuyên bố raw+derived đủ200GB. Future pilot cần source/output bytes per-case, Nvoxels, p50/p95/max ratio và decode time/peak RSS theo transfer syntax.

Kaggle Datasets [unpacks uploaded archives](https://www.kaggle.com/docs/datasets): không giả định upload ZIP sẽ giữ immutable ZIP bytes hoặc giảm quota. XML original ZIP cần được giữ như opaque file trong approved storage có thể read-back byte-for-byte; nếu platform unpack, cần outer container/opaque representation được kiểm rồi restore original ZIP SHA256. Không đổi extension rồi mặc định policy/platform đảm bảo. Không publish medical data để lách private quota.

## Layout và lifecycle

Thiết kế logical keys: `sources/<dataset>/<release>/<sha256>/...`, `derived/<dataset>/<source_digest>/<implementation>/<config>/...`, `batches/<batch_id>/receipts/...`. Archive XML digest pinned trong XML readiness doc; all conversions tham chiếu cùng receipt. Không chép local absolute user directory vào reports; private runtime mapping nối logical key với mount.

State machine: SOURCE_VERIFIED →CONVERTED_OR_QUARANTINED →QA_RECORDED →PERSISTED_READBACK_VERIFIED →NEW_SESSION_RESTORE_VERIFIED →BATCH_COMMITTED →CLEANUP_ELIGIBLE. Technical status và expert/training clearance tách biệt; persisted quarantine vẫn quarantine.

Không cleaner được hiện thực/chạy. Proposal cleanup phải có exact owned scratch paths, dry-run files/bytes/hashes, immutable remote generations/receipts, read-back full bytes, **session2 restore** gồm arrays/geometry/annotation/provenance, retained independent source/backup và user approval. Refuse roots/junction escapes/unowned paths; failed stages/conflicts/annotations chưa persist không tự dọn. Baseline MSD/NSCLC/weak và XML original đã tải được bảo vệ.

Nếu quota/RAM/Internet/restore chưa pass: dừng nhận batch mới và giữ blocker, không giảm dataset/case count hoặc silently discard old versions. Những thay đổi source representation/preprocessing/cache identity phải review riêng, version output mới. Budget future transformed arrays và checkpoints tính thêm từ resolved voxel shapes/update plan; phase này chưa implement T08/training.
