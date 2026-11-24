"""T06 native CT + expert SR bbox inventory. No segmentation GT, splits or training."""
from collections import Counter,defaultdict
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
from uuid import uuid4
import nibabel as nib
import numpy as np
import pydicom
from pydicom.uid import CTImageStorage

from lungseg.data.dicom_geometry import DataIssue,build_ct_geometry,read_ct_pixels
from lungseg.data.msd import inspect_nifti,write_manifest
from lungseg.data.msd_acquire import file_sha256,require_space
from lungseg.data.nsclc import save_nifti
from lungseg.data.weak_acquire import LICENSE_URL,IMAGE_DOI,ANNOTATION_DOI
from lungseg.data.weak_boxes import parse_sr,rasterize_boxes,evidence_reference
from lungseg.runs import utc_now,write_json

FIELDS=('schema_version','dataset','case_id','patient_id','patient_id_source','study_uid','series_uid','sr_sop_uid','sr_series_uid',
 'modality','image_type','ct_eligible','paper_filter_eligible','ct_source_paths','annotation_source_paths','source_files','source_sha256',
 'annotation_kind','ground_truth_available','annotation_coverage_status','box_count','annotated_slice_count','missing_slice_count',
 'explicit_negative_slice_count','multiple_box_slice_count','duplicate_box_geometry_count','finding_codes','coordinate_convention',
 'native_geometry','image_shape','image_spacing_mm','image_affine','image_orientation','slice_center_span_mm','physical_z_extent_mm',
 'anatomical_si_extent_mm','physical_extent_convention','image_path','bbox_path','coverage_path','boxes_path',
 'image_sha256','bbox_sha256','coverage_sha256','boxes_sha256','provenance_path','provenance_sha256',
 'label_values','bbox_foreground_voxels','bbox_envelope_volume_mm3','geometry_aligned','conversion_status','weak_eligible',
 'weak_eligibility_status','qc_errors','qc_warnings','config_sha256','implementation_fingerprint_sha256')


