"""Offline T06 repeat/QA/raw-preservation checks; never downloads or edits sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from lungseg.data.msd_acquire import file_sha256
from lungseg.data.weak_config import load_weak_config
from lungseg.runs import utc_now,write_json


def snapshot(root):
    files=sorted(p for p in root.rglob('*') if p.is_file())
    if not files:raise ValueError('Raw sample is empty')
    values={p.relative_to(root).as_posix():file_sha256(p) for p in files}
    return {'files':len(files),'bytes':sum(p.stat().st_size for p in files),
            'tree_sha256':hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--baseline-snapshot',type=Path)
    args=parser.parse_args();config=load_weak_config(args.config)
    evidence=Path(config.evidence_dir);evidence.mkdir(parents=True,exist_ok=True)
    before=snapshot(Path(config.raw_root));commands=[]
    def run(name):
        command=[sys.executable,'-m','lungseg.cli',name,'--config',str(args.config)];stamp=utc_now()
        proc=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
        log=evidence/f'sample_{len(commands):02d}_{name}.txt'
        log.write_text(f'timestamp_utc: {stamp}\ncommand_argv: {json.dumps(command)}\nexit_code: {proc.returncode}\n'+proc.stdout+proc.stderr,encoding='utf-8')
        commands.append({'command_argv':command,'timestamp_utc':stamp,'exit_code':proc.returncode,'log':log.name})
        write_json(evidence/'sample_execution.json',{'commands':commands,'status':'running'})
        if proc.returncode not in {0,2}:raise RuntimeError(f'{name}: inspect {log}')
        print(name,proc.returncode,flush=True)
    try:
        run('survey-weak');run('audit-weak')
        manifest=Path(config.output_dir)/'manifest_weak.csv';first=file_sha256(manifest)
        run('audit-weak');second=file_sha256(manifest)
        after=snapshot(Path(config.raw_root))
        write_json(evidence/'repeat_and_preservation.json',{'timestamp_utc':utc_now(),'real_data':True,
            'raw_before':before,'raw_after':after,'raw_preserved':before==after,
            'manifest_sha256_first':first,'manifest_sha256_second':second,'repeat_identical':first==second})
        if before!=after or first!=second:raise RuntimeError('Raw preservation/manifest determinism failed')
        report=json.loads((Path(config.output_dir)/'conversion_report.json').read_text())
        if (not report.get('reconciliation',{}).get('pass') or report['converted_cases']!=len(config.sample_patient_ids)
            or report['quarantined_cases'] or report['excluded_cases'] or report.get('annotation_failure_count') or report.get('acquisition_errors')):
            raise RuntimeError('Partial sample; machine verification cannot claim complete sample validation')
        run('qa-weak')
        if json.loads((Path(config.qa_dir)/'qa_index.json').read_text())['n_cases']!=report['converted_cases']:
            raise RuntimeError('QA coverage incomplete')
        if args.baseline_snapshot:
            baseline=json.loads(args.baseline_snapshot.read_text());changed=[]
            for path,old in baseline.items():
                p=Path(path)
                if not p.is_file() or p.stat().st_size!=old['bytes'] or file_sha256(p)!=old['sha256']:changed.append(path)
            write_json(evidence/'msd_nsclc_preservation.json',{'timestamp_utc':utc_now(),'files_checked':len(baseline),
                'bytes_checked':sum(r['bytes'] for r in baseline.values()),'changed_files':changed,
                'all_preexisting_MSD_NSCLC_artifacts_preserved':not changed,
                'baseline_snapshot_sha256':file_sha256(args.baseline_snapshot)})
            if changed:raise RuntimeError('Preexisting baseline changed')
        from lungseg.data.nsclc_version import conversion_implementation
        actual=conversion_implementation()
        old=json.loads(Path('docs/evidence/p1_2_1/artifact_audit.json').read_text())['conversion_fingerprint_sha256']
        write_json(evidence/'nsclc_cache_identity_preserved.json',{'before':old,'after':actual['fingerprint_sha256'],'equal':old==actual['fingerprint_sha256']})
        if old!=actual['fingerprint_sha256']:raise RuntimeError('NSCLC implementation identity changed')
    except Exception as exc:
        write_json(evidence/'sample_execution.json',{'commands':commands,'status':'failed','error':str(exc)});raise
    write_json(evidence/'sample_execution.json',{'commands':commands,'status':'SAMPLE_MACHINE_CHECKS_PASS_VISUAL_REVIEW_PENDING'})


if __name__=='__main__':main()
