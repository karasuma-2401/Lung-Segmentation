"""Bounded, CPU-only pilot. No upload, acquisition, cleanup or full scheduler.

prepare builds an ignored local input bundle; run converts existing samples into
fresh outputs; restore verifies a mounted prior session without modifying it.
"""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import platform
import shutil
import subprocess
import sys
import time
from urllib.request import Request,urlopen
from uuid import uuid4

REVISION='dc6e179087737621b69d538ef200436c644a7687'
XML_SHA='74578564508a2c52c6046ef8065708c068b884711dd924d4eaf3db298914d377'
GIB=1024**3


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024**2),b''):value.update(block)
    return value.hexdigest()


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n',encoding='utf-8')


def files(root):
    result={}
    for p in sorted(Path(root).rglob('*')):
        if p.is_symlink():raise ValueError('Symlinks are not permitted in pilot bundles')
        if p.is_file():result[p.relative_to(root).as_posix()]={'bytes':p.stat().st_size,'sha256':sha(p)}
    return result


def seal(root,filename):
    root=Path(root)
    if (root/filename).exists():raise ValueError('Receipt exists; use fresh output')
    write(root/filename,{'schema_version':1,'files':files(root)})
    return sha(root/filename)


def verify(root,filename,expected):
    root=Path(root)
    if sha(root/filename)!=expected:raise ValueError('Receipt does not match externally pinned digest')
    inventory=json.loads((root/filename).read_text())['files']
    for name,value in inventory.items():
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:raise ValueError('Unsafe artifact path')
        p=root.joinpath(*path.parts)
        if not p.resolve().is_relative_to(root.resolve()) or p.is_symlink():raise ValueError('Artifact escapes root')
        if not p.is_file() or p.stat().st_size!=value['bytes'] or sha(p)!=value['sha256']:raise ValueError('Artifact missing/corrupt: '+name)
    actual=files(root);actual.pop(filename,None)
    if set(actual)!=set(inventory):raise ValueError('Unlisted or missing artifacts')
    return inventory


def memory():
    if sys.platform=='win32':
        import ctypes
        class Status(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
        item=Status();item.length=ctypes.sizeof(item)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(item)):raise OSError('Memory query failed')
        return {'total_bytes':item.total,'available_bytes':item.available}
    if Path('/proc/meminfo').is_file():
        info={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if len(line.split())>=2 and line.split()[1].isdigit()}
        return {'total_bytes':info['MemTotal'],'available_bytes':info['MemAvailable']}
    return {'total_bytes':None,'available_bytes':None}


def peak_rss():
    if sys.platform!='win32':
        import resource
        value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value*(1 if sys.platform=='darwin' else 1024))
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(k,ctypes.c_size_t) for k in ('peak','working','quota_peak_paged','quota_paged','quota_peak_nonpaged','quota_nonpaged','pagefile','peak_pagefile')]
    api=ctypes.windll.kernel32;api.GetCurrentProcess.restype=wintypes.HANDLE
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    ctypes.windll.psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    item=Counters();item.cb=ctypes.sizeof(item)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(api.GetCurrentProcess(),ctypes.byref(item),item.cb):raise OSError('Peak RSS query failed')
    return item.peak


def resources(root):
    disk=shutil.disk_usage(root)
    return {'platform':platform.system(),'python':platform.python_version(),'cpu_count':os.cpu_count(),
            'ram':memory(),'disk':{'total_bytes':disk.total,'free_bytes':disk.free},
            'kaggle_runtime_detected':sys.platform=='linux' and Path('/kaggle/working').is_dir()}


def nifti_signature(path):
    import nibabel as nib
    import numpy as np
    image=nib.load(path);digest=hashlib.sha256()
    for k in range(0,image.shape[2],16):digest.update(np.asarray(image.dataobj[:,:,k:k+16]).tobytes(order='C'))
    qform=image.get_qform();sform=image.get_sform()
    return {'shape':list(image.shape),'affine':image.affine.tolist(),'spacing':list(map(float,image.header.get_zooms())),
            'dtype':str(image.get_data_dtype()),'units':list(image.header.get_xyzt_units()),'voxel_sha256_slab16':digest.hexdigest(),
            'qform':None if qform is None else qform.tolist(),'sform':None if sform is None else sform.tolist(),
            'qform_code':int(image.header['qform_code']),'sform_code':int(image.header['sform_code'])}


