"""Synthetic-only P1.3.1 regressions; no real dataset or network required."""
from copy import deepcopy
from dataclasses import asdict,replace
import csv
import hashlib
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from pydicom.uid import MRImageStorage
from test_weak import config,fixture,write_fixture
from lungseg.data.weak import inventory,survey
from lungseg.data.weak_sources import acquisition_semantics,command_exit_code
from lungseg.data.weak_acquire import DownloadBudget,download_series
from lungseg.data.msd_acquire import file_sha256
from lungseg.runs import write_json


@pytest.mark.parametrize('change',['malformed','no_reference','unsupported','unreadable'])
@pytest.mark.parametrize('ct_available',[True,False])
def test_annotation_failure_ledger_complete(config,change,ct_available):
    headers,_,sr=fixture(config)
    if change=='malformed':del sr.ContentTemplateSequence
    if change=='no_reference':del sr.CurrentRequestedProcedureEvidenceSequence
    if change=='unsupported':sr.CurrentRequestedProcedureEvidenceSequence[0].ReferencedSeriesSequence[0].ReferencedSOPSequence[0].ReferencedSOPClassUID=MRImageStorage
    write_fixture(config,headers if ct_available else [],sr)
    if change=='unreadable':
        folder=Path(config.raw_root)/'dicom'/sr.PatientID/sr.SeriesInstanceUID
        path=folder/(str(sr.SOPInstanceUID)+'.dcm');path.write_bytes(b'not a DICOM')
        marker=json.loads((folder/'source.json').read_text());marker['objects'][0]['sha256']=file_sha256(path);write_json(folder/'source.json',marker)
    report=inventory(config,synthetic=True)
    assert report['annotation_failure_count']==1 and report['reconciliation']['pass']
    records=list(csv.DictReader((Path(config.output_dir)/'annotation_failures.csv').open()))
    assert len(records)==1 and records[0]['patient_id']==sr.PatientID
    assert records[0]['sha256'] and records[0]['source_path'] and records[0]['reason']
    assert records[0]['declared_sop_uid']==sr.SOPInstanceUID
    assert records[0]['declared_series_uid']==sr.SeriesInstanceUID
    assert report['quarantined_cases']==len(list(csv.DictReader((Path(config.output_dir)/'quarantine.csv').open())))
    assert report['cases']<=1  # No fabricated CT series for unresolved annotation.
    if change in ('no_reference','unsupported','unreadable') and not ct_available:assert report['cases']==0
    assert survey(config,synthetic=True)['annotation_failure_count']==1


def test_multiple_failures_one_ct_case_and_mixed_valid_invalid(config):
    headers,_,sr=fixture(config);write_fixture(config,headers,sr)
    for n in (91,92):
        bad=deepcopy(sr);bad.SeriesInstanceUID=f'1.2.3.{n}';bad.SOPInstanceUID=f'1.2.3.{n}.1'
        bad.file_meta.MediaStorageSOPInstanceUID=bad.SOPInstanceUID
        del bad.ContentTemplateSequence
        write_fixture(config,[],bad)
    report=inventory(config,synthetic=True)
    assert report['cases']==1 and report['quarantined_cases']==1
    assert report['annotation_failure_count']==2 and report['annotation_SR_objects']==3
    assert report['reconciliation']['parsed_annotation_objects']==1
    assert report['reconciliation']['pass']
    assert len(report['annotation_failures'][0]['ct_references'])==1


def test_requested_patient_without_sources_not_silently_omitted(config):
    headers,_,sr=fixture(config);write_fixture(config,headers,sr)
    config=replace(config,sample_patient_ids=config.sample_patient_ids+['Lung_Dx-A0002'])
    report=inventory(config,synthetic=True)
    assert report['cases']==1 and report['acquisition_failure_patient_count']==1
    assert report['reconciliation']['requested_patients']==2 and report['reconciliation']['pass']
    assert report['reconciliation']['patients'][1]['acquisition_failure']=='missing_patient_acquisition'


def test_scan_continues_after_bad_object_and_reconciles_missing(config):
    headers,_,sr=fixture(config);write_fixture(config,headers,sr)
    path=Path(config.raw_root)/'dicom'/headers[0].PatientID/headers[0].SeriesInstanceUID/(str(headers[0].SOPInstanceUID)+'.dcm')
    path.unlink()  # Synthetic fixture only.
    report=inventory(config,synthetic=True)
    assert report['annotation_SR_objects']==1 and report['reconciliation']['missing_source_objects']==1
    assert report['reconciliation']['source_object_records']==5 and report['reconciliation']['pass']


