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
from threading import Lock
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


class DownloadBudget:
    """Cap selected raw bytes (verified cache + new payload), not catalog estimates."""
    def __init__(self,limit):
        if type(limit) is not int or limit<0:raise ValueError('Budget must be nonnegative integer bytes')
        self.limit=limit;self.selected_bytes=0;self.cache_bytes=0;self.network_bytes=0;self.decisions=[];self.lock=Lock()

    def claim(self,uid,size,*,cached):
        if type(size) is not int or size<=0:raise ValueError('Series listing/cache bytes must be positive integers')
        remaining=self.limit-self.selected_bytes
        self.decisions.append({'series_uid':uid,'actual_listing_or_verified_cache_bytes':size,
                               'remaining_before':remaining,'cached':cached,'accepted':size<=remaining})
        if size>remaining:raise OSError('Actual series bytes exceed remaining explicit sample budget; no payload requested or published')
        self.selected_bytes+=size
        if cached:self.cache_bytes+=size

    def received(self,size):
        with self.lock:self.network_bytes+=size

    def report(self):
        return {'sample_byte_cap':self.limit,'selected_raw_bytes':self.selected_bytes,
                'existing_verified_cache_bytes':self.cache_bytes,'network_payload_bytes_this_run':self.network_bytes,
                'remaining_selected_byte_budget':self.limit-self.selected_bytes,'budget_decisions':self.decisions}


def download_series(record,raw_root,*,budget):
    uid=record['SeriesInstanceUID'];patient=record['PatientID']
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',uid) or not re.fullmatch(r'Lung_Dx-[ABEG]\d{4}',patient):raise ValueError('Unsafe public identifiers')
    destination=raw_root/'dicom'/patient/uid
    expected={'PatientID':patient,'StudyInstanceUID':record['StudyInstanceUID'],'SeriesInstanceUID':uid,'Modality':record['Modality']}
    if destination.exists():
        info=json.loads((destination/'source.json').read_text())
        if info.get('catalog_identity')!=expected or info.get('source_doi','').lower()!=record['source_DOI'].lower() or info.get('license_url')!=LICENSE_URL or len(info['objects'])!=record['instanceCount']:
            raise ValueError('Existing raw provenance disagrees; preserve it')
        paths=[]
        for obj in info['objects']:
            if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',obj['sop_uid']) or file_sha256(destination/(obj['sop_uid']+'.dcm'))!=obj['sha256']:raise ValueError('Raw checksum mismatch; no overwrite')
            path=destination/(obj['sop_uid']+'.dcm');paths.append(path)
            if path.stat().st_size!=obj['bytes']:raise ValueError('Raw object byte count mismatch')
            ds=pydicom.dcmread(path,stop_before_pixels=True)
            if any(str(getattr(ds,k,''))!=v for k,v in expected.items()) or str(ds.SOPInstanceUID)!=obj['sop_uid']:raise ValueError('Cached header identity mismatch')
        total=sum(p.stat().st_size for p in paths)
        if len(set(paths))!=len(paths) or set(destination.glob('*.dcm'))!=set(paths) or total!=info['bytes'] or info.get('transport')!='official_IDC_S3':raise ValueError('Raw cache incomplete/unlisted/byte mismatch')
        budget.claim(uid,total,cached=True)
        return info
    base,objects=list_objects(record['series_aws_url'])
    if any(type(o['bytes']) is not int or o['bytes']<=0 for o in objects):raise ValueError('Invalid object listing size')
    total=sum(o['bytes'] for o in objects)
    if len(objects)!=record['instanceCount'] or total>record['series_size_MB']*1e6*1.05+2*1024**2:raise ValueError('IDC size/count mismatch')
    budget.claim(uid,total,cached=False)
    require_space(raw_root,total+4*1024**3)
    stage=raw_root/'staging'/(uid+'.partial-'+uuid4().hex[:8]);stage.mkdir(parents=True)
    def fetch(obj):
        with urlopen(base+obj['key'],timeout=60) as response:
            length=response.headers.get('Content-Length')
            if length is not None and int(length)!=obj['bytes']:raise ValueError('Payload Content-Length differs from listing')
            # Bound every read by the reserved listing size, including failed transfers.
            chunks=[];remaining=obj['bytes']
            while remaining:
                chunk=response.read(min(1024**2,remaining))
                if not chunk:break
                budget.received(len(chunk));chunks.append(chunk);remaining-=len(chunk)
            raw=b''.join(chunks)
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
    budget=DownloadBudget(config.max_download_bytes)
    plan.update(status='running',downloaded=results,selected_cases=mapping)
    write_json(target,plan)
    try:
        for sr_record in selected:
            result=download_series(sr_record,Path(config.raw_root),budget=budget);results.append(result)
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
        if not annotations_only:
            for ct_record in ct_records:
                results.append(download_series(ct_record,Path(config.raw_root),budget=budget))
                plan.update(budget.report())
                write_json(target,plan)
        plan.update(status='ANNOTATION_SAMPLE_ACQUIRED' if annotations_only else 'CT_SR_SAMPLE_ACQUIRED',planned_sample_raw_bytes=planned,
                    actual_downloaded_bytes=sum(r['bytes'] for r in results),
                    **budget.report())
    except Exception as exc:
        plan.update(status='PARTIAL_ACQUISITION_FAILURE',error=f'{type(exc).__name__}: {exc}',**budget.report())
    write_json(target,plan)
    return plan
