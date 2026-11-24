# P1-R.1 — Kaggle CPU pilot và session restore guide

**Kaggle native CPU pilot2sample và cross-session restore27artifacts PASS theo user-run evidence/attestation.** [Latest restore review](evidence/p1_r_1/kaggle_session2_restore_user_verified.json). Source/packages/runtime identities, hashes, arrays/geometry và annotation/provenance đã kiểm; account quota/privacy/version và independent host lifecycle chưa inspected. Các hướng dẫn/milestone bên dưới giữ để tái chạy, không yêu cầu chạy thêm ở latest handoff. Local RAM blocker giữ lịch sử; không GPU, full download, paid provisioning, automatic upload hoặc cleanup. Cả3datasets vẫn trong scope; conversion pilot chỉ1NSCLC+1weak, MSD inventory đã có. Dừng P1-R.1 để review.

Kiến trúc được chốt [Hybrid B](hybrid_storage_architecture.md): Kaggle Private Datasets primary target180GB, R2 Standard checkpoints/approved overflow8GBtarget/10GBappcap. Native kit/steps đã chuẩn bị vẫn giữ; synthetic R2 pilot/Secrets/2session instructions trong hybrid report, không thay native array/geometry restore bằng synthetic checksum. Không upload medical data hoặc tạo paid resources tự động.

## 1. Review và phê duyệt transfer trước khi upload

Current status: exact Private input đã được user upload và verify, result destination cũng đã duyệt. Phần chuẩn bị transfer ban đầu bên dưới giữ lịch sử; current persistence handoff ở phần4, không cần upload lại input.

