"""Synthetic receipt/integrity and resource guard tests; no cloud/data acquisition."""
import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('pilot',Path(__file__).parents[1]/'scripts/cloud_pilot.py')
pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)


def test_receipt_external_digest_and_corrupt_cache(tmp_path):
    (tmp_path/'artifact').write_bytes(b'synthetic fixture')
    digest=pilot.seal(tmp_path,'ROOT.json');assert len(pilot.verify(tmp_path,'ROOT.json',digest))==1
    (tmp_path/'artifact').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='corrupt'):pilot.verify(tmp_path,'ROOT.json',digest)


def test_receipt_rejects_unpinned_and_unlisted(tmp_path):
    (tmp_path/'artifact').write_bytes(b'x');digest=pilot.seal(tmp_path,'ROOT.json')
    with pytest.raises(ValueError,match='pinned'):pilot.verify(tmp_path,'ROOT.json','0'*64)
    (tmp_path/'unexpected').write_bytes(b'x')
    with pytest.raises(ValueError,match='Unlisted'):pilot.verify(tmp_path,'ROOT.json',digest)


@pytest.mark.parametrize('name',['../escape','/absolute','C:/Users/private','a\\b'])
def test_receipt_path_traversal_refused(tmp_path,name):
    pilot.write(tmp_path/'ROOT.json',{'files':{name:{'bytes':1,'sha256':'x'}}})
    with pytest.raises(ValueError,match='Unsafe'):pilot.verify(tmp_path,'ROOT.json',pilot.sha(tmp_path/'ROOT.json'))


def test_existing_receipt_never_overwritten(tmp_path):
    (tmp_path/'file').write_bytes(b'x');digest=pilot.seal(tmp_path,'ROOT.json')
    with pytest.raises(ValueError,match='fresh'):pilot.seal(tmp_path,'ROOT.json')
    assert pilot.sha(tmp_path/'ROOT.json')==digest


def test_nifti_signature_detects_voxel_and_geometry_change(tmp_path):
    import nibabel as nib
    import numpy as np
    a=tmp_path/'a.nii.gz';b=tmp_path/'b.nii.gz';data=np.zeros((3,4,5),dtype=np.float32)
    nib.save(nib.Nifti1Image(data,np.eye(4)),a);nib.save(nib.Nifti1Image(data,np.eye(4)),b)
    assert pilot.same_geometry(pilot.nifti_signature(a),pilot.nifti_signature(b))
    data[0,0,0]=1;nib.save(nib.Nifti1Image(data,np.eye(4)),b)
    assert not pilot.same_geometry(pilot.nifti_signature(a),pilot.nifti_signature(b))
    data[:]=0;affine=np.eye(4);affine[0,3]=2;nib.save(nib.Nifti1Image(data,affine),b)
    assert not pilot.same_geometry(pilot.nifti_signature(a),pilot.nifti_signature(b))


def test_real_peak_rss_measurement_available():
    assert pilot.peak_rss()>0


def test_local_restore_cannot_claim_cloud_session_pass(tmp_path):
    pilot.write(tmp_path/'run.json',{'execution_kind':'local','session_id':'fixture','checks':{'nsclc':{'signatures':{}},'weak':{'signatures':{}}}})
    digest=pilot.seal(tmp_path,'RESULT_ROOT.json')
    result=pilot.restore(tmp_path,digest,True)
    assert result['status']=='RESTORE_CONTENT_VERIFIED'
    assert result['session_restore_status']=='NOT_VERIFIED_NEW_CLOUD_SESSION'


def test_pilot_case_cap_no_files_created(tmp_path):
    with pytest.raises(ValueError,match='1-2'):pilot.prepare(tmp_path/'bundle',['a','b','c'],['x'])
    assert not (tmp_path/'bundle').exists()


def test_resource_guard_blocks_worker_and_retains_preflight(tmp_path,monkeypatch):
    source=tmp_path/'input';source.mkdir();output=tmp_path/'run'
    ident={'weak':{'sources':{'module':'hash'}},'nsclc':{'source_sha256':{'module':'hash'}}}
    pilot.write(source/'spec.json',{'revision':pilot.REVISION,'production_implementation':ident,
                                  'reference_signatures':{'weak':{'fixture':{'shape':[2,2,2]}}}})
    monkeypatch.setattr(pilot,'verify',lambda *a:None);monkeypatch.setattr(pilot,'identity',lambda:ident)
    monkeypatch.setattr(pilot.subprocess,'check_output',lambda *a,**k:pilot.REVISION)
    monkeypatch.setattr(pilot,'resources',lambda *a:{'kaggle_runtime_detected':False,'disk':{'free_bytes':20*pilot.GIB},'ram':{'available_bytes':0}})
    monkeypatch.setattr(pilot.subprocess,'run',lambda *a,**k:pytest.fail('No worker after failed admission'))
    with pytest.raises(OSError,match='admission'):pilot.run(source,output,'fixture','local')
    assert json.loads((output/'preflight.json').read_text())['admitted'] is False


def test_changed_production_source_rejected_before_output(tmp_path,monkeypatch):
    source=tmp_path/'input';source.mkdir()
    pilot.write(source/'spec.json',{'revision':pilot.REVISION,'production_implementation':{'weak':{'sources':{'module':'old'}}}})
    monkeypatch.setattr(pilot,'verify',lambda *a:None)
    monkeypatch.setattr(pilot,'identity',lambda:{'weak':{'sources':{'module':'changed'}}})
    monkeypatch.setattr(pilot.subprocess,'check_output',lambda *a,**k:pilot.REVISION)
    with pytest.raises(ValueError,match='source changed'):pilot.run(source,tmp_path/'out','fixture','local')
    assert not (tmp_path/'out').exists()