@pytest.mark.parametrize('mode,expected,reject',[
    ('consistent','verified',False),('missing','unknown',False),('empty','unknown',False),
    ('acquisition','suspicious',False),('temporal','suspicious',True),('image_type','suspicious',False)])
def test_acquisition_semantics(config,mode,expected,reject):
    headers,_,_=fixture(config)
    for ds in headers:ds.AcquisitionNumber=1;ds.TemporalPositionIdentifier=1
    if mode=='missing':del headers[0].AcquisitionNumber
    if mode=='empty':headers[0].AcquisitionNumber=None
    if mode=='acquisition':headers[1].AcquisitionNumber=2
    if mode=='temporal':headers[1].TemporalPositionIdentifier=2
    if mode=='image_type':headers[1].ImageType=['ORIGINAL','PRIMARY','AXIAL','HELIX']
    finding=acquisition_semantics(headers)
    assert finding['status']==expected and finding['reject_mixed_temporal']==reject


@pytest.mark.parametrize('mixed_temporal',[False,True])
def test_acquisition_findings_persist_without_blanket_acquisition_reject(config,mixed_temporal):
    headers,_,sr=fixture(config)
    for k,ds in enumerate(headers):ds.AcquisitionNumber=k+1;ds.TemporalPositionIdentifier=2 if mixed_temporal and k==1 else 1
    write_fixture(config,headers,sr);report=inventory(config,synthetic=True)
    row=next(csv.DictReader((Path(config.output_dir)/'manifest_weak.csv').open()))
    assert json.loads(row['acquisition_semantics'])['status']=='suspicious'
    assert report['converted_cases']==(0 if mixed_temporal else 1)
    if not mixed_temporal:
        prov=json.loads(next(Path(config.converted_root).rglob('provenance.json')).read_text())
        assert prov['acquisition_semantics']['status']=='suspicious'


@pytest.mark.parametrize('command,result,expected',[
    ('survey-weak',{'errors':{'p':'bad'}},2),('survey-weak',{'annotation_failure_count':1},2),
    ('survey-weak',{'cases':[{}]},0),('audit-weak',{'actionable_findings':True},2),
    ('audit-weak',{'quarantined_cases':1},2),('qa-weak',{'actionable_findings':True},2),
    ('qa-weak',{},0),('acquire-weak',{'status':'PARTIAL_ACQUISITION_FAILURE'},2),
    ('acquire-weak',{'status':'CT_SR_SAMPLE_ACQUIRED'},0),
    ('acquire-weak',{'metadata_only':True,'sample_capacity_pass':False},2)])
def test_cli_exit_contract(config,monkeypatch,command,result,expected):
    import lungseg.cli as cli
    import lungseg.data.weak as weak
    import lungseg.data.weak_acquire as acquire
    import lungseg.data.weak_config as cfg
    monkeypatch.setattr(cfg,'load_weak_config',lambda p:config)
    module,name=(acquire,'acquire') if command=='acquire-weak' else (weak,{'survey-weak':'survey','audit-weak':'inventory','qa-weak':'generate_qa'}[command])
    monkeypatch.setattr(module,name,lambda *a,**kw:result)
    assert cli.main([command,'--config','unused'])==expected


@pytest.mark.parametrize('command',['acquire-weak','survey-weak','audit-weak','qa-weak'])
def test_cli_fatal_keeps_error_artifact(config,monkeypatch,command):
    import lungseg.cli as cli
    import lungseg.data.weak as weak
    import lungseg.data.weak_acquire as acquire
    import lungseg.data.weak_config as cfg
    monkeypatch.setattr(cfg,'load_weak_config',lambda p:config)
    def fail(*a,**kw):raise ValueError('fixture fatal error')
    module,name=(acquire,'acquire') if command=='acquire-weak' else (weak,{'survey-weak':'survey','audit-weak':'inventory','qa-weak':'generate_qa'}[command])
    monkeypatch.setattr(module,name,fail)
    assert cli.main([command,'--config','unused'])==1
    assert json.loads((Path(config.evidence_dir)/(command+'_fatal.json')).read_text())['exit_code']==1


def download_fixture(config):
    headers,_,_=fixture(config)
    record={k:str(getattr(headers[0],k)) for k in ('PatientID','StudyInstanceUID','SeriesInstanceUID','Modality')}
    record.update(instanceCount=1,series_size_MB=.000001,source_DOI='10.7937/tcia.2020.nnc2-0461',series_aws_url='fixture')
    buf=BytesIO();headers[0].save_as(buf,enforce_file_format=True);raw=buf.getvalue()
    return record,raw