def implementation():
    root=Path(__file__).resolve().parents[1]
    names=('data/weak.py','data/weak_boxes.py','data/weak_config.py','data/weak_acquire.py','data/weak_qa.py',
           'data/dicom_geometry.py','data/nsclc.py','data/msd.py','data/msd_acquire.py','data/nsclc_idc.py')
    value={'version':'weak-sr-native-v1','sources':{n:hashlib.sha256((root/n).read_text(encoding='utf-8').encode()).hexdigest() for n in names},
           'runtime':{'python':platform.python_version(),**{n:version(n) for n in ('numpy','nibabel','pydicom')}}}
    return {**value,'sha256':hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def ct_type_eligible(ds):
    if str(getattr(ds,'Modality',''))!='CT':return False,'non_ct_modality'
    if str(getattr(ds,'SOPClassUID',''))!=str(CTImageStorage):return False,'non_classic_ct_sop'
    raw_type=getattr(ds,'ImageType',[])
    image_type=[str(x).upper() for x in (raw_type.split('\\') if isinstance(raw_type,str) else raw_type)]
    if any(token in {'LOCALIZER','SCOUT','FUSED','MIP','MPR','SECONDARY'} for token in image_type) or hasattr(ds,'SecondaryCaptureDeviceID'):
        return False,'localizer_fused_or_secondary_capture'
    if 'DERIVED' in image_type:return False,'derived_ct_requires_review'
    return True,None


def physical_extent(geometry):
    span=float(geometry.slice_positions[-1]-geometry.slice_positions[0])
    edge=span+geometry.slice_spacing_mm
    shape=geometry.shape
    corners=np.array([[x,y,z,1] for x in (-.5,shape[0]-.5) for y in (-.5,shape[1]-.5) for z in (-.5,shape[2]-.5)])
    world=(geometry.affine_lps@corners.T).T[:,:3]
    return span,edge,float(np.ptp(world[:,2]))


def extent_eligible(extent_mm,config):
    return bool(np.isfinite(extent_mm) and config.min_extent_mm<=extent_mm<=config.max_extent_mm)


def scan(config,*,synthetic=False):
    root=Path(config.raw_root)
    if not root.is_dir():raise FileNotFoundError('Acquire bounded weak sample first')
    items=[];errors={};seen={}
    for patient in sorted(config.sample_patient_ids):
        try:
            folders=sorted((root/'dicom'/patient).iterdir())
            if not folders:raise DataIssue('missing_patient_acquisition')
            for folder in folders:
                marker=folder/'source.json';source=json.loads(marker.read_text())
                identity=source['catalog_identity'];modality=identity['Modality']
                if identity['PatientID']!=patient or source.get('synthetic',False)!=synthetic or source.get('license_url')!=LICENSE_URL:
                    raise DataIssue('unverified_origin_or_synthetic_fixture')
                if not synthetic and (source.get('transport')!='official_IDC_S3' or source.get('source_doi','').lower()!=(ANNOTATION_DOI if modality=='SR' else IMAGE_DOI)):
                    raise DataIssue('unverified_source_doi_transport')
                expected=[]
                for obj in source['objects']:
                    sop=obj['sop_uid']
                    import re
                    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',sop):raise DataIssue('unsafe_sop_uid')
                    path=folder/(sop+'.dcm');expected.append(path)
                    sha=file_sha256(path)
                    if sha!=obj['sha256']:raise DataIssue('raw_checksum_mismatch')
                    ds=pydicom.dcmread(path,stop_before_pixels=True)
                    if any(str(getattr(ds,k,''))!=v for k,v in identity.items()) or str(ds.SOPInstanceUID)!=sop:raise DataIssue('raw_header_identity_mismatch')
                    if sop in seen:
                        errors[seen[sop]]='duplicate_sop_instance_uid'
                        raise DataIssue('duplicate_sop_instance_uid')
                    seen[sop]=patient
                    items.append({'path':path,'header':ds,'sha256':sha,'marker_sha256':file_sha256(marker)})
                if not expected or set(folder.glob('*.dcm'))!=set(expected):raise DataIssue('missing_or_unlisted_raw_files')
        except Exception as exc:
            errors[patient]=str(exc) if isinstance(exc,DataIssue) else f'acquisition_read_error:{type(exc).__name__}'
    return items,errors


def survey(config,*,synthetic=False):
    items,errors=scan(config,synthetic=synthetic);cases=[]
    for item in items:
        ds=item['header']
        if ds.Modality!='SR':continue
        try:
            parsed=parse_sr(ds);counts=Counter(b['sop_uid'] for b in parsed['boxes'])
            cases.append({k:parsed[k] for k in ('patient_id','sr_study_uid','sr_series_uid','sr_sop_uid','ct_reference','duplicate_box_geometry_count')}
                         | {'box_count':len(parsed['boxes']),'annotated_slices':len(counts),'multiple_box_slices':sum(n>1 for n in counts.values()),
                            'finding_codes':sorted({tuple(b['finding_code']) for b in parsed['boxes']}),
                            'coordinate_convention':'DICOM SCOORD zero-based continuous pixel edges, x=column/y=row; center=i+.5',
                            'missing_is_negative':False,'original_XML_equivalence_verified_locally':False})
        except DataIssue as exc:errors[str(ds.PatientID)]=str(exc)
    report={'timestamp_utc':utc_now(),'dataset':'Lung-PET-CT-Dx','real_data':False if synthetic else True if cases else None,
            'format':'expert XML harmonized to DICOM SR by IDC, DOI10.5281/zenodo.16989819','cases':cases,'errors':errors,
            'negative_coverage':'not established; COMPLETE SR is not exhaustive slice coverage','config_sha256':config.sha256}
    write_json(Path(config.output_dir)/'annotation_survey.json',report)
    return report


def validate_case(config,patient,study_uid,ct_uid,sr_items,ct_items,*,synthetic=False):
    ident=implementation();root=Path(config.raw_root);destination=Path(config.converted_root)/(patient+'__'+ct_uid)
    sources=sorted([{'path':i['path'].relative_to(root).as_posix(),'sha256':i['sha256'],'marker_sha256':i['marker_sha256']} for i in sr_items+ct_items],key=lambda r:r['path'])
    source_sha=hashlib.sha256(json.dumps(sources,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    row={k:None for k in FIELDS}
    row.update(schema_version=1,dataset='Lung-PET-CT-Dx',case_id=destination.name,patient_id=patient,
      patient_id_source='synthetic_fixture' if synthetic else 'IDC_public_PatientID_verified_against_DICOM',study_uid=study_uid,series_uid=ct_uid,
      source_files=sources,source_sha256=source_sha,annotation_kind='weak_expert_bbox_SR_not_segmentation_GT',ground_truth_available=False,
      annotation_coverage_status='unknown',conversion_status='quarantined',ct_eligible=False,paper_filter_eligible=False,weak_eligible=False,
      weak_eligibility_status='not_cleared_for_training',qc_errors=[],qc_warnings=[],config_sha256=config.sha256,
      implementation_fingerprint_sha256=ident['sha256'],ct_source_paths=[i['path'].relative_to(root).as_posix() for i in ct_items],
      annotation_source_paths=[i['path'].relative_to(root).as_posix() for i in sr_items],geometry_aligned=False)
    try:
        if not ct_items:raise DataIssue('referenced_ct_series_unavailable')
        raw_type=getattr(ct_items[0]['header'],'ImageType',[])
        row.update(modality=str(ct_items[0]['header'].Modality),image_type=raw_type.split('\\') if isinstance(raw_type,str) else list(raw_type))
        for i in ct_items:
            eligible,reason=ct_type_eligible(i['header'])
            if not eligible:
                row['conversion_status']='excluded';raise DataIssue(reason)
        if any(i['header'].StudyInstanceUID!=study_uid or i['header'].PatientID!=patient for i in ct_items):raise DataIssue('ct_identity_group_mismatch')
        geometry=build_ct_geometry([i['header'] for i in ct_items],config)
        row.update(ct_eligible=True,native_geometry=geometry.to_dict(),image_shape=list(geometry.shape),
                   image_spacing_mm=np.linalg.norm(geometry.affine_ras[:3,:3],axis=0).tolist(),image_affine=geometry.affine_ras.tolist(),
                   image_orientation=''.join(nib.aff2axcodes(geometry.affine_ras)))
        span,extent,world_z=physical_extent(geometry)
        row.update(slice_center_span_mm=span,physical_z_extent_mm=extent,anatomical_si_extent_mm=world_z,
                   physical_extent_convention='slice-normal voxel-edge FOV: projected IPP span + median gap; closed [160,600] mm')
        row['paper_filter_eligible']=extent_eligible(extent,config)
        if not row['paper_filter_eligible']:
            row['conversion_status']='excluded';raise DataIssue('physical_extent_outside_paper_range',f'extent_mm={extent}')
        if int(np.prod(geometry.shape))>config.max_volume_voxels:raise DataIssue('sample_volume_memory_budget_exceeded')
        if len(sr_items)!=1:raise DataIssue('ambiguous_or_missing_annotation_report')
        parsed=parse_sr(sr_items[0]['header'])
        row.update(sr_sop_uid=parsed['sr_sop_uid'],sr_series_uid=parsed['sr_series_uid'])
        bbox,records,coverage=rasterize_boxes(parsed,geometry)
        statuses=Counter(c['status'] for c in coverage);counts=Counter(b['sop_uid'] for b in records)
        row.update(box_count=len(records),annotated_slice_count=statuses['positive_bbox'],missing_slice_count=statuses['missing_unknown'],
                   explicit_negative_slice_count=statuses['explicit_negative'],multiple_box_slice_count=sum(n>1 for n in counts.values()),
                   duplicate_box_geometry_count=parsed['duplicate_box_geometry_count'],finding_codes=sorted({tuple(b['finding_code']) for b in records}),
                   coordinate_convention='dicom_scoord_pixel_edges; voxel-center inclusion; integer edges give zero-based half-open indices',
                   annotation_coverage_status='partial_positive_only_unknown_elsewhere' if statuses['missing_unknown'] else 'positive_boxes_on_all_slices_exhaustiveness_unverified')
        row['qc_warnings']=['coverage_exhaustiveness_and_negative_slices_unverified','bbox_is_not_segmentation_GT','original_XML_archive_not_locally_verified']
        if parsed['duplicate_box_geometry_count']:row['qc_warnings'].append('duplicate_box_geometry_retained_for_review')
        if destination.exists():
            prov=json.loads((destination/'provenance.json').read_text())
            if prov.get('implementation')!=ident:raise DataIssue('stale_weak_conversion_cache','Use a new versioned converted_root; preserve old outputs')
            if prov.get('source_sha256')!=source_sha or prov.get('config_sha256')!=config.sha256 or prov.get('real_data') is not (not synthetic):raise DataIssue('weak_cache_source_config_origin_changed')
            for filename,digest in prov['output_sha256'].items():
                if filename not in ('ct.nii.gz','bbox.nii.gz','boxes.json','coverage.json') or file_sha256(destination/filename)!=digest:raise DataIssue('weak_cache_corrupt')
            if set(prov['output_sha256'])!={'ct.nii.gz','bbox.nii.gz','boxes.json','coverage.json'}:raise DataIssue('weak_cache_incomplete')
        else:
            require_space(destination,int(np.prod(geometry.shape))*5+config.reserve_bytes)
            ct,transforms=read_ct_pixels([i['path'] for i in ct_items],geometry)
            stage=destination.with_name(destination.name+'.partial-'+uuid4().hex[:8]);stage.mkdir(parents=True)
            save_nifti(stage/'ct.nii.gz',ct,geometry.affine_ras);save_nifti(stage/'bbox.nii.gz',bbox,geometry.affine_ras)
            write_json(stage/'boxes.json',{'kind':'weak_bbox_records_not_segmentation','records':records,'raw_sr_sha256':sr_items[0]['sha256']})
            write_json(stage/'coverage.json',{'slice_status':coverage,'outside_boxes_is_background':False,'exhaustive_lesion_annotation_verified':False})
            prov={'dataset':'Lung-PET-CT-Dx','real_data':not synthetic,'source_files':sources,'source_sha256':source_sha,
                  'config':asdict(config),'config_sha256':config.sha256,'implementation':ident,'native_geometry':geometry.to_dict(),
                  'annotation_reference':parsed['ct_reference'],'intensity_transforms':transforms,'source_annotation_changed':False,
                  'annotation_representation':'expert XML harmonized by IDC to SR; not AI SEG','timestamp_utc':utc_now(),
                  'output_sha256':{n:file_sha256(stage/n) for n in ('ct.nii.gz','bbox.nii.gz','boxes.json','coverage.json')}}
            write_json(stage/'provenance.json',prov);os.rename(stage,destination)
        ct_info,ce,cw=inspect_nifti(destination/'ct.nii.gz','image',config)
        bi,be,bw=inspect_nifti(destination/'bbox.nii.gz','bbox',config,label=True)
        if ce or be:raise DataIssue('converted_nifti_validation_failed',','.join(ce+be))
        if ct_info['image_shape']!=bi['bbox_shape'] or not np.allclose(ct_info['image_affine_mm'],geometry.affine_ras,atol=config.affine_atol_mm,rtol=0) or not np.allclose(bi['bbox_affine_mm'],geometry.affine_ras,atol=config.affine_atol_mm,rtol=0):raise DataIssue('native_bbox_geometry_mismatch')
        row.update(image_path=destination.name+'/ct.nii.gz',bbox_path=destination.name+'/bbox.nii.gz',
                   coverage_path=destination.name+'/coverage.json',boxes_path=destination.name+'/boxes.json',
                   provenance_path=destination.name+'/provenance.json',provenance_sha256=file_sha256(destination/'provenance.json'),
                   image_sha256=ct_info['image_sha256'],bbox_sha256=bi['bbox_sha256'],coverage_sha256=file_sha256(destination/'coverage.json'),
                   boxes_sha256=file_sha256(destination/'boxes.json'),label_values=bi['label_values'],bbox_foreground_voxels=bi['foreground_voxels'],
                   bbox_envelope_volume_mm3=bi['tumor_volume_mm3'],geometry_aligned=True,conversion_status='converted',
                   weak_eligibility_status='bbox_geometry_valid_coverage_review_required')
        row['qc_warnings']+=cw+bw
    except Exception as exc:
        row['qc_errors'].append(str(exc) if isinstance(exc,DataIssue) else f'conversion_error:{type(exc).__name__}:{exc}')
    return row


def inventory(config,*,synthetic=False):
    items,errors=scan(config,synthetic=synthetic);groups=defaultdict(list);sr_groups=defaultdict(list);failures=[]
    for i in items:
        ds=i['header']
        if ds.Modality!='SR':groups[(str(ds.PatientID),str(ds.StudyInstanceUID),str(ds.SeriesInstanceUID))].append(i)
        else:
            try:
                ref=evidence_reference(ds)
                sr_groups[(str(ds.PatientID),ref['study_uid'],ref['series_uid'])].append(i)
            except DataIssue as exc:failures.append({'patient_id':str(ds.PatientID),'reason':str(exc),'source_path':i['path'].relative_to(Path(config.raw_root)).as_posix(),'sha256':i['sha256']})
    rows=[]
    for key in sorted(groups.keys() | sr_groups.keys()):
        if key[0] in errors:continue
        rows.append(validate_case(config,*key,sr_groups[key],groups[key],synthetic=synthetic))
        print('weak',key[0],rows[-1]['conversion_status'],flush=True)
    for patient,reason in sorted(errors.items()):
        row={k:None for k in FIELDS}
        row.update(schema_version=1,dataset='Lung-PET-CT-Dx',case_id=patient+'__unresolved_acquisition',patient_id=patient,
                   patient_id_source='configured_public_ID_not_source_verified',annotation_kind='unresolved',ground_truth_available=False,
                   conversion_status='quarantined',weak_eligible=False,weak_eligibility_status='not_cleared_for_training',
                   annotation_coverage_status='unknown',qc_errors=[reason],qc_warnings=[],config_sha256=config.sha256,
                   implementation_fingerprint_sha256=implementation()['sha256'])
        rows.append(row)
    output=Path(config.output_dir)
    write_manifest(output/'manifest_weak.csv',rows,fields=FIELDS)
    write_manifest(output/'exclusion_log.csv',[r for r in rows if r['conversion_status']=='excluded'],fields=FIELDS)
    write_manifest(output/'quarantine.csv',[r for r in rows if r['conversion_status']=='quarantined'],fields=FIELDS)
    verified_patients={str(i['header'].PatientID) for i in items if str(i['header'].PatientID) not in errors}
    report={'timestamp_utc':utc_now(),'dataset':'Lung-PET-CT-Dx','real_data':False if synthetic else True if verified_patients else None,
            'cases':len(rows),'patient_count':len({r['patient_id'] for r in rows}),'ct_series':len(groups),
            'source_dicom_objects':len(items),'annotation_SR_objects':sum(i['header'].Modality=='SR' for i in items),
            'converted_cases':sum(r['conversion_status']=='converted' for r in rows),'excluded_cases':sum(r['conversion_status']=='excluded' for r in rows),
            'quarantined_cases':sum(r['conversion_status']=='quarantined' for r in rows)+len(failures),
            'acquisition_errors':errors,'annotation_failures':failures,'config':asdict(config),'config_sha256':config.sha256,
            'implementation':implementation(),'manifest_sha256':file_sha256(output/'manifest_weak.csv'),
            'quarantine':[{'case_id':r['case_id'],'reasons':r['qc_errors']} for r in rows if r['conversion_status']=='quarantined'],
            'bbox_count':sum(r['box_count'] or 0 for r in rows),'annotated_slice_count':sum(r['annotated_slice_count'] or 0 for r in rows),
            'multiple_box_slice_count':sum(r['multiple_box_slice_count'] or 0 for r in rows),'weak_eligible_count':0,
            'full_corpus_status':'NOT_VALIDATED','status':'SAMPLE_CONVERTED_QA_PENDING' if any(r['conversion_status']=='converted' for r in rows) else 'PARTIAL'}
    write_json(output/'conversion_report.json',report)
    return report


def generate_qa(config):
    from lungseg.data.weak_qa import generate
    return generate(config,implementation())
