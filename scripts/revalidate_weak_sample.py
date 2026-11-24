"""Offline P1.3.1 revalidation into separate versioned roots, preserving P1.3."""
import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from lungseg.data.msd_acquire import file_sha256,require_space
from lungseg.data.nsclc_version import conversion_implementation
from lungseg.data.weak_config import load_weak_config
from lungseg.data.weak import implementation
from lungseg.data.weak_acquire import acquire
from lungseg.runs import utc_now,write_json
from revalidate_nsclc_sample import tree_snapshot,compare_nifti


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-config',type=Path,default=Path('configs/weak.yaml'))
    parser.add_argument('--config',type=Path,default=Path('configs/weak_p1_3_1.yaml'))
    args=parser.parse_args();old,new=load_weak_config(args.baseline_config),load_weak_config(args.config)
    execution_paths={'converted_root','output_dir','qa_dir','evidence_dir'}
    ov,nv=asdict(old),asdict(new)
    if any(ov[k]!=nv[k] for k in ov.keys()-execution_paths):raise ValueError('Only output roots may change')
    preserved={k:Path(ov[k]) for k in execution_paths|{'raw_root'}}
    interrupted=Path('data/converted/weak_v1')
    if interrupted.is_dir():preserved['interrupted_p1_3']=interrupted
    for k in execution_paths:
        target=Path(nv[k]).resolve()
        for root in preserved.values():
            root=root.resolve()
            if target==root or target in root.parents or root in target.parents:raise ValueError('New outputs overlap baseline')
    evidence=Path(new.evidence_dir);evidence.mkdir(parents=True,exist_ok=True)
    before=tree_snapshot(preserved)
    nsclc_before=conversion_implementation()['fingerprint_sha256']
    accepted=json.loads(Path('docs/evidence/p1_2_1/artifact_audit.json').read_text())['conversion_fingerprint_sha256']
    if nsclc_before!=accepted:raise ValueError('NSCLC fingerprint changed before weak revalidation')
    allowance=4*sum(p.stat().st_size for p in Path(old.converted_root).rglob('*') if p.is_file())
    preflight={'timestamp_utc':utc_now(),'operation':'offline_revalidation_no_network',
               'free_bytes':require_space(Path(new.converted_root),allowance+new.reserve_bytes),
               'output_allowance_bytes':allowance,'reserve_bytes':new.reserve_bytes,
               'preserved_roots':{k:p.as_posix() for k,p in preserved.items()},'baseline_snapshot':before,
               'implementation':implementation(),'nsclc_fingerprint':nsclc_before}
    write_json(evidence/'revalidation_preflight.json',preflight)
    commands=[]
    def run(name):
        argv=[sys.executable,'-m','lungseg.cli',name,'--config',str(args.config)];stamp=utc_now()
        proc=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace')
        log=evidence/f'revalidate_{len(commands):02d}_{name}.txt'
        log.write_text(f'timestamp_utc: {stamp}\ncommand_argv: {json.dumps(argv)}\nexit_code: {proc.returncode}\n'+proc.stdout+proc.stderr,encoding='utf-8')
        commands.append({'command_argv':argv,'timestamp_utc':stamp,'exit_code':proc.returncode,'log':log.name})
        write_json(evidence/'revalidation_execution.json',{'commands':commands,'status':'running'})
        if proc.returncode not in (0,2):raise RuntimeError(f'{name} failed; inspect {log}')
        print(name,proc.returncode,flush=True)
    try:
        # Exercise real verified-cache admission while forbidding every payload/listing request.
        def no_network(*a,**kw):raise RuntimeError('Offline revalidation prohibits network/cache miss')
        with patch('lungseg.data.weak_acquire.urlopen',no_network),patch('lungseg.data.weak_acquire.list_objects',no_network):
            cache=acquire(new,Path(old.output_dir)/'public_catalog.json',download=True)
        if cache.get('status')!='CT_SR_SAMPLE_ACQUIRED' or cache['network_payload_bytes_this_run']!=0:raise RuntimeError('Cache-only acquisition validation failed')
        write_json(evidence/'cached_acquisition_execution.json',{'operation':'acquire(download=True), network/listing explicitly disabled',
                   'status':cache['status'],'exit_code_contract':0,'network_payload_bytes_this_run':cache['network_payload_bytes_this_run'],
                   'existing_verified_cache_bytes':cache['existing_verified_cache_bytes']})
        run('survey-weak');run('audit-weak')
        manifest=Path(new.output_dir)/'manifest_weak.csv';first=file_sha256(manifest)
        run('audit-weak');second=file_sha256(manifest);run('qa-weak')
        def rows(cfg):
            with (Path(cfg.output_dir)/'manifest_weak.csv').open(newline='',encoding='utf-8') as handle:
                return {r['case_id']:r for r in csv.DictReader(handle)}
        a,b=rows(old),rows(new);comparisons=[]
        for key in sorted(a.keys()|b.keys()):
            left,right=a.get(key),b.get(key)
            r={'case_id':key,'before_status':left['conversion_status'] if left else None,
               'after_status':right['conversion_status'] if right else None}
            if left and right and left['conversion_status']==right['conversion_status']=='converted':
                for field in ('image_path','bbox_path'):
                    r[field]=compare_nifti(Path(old.converted_root)/left[field],Path(new.converted_root)/right[field],new.slab_slices)
                for field in ('boxes_path','coverage_path'):
                    x,y=Path(old.converted_root)/left[field],Path(new.converted_root)/right[field]
                    r[field]={'records_equal':json.loads(x.read_text())==json.loads(y.read_text()),'file_sha256_equal':file_sha256(x)==file_sha256(y)}
                fields=('box_count','annotated_slice_count','missing_slice_count','explicit_negative_slice_count',
                        'bbox_foreground_voxels','bbox_envelope_volume_mm3','source_sha256','weak_eligible')
                r['unchanged_manifest_fields']={f:left[f]==right[f] for f in fields}
                r['acquisition_semantics']=json.loads(right['acquisition_semantics'])
                r['provenance_sha256_changed']=left['provenance_sha256']!=right['provenance_sha256']
                r['equivalent']=all(all(v is True for k,v in r[f].items() if k not in ('different_voxels','max_abs_voxel_difference'))
                                    for f in ('image_path','bbox_path','boxes_path','coverage_path')) and all(r['unchanged_manifest_fields'].values())
            else:r['equivalent']=False
            comparisons.append(r)
        old_qa=json.loads((Path(old.qa_dir)/'qa_index.json').read_text())
        new_qa=json.loads((Path(new.qa_dir)/'qa_index.json').read_text())
        old_pngs={r['case_id']:r for r in old_qa['cases']}
        qa_comparison=[]
        for record in new_qa['cases']:
            previous=old_pngs.get(record['case_id'])
            actual=file_sha256(Path(new.qa_dir)/record['file'])
            qa_comparison.append({'case_id':record['case_id'],'new_png_hash_verified':actual==record['png_sha256'],
                                  'baseline_png_bytes_equal':bool(previous and previous['png_sha256']==actual)})
        after=tree_snapshot(preserved);nsclc_after=conversion_implementation()['fingerprint_sha256']
        findings={'timestamp_utc':utc_now(),'real_data':True,'cases':comparisons,'case_count':len(comparisons),
                  'all_case_outputs_equivalent':all(r['equivalent'] for r in comparisons),
                  'manifest_repeat_identical':first==second,'manifest_sha256':second,
                  'qa_comparison':qa_comparison,
                  'baseline_before':before,'baseline_after':after,'baseline_preserved':before==after,
                  'nsclc_fingerprint_before':nsclc_before,'nsclc_fingerprint_after':nsclc_after,'nsclc_unchanged':nsclc_before==nsclc_after,
                  'manual_expert_approval':False,'weak_training_clearance':False}
        write_json(evidence/'before_after_comparison.json',findings)
        if not all((findings['all_case_outputs_equivalent'],first==second,before==after,nsclc_before==nsclc_after)):
            raise RuntimeError('Revalidation comparison/preservation failed')
    except Exception as exc:
        write_json(evidence/'revalidation_execution.json',{'commands':commands,'status':'failed','error':str(exc)});raise
    write_json(evidence/'revalidation_execution.json',{'commands':commands,'status':'MACHINE_REVALIDATION_PASS_REVIEW_REQUIRED'})
    print('10-case comparison and preservation checks complete; expert review pending',flush=True)


if __name__=='__main__':main()
