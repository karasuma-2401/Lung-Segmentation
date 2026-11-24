"""Weak-only source ledger, acquisition semantics and command result contract."""
import json
from pathlib import Path
import re
import pydicom
from lungseg.data.msd_acquire import file_sha256
from lungseg.data.weak_acquire import LICENSE_URL, IMAGE_DOI, ANNOTATION_DOI
from lungseg.data.weak_boxes import parse_sr

RECORD_FIELDS=('record_type','patient_id','observed_patient_id','sr_sop_uid','sr_series_uid','source_path','sha256',
               'declared_sop_uid','declared_series_uid','ct_references','status','reason','ct_case_ids','ct_case_results')


def scan_sources(config, *, synthetic=False):
    root=Path(config.raw_root)
    if not root.is_dir():raise FileNotFoundError('Acquire bounded weak sample first')
    items=[];errors={};seen={}
    for patient in sorted(config.sample_patient_ids):
        folders=sorted(p for p in (root/'dicom'/patient).glob('*') if p.is_dir())
        if not folders:errors[patient]='missing_patient_acquisition'
        for folder in folders:
            source={};identity={};folder_error=None;marker=folder/'source.json'
            try:
                source=json.loads(marker.read_text())
                if not isinstance(source,dict):source={};raise ValueError('invalid_source_marker')
                identity=source['catalog_identity']
                if not isinstance(identity,dict):identity={};raise ValueError('invalid_catalog_identity')
                modality=identity['Modality']
                if identity['PatientID']!=patient or source.get('synthetic',False)!=synthetic or source.get('license_url')!=LICENSE_URL:
                    raise ValueError('unverified_origin_or_synthetic_fixture')
                if not synthetic and (source.get('transport')!='official_IDC_S3' or source.get('source_doi','').lower()!=(ANNOTATION_DOI if modality=='SR' else IMAGE_DOI)):
                    raise ValueError('unverified_source_doi_transport')
                if not isinstance(source.get('objects'),list):source['objects']=[];raise ValueError('invalid_source_objects')
                if not source['objects']:raise ValueError('empty_source_objects')
                if len({o['sop_uid'] for o in source['objects']})!=len(source['objects']):raise ValueError('duplicate_source_object_record')
            except Exception as exc:
                folder_error=f'acquisition_source_error:{type(exc).__name__}:{exc}'
                errors[patient]=folder_error
            objects=source.get('objects',[])
            if not isinstance(objects,list):objects=[]
            declared={o.get('sop_uid'):o for o in objects if isinstance(o,dict)}
            paths={p.name:p for p in folder.glob('*.dcm')}
            for sop in declared:
                if isinstance(sop,str) and re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',sop):paths.setdefault(sop+'.dcm',folder/(sop+'.dcm'))
                else:errors[patient]='unsafe_declared_sop_uid'
            if not paths:errors[patient]=folder_error or 'missing_or_unlisted_raw_files'
            for name,path in sorted(paths.items()):
                sop=name[:-4];obj=declared.get(sop);ds=None;sha=None;reason=folder_error
                try:
                    sha=file_sha256(path)
                    ds=pydicom.dcmread(path,stop_before_pixels=True)
                    if reason:raise ValueError(reason)
                    if obj is None:raise ValueError('unlisted_raw_file')
                    if sha!=obj['sha256']:raise ValueError('raw_checksum_mismatch')
                    if any(str(getattr(ds,k,''))!=v for k,v in identity.items()) or str(getattr(ds,'SOPInstanceUID',''))!=sop:
                        raise ValueError('raw_header_identity_mismatch')
                    if sop in seen:
                        previous=seen[sop];previous['source_error']='duplicate_sop_instance_uid'
                        errors[previous['patient_id']]='duplicate_sop_instance_uid'
                        raise ValueError('duplicate_sop_instance_uid')
                except Exception as exc:
                    reason=reason or f'acquisition_object_error:{type(exc).__name__}:{exc}'
                    errors[patient]=reason
                entry={'path':path,'header':ds,'sha256':sha,'marker_sha256':file_sha256(marker) if marker.is_file() else None,
                       'patient_id':patient,'declared_identity':identity,'declared_sop_uid':sop if obj else None,
                       'annotation_expected':identity.get('Modality')=='SR' or (ds is not None and str(getattr(ds,'Modality',''))=='SR'),
                       'source_error':reason,'exists':path.is_file()}
                items.append(entry)
                if not reason:seen[sop]=entry
    return items,errors