def signatures(root):
    return {p.relative_to(root).as_posix():nifti_signature(p) for p in sorted(Path(root).rglob('*.nii.gz'))}


def same_geometry(a,b):
    import numpy as np
    if set(a)!=set(b):return False
    for key in a:
        if key in ('affine','spacing','qform','sform'):
            if a[key] is None or b[key] is None:
                if a[key]!=b[key]:return False
            elif not np.allclose(a[key],b[key],atol=1e-6,rtol=0):return False
        elif a[key]!=b[key]:return False
    return True


def rows(path):
    with Path(path).open(encoding='utf-8',newline='') as handle:return list(csv.DictReader(handle))


def identity():
    from lungseg.data.weak import implementation
    from lungseg.data.nsclc_version import conversion_implementation
    return {'weak':implementation(),'nsclc':conversion_implementation()}


def prepare(target,nsclc_ids,weak_ids,xml_archive=None):
    from lungseg.data.nsclc_config import load_nsclc_config
    from lungseg.data.weak_config import load_weak_config
    if not 1<=len(nsclc_ids)<=2 or not 1<=len(weak_ids)<=2 or len(set(nsclc_ids))!=len(nsclc_ids) or len(set(weak_ids))!=len(weak_ids):raise ValueError('Require 1-2 unique existing cases per source')
    configs={'nsclc':load_nsclc_config('configs/nsclc_p1_2_1.yaml'),'weak':load_weak_config('configs/weak_p1_3_1.yaml')}
    selections={'nsclc':nsclc_ids,'weak':weak_ids};planned=[];references={}
    for name,cfg in configs.items():
        manifest=rows(Path(cfg.output_dir)/('manifest_nsclc.csv' if name=='nsclc' else 'manifest_weak.csv'))
        selected=[r for r in manifest if r['patient_id'] in selections[name] and r['conversion_status']=='converted']
        if {r['patient_id'] for r in selected}!=set(selections[name]):raise ValueError('Pilot IDs must have accepted local converted references')
        references[name]=selected
        for patient in selections[name]:
            for p in (Path(cfg.raw_root)/'dicom'/patient).rglob('*'):
                if p.is_file():planned.append((p,Path('raw')/name/p.relative_to(cfg.raw_root)))
        for row in selected:
            fields=('image_path','mask_path','provenance_path') if name=='nsclc' else ('image_path','bbox_path','boxes_path','coverage_path','provenance_path')
            for field in fields:
                p=Path(cfg.converted_root)/row[field]
                if sha(p)!=row[field.replace('_path','_sha256')]:raise ValueError('Reference artifact hash mismatch')
                planned.append((p,Path('reference')/name/row[field]))
    if xml_archive:
        if Path(xml_archive).stat().st_size!=17304054 or sha(xml_archive)!=XML_SHA:raise ValueError('XML reference digest/bytes mismatch')
        planned.append((Path(xml_archive),Path('reference/xml')/Path(xml_archive).name))
    total=sum(p.stat().st_size for p,_ in planned)
    if total>2*GIB:raise ValueError('Pilot bundle exceeds 2 GiB cap')
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(target.parent).free<total+4*GIB:raise OSError('Insufficient disk reserve')
    resolved=target.resolve()
    protected=[Path('data/raw').resolve(),Path('data/converted').resolve(),Path('data/manifests').resolve(),Path('data/qa').resolve()]
    if any(resolved==p or resolved.is_relative_to(p) or p.is_relative_to(resolved) for p in protected):raise ValueError('Bundle overlaps preserved roots')
    target.mkdir()  # Create-only, including interrupted bundles. Nothing is deleted.
    for p,dest in planned:
        if p.is_symlink():raise ValueError('Source symlink is not permitted')
        out=target/dest;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)
    spec={'schema_version':1,'revision':REVISION,'selections':selections,'configs':{k:asdict(v) for k,v in configs.items()},
          'production_implementation':identity(),'reference_signatures':{k:signatures(target/'reference'/k) for k in configs},
          'licenses':{'nsclc':'https://creativecommons.org/licenses/by-nc/3.0/','weak':'https://creativecommons.org/licenses/by/4.0/'},
          'xml_reference':{'sha256':XML_SHA,'included':bool(xml_archive),'role':'immutable_reference_not_production','equivalence':'REVIEW_REQUIRED'},
          'input_payload_bytes':total,'upload_authorized':False,'training_clearance':False}
    write(target/'spec.json',spec);digest=seal(target,'INPUT_ROOT.json')
    return {'status':'PREPARED_LOCAL_ONLY','input_root_sha256':digest,'input_files':len(planned),'payload_bytes':total,
            'upload_performed':False,'cloud_pilot':'NOT_RUN','persistence':'NOT_RUN'}