**Current approval:** người dùng đã duyệt transfer161,341,440bytes vào “SE374 LungSeg Pilot Input v1”, Private, owner-only, trong tài khoản cá nhân Kaggle đang dùng. [Approval receipt](evidence/p1_r_1/kaggle_destination_approval.json). Upload chưa thực hiện vì browser/native automation host unavailable; user upload trực tiếp một lần. Không xin lại cùng quyền, không đổi đích/visibility/collaborators hoặc mở rộng sang full corpus/R2. Chọn license “Other (specified in description)” và giữ per-source attribution bằng [mô tả sẵn](evidence/p1_r_1/kaggle_dataset_description.txt), theo [Kaggle dataset docs](https://www.kaggle.com/docs/datasets); không blanket CC0/CC BY4.0 cho mixed bundle.

Đã chuẩn bị optional local transfer `data/cache/cloud_pilot/se374-pilot-transfer-v1.bin`:161,341,440bytes, SHA256`f70a2120cb28ce2712e86953669838115c41b658a374ed749645585e6e6454b9`. Đây là uncompressed tar đặt đuôi`.bin`, chứa `pilot_input/` và `code/` cùng pinned kit manifest,184regular members được kiểm hash. Mục tiêu hạn chế platform tự unpack nested XML ZIP; **chưa verify cách Kaggle xử lý file**. Sau upload phải verify outer SHA trước controlled extraction vào fresh notebook cache, rồi verify INPUT_ROOT/code digests; không đổi đuôi thành`.zip` hoặc sửa receipt để bỏ lỗi. [Transfer receipt](evidence/p1_r_1/kaggle_transfer.json) là snapshot lúc chuẩn bị trước approval; current approval ở đoạn trên, upload vẫn chưa thực hiện.

Local-only input ở ignored `data/cache/cloud_pilot/input_p1_r_1/`, payload160,929,353bytes,176source/reference files +spec/receipt. Default NSCLC LUNG1-001, weak Lung_Dx-A0003; gồm raw source markers/DICOM, accepted converted references/provenance và original XML ZIP. XML reference bất biến; SR production giữ77box policy, pilot A0003giữ4SR boxes/2positive slices.

**Chỉ exact pilot transfer đã duyệt ở trên được phép upload.** Medical datasets khác/target khác vẫn cần review destination/account, visibility/collaborators/license và remaining quota. NSCLC giữ CC BY-NC3.0; weak CT/XML/SR CC BY4.0. Không publish public để lấy quota hoặc ghi token vào notebook/Git. Approval không là bằng chứng account quota/persistence đã pass.

Kaggle có thể unpack archives: việc platform giữ nguyên XML ZIP bytes phải được kiểm. Giữ folder structure đúng receipt; nếu source archive bị unpack hoặc thêm/xóa files trong bundle, input verify sẽ fail. Cách transfer/outer container cần review riêng; không thay pinned receipt để bỏ qua corruption. Không tạo Kaggle account trong task này.

## 2. Input/kit pins và reproducibility

**Current input status:** người dùng đã upload approved Private Dataset, outer SHA và extraction177files PASS trong Kaggle screenshots; [transfer](evidence/p1_r_1/kaggle_transfer_user_verified.json), [extraction](evidence/p1_r_1/kaggle_unpack_user_verified.json). Cell01 giữ làm lịch sử; khi cache cũ không còn, dùng cell02c ở phần3 để verify/extract lại từ mounted Dataset vào namespace mới. Không cần upload lại hoặc chạy lại cell01 vào cùng stage. Bước verify/extraction chưa phải conversion/restore. Original preparation receipts “upload=false” là lịch sử trước upload.

Input receipt `INPUT_ROOT.json` SHA256:

`c97683893715b34fbb7cdf7193134220625169021acb39aae00f6243ce9c4f6f`

Receipt chứa full relative file list, bytes/SHA256; spec gồm selected IDs, approved configuration, source/runtime implementation identities, local native-array signatures, source licenses và XML digest. Compare expected digest với giá trị tin cậy ở trên, không chỉ tự tính SHA của receipt vừa tải rồi tin nó. New selections/config cần **bundle mới**, không sửa bundle đã pin.

Code kit: reviewed `scripts/cloud_pilot.py` và `scripts/bootstrap_cloud_pilot.sh` của working tree P1-R.1, chưa commit/push. Clone revision `dc6e179087737621b69d538ef200436c644a7687` pin **production source**; revision đó chưa chứa pilot scripts mới. Copy riêng reviewed code kit vào notebook qua cơ chế code-only được chấp thuận hoặc paste bootstrap trong cell; không giả định clone cũ có scripts mới. Pin/check kit SHA256 từ [kit manifest](evidence/p1_r_1/kit_manifest.json) trước thực thi.

Nếu revision chưa fetch được từ remote/private repository, dừng và ghi BLOCKED_SOURCE_CODE; không chạy branch HEAD khác. Người dùng có thể cung cấp reviewed offline Git bundle có exact commit sau duyệt code transfer. Không nhúng credentials vào URL.

## 3. Session1 — CPU setup

**Current handoff — setup đã pass:** [log người dùng](evidence/p1_r_1/kaggle_setup_user_success.json) cho Linux/Python3.13.18, target imports/pip check/source hashes PASS. Trong cùng session, copy toàn bộ [cell03 native conversion](evidence/p1_r_1/notebook_cells/03_run_native_pilot.py) vào Python Code cell mới, chạy riêng cell đó một lần. Không Run All cell setup cũ và chưa kết thúc session. Cell03 đọc `PILOT_CONTEXT` do02c tạo (fallback đúngcontext trong log), verify lại sealed kit/input, rồi gọi existing native pilot với1NSCLC+1weak, output/log mới. Giữ Accelerator **None** và Internet bật. Chưa upload output hoặc thực hiện persistence bước này.

Khi hoàn tất, gửi từ marker `NATIVE_PILOT_RESULT_SUMMARY` đến cuối output để review: arrays/geometry, annotation records/coverage/provenance, peak RSS/time/bytes, source connectivity và result receipt SHA256. Cell hiển thị retained failure/worker logs nếu fail; không xóa artifacts hoặc đổi policy để pass. Native conversion và session restore vẫn NOT_RUN cho tới khi có log thật.

Cell03 đã syntax-check, kiểm context guards với synthetic Linux report và verify actual177inputfiles trên local Windows ([check](evidence/p1_r_1/notebook_cells/local_native_cell_check.json)). Full suite chạy lại **253passed**, CPU smoke/env/pip check PASS ([latest logs](evidence/p1_r_1/verification_native_cell/verification.json)). Không coi local adapter checks là Kaggle conversion PASS.

Setup có cảnh báo `sitecustomize` thiếu `wrapt` nhưng install/check/freeze/import probes exit0; chưa điều tra root cause, không khẳng định đã sửa. Giữ warning trong native logs, không cần tự cài wrapt hoặc sửa notebook base trước khi đo conversion. Runtime fingerprints khác local vì Python3.13.18 so với3.13.15; source hashes khớp. Native output mới giữ identity cloud, so decoded arrays/geometry/annotations với local reference, không reuse cache Windows.

**Setup reference khi session cache mất:** chạy riêng [cell02c standalone](evidence/p1_r_1/notebook_cells/02c_setup_from_attached_dataset.py) trong **Python Code cell mới**, không Run All các cell setup02/02b cũ. Giữ approved Private Dataset attached, Accelerator **None**, Internet bật. Cell không cần biến hoặc cache của các cell trước: tìm đúng mounted transfer, kiểm outer hash/safe members/code/input receipt, tạo stage/work mới theo run ID, clone/fetch/detach đúng reviewed SHA và kiểm production source hashes. Sau đó tạo target bằng `venv --without-pip`, dùng **parent pip>=22.3 `--python` target** cài pip +4data dependencies chỉ vào target; không sửa notebook base. Đây là [pip workflow chính thức](https://pip.pypa.io/en/stable/topics/python-option/).

Cell giữ `setup.log`/freeze, kiểm isolated prefix/imports/source/runtime fingerprints và verify input lần nữa trước khi in `LINUX_ENVIRONMENT_READY_NO_CONVERSION` cùng `PILOT_CONTEXT: .../runtime_context.json`. File context mới chứa Python/kit/input/repo của lần chạy này; bước conversion sau phải đọc context đó, không hardcode namespace của session cũ. Gửi output cuối để review trước conversion. Không cần upload lại/commit/push hoặc sửa sealed input/kit. Không xóa failed stages/logs.

Lịch sử: cell02 clone/checkout đúngSHA nhưng child `ensurepip --upgrade --default-pip` exit1 ([evidence](evidence/p1_r_1/kaggle_setup_user_failure.json)); chưa có inner traceback để kết luận thiếu OS package. Cell02b dựa vào repo cũ và dừng vì `Pinned repo missing` trong screenshot session0m ([evidence](evidence/p1_r_1/kaggle_recovery_missing_repo.json)); reset là khả năng, chưa xác minh nguyên nhân. Hai cell cũ được giữ làm evidence, không còn là hướng dẫn recovery hiện tại.

Local verification: actual transfer extraction/input177files và exact environment probe trên Windows PASS ([evidence](evidence/p1_r_1/notebook_cells/local_restart_setup_check.json)); offline parent-pip integration và8restart staging regressions pass, toàn suite **253passed**, CPU smoke/env/pip check pass ([logs](evidence/p1_r_1/verification_restart_setup/verification.json)). Linux setup PASS lấy từ user log mới, không suy từ local checks. Các shell commands gốc bên dưới chỉ là reference cho flow ban đầu, không chạy thêm khi đang dùng cells02c/03.

Tạo notebook **private**, Accelerator **None**, Internet bật khi account/terms cho phép. Kiểm actual UI: current CPU/GPU quota, session limit, private used/remaining storage, collaborators và input/output version accounting. Published limits không phải actual account allocation; ghi thông tin đo được trong evidence, không điền assumed defaults.

Sau khi input transfer đã được duyệt và mount read-only, đặt các biến trong notebook (đổi placeholders, không dùng user home path):

```bash
export PILOT_WORK_ROOT=/kaggle/working/pilot_session_01
export PILOT_KIT=/kaggle/working/code/cloud_pilot.py
# Đặt reviewed bootstrap ở code/bootstrap_cloud_pilot.sh; LF line endings.
bash /kaggle/working/code/bootstrap_cloud_pilot.sh
export PYTHONPATH="$PILOT_WORK_ROOT/repo/src"
export CUDA_VISIBLE_DEVICES=""
cd "$PILOT_WORK_ROOT/repo"
"$PILOT_WORK_ROOT/venv/bin/python" -c 'import sys,numpy,nibabel,pydicom,yaml; print(sys.version)'
```

Bootstrap create-only, clone/fetch/detach exact SHA, Python3.11–3.13 guard, fresh Linux venv, install bounded NumPy/NiBabel/pydicom/PyYAML ranges, `pip check` và resolved freeze. Không install Windows CPU lock; Torch/MONAI/GPU không cần cho native conversion. Linux package resolution chưa được test ở đây: nếu install/import fail, giữ logs/freeze và ghi BLOCKED_ENVIRONMENT, không tự đổi production code. Freeze thực của successful run cần pin cho rerun, không coi ranges là exact Linux lock.

```bash
PILOT_INPUT=/kaggle/input/APPROVED_PRIVATE_INPUT/pilot_input
PILOT_INPUT_SHA=c97683893715b34fbb7cdf7193134220625169021acb39aae00f6243ce9c4f6f
"$PILOT_WORK_ROOT/venv/bin/python" "$PILOT_KIT" run \
  --input "$PILOT_INPUT" --output "$PILOT_WORK_ROOT/result" \
  --expected-root-sha256 "$PILOT_INPUT_SHA" --execution-kind kaggle \
  --probe-connectivity
```

Input/output tách biệt; output fresh, không reuse artifact cache local/Linux. Pilot metadata probes chỉ1KiB/source, timeout10s, không reacquire. Nếu Internet false thì source probes report failure, không gọi connectivity PASS; native conversion từ mounted input vẫn có thể chạy nhưng cần review connectivity riêng.

Admission:8GiBdiskfree và available RAM≥`max(1GiB,12×max_reference_voxels+768MiB)`, hiện2sample cần1,226,833,920bytes. Đây là estimate; worker ghi peak RSS thực (OS peak working set), wall seconds, input/reference/output bytes; conversion tuần tự mỗi source, không multi-case parallel. Không hạ guard hoặc downsample khi blocked. Failed/preflight stages giữ, retry dùng namespace mới.

## 4. Session1 — acceptance review

**Current result:** [summary](evidence/p1_r_1/kaggle_native_user_summary.json), [review](evidence/p1_r_1/kaggle_native_review.json) PASS cho1NSCLC+1weak,0quarantine, arrays/geometry/weak records/selected provenance equal. Agent so4reported signatures với pinned local spec đều khớp, chưa fetch remote artifacts. Receipt SHA256 `8da1ebd95caac4551160cfcdfc9e8e749fec7f82d13a3bb6f1a836d6c670687a` phải giữ làm external trust anchor khi restore, không thay bằng digest tính từ bản tải mới.

**Đích result đã duyệt:** “SE374 LungSeg Pilot Result v1”, Private/personal owner-only; [approval](evidence/p1_r_1/kaggle_result_destination_approval.json). Không hỏi lại cùng quyền. Chạy riêng [cell04 package](evidence/p1_r_1/notebook_cells/04_package_verified_result.py) trong session hiện tại. Cell verify pinned result27files, đóng gói28regular members vào `/kaggle/working/se374-pilot-result-8da1ebd95caa.bin`, đọc lại từng archived byte/hash và đo actual transfer bytes/SHA. Không copy raw/XML/input/codekit/venv vào result transfer; không sửa result tree. `RESULT_TRANSFER_READY_NO_UPLOAD` chỉ xác nhận temporary package, **không là persistence PASS**.

Local3synthetic packaging tests pass, full regression **256passed** và CPU smoke/env/pip check PASS ([logs](evidence/p1_r_1/verification_result_transfer/verification.json)). Cloud packaging chờ user execution.

**Packaging update:** [user screenshot receipt](evidence/p1_r_1/kaggle_result_package_user_verified.json) cho actual transfer57,477,120bytes,28members và outer SHA256 `a7285babe7d1c0fa5a24fef48f064b2fc558113ba75aa1b2e948d493c1b4f3dc`. Cell04 đã PASS trên user Kaggle session; không chạy lại packaging/conversion. User tải chỉ `se374-pilot-result-8da1ebd95caa.bin` từ Output, tạo approved “SE374 LungSeg Pilot Result v1” Private/owner-only, Other+description đã chuẩn bị, upload đúngfile. Giữ nguyên tên/đuôi. Mount Dataset đó qua Add Input vào notebook đang mở, chạy riêng [cell05 verify uploaded container](evidence/p1_r_1/notebook_cells/05_verify_result_dataset_transfer.py). Expected `RESULT_DATASET_TRANSFER_SHA256_PASS`; gửi output và Dataset link/version trước khi kết thúc session. Không Save Version toàn workingdir. Same-session mounted read-back PASS chưa là cross-session persistence PASS.

Gửi receipt cell04 để pin outer hash/size, giữ session mở. Sau verification, user tải đúng file này và upload vào approved Private Dataset, chọn Other và dùng [description/attribution](evidence/p1_r_1/kaggle_result_dataset_description.txt); không blanket CC0/relicense hoặc thêm collaborators. Xác minh exact uploaded file hash/bytes trước kết thúc session. Không Save Version toàn `/kaggle/working` vì chứa input copies/repos/venv ngoài exact result approval. Không cần commit/push hoặc chạy lại conversion. Upload/actual session2 vẫn NOT_RUN tại handoff.

Pilot kiểm:

- Externally pinned input receipt, toàn bộ raw/reference hashes và file set; input preserved sau run.
- Exact production source hashes +reviewed Git SHA. Runtime fingerprint có thể khác Windows; recorded đầy đủ, không reuse cache incompatible.
- Native CT/mask/bbox shapes/affines/spacings/dtypes/units/qform/sform và decoded voxel SHA; geometry tolerance1e-6, voxel arrays exact.
- Weak boxes.json/coverage.json equality; NSCLC annotation/ROI/coordinate/intensity provenance và source/geometry giữ nguyên. Runtime/config/output-path provenance differences được version riêng, không gộp cache.
- `run.json`, metrics/logs/freeze và `RESULT_ROOT.json` full artifact hashes. Không training/expert approval; unknown vẫnunknown.

Geometry/reference mismatch, source implementation change, hash corruption hoặc conversion/quarantine unexpected đều fail; không chỉnh local reference để ép PASS. `KAGGLE_CPU_PILOT_PASS` chỉ là bounded native conversion/comparison, không full readiness, account quota hoặc persistence PASS. Source reachability failures phải được báo riêng.

Ghi externally trusted result receipt SHA256 từ stdout session1; export **metadata summary** để review (không token/home paths). Chỉ sau approved persistence destination mới lưu đủ result tree và receipt. Notebook “Save Version”/file visible không là read-back verification. Kiểm saved bytes/output limit trước publish; không tự upload bằng script.

## 5. Session2 — persistence và restore

**Latest result ngày25/11:** user đã chạy06 trong notebook mới và gửi [output](evidence/p1_r_1/kaggle_session2_restore_user_verified.json): `RESTORE_CONTENT_VERIFIED`,27files, arrays/geometry/annotation-provenance hashes verified, producer implementation equal, input read-back verified, old work absent và fresh-session attestation=true. Notebook URL mới đã được user cung cấp. Reviewed status **PASS_BOUNDED_RESTORE_WITH_USER_ATTESTATION**; host shutdown/account/version/privacy không independently observed. Warningwrapt còn OPEN nhưng restore thành công. Không chạy lại02c/03/04/06 chỉ để có commit; preserve artifacts, chuẩn bị review/snapshot với R2/quota/full capacity OPEN.

**Latest session2 setup:** user đã gửi [notebook mới](https://www.kaggle.com/code/winpear/notebooka1b5088c00/edit) và log02c ngày25/11 ([evidence](evidence/p1_r_1/kaggle_session2_setup_user_verified.json)). Source/package checks PASS và cả2cloud runtime fingerprints khớp producer. Trong notebook mới này, copy cell06 vào Python Code cell mới; chỉ đổi `FRESH_SESSION_ATTESTED=True` nếu user đã thực sự kết thúc original session. Giữ Result Dataset attached, chạy riêng06 và gửi từ `RESTORE_RESULT_SUMMARY` đến cuối cùng xác nhận lifecycle. Không cần rerun02c/03/04; context02c mới đã có. Actual restore vẫn NOT_RUN, original session termination chưa được explicit user attestation trong message setup.

**Current handoff:** cell05 [user screenshot](evidence/p1_r_1/kaggle_result_upload_user_verified.json) đã PASS mounted result transfer bytes/SHA, original session27m. Bây giờ kết thúc session cũ thật, tạo notebook **Private mới** (đề xuất `SE374 P1-R1 Restore Session 2`), Accelerator **None**, Internet bật; attach cả “SE374 LungSeg Pilot Input v1” và “SE374 LungSeg Pilot Result v1”. Không chỉ restart Python kernel trong cùng session. Chạy riêng [cell02c](evidence/p1_r_1/notebook_cells/02c_setup_from_attached_dataset.py) để verify source bundle/XML và tạo fresh pinned checkout/environment; không03/04, không conversion. Gửi output `LINUX_ENVIRONMENT_READY_NO_CONVERSION` và notebook URL mới để review setup/session evidence trước restore.

Sau setup/session review, [cell06 restore](evidence/p1_r_1/notebook_cells/06_restore_in_new_session.py) chạy trong notebook mới. User chỉ đổi `FRESH_SESSION_ATTESTED=False` thành `True` sau khi đã thực hiện lifecycle trên. Cell từ chối old work directory còn tồn tại, verify approved mounted outer transfer, safe-extract28regular result members vào fresh cache, verify inner pinned receipt27artifacts, exact producer implementation/runtime identities rồi decode/compare4NIfTI signatures. Annotation/coverage/provenance/freeze/logs kiểm toàn bộ bytes/hash; input bundle177files được read-back verify riêng. Không upload/delete/reconvert hoặc sửa producer receipt. Runtime không khớp phải review và tái dựng environment đúngfreeze, không hạ check để pass.

Expected `RESTORE_RESULT_SUMMARY` và `USER_ATTESTED_FRESH_SESSION_CONTENT_PASS` chỉ là content +user attestation evidence; gửi summary, URL notebook mới và xác nhận session cũ đã kết thúc để reviewer đối chiếu. Cần thêm Dataset privacy/version evidence, không suy private access hoặc exact Kaggle Dataset version từ mount slug. Actual restore chưa chạy tại handoff này.

Local restore preparation:7synthetic safe-extraction/session guard tests PASS, cell/child syntax checked, fullsuite **263passed**, CPU smoke/env/pip check PASS ([logs](evidence/p1_r_1/verification_restore_cell/verification.json)). Không coi các test local là evidence session lifecycle thật.

Sau khi session1 đã kết thúc thật, mở notebook/session mới (không chỉ restart Python trong cùng process), mount approved **versioned result output** read-only. Ghi previous/new notebook version/session evidence và user attestation; giữ data-input receipt nếu restore source bundle được yêu cầu. Restore content kiểm toàn bộ outputs; source bundle persistence cần verify INPUT_ROOT riêng, không suy ra từ result receipt.

Tạo fresh Linux venv bằng previous run's resolved versions hoặc bootstrap rồi kiểm versions; set PYTHONPATH tới same pinned production repo. Chạy reviewed kit:

```bash
RESTORED_RESULT=/kaggle/input/APPROVED_SAVED_RESULT/result
TRUSTED_RESULT_SHA=PASTE_TRUSTED_SESSION1_RESULT_ROOT_SHA256
"$PILOT_WORK_ROOT/venv/bin/python" "$PILOT_KIT" restore \
  --input "$RESTORED_RESULT" --expected-root-sha256 "$TRUSTED_RESULT_SHA" \
  --report /kaggle/working/session_02_restore.json --fresh-session-attested
```

Đổi PILOT_WORK_ROOT sang fresh session2namespace trước bootstrap; không reuse existing dir. Report phải ngoài immutable input. `restore` read-back full file bytes/hashes rồi decode native arrays/geometry; annotation records/coverage/provenance/freeze/logs được kiểm content hashes trong same receipt. Trước đó nó không gọi artifacts verified chỉ vì filenames có mặt.

`RESTORE_CONTENT_VERIFIED` không tự chứng minh new session. `USER_ATTESTED_FRESH_SESSION_CONTENT_PASS` cần current Kaggle runtime, prior run Kaggle và **user xác nhận session mới thật**; reviewer còn đối chiếu session metadata/attestation. Local restore/unit tests hoặc cùng session không là cloud persistence acceptance. Restore result tree chưa đồng nghĩa raw input archive đã có independent durable copy: verify source INPUT_ROOT trên persistent input riêng trước bất kỳ cleanup proposal nào.

Nếu chưa có quyền/source mount hoặc không làm được session2: NOT_RUN/BLOCKED_USER_ACTION, không ghi PASS. Không xóa local raw/baselines/XML/failed stages sau pilot, kể cả restore thành công; cleanup cần policy và user approval riêng.

## Local preparation/checks đã thực hiện

```powershell
.venv\Scripts\python.exe scripts/cloud_pilot.py assess --output docs/evidence/p1_r_1/local_assessment.json
# Local archive location đặt qua biến môi trường/private config, không commit absolute path:
.venv\Scripts\python.exe scripts/cloud_pilot.py prepare --output data/cache/cloud_pilot/input_p1_r_1 --xml-archive $env:LUNGSEG_XML_ARCHIVE
.venv\Scripts\python.exe -m pytest -q tests/test_cloud_pilot.py
.\scripts\verify.ps1 -EvidenceDirectory docs/evidence/p1_r_1/verification
```

Prepare tạo output mới và có thể mất disk; không chạy lại vào namespace đã có. Local attempt đã BLOCKED_RAM, xem [evidence](evidence/p1_r_1/local_pilot.json). Không dùng `--execution-kind kaggle` trên local: guard sẽ từ chối. Không báo cloud execution/restore PASS nếu chỉ tạo xong kit hoặc chạy synthetic tests. Dừng sau P1-R.1 để review, không tự P1-R.2/T07/T08/training/full scheduler.