@pytest.mark.parametrize('remaining',[0,1])
@pytest.mark.parametrize('modality',['CT','SR'])
def test_actual_listing_budget_before_network(config,monkeypatch,remaining,modality):
    import lungseg.data.weak_acquire as module
    record,raw=download_fixture(config);record['Modality']=modality
    objects=[{'key':'fixture.dcm','bytes':len(raw),'md5':hashlib.md5(raw).hexdigest()}]
    monkeypatch.setattr(module,'list_objects',lambda url:('fixture/',objects))
    monkeypatch.setattr(module,'urlopen',lambda *a,**kw:pytest.fail('Payload requested beyond budget'))
    budget=DownloadBudget(len(raw)+100);budget.claim('previous',len(raw)+100-remaining,cached=True)
    with pytest.raises(OSError,match='remaining'):download_series(record,Path(config.raw_root),budget=budget)
    assert budget.network_bytes==0 and not list(Path(config.raw_root).rglob('source.json'))


def test_actual_larger_than_catalog_allowed_only_within_budget_and_cache_separate(config,monkeypatch):
    import lungseg.data.weak_acquire as module
    record,raw=download_fixture(config)
    monkeypatch.setattr(module,'list_objects',lambda url:('fixture/',[{'key':'a','bytes':len(raw),'md5':hashlib.md5(raw).hexdigest()}]))
    monkeypatch.setattr(module,'require_space',lambda *a:10**12)
    class Response(BytesIO):headers={}
    monkeypatch.setattr(module,'urlopen',lambda *a,**kw:Response(raw))
    budget=DownloadBudget(len(raw));info=download_series(record,Path(config.raw_root),budget=budget)
    assert info['bytes']==len(raw)>record['series_size_MB']*1e6
    assert budget.network_bytes==len(raw) and budget.cache_bytes==0
    monkeypatch.setattr(module,'urlopen',lambda *a,**kw:pytest.fail('Verified cache must not download'))
    second=DownloadBudget(len(raw));download_series(record,Path(config.raw_root),budget=second)
    assert second.cache_bytes==len(raw) and second.network_bytes==0
    with pytest.raises(OSError):download_series(record,Path(config.raw_root),budget=DownloadBudget(len(raw)-1))


def test_interrupted_stage_retained_not_published(config,monkeypatch):
    import lungseg.data.weak_acquire as module
    record,raw=download_fixture(config)
    monkeypatch.setattr(module,'list_objects',lambda url:('fixture/',[{'key':'a','bytes':len(raw),'md5':hashlib.md5(raw).hexdigest()}]))
    monkeypatch.setattr(module,'require_space',lambda *a:10**12)
    class Response(BytesIO):headers={}
    monkeypatch.setattr(module,'urlopen',lambda *a,**kw:Response(raw[:10]))
    budget=DownloadBudget(len(raw))
    with pytest.raises(ValueError,match='byte count'):download_series(record,Path(config.raw_root),budget=budget)
    assert budget.network_bytes==10 and list((Path(config.raw_root)/'staging').iterdir())
    assert not list(Path(config.raw_root).rglob('source.json'))


def test_acquire_partial_keeps_budget_failure_artifact(config,monkeypatch):
    import lungseg.data.weak_acquire as module
    headers,_,sr=fixture(config)
    record,raw=download_fixture(config);record.update(Modality='SR',SeriesInstanceUID=str(sr.SeriesInstanceUID))
    monkeypatch.setattr(module,'load_catalog',lambda p:[record])
    monkeypatch.setattr(module,'file_sha256',lambda p:'fixture')
    monkeypatch.setattr(module,'capacity_plan',lambda *a:{'sample_capacity_pass':True})
    monkeypatch.setattr(module,'list_objects',lambda url:('fixture/',[{'key':'a','bytes':len(raw),'md5':'0'*32}]))
    monkeypatch.setattr(module,'urlopen',lambda *a,**kw:pytest.fail('No payload when actual listing exceeds cap'))
    result=module.acquire(replace(config,max_download_bytes=len(raw)-1),Path('fixture'),download=True)
    assert result['status']=='PARTIAL_ACQUISITION_FAILURE' and result['network_payload_bytes_this_run']==0
    assert not result['budget_decisions'][0]['accepted']
    artifact=json.loads((Path(config.evidence_dir)/'acquisition.json').read_text())
    assert artifact==result and command_exit_code('acquire-weak',artifact)==2