def probe():
    urls={'IDC':'https://idc-open-data.s3.amazonaws.com/?list-type=2&max-keys=1',
          'TCIA':'https://www.cancerimagingarchive.net/collection/lung-pet-ct-dx/'}
    result={}
    for name,url in urls.items():
        try:
            with urlopen(Request(url,headers={'User-Agent':'lungseg-bounded-connectivity-probe'}),timeout=10) as response:
                result[name]={'status':response.status,'read_bytes':len(response.read(1024)),'reachable':True}
        except Exception as exc:result[name]={'reachable':False,'error_type':type(exc).__name__}
    return result


def worker(input_root,output,name):
    from lungseg.data.nsclc_config import NsclcConfig
    from lungseg.data.weak_config import WeakConfig
    from lungseg.data.nsclc import convert_sample
    from lungseg.data.weak import inventory
    spec=json.loads((input_root/'spec.json').read_text());value=spec['configs'][name]
    value.update(raw_root=str((input_root/'raw'/name).resolve()),sample_patient_ids=spec['selections'][name])
    for key,folder in [('converted_root','converted'),('output_dir','manifests'),('qa_dir','qa'),('evidence_dir','evidence')]:value[key]=str((output/name/folder).resolve())
    cfg=(NsclcConfig if name=='nsclc' else WeakConfig).from_dict(value)
    start=time.perf_counter();result=(convert_sample if name=='nsclc' else inventory)(cfg)
    metric={'wall_seconds':time.perf_counter()-start,'peak_rss_bytes':peak_rss(),
            'input_raw_bytes':sum(p.stat().st_size for p in (input_root/'raw'/name).rglob('*') if p.is_file()),
            'reference_bytes':sum(p.stat().st_size for p in (input_root/'reference'/name).rglob('*') if p.is_file()),
            'output_data_bytes_before_metric':sum(p.stat().st_size for p in (output/name).rglob('*') if p.is_file()),
            'converted_cases':result['converted_cases'],'quarantined_cases':result['quarantined_cases'],
            'annotation_review':'not newly approved','cpu_only':True}
    write(output/name/'metrics.json',metric)
    if metric['converted_cases']!=len(spec['selections'][name]) or metric['quarantined_cases']:raise RuntimeError('Pilot conversion incomplete')