def raw_references(ds):
    """Trace observed evidence only; these references are not validated mappings."""
    result=[]
    for study in getattr(ds,'CurrentRequestedProcedureEvidenceSequence',[]):
        for series in getattr(study,'ReferencedSeriesSequence',[]):
            result.append({'study_uid':str(study.StudyInstanceUID) if hasattr(study,'StudyInstanceUID') else None,
                           'series_uid':str(series.SeriesInstanceUID) if hasattr(series,'SeriesInstanceUID') else None,
                           'sops':[{'sop_uid':str(getattr(s,'ReferencedSOPInstanceUID','')),
                                    'sop_class_uid':str(getattr(s,'ReferencedSOPClassUID',''))}
                                   for s in getattr(series,'ReferencedSOPSequence',[])]})
    return result


def annotation_records(items,root):
    records=[];parsed={}
    for i in items:
        if not i['annotation_expected']:continue
        ds=i['header']
        row={'record_type':'annotation_source','patient_id':i['patient_id'],
             'observed_patient_id':str(ds.PatientID) if ds is not None and hasattr(ds,'PatientID') else None,
             'sr_sop_uid':str(ds.SOPInstanceUID) if ds is not None and hasattr(ds,'SOPInstanceUID') else None,
             'sr_series_uid':str(ds.SeriesInstanceUID) if ds is not None and hasattr(ds,'SeriesInstanceUID') else None,
             'declared_sop_uid':i['declared_sop_uid'],'declared_series_uid':i['declared_identity'].get('SeriesInstanceUID'),
             'source_path':i['path'].relative_to(root).as_posix(),'sha256':i['sha256'],
             'ct_references':raw_references(ds) if ds is not None else [],'status':'failed','reason':i['source_error']}
        if not row['reason']:
            try:
                parsed[row['source_path']]=parse_sr(ds);row.update(status='parsed',reason=None)
            except Exception as exc:row['reason']=f'{type(exc).__name__}:{exc}'
        records.append(row)
    return records,parsed


def acquisition_semantics(headers):
    """Independent of geometry validity. Multiple acquisition numbers alone do not reject."""
    fields=('AcquisitionNumber','TemporalPositionIdentifier','ImageType','NumberOfTemporalPositions')
    values={};missing={}
    for field in fields:
        observed=[];absent=0
        for ds in headers:
            value=getattr(ds,field,None)
            if value is None or str(value)=='':absent+=1;continue
            if field=='ImageType':
                value=tuple(str(v).upper() for v in (value.split('\\') if isinstance(value,str) else value))
                if not value:absent+=1;continue
            else:value=str(value)
            observed.append(value)
        values[field]=sorted(set(observed));missing[field]=absent
    findings=[]
    temporal_mixed=len(values['TemporalPositionIdentifier'])>1 or any(v!='1' for v in values['NumberOfTemporalPositions'])
    if temporal_mixed:findings.append('mixed_or_multiple_temporal_positions')
    if len(values['AcquisitionNumber'])>1:findings.append('multiple_acquisition_numbers_semantics_require_review')
    if len(values['ImageType'])>1:findings.append('mixed_image_type_requires_review')
    required=('AcquisitionNumber','TemporalPositionIdentifier','ImageType')
    if any(missing[k] for k in required):findings.append('incomplete_acquisition_metadata')
    status='suspicious' if any(f!='incomplete_acquisition_metadata' for f in findings) else 'unknown' if findings else 'verified'
    return {'status':status,'observed_values':values,'missing_object_counts':missing,'findings':findings,
            'reject_mixed_temporal':temporal_mixed,'scope':'metadata consistency only; native geometry validated separately'}


def command_exit_code(command,result):
    """0=scope complete, 2=usable partial/review findings, 1=fatal exception (CLI)."""
    if command=='acquire-weak':
        if result.get('status')=='PARTIAL_ACQUISITION_FAILURE':return 2
        if result.get('metadata_only'):return 0 if result['sample_capacity_pass'] else 2
        return 0 if result.get('status') in ('CT_SR_SAMPLE_ACQUIRED','ANNOTATION_SAMPLE_ACQUIRED') else 2
    if command=='survey-weak':return 2 if result.get('errors') or result.get('annotation_failure_count') else 0
    return 2 if result.get('actionable_findings') or result.get('quarantined_cases') or result.get('excluded_cases') or result.get('acquisition_errors') or result.get('annotation_failure_count') else 0
