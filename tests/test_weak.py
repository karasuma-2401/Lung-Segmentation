"""SYNTHETIC expert-box SR/CT fixtures; not real Lung-PET-CT-Dx evidence."""
from copy import deepcopy
from dataclasses import asdict,replace
import json
from pathlib import Path
import numpy as np
import pydicom
from pydicom.uid import CTImageStorage,Comprehensive3DSRStorage
import pytest
from test_nsclc import ct_headers,item,file_dataset

from lungseg.data.dicom_geometry import DataIssue,build_ct_geometry
from lungseg.data.weak_boxes import parse_sr,index_bounds,annotation_coverage,rasterize_boxes,rectangle_bounds
from lungseg.data.weak_config import load_weak_config,WeakConfig
from lungseg.data.weak import inventory,ct_type_eligible,physical_extent,extent_eligible
from lungseg.data.weak_acquire import LICENSE_URL,IMAGE_DOI,ANNOTATION_DOI
from lungseg.data.msd_acquire import file_sha256
from lungseg.runs import write_json


@pytest.fixture
def config(tmp_path):
    base=load_weak_config('configs/weak.yaml')
    return replace(base,raw_root=str(tmp_path/'raw'),converted_root=str(tmp_path/'converted'),output_dir=str(tmp_path/'manifest'),
                   qa_dir=str(tmp_path/'qa'),evidence_dir=str(tmp_path/'evidence'),sample_patient_ids=['Lung_Dx-A0001'])


def code(value,meaning):
    return [item(CodingSchemeDesignator='DCM',CodeValue=value,CodeMeaning=meaning)]


def fixture(config,boxes=None):
    headers=ct_headers()
    for k,ds in enumerate(headers):
        ds.PatientID='Lung_Dx-A0001';ds.ImageType=['ORIGINAL','PRIMARY','AXIAL']
        ds.ImagePositionPatient=[10,20,30+k*50];ds.SpacingBetweenSlices=50
    g=build_ct_geometry(headers,config)
    sr=file_dataset(Comprehensive3DSRStorage,'1.2.3.90.1')
    sr.PatientID='Lung_Dx-A0001';sr.Modality='SR';sr.SeriesInstanceUID='1.2.3.90'
    sr.ContentTemplateSequence=[item(TemplateIdentifier='1500')]
    sr.CurrentRequestedProcedureEvidenceSequence=[item(StudyInstanceUID=g.study_uid,ReferencedSeriesSequence=[item(SeriesInstanceUID=g.series_uid,
        ReferencedSOPSequence=[item(ReferencedSOPClassUID=CTImageStorage,ReferencedSOPInstanceUID=s) for s in g.sop_uids])])]
    records=boxes if boxes is not None else [(g.sop_uids[1],[2,2,4,4]),(g.sop_uids[1],[6,6,8,8])]
    groups=[]
    for i,(sop,(x0,y0,x1,y1)) in enumerate(records):
        image=item(ValueType='IMAGE',RelationshipType='SELECTED FROM',ReferencedSOPSequence=[item(ReferencedSOPInstanceUID=sop,ReferencedSOPClassUID=CTImageStorage)])
        region=item(ValueType='SCOORD',GraphicType='POLYLINE',GraphicData=[x0,y0,x1,y0,x1,y1,x0,y1,x0,y0],ContentSequence=[image])
        groups.append(item(ValueType='CONTAINER',ConceptNameCodeSequence=code('125007','Measurement Group'),ContentSequence=[
            item(ValueType='UIDREF',ConceptNameCodeSequence=code('112040','Tracking Unique Identifier'),UID=f'1.2.3.99.{i+1}'),
            item(ValueType='CODE',ConceptNameCodeSequence=code('121071','Finding'),ConceptCodeSequence=code('1187332001','Adenocarcinoma')),region]))
    sr.ContentSequence=groups
    return headers,g,sr