def run(input_root,output,expected,execution_kind,connectivity=False):
    verify(input_root,'INPUT_ROOT.json',expected)
    spec=json.loads((input_root/'spec.json').read_text());current=identity()
    revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if revision!=spec['revision']:raise ValueError('Repository revision differs from pinned input')
    for name in current:
        key='sources' if name=='weak' else 'source_sha256'
        if current[name][key]!=spec['production_implementation'][name][key]:raise ValueError('Production implementation source changed')
    runtime=resources(output.parent)
    if execution_kind=='kaggle' and not runtime['kaggle_runtime_detected']:raise ValueError('Cannot label a local process as Kaggle pilot')
    max_voxels=max(__import__('math').prod(s['shape']) for group in spec['reference_signatures'].values() for s in group.values())
    required_ram=max(GIB,12*max_voxels+768*1024**2)
    # Inputs are never output/cache roots. Reject overlap before creating anything.
    if output.resolve()==input_root.resolve() or output.resolve().is_relative_to(input_root.resolve()) or input_root.resolve().is_relative_to(output.resolve()):raise ValueError('Input/output overlap')
    output.mkdir();checks={}
    admitted=runtime['disk']['free_bytes']>=8*GIB and (runtime['ram']['available_bytes'] or 0)>=required_ram
    write(output/'preflight.json',{'runtime':runtime,'required_available_ram_bytes':required_ram,
                                'required_free_disk_bytes':8*GIB,'admitted':admitted})
    if not admitted:raise OSError(f'Pilot admission blocked: need 8 GiB disk and {required_ram} available RAM bytes; no conversion started')
    try:
        for name in ('nsclc','weak'):
            with (output/(name+'_worker.log')).open('w',encoding='utf-8') as log:
                env={**os.environ,'CUDA_VISIBLE_DEVICES':''}
                proc=subprocess.run([sys.executable,str(Path(__file__).resolve()),'_worker','--input',str(input_root),'--output',str(output),'--dataset',name],env=env,stdout=log,stderr=subprocess.STDOUT)
            if proc.returncode:raise RuntimeError(name+' worker failed; logs retained')
            actual=signatures(output/name/'converted');expected_signatures=spec['reference_signatures'][name]
            equal=set(actual)==set(expected_signatures) and all(same_geometry(actual[k],expected_signatures[k]) for k in actual)
            json_equal=True
            if name=='weak':
                for p in (input_root/'reference/weak').rglob('*.json'):
                    if p.name in ('boxes.json','coverage.json'):
                        other=output/'weak/converted'/p.relative_to(input_root/'reference/weak')
                        json_equal &= json.loads(p.read_text())==json.loads(other.read_text())
            provenance_equal=True
            for p in (input_root/'reference'/name).rglob('provenance.json'):
                previous=json.loads(p.read_text());fresh=json.loads((output/name/'converted'/p.relative_to(input_root/'reference'/name)).read_text())
                fields=('source_files','source_sha256','native_geometry','real_data')
                fields+=('annotation','coordinate_transform','intensity_transforms_in_spatial_order','source_annotation_edited') if name=='nsclc' else ('annotation_reference','intensity_transforms','source_annotation_changed','acquisition_semantics')
                provenance_equal &= all(previous[k]==fresh[k] for k in fields)
            checks[name]={'nifti_arrays_geometry_equal':equal,'annotation_records_coverage_equal':json_equal,
                          'source_geometry_annotation_provenance_equal':provenance_equal,
                          'signatures':actual,'metrics':json.loads((output/name/'metrics.json').read_text()),
                          'runtime_fingerprint_equal_to_local':current[name]==spec['production_implementation'][name]}
            if not equal or not json_equal or not provenance_equal:raise RuntimeError(name+' reference comparison failed')
        verify(input_root,'INPUT_ROOT.json',expected)
        report={'status':'KAGGLE_CPU_PILOT_PASS' if execution_kind=='kaggle' else 'LOCAL_CPU_PILOT_PASS',
                'execution_kind':execution_kind,'session_id':uuid4().hex,'revision':revision,'pilot_kit_sha256':sha(Path(__file__)),
                'input_root_sha256':expected,'runtime':runtime,'required_available_ram_bytes':required_ram,'implementation':current,'checks':checks,
                'source_connectivity':probe() if connectivity else {'status':'NOT_RUN'},
                'persistence_restore_status':'NOT_RUN','training_clearance':False,'input_preserved':True}
        write(output/'run.json',report)
        freeze=subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True,check=True)
        (output/'environment.freeze.txt').write_text(freeze.stdout,encoding='utf-8')
        digest=seal(output,'RESULT_ROOT.json')
        return {'status':report['status'],'result_root_sha256':digest,'checks':checks,'persistence_restore_status':'NOT_RUN'}
    except Exception as exc:
        write(output/'failure.json',{'status':'PILOT_FAILED','error_type':type(exc).__name__,'message':str(exc),'checks':checks})
        raise


