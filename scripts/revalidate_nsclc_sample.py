"""Offline before/after revalidation into separate NSCLC output roots.

Never downloads, edits raw, deletes or overwrites baseline artifacts. Reports
per-case transitions instead of assuming the new algorithm must convert 7 cases.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import nibabel as nib
import numpy as np

from lungseg.data.msd_acquire import file_sha256, require_space
from lungseg.data.msd_qa import load_manifest
from lungseg.data.nsclc_config import load_nsclc_config
from lungseg.data.nsclc_version import conversion_implementation
from lungseg.runs import utc_now, write_json


def tree_snapshot(roots):
    digest, files, size = hashlib.sha256(), 0, 0
    for label, root in roots.items():
        if not root.is_dir():
            raise FileNotFoundError(f"Missing preserved baseline {label}")
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            digest.update(f"{label}/{path.relative_to(root).as_posix()}\0".encode())
            digest.update(file_sha256(path).encode())
            files += 1
            size += path.stat().st_size
    return {"files": files, "bytes": size, "tree_sha256": digest.hexdigest()}


def compare_nifti(left, right, slab_slices):
    a, b = nib.load(left, keep_file_open=True), nib.load(right, keep_file_open=True)
    shape_equal = a.shape == b.shape
    result = {"shape_equal": shape_equal, "affine_equal": bool(np.array_equal(a.affine, b.affine)),
              "spacing_equal": bool(np.array_equal(a.header.get_zooms(), b.header.get_zooms())),
              "units_equal": a.header.get_xyzt_units() == b.header.get_xyzt_units(),
              "dtype_equal": a.get_data_dtype() == b.get_data_dtype(),
              "qform_equal": bool(np.array_equal(a.get_qform(), b.get_qform()) and a.header['qform_code'] == b.header['qform_code']),
              "sform_equal": bool(np.array_equal(a.get_sform(), b.get_sform()) and a.header['sform_code'] == b.header['sform_code']),
              "file_sha256_equal": file_sha256(left) == file_sha256(right)}
    different, max_difference = 0, 0.
    if shape_equal:
        for start in range(0, a.shape[2], slab_slices):
            aa = np.asanyarray(a.dataobj[:, :, start:start+slab_slices])
            bb = np.asanyarray(b.dataobj[:, :, start:start+slab_slices])
            different += int(np.count_nonzero(aa != bb))
            max_difference = max(max_difference, float(np.max(np.abs(aa.astype(float)-bb.astype(float)))))
    result.update(voxel_arrays_equal=shape_equal and different == 0,
                  different_voxels=different if shape_equal else None, max_abs_voxel_difference=max_difference if shape_equal else None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-config', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    old, new = load_nsclc_config(args.baseline_config), load_nsclc_config(args.config)
    execution_paths = {'converted_root','output_dir','qa_dir','evidence_dir'}
    old_values, new_values = asdict(old), asdict(new)
    if any(old_values[k] != new_values[k] for k in old_values.keys()-execution_paths):
        raise ValueError('Only output roots may change; preserve raw root, sample, ROI and QC policy')
    for new_key in execution_paths:
        target = Path(new_values[new_key]).resolve()
        for old_key in execution_paths | {'raw_root'}:
            preserved = Path(old_values[old_key]).resolve()
            if target == preserved or target in preserved.parents or preserved in target.parents:
                raise ValueError('Revalidation output must not overlap any preserved baseline/raw root')
    evidence = Path(new.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)
    preserved = {k:Path(old_values[k]) for k in execution_paths | {'raw_root'}}
    # Acquisition planning allowance based on pinned catalog, not measured gzip size.
    catalog_path = Path(old.output_dir)/'public_catalog.json'
    catalog = json.loads(catalog_path.read_text())['series']
    sample_ct = [r for r in catalog if r['PatientID'] in new.sample_patient_ids and r['Modality']=='CT']
    estimate = int(sum(r['FileSize'] for r in sample_ct)*2.5)
    preflight = {'timestamp_utc':utc_now(), 'operation':'offline_sample_reconversion_only',
                 'free_bytes':require_space(Path(new.converted_root), estimate+new.reserve_bytes),
                 'new_output_allowance_bytes':estimate, 'reserve_bytes':new.reserve_bytes,
                 'catalog_sha256':file_sha256(catalog_path), 'conversion_implementation':conversion_implementation()}
    write_json(evidence/'revalidation_preflight.json',preflight)
    before = tree_snapshot(preserved)
    commands = []

    def run(name):
        command = [sys.executable,'-m','lungseg.cli',name,'--config',str(args.config)]
        stamp = utc_now()
        proc = subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
        log = evidence/f'revalidate_{len(commands):02d}_{name}.txt'
        log.write_text(f'timestamp_utc: {stamp}\ncommand_argv: {json.dumps(command)}\nexit_code: {proc.returncode}\n'
                       + proc.stdout+proc.stderr,encoding='utf-8')
        commands.append({'command_argv':command,'timestamp_utc':stamp,'exit_code':proc.returncode,'log':log.name})
        write_json(evidence/'revalidation_execution.json',{'commands':commands,'status':'running'})
        if proc.returncode not in ({0,2} if name=='convert-nsclc' else {0}):
            raise RuntimeError(f'{name} failed; inspect {log}')
        print(f'{name}: exit {proc.returncode}',flush=True)

    try:
        run('survey-nsclc')
        run('convert-nsclc')
        manifest = Path(new.output_dir)/'manifest_nsclc.csv'
        first_digest = file_sha256(manifest)
        # Reuse tests real cache hit and repeat manifest under the same implementation.
        run('convert-nsclc')
        repeat_digest = file_sha256(manifest)
        if first_digest != repeat_digest:
            raise RuntimeError('Manifest differs on cache-hit repeat')
        old_rows = {r['case_id']:r for r in load_manifest(Path(old.output_dir)/'manifest_nsclc.csv')}
        new_rows = {r['case_id']:r for r in load_manifest(manifest)}
        if old_rows.keys() != new_rows.keys():
            raise RuntimeError('Sample membership changed')
        comparisons = []
        for case, a in old_rows.items():
            b = new_rows[case]
            entry = {'case_id':case,'before_status':a['conversion_status'],'after_status':b['conversion_status'],
                     'before_errors':a['qc_errors'],'after_errors':b['qc_errors'],
                     'failure_context':json.loads(b['qc_failure_context']) if b['qc_failure_context'] else None,
                     'source_sha256_equal':a['source_sha256']==b['source_sha256'],
                     'roi_number_equal':a['roi_number']==b['roi_number'], 'roi_name_equal':a['roi_name']==b['roi_name']}
            if a['conversion_status']==b['conversion_status']=='converted':
                entry['ct'] = compare_nifti(Path(old.converted_root)/a['image_path'],Path(new.converted_root)/b['image_path'],new.slab_slices)
                entry['mask'] = compare_nifti(Path(old.converted_root)/a['mask_path'],Path(new.converted_root)/b['mask_path'],new.slab_slices)
                entry['tumor_volume_mm3_before'],entry['tumor_volume_mm3_after'] = a['tumor_volume_mm3'],b['tumor_volume_mm3']
                entry['tumor_volume_mm3_difference'] = b['tumor_volume_mm3']-a['tumor_volume_mm3']
            comparisons.append(entry)
        if any(r['conversion_status']=='converted' for r in new_rows.values()):
            run('qa-nsclc')
        report = {'timestamp_utc':utc_now(),'real_data':True,'baseline_config_sha256':old.sha256,'config_sha256':new.sha256,
                  'conversion_implementation':conversion_implementation(),'manifest_sha256':repeat_digest,
                  'repeat_manifest_identical':True,'patients':len(comparisons),'cases':comparisons,
                  'converted_before':sum(r['conversion_status']=='converted' for r in old_rows.values()),
                  'converted_after':sum(r['conversion_status']=='converted' for r in new_rows.values()),
                  'quarantined_after':sum(r['conversion_status']=='quarantined' for r in new_rows.values()),
                  'manual_review':'not newly approved; prior LUNG1-002 REVIEW_REQUIRED remains open',
                  'expert_approval':False,'full_corpus_status':'BLOCKED_STORAGE_NOT_VALIDATED'}
        write_json(evidence/'before_after_comparison.json',report)
    except Exception as exc:
        write_json(evidence/'revalidation_execution.json',{'commands':commands,'status':'failed','error':str(exc)})
        raise
    finally:
        after = tree_snapshot(preserved)
        write_json(evidence/'preservation.json',{'timestamp_utc':utc_now(),'baseline_roots':old_values,
                   'before':before,'after':after,'raw_and_baseline_preserved':before==after})
        if before != after:
            raise RuntimeError('Raw/baseline preservation check failed')
    write_json(evidence/'revalidation_execution.json',{'commands':commands,'status':'sample_revalidated_with_findings'})
    print(json.dumps({'converted_before':report['converted_before'],'converted_after':report['converted_after'],
                      'quarantined_after':report['quarantined_after'],'raw_and_baseline_preserved':True},indent=2))


if __name__=='__main__':
    main()