def write_fixture(config,headers,sr):
    for datasets in (headers,[sr] if sr is not None else []):
        if not datasets:continue
        ds=datasets[0];identity={key:str(getattr(ds,key)) for key in ('PatientID','StudyInstanceUID','SeriesInstanceUID','Modality')}
        folder=Path(config.raw_root)/'dicom'/ds.PatientID/ds.SeriesInstanceUID;folder.mkdir(parents=True)
        objects=[]
        for d in datasets:
            path=folder/(str(d.SOPInstanceUID)+'.dcm');d.save_as(path,enforce_file_format=True)
            objects.append({'sop_uid':str(d.SOPInstanceUID),'sha256':file_sha256(path)})
        write_json(folder/'source.json',{'synthetic':True,'catalog_identity':identity,'license_url':LICENSE_URL,
                   'source_doi':ANNOTATION_DOI if ds.Modality=='SR' else IMAGE_DOI,'objects':objects})


def test_all_boxes_and_sop_identity_native_alignment(config):
    headers,g,sr=fixture(config)
    shuffled=build_ct_geometry([headers[i] for i in [2,0,3,1]],config)
    parsed=parse_sr(sr);volume,records,coverage=rasterize_boxes(parsed,shuffled)
    assert len(records)==2 and volume.sum()==8
    assert volume[:,:,1].sum()==8 and volume[:,:,0].sum()==0
    assert coverage[1]['bbox_count']==2 and coverage[0]['status']=='missing_unknown'
    assert records[0]['index_bounds_half_open']==[2,2,4,4]
    np.testing.assert_allclose(records[0]['physical_corners_lps_mm'][0],[12.25,23.,80.])
    assert g.shape==volume.shape


@pytest.mark.parametrize('box,convention,expected',[
 ([1,1,1,1],'voc_one_based_inclusive',[0,0,1,1]),([1,1,3,4],'voc_one_based_inclusive',[0,0,3,4]),
 ([0,0,3,4],'zero_based_half_open',[0,0,3,4]),([0,0,3,4],'dicom_scoord_pixel_edges',[0,0,3,4]),
 ([.5,.5,1.5,1.5],'dicom_scoord_pixel_edges',[0,0,2,2]),([9,7,12,8],'dicom_scoord_pixel_edges',[9,7,12,8])])
def test_explicit_coordinate_conventions_off_by_one(box,convention,expected):
    assert index_bounds(box,(12,8),convention)==expected


@pytest.mark.parametrize('box,convention',[
 ([4,2,2,4],'zero_based_half_open'),([2,2,2,4],'zero_based_half_open'),([-1,0,3,4],'dicom_scoord_pixel_edges'),
 ([0,0,13,8],'dicom_scoord_pixel_edges'),([0,0,8,12],'dicom_scoord_pixel_edges'),
 ([0,0,float('nan'),2],'dicom_scoord_pixel_edges'),([0,0,.1,.1],'dicom_scoord_pixel_edges'),
 ([0,0,1,1],'voc_one_based_inclusive'),([0,0,1,1],'guess')])
def test_invalid_bounds_not_clipped(box,convention):
    with pytest.raises(DataIssue):index_bounds(box,(12,8),convention)


def test_coverage_missing_is_never_negative():
    result=annotation_coverage(['1','2','3'],[{'sop_uid':'1'}],['2'])
    assert [r['status'] for r in result]==['positive_bbox','explicit_negative','missing_unknown']
    with pytest.raises(DataIssue,match='positive_negative'):annotation_coverage(['1'],[{'sop_uid':'1'}],['1'])
    with pytest.raises(DataIssue,match='not_in_ct'):annotation_coverage(['1'],[{'sop_uid':'9'}])


@pytest.mark.parametrize('change,reason',[
 ('patient','identity_mismatch'),('study','identity_mismatch'),('series','identity_mismatch'),
 ('sop','not_in_ct'),('duplicate_tracking','duplicate_annotation'),('scoord3d','unsupported_bbox'),
 ('frame','unsupported_bbox'),('open','not_closed'),('crossed','non_rectangular'),('template','unsupported_sr_template')])
