"""Read-only XML ZIP investigation against existing real SR sample artifacts.

This is an evidence tool, not an XML production parser or a coordinate policy.
No extraction, annotation edits, acquisition or conversion is performed.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit,urlunsplit
import xml.etree.ElementTree as ET
import zipfile

import pydicom
from lungseg.data.msd_acquire import file_sha256
from lungseg.data.nsclc_version import conversion_implementation
from lungseg.data.weak import implementation
from lungseg.data.weak_boxes import parse_sr
from lungseg.data.weak_config import load_weak_config
from lungseg.runs import utc_now,write_json

EXPECTED_ARCHIVE='Lung-PET-CT-Dx-Annotations-XML-Files-rev12222020.zip'


def snapshot(roots):
    hashes={str(p):file_sha256(p) for root in roots for p in sorted(root.rglob('*')) if p.is_file()}
    return {'files':len(hashes),'sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()}


def investigate(archive_path,config):
    roots=[Path(getattr(config,k)) for k in ('raw_root','converted_root','output_dir','qa_dir')]
    before=snapshot(roots);archive_sha=file_sha256(archive_path)
    identity_before={'weak':implementation()['sha256'],'nsclc':conversion_implementation()['fingerprint_sha256']}
    findings=[];records={};classes=Counter();object_counts=Counter();dimensions=Counter();verified=Counter();bbox_count=0
    with zipfile.ZipFile(archive_path) as archive:
        members=archive.infolist()
        if archive_path.stat().st_size>24*1024**2 or sum(m.file_size for m in members)>64*1024**2:
            raise ValueError('Investigation archive exceeds bounded compressed/uncompressed limits')
        if len({m.filename for m in members})!=len(members):raise ValueError('Duplicate ZIP member names')
        bad_crc=archive.testzip()
        if bad_crc:raise ValueError('CRC failure: '+bad_crc)
        xml_members=[m for m in members if not m.is_dir() and m.filename.lower().endswith('.xml')]
        for member in xml_members:
            raw=archive.read(member)
            try:
                path=PurePosixPath(member.filename)
                if len(path.parts)!=3 or path.parts[0]!='Annotation':raise ValueError('Unexpected archive path')
                root=ET.fromstring(raw)
                if root.tag!='annotation':raise ValueError('Unexpected XML root')
                width,height,depth=(int(root.findtext('size/'+key)) for key in ('width','height','depth'))
                boxes=[];objects=root.findall('object')
                for obj in objects:
                    label=obj.findtext('name');bounds=obj.findall('bndbox')
                    if not label or len(bounds)!=1:raise ValueError('Missing class or ambiguous object box')
                    values=tuple(float(bounds[0].findtext(k)) for k in ('xmin','ymin','xmax','ymax'))
                    if not all(math.isfinite(v) for v in values):raise ValueError('Nonfinite bbox')
                    boxes.append((label,*values))
                key=('Lung_Dx-'+path.parts[1],path.stem)
                if key in records:raise ValueError('Duplicate patient/SOP XML mapping')
                records[key]={'member':member.filename,'sha256':hashlib.sha256(raw).hexdigest(),
                              'size':[width,height,depth],'boxes':boxes}
                classes.update(b[0] for b in boxes);object_counts[len(objects)]+=1;dimensions[(width,height,depth)]+=1
                verified[root.get('verified','<absent>')]+=1;bbox_count+=len(boxes)
            except Exception as exc:
                findings.append({'member':member.filename,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                                 'first_16_bytes_hex':raw[:16].hex(),'reason':f'{type(exc).__name__}:{exc}',
                                 'contains_Mac_OS_X_header':b'Mac OS X' in raw[:64]})
    with (Path(config.output_dir)/'manifest_weak.csv').open(newline='',encoding='utf-8') as handle:rows=list(csv.DictReader(handle))
    sample=[]
    for row in rows:
        raw_root=Path(config.raw_root);out=Path(config.converted_root)
        for path,hashfield in [('boxes_path','boxes_sha256'),('coverage_path','coverage_sha256')]:
            if file_sha256(out/row[path])!=row[hashfield]:raise ValueError('Existing artifact hash mismatch')
        boxes=json.loads((out/row['boxes_path']).read_text())['records']
        sources=json.loads(row['annotation_source_paths'])
        if len(sources)!=1:raise ValueError('Expected exactly one SR source')
        sr=parse_sr(pydicom.dcmread(raw_root/sources[0],stop_before_pixels=True))
        stored=Counter((b['sop_uid'],tuple(b['bounds_scoord_edges']),tuple(b['finding_code'])) for b in boxes)
        actual=Counter((b['sop_uid'],tuple(b['bounds_scoord_edges']),tuple(b['finding_code'])) for b in sr['boxes'])
        if stored!=actual:raise ValueError('Raw SR and existing boxes.json disagree')
        coverage=json.loads((out/row['coverage_path']).read_text())['slice_status'];ct_sops={s['sop_uid'] for s in coverage}
        xml_for_ct={sop:value for (patient,sop),value in records.items() if patient==row['patient_id'] and sop in ct_sops}
        xml_bounds=Counter((sop,tuple(b[1:])) for sop,v in xml_for_ct.items() for b in v['boxes'])
        sr_bounds=Counter((b['sop_uid'],tuple(b['bounds_scoord_edges'])) for b in boxes)
        common=xml_bounds & sr_bounds
        def serialize(counter):return [{'sop_uid':sop,'bounds':list(bounds),'count':n} for (sop,bounds),n in sorted(counter.items())]
        matched_class_pairs=Counter()
        for sop,value in xml_for_ct.items():
            for box in value['boxes']:
                for b in boxes:
                    if b['sop_uid']==sop and tuple(b['bounds_scoord_edges'])==box[1:]:matched_class_pairs[(box[0],*b['finding_code'])]+=1
        sample.append({'patient_id':row['patient_id'],'case_id':row['case_id'],'ct_slices':len(ct_sops),
                       'sr_boxes':len(boxes),'xml_boxes':sum(xml_bounds.values()),'xml_positive_sops':len(xml_for_ct),
                       'sr_positive_sops':len({b['sop_uid'] for b in boxes}),'matching_raw_bounds':sum(common.values()),
                       'same_positive_sop_set':set(xml_for_ct)=={b['sop_uid'] for b in boxes},
                       'raw_bounds_multiset_equal':xml_bounds==sr_bounds,
                       'xml_only':serialize(xml_bounds-sr_bounds),'sr_only':serialize(sr_bounds-xml_bounds),
                       'xml_sources':[{'member':v['member'],'sha256':v['sha256'],'sop_uid':sop,'size':v['size']} for sop,v in sorted(xml_for_ct.items())],
                       'xml_width_height_match_CT':all(v['size'][:2]==json.loads(row['image_shape'])[:2] for v in xml_for_ct.values()),
                       'xml_depth_metadata_values':sorted({v['size'][2] for v in xml_for_ct.values()}),
                       'observed_class_pairs':[{'xml_name':key[0],'sr_finding_code':list(key[1:]),'matches':n} for key,n in sorted(matched_class_pairs.items())],
                       'class_mapping_status':'observed associations only; no automatic normalization or adjudication',
                       'coverage_unknown_preserved':sum(s['status']=='missing_unknown' for s in coverage),
                       'outside_boxes_is_background':False})
    xml_patients={p for p,s in records}
    catalog=json.loads(Path('data/manifests/weak/public_catalog.json').read_text())['series']
    catalog_patients={r['PatientID'] for r in catalog if r['Modality'] in ('CT','PT')}
    after=snapshot(roots)
    identity_after={'weak':implementation()['sha256'],'nsclc':conversion_implementation()['fingerprint_sha256']}
    browser_origin={}
    try:
        zone=Path(str(archive_path)+':Zone.Identifier').read_text(encoding='utf-8-sig')
        for line in zone.splitlines():
            key,separator,value=line.partition('=')
            if separator and key in ('HostUrl','ReferrerUrl'):
                parts=urlsplit(value);browser_origin[key]=urlunsplit((parts.scheme,parts.netloc,parts.path,'',''))
    except OSError:browser_origin={'status':'Zone.Identifier unavailable'}
    return {'timestamp_utc':utc_now(),'status':'XML_ACCESS_RESOLVED_SAMPLE_DIFFERENCE_REVIEW_REQUIRED',
            'archive':{'path':str(archive_path),'name_matches_expected':archive_path.name==EXPECTED_ARCHIVE,
                       'bytes':archive_path.stat().st_size,'sha256':archive_sha,'zip_crc_pass':True,
                       'members':len(members),'xml_members':len(xml_members),'uncompressed_bytes':sum(m.file_size for m in members),
                       'provenance':'user downloaded after VPN change from reported official TCIA page; no independent publisher checksum available',
                       'browser_origin_without_query':browser_origin,
                       'official_page':'https://www.cancerimagingarchive.net/tcia-downloads/lung-pet-ct-dx-da-other/lung-pet-ct-dx-annotations-xml-files-rev12222020/'},
            'archive_scan':{'parsed_xml':len(records),'parse_failures':findings,'patient_folders_with_parsed_xml':len(xml_patients),
                            'object_count':bbox_count,'classes':dict(sorted(classes.items())),
                            'objects_per_xml':dict(sorted(object_counts.items())),
                            'dimensions':[{'size':list(size),'xml_files':n} for size,n in sorted(dimensions.items())],
                            'verified_attribute_values':dict(verified),'outside_catalog_patient_folders':sorted(xml_patients-catalog_patients),
                            'catalog_patients_without_parsed_xml':sorted(catalog_patients-xml_patients)},
            'sample':sample,'sample_case_count':len(sample),'sr_boxes':sum(r['sr_boxes'] for r in sample),
            'xml_boxes_on_sample_CT':sum(r['xml_boxes'] for r in sample),
            'matching_raw_bounds':sum(r['matching_raw_bounds'] for r in sample),
            'exact_raw_record_case_count':sum(r['raw_bounds_multiset_equal'] for r in sample),
            'coordinate_convention_status':'Numeric bounds compared without offset; XML itself does not establish pixel-center/edge or inclusive semantics. No XML voxel rasterization asserted.',
            'full_XML_SR_equivalence_verified':False,'manual_expert_approval':False,'weak_training_clearance':False,
            'baseline_before':before,'baseline_after':after,'baseline_preserved':before==after,
            'implementation_before':identity_before,'implementation_after':identity_after,'implementation_unchanged':identity_before==identity_after,
            'archive_unchanged':file_sha256(archive_path)==archive_sha}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--config',default='configs/weak_p1_3_1.yaml')
    parser.add_argument('--output',type=Path,default=Path('docs/evidence/p1_3_1/xml_followup/comparison.json'))
    args=parser.parse_args();result=investigate(args.archive,load_weak_config(args.config));write_json(args.output,result)
    print(json.dumps({k:result[k] for k in ('status','sample_case_count','sr_boxes','xml_boxes_on_sample_CT','matching_raw_bounds',
                     'exact_raw_record_case_count','baseline_preserved','archive_unchanged','implementation_unchanged')},indent=2))
    if not all(result[k] for k in ('baseline_preserved','archive_unchanged','implementation_unchanged')):raise RuntimeError('Preservation check failed')


if __name__=='__main__':main()
