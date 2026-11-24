"""Official IDC original CT/PT metadata + harmonized expert SR; bounded samples."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
from urllib.request import urlopen
from uuid import uuid4
import pydicom

from lungseg.data.msd_acquire import file_sha256, require_space
from lungseg.data.nsclc_idc import INDEX_URL, list_objects
from lungseg.data.weak_boxes import evidence_reference
from lungseg.runs import utc_now, write_json

LICENSE_URL='https://creativecommons.org/licenses/by/4.0/'
IMAGE_DOI='10.7937/tcia.2020.nnc2-0461'
ANNOTATION_DOI='10.5281/zenodo.16989819'


def load_catalog(path):
    value=json.loads(Path(path).read_text())
    if value.get('source')!=INDEX_URL or not re.fullmatch(r'[a-f0-9]{64}',value.get('index_sha256','')):
        raise ValueError('Expected official IDC index source/hash')
    rows=value['series']
    seen=set()
    for row in rows:
        if row['collection_id']!='lung_pet_ct_dx' or row['license_short_name']!='CC BY 4.0':raise ValueError('Collection/license changed')
        if not re.fullmatch(r'Lung_Dx-[ABEG]\d{4}',row['PatientID']):raise ValueError('Only verified public IDs may be exported')
        expected=ANNOTATION_DOI if row['Modality']=='SR' else IMAGE_DOI
        if row['Modality'] not in ('CT','PT','SR') or row['source_DOI'].lower()!=expected:raise ValueError('No AI/other analysis annotation allowed')
        for field in ('StudyInstanceUID','SeriesInstanceUID'):
            if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',row[field]):raise ValueError('Invalid catalog UID')
        if row['SeriesInstanceUID'] in seen:raise ValueError('Duplicate catalog series')
        seen.add(row['SeriesInstanceUID'])
        if type(row['instanceCount']) is not int or row['instanceCount']<=0 or not math.isfinite(row['series_size_MB']) or row['series_size_MB']<=0:
            raise ValueError('Missing positive object count/size')
    return rows


def capacity_plan(config,rows):
    stats={m:{'series':sum(r['Modality']==m for r in rows),'objects':sum(r['instanceCount'] for r in rows if r['Modality']==m),
              'bytes':round(sum(r['series_size_MB']*1e6 for r in rows if r['Modality']==m))} for m in ('CT','PT','SR')}
    originals=[r for r in rows if r['Modality']!='SR']
    full=stats['CT']['bytes']+stats['SR']['bytes']+math.ceil(2.5*stats['CT']['bytes'])+config.reserve_bytes
    free=require_space(Path(config.raw_root),0)
    converted_free=require_space(Path(config.converted_root),0)
    same_volume=Path(config.raw_root).resolve().anchor.lower()==Path(config.converted_root).resolve().anchor.lower()
    sample_required=math.ceil(3.5*config.max_download_bytes)+config.reserve_bytes
    sample_ok=(free>=sample_required if same_volume else free>=config.max_download_bytes+config.reserve_bytes and converted_free>=2.5*config.max_download_bytes+config.reserve_bytes)
    full_ok=(free>=full if same_volume else free>=stats['CT']['bytes']+stats['SR']['bytes']+config.reserve_bytes and converted_free>=2.5*stats['CT']['bytes']+config.reserve_bytes)
    report={'timestamp_utc':utc_now(),'dataset':'Lung-PET-CT-Dx','metadata_only':True,'modality_counts':stats,
            'original_patients':len({r['PatientID'] for r in originals}),'original_studies':len({r['StudyInstanceUID'] for r in originals}),
            'original_series':len(originals),'sr_patients':len({r['PatientID'] for r in rows if r['Modality']=='SR'}),
            'raw_free_bytes':free,'converted_free_bytes':converted_free,'same_volume':same_volume,
            'full_ct_sr_conversion_plan_bytes':full,'full_status':'NOT_AUTHORIZED' if full_ok else 'BLOCKED_STORAGE',
            'sample_max_raw_bytes':config.max_download_bytes,'sample_planning_bytes':sample_required,'sample_capacity_pass':sample_ok,
            'estimate':'2.5x CT bytes conversion allowance, not a measured compressed size; PT not requested',
            'config_sha256':config.sha256}
    write_json(Path(config.evidence_dir)/'capacity_plan.json',report)
    return report


def download_series(record,raw_root):
    uid=record['SeriesInstanceUID'];patient=record['PatientID']
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',uid) or not re.fullmatch(r'Lung_Dx-[ABEG]\d{4}',patient):raise ValueError('Unsafe public identifiers')
    destination=raw_root/'dicom'/patient/uid
    expected={'PatientID':patient,'StudyInstanceUID':record['StudyInstanceUID'],'SeriesInstanceUID':uid,'Modality':record['Modality']}
    if destination.exists():
        info=json.loads((destination/'source.json').read_text())
        if info.get('catalog_identity')!=expected or info.get('source_doi','').lower()!=record['source_DOI'].lower() or info.get('license_url')!=LICENSE_URL or len(info['objects'])!=record['instanceCount']:
            raise ValueError('Existing raw provenance disagrees; preserve it')
        for obj in info['objects']:
            if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',obj['sop_uid']) or file_sha256(destination/(obj['sop_uid']+'.dcm'))!=obj['sha256']:raise ValueError('Raw checksum mismatch; no overwrite')
        return info
    base,objects=list_objects(record['series_aws_url'])
    total=sum(o['bytes'] for o in objects)
    if len(objects)!=record['instanceCount'] or total>record['series_size_MB']*1e6*1.05+2*1024**2:raise ValueError('IDC size/count mismatch')
    require_space(raw_root,total+4*1024**3)
    stage=raw_root/'staging'/(uid+'.partial-'+uuid4().hex[:8]);stage.mkdir(parents=True)
    def fetch(obj):
        with urlopen(base+obj['key'],timeout=60) as response:raw=response.read(obj['bytes']+1)
        if len(raw)!=obj['bytes'] or hashlib.md5(raw).hexdigest()!=obj['md5']:raise ValueError('IDC byte count/MD5 mismatch')
        ds=pydicom.dcmread(BytesIO(raw),stop_before_pixels=True)
        if any(str(getattr(ds,k,''))!=v for k,v in expected.items()):raise ValueError('Header/catalog identity mismatch')
        sop=str(ds.SOPInstanceUID)
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',sop):raise ValueError('Invalid SOP UID')
        with (stage/(sop+'.dcm')).open('xb') as handle:handle.write(raw)
        return {'sop_uid':sop,'key':obj['key'],'bytes':len(raw),'md5':obj['md5'],'sha256':hashlib.sha256(raw).hexdigest()}
    with ThreadPoolExecutor(max_workers=4) as executor:verified=list(executor.map(fetch,objects))
    info={'catalog_identity':expected,'source_doi':record['source_DOI'],'license_url':LICENSE_URL,
          'source_url':record['series_aws_url'],'transport':'official_IDC_S3','bytes':total,
          'objects':sorted(verified,key=lambda o:o['sop_uid']),'timestamp_utc':utc_now()}
    write_json(stage/'source.json',info);destination.parent.mkdir(parents=True,exist_ok=True);os.rename(stage,destination)
    return info


def acquire(config,catalog_path,*,download=False,annotations_only=False):
    rows=load_catalog(catalog_path);plan=capacity_plan(config,rows)
    plan['catalog_sha256']=file_sha256(Path(catalog_path))
    if not download:return plan
    if not plan['sample_capacity_pass']:raise OSError('Sample capacity preflight failed; no download')
    selected=[]
    for patient in config.sample_patient_ids:
        candidates=[r for r in rows if r['PatientID']==patient and r['Modality']=='SR']
        if not candidates:raise ValueError('Requested sample patient has no expert SR catalog entry')
        selected.append(sorted(candidates,key=lambda r:(r['StudyInstanceUID'],r['SeriesInstanceUID']))[0])
    results=[];mapping=[];target=Path(config.evidence_dir)/'acquisition.json'
    existing={p.parent.name for p in (Path(config.raw_root)/'dicom').rglob('source.json')}
    plan.update(status='running',downloaded=results,selected_cases=mapping)
    write_json(target,plan)
    try:
        for sr_record in selected:
            result=download_series(sr_record,Path(config.raw_root));results.append(result)
            source=Path(config.raw_root)/'dicom'/sr_record['PatientID']/sr_record['SeriesInstanceUID']
            files=list(source.glob('*.dcm'))
            if len(files)!=1:raise ValueError('Expected one SR instance per surveyed SR series')
            ref=evidence_reference(pydicom.dcmread(files[0]))
            ct=[r for r in rows if r['SeriesInstanceUID']==ref['series_uid'] and r['StudyInstanceUID']==ref['study_uid'] and r['PatientID']==sr_record['PatientID'] and r['Modality']=='CT']
            if len(ct)!=1:raise ValueError('Referenced CT identity unavailable in official catalog')
            mapping.append({'patient_id':sr_record['PatientID'],'sr_series_uid':sr_record['SeriesInstanceUID'],
                            'ct_series_uid':ref['series_uid'],'study_uid':ref['study_uid']})
        ct_records=[next(r for r in rows if r['SeriesInstanceUID']==m['ct_series_uid']) for m in mapping]
        planned=round(sum(r['series_size_MB']*1e6 for r in selected+ct_records))
        if planned>config.max_download_bytes:raise OSError('Selected CT+SR exceeds explicit sample byte cap; no CT downloaded')
        if not annotations_only:
            for ct_record in ct_records:
                results.append(download_series(ct_record,Path(config.raw_root)))
                if sum(r['bytes'] for r in results)>config.max_download_bytes:raise OSError('Actual byte cap exceeded')
                write_json(target,plan)
        plan.update(status='ANNOTATION_SAMPLE_ACQUIRED' if annotations_only else 'CT_SR_SAMPLE_ACQUIRED',planned_sample_raw_bytes=planned,
                    actual_downloaded_bytes=sum(r['bytes'] for r in results),
                    network_payload_bytes_this_run=sum(r['bytes'] for r in results if r['catalog_identity']['SeriesInstanceUID'] not in existing))
    except Exception as exc:
        plan.update(status='PARTIAL_ACQUISITION_FAILURE',error=f'{type(exc).__name__}: {exc}');write_json(target,plan);raise
    write_json(target,plan)
    return plan