def test_invalid_sr_mapping_and_records(config,change,reason):
    _,g,sr=fixture(config)
    region=sr.ContentSequence[0].ContentSequence[-1]
    if change=='patient':sr.PatientID='Lung_Dx-A0002'
    if change=='study':sr.CurrentRequestedProcedureEvidenceSequence[0].StudyInstanceUID='1.9'
    if change=='series':sr.CurrentRequestedProcedureEvidenceSequence[0].ReferencedSeriesSequence[0].SeriesInstanceUID='1.9'
    if change=='sop':
        ref=sr.CurrentRequestedProcedureEvidenceSequence[0].ReferencedSeriesSequence[0].ReferencedSOPSequence[0];ref.ReferencedSOPInstanceUID='1.9'
    if change=='duplicate_tracking':sr.ContentSequence[1].ContentSequence[0].UID=sr.ContentSequence[0].ContentSequence[0].UID
    if change=='scoord3d':region.ValueType='SCOORD3D'
    if change=='frame':region.PixelOriginInterpretation='VOLUME'
    if change=='open':region.GraphicData[-1]=3
    if change=='crossed':region.GraphicData=[2,2,4,4,4,2,2,4,2,2]
    if change=='template':sr.ContentTemplateSequence[0].TemplateIdentifier='9999'
    with pytest.raises(DataIssue,match=reason):rasterize_boxes(parse_sr(sr),g)


def test_duplicate_geometry_retained_not_first_box_only(config):
    _,g,sr=fixture(config)
    sr.ContentSequence[1].ContentSequence[-1].GraphicData=sr.ContentSequence[0].ContentSequence[-1].GraphicData
    parsed=parse_sr(sr)
    assert len(parsed['boxes'])==2 and parsed['duplicate_box_geometry_count']==1
    assert len(rasterize_boxes(parsed,g)[1])==2


@pytest.mark.parametrize('modality,image_type,eligible',[
 ('CT',['ORIGINAL','PRIMARY','AXIAL'],True),('PT',['ORIGINAL'],False),('OT',['FUSED'],False),
 ('CT',['ORIGINAL','LOCALIZER'],False),('CT',['DERIVED','PRIMARY'],False),('CT',['SECONDARY'],False)])
def test_ct_modality_type_filter(config,modality,image_type,eligible):
    ds=fixture(config)[0][0];ds.Modality=modality;ds.ImageType=image_type
    assert ct_type_eligible(ds)[0] is eligible


@pytest.mark.parametrize('extent,passed',[(159.999,False),(160,True),(600,True),(600.001,False),(float('nan'),False)])
def test_closed_physical_extent_boundaries(config,extent,passed):
    assert extent_eligible(extent,config) is passed


def test_extent_uses_positions_not_thickness(config):
    headers,g,_=fixture(config)
    for ds in headers:ds.SliceThickness=999
    span,edge,z=physical_extent(build_ct_geometry(headers,config))
    assert span==150 and edge==200 and z==200


def test_manifest_repeat_raw_preservation_and_origin(config):
    headers,g,sr=fixture(config);write_fixture(config,headers,sr)
    before={p:file_sha256(p) for p in Path(config.raw_root).rglob('*') if p.is_file()}
    r=inventory(config,synthetic=True);assert r['converted_cases']==1 and r['bbox_count']==2 and r['weak_eligible_count']==0 and r['real_data'] is False
    manifest=Path(config.output_dir)/'manifest_weak.csv';digest=file_sha256(manifest)
    inventory(config,synthetic=True);assert file_sha256(manifest)==digest
    assert before=={p:file_sha256(p) for p in before}
    assert inventory(config)['real_data'] is None


def test_missing_or_empty_annotation_not_fake_background(config):
    headers,_,sr=fixture(config,boxes=[]);write_fixture(config,headers,sr)
    report=inventory(config,synthetic=True)
    assert report['converted_cases']==0 and report['quarantined_cases']==1
    assert not list(Path(config.converted_root).rglob('bbox.nii.gz'))


def test_no_sr_report_quarantines_valid_ct(config):
    headers,_,_=fixture(config);write_fixture(config,headers,None)
    report=inventory(config,synthetic=True)
    assert report['quarantined_cases']==1 and 'missing_annotation_report' in report['quarantine'][0]['reasons'][0]