def restore(root,expected,fresh_session_attested=False):
    inventory=verify(root,'RESULT_ROOT.json',expected)
    report=json.loads((root/'run.json').read_text());actual={name:signatures(root/name/'converted') for name in ('nsclc','weak')}
    for name,value in actual.items():
        original=report['checks'][name]['signatures']
        if set(value)!=set(original) or not all(same_geometry(value[k],original[k]) for k in value):raise ValueError('Restored array/geometry mismatch')
    is_cloud=resources(root)['kaggle_runtime_detected'] and report['execution_kind']=='kaggle'
    return {'status':'RESTORE_CONTENT_VERIFIED','files_verified':len(inventory),'arrays_geometry_verified':True,
            'annotation_provenance_hashes_verified':True,'previous_session_id':report['session_id'],
            'fresh_session_attested':fresh_session_attested,'actual_kaggle_runtime':is_cloud,
            'session_restore_status':'USER_ATTESTED_FRESH_SESSION_CONTENT_PASS' if is_cloud and fresh_session_attested else 'NOT_VERIFIED_NEW_CLOUD_SESSION',
            'source_receipt_sha256':expected,'training_clearance':False}


def assess(output):
    roots=['data/raw/Task06_Lung','data/raw/archives','data/raw/NSCLC-Radiomics','data/raw/Lung-PET-CT-Dx',
           'data/converted/nsclc','data/converted/nsclc_p1_2_1_v2','data/converted/weak_v1','data/converted/weak_v1_1','data/converted/weak_p1_3_1_v2']
    stats={}
    for name in roots:
        paths=[p for p in Path(name).rglob('*') if p.is_file()]
        stats[name]={'files':len(paths),'bytes':sum(p.stat().st_size for p in paths),'status':'measured' if Path(name).is_dir() else 'missing'}
    report={'status':'LOCAL_MEASURED_CLOUD_NOT_RUN','runtime':resources(Path.cwd()),'trees':stats,
            'xml_reference_bytes':17304054,'xml_reference_sha256':XML_SHA,'source_connectivity':probe(),
            'production_implementation':identity(),'actual_kaggle_account_limits':'NOT_VERIFIED','cloud_pilot':'NOT_RUN','session_restore':'NOT_RUN'}
    write(output,report);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('assess');p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('prepare');p.add_argument('--output',type=Path,required=True);p.add_argument('--nsclc',nargs='+',default=['LUNG1-001']);p.add_argument('--weak',nargs='+',default=['Lung_Dx-A0003']);p.add_argument('--xml-archive',type=Path)
    p=sub.add_parser('run');p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-root-sha256',required=True);p.add_argument('--execution-kind',choices=('local','kaggle'),default='local');p.add_argument('--probe-connectivity',action='store_true')
    p=sub.add_parser('restore');p.add_argument('--input',type=Path,required=True);p.add_argument('--expected-root-sha256',required=True);p.add_argument('--fresh-session-attested',action='store_true');p.add_argument('--report',type=Path,required=True)
    p=sub.add_parser('_worker');p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--dataset',choices=('nsclc','weak'),required=True)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.output,args.nsclc,args.weak,args.xml_archive)
    elif args.command=='assess':result=assess(args.output)
    elif args.command=='run':result=run(args.input,args.output,args.expected_root_sha256,args.execution_kind,args.probe_connectivity)
    elif args.command=='restore':
        if args.report.resolve().is_relative_to(args.input.resolve()):raise ValueError('Restore report must be outside immutable source root')
        result=restore(args.input,args.expected_root_sha256,args.fresh_session_attested);write(args.report,result)
    else:worker(args.input,args.output,args.dataset);return
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__':main()