@pytest.mark.parametrize('change',['implementation','config','corrupt'])
def test_conversion_cache_mismatch_safe_failure(config,monkeypatch,change):
    import lungseg.data.weak as module
    headers,_,sr=fixture(config);write_fixture(config,headers,sr)
    assert inventory(config,synthetic=True)['converted_cases']==1
    root=Path(config.converted_root)
    if change=='implementation':
        ident=module.implementation();ident['sha256']='changed'
        monkeypatch.setattr(module,'implementation',lambda:ident)
    if change=='config':config=replace(config,qa_dir=config.qa_dir+'_changed')
    if change=='corrupt':next(root.rglob('bbox.nii.gz')).write_bytes(b'deliberate fixture corruption')
    before={p:file_sha256(p) for p in root.rglob('*') if p.is_file()}
    result=inventory(config,synthetic=True)
    assert result['converted_cases']==0 and result['quarantined_cases']==1
    assert before=={p:file_sha256(p) for p in before}


def test_capacity_preflight_no_network_on_failure(config,monkeypatch):
    import lungseg.data.weak_acquire as module
    rows=[{'PatientID':'Lung_Dx-A0001','StudyInstanceUID':'1.2','Modality':'CT','instanceCount':10,'series_size_MB':10}]
    monkeypatch.setattr(module,'load_catalog',lambda p:rows);monkeypatch.setattr(module,'file_sha256',lambda p:'x')
    monkeypatch.setattr(module,'require_space',lambda *a:0)
    monkeypatch.setattr(module,'download_series',lambda *a:pytest.fail('No download after failed capacity'))
    with pytest.raises(OSError,match='preflight'):module.acquire(config,Path('fixture'),download=True)


def test_config_refuses_protocol_tuning_and_overlap(config):
    value=asdict(config);value['min_extent_mm']=200
    with pytest.raises(ValueError,match='fixed closed'):WeakConfig.from_dict(value)
    value=asdict(config);value['converted_root']=value['raw_root']
    with pytest.raises(ValueError,match='separate'):WeakConfig.from_dict(value)


@pytest.mark.parametrize('swap', [False,True])
def test_native_bbox_with_orientation_flip_or_axis_swap(config,swap):
    headers,_,sr=fixture(config)
    for ds in headers:
        ds.ImageOrientationPatient=[0,1,0,1,0,0] if swap else [-1,0,0,0,-1,0]
    geometry=build_ct_geometry(headers,config)
    volume,records,_=rasterize_boxes(parse_sr(sr),geometry)
    expected_k=geometry.sop_uids.index(str(headers[1].SOPInstanceUID))
    assert volume[:,:,expected_k].sum()==8 and records[0]['slice_index']==expected_k
    expected=[13.,22.25,80.] if swap else [7.75,17.,80.]
    np.testing.assert_allclose(records[0]['physical_corners_lps_mm'][0],expected)


def test_catalog_rejects_duplicate_series_and_ai_annotation(tmp_path):
    from lungseg.data.weak_acquire import load_catalog
    from lungseg.data.nsclc_idc import INDEX_URL
    row={'collection_id':'lung_pet_ct_dx','license_short_name':'CC BY 4.0','PatientID':'Lung_Dx-A0001',
         'StudyInstanceUID':'1.2','SeriesInstanceUID':'1.3','Modality':'CT','source_DOI':IMAGE_DOI,'instanceCount':2,'series_size_MB':1.}
    path=tmp_path/'catalog.json'
    write_json(path,{'source':INDEX_URL,'index_sha256':'a'*64,'series':[row,row]})
    with pytest.raises(ValueError,match='Duplicate'):load_catalog(path)
    row['Modality']='SEG';row['source_DOI']='10.5281/zenodo.8345959'
    write_json(path,{'source':INDEX_URL,'index_sha256':'a'*64,'series':[row]})
    with pytest.raises(ValueError,match='AI/other'):load_catalog(path)
