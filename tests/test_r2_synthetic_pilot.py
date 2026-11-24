"""Fake R2 transport only. No credentials, bucket or network requests."""
from datetime import datetime,timezone
import importlib.util
from io import BytesIO
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('r2pilot',Path(__file__).parents[1]/'scripts/r2_synthetic_pilot.py')
r2=importlib.util.module_from_spec(spec);spec.loader.exec_module(r2)


def approval():
    now=datetime.now(timezone.utc)
    return {'approved_synthetic_only':True,'single_writer_attested':True,'account_free_tier_headroom_attested':True,
            'verified_at_utc':now.isoformat(),'billing_month_utc':now.strftime('%Y-%m'),'incremental_paid_spend_authorized_vnd':0,
            'free_class_a_remaining':100,'free_class_b_remaining':100,'account_storage_estimate_bytes':0}


class Missing(Exception):response={'ResponseMetadata':{'HTTPStatusCode':404}}
class Denied(Exception):response={'ResponseMetadata':{'HTTPStatusCode':403}}


class FakeR2:
    def __init__(self):self.objects={};self.puts=0;self.corrupt=False;self.timeouts=0
    def list_multipart_uploads(self,**kwargs):return {}
    def list_objects_v2(self,**kwargs):return {'Contents':[{'Size':len(v)} for v in self.objects.values()]}
    def head_object(self,Key,**kwargs):
        if Key not in self.objects:raise Missing()
        return {'ContentLength':len(self.objects[Key])}
    def put_object(self,Key,Body,**kwargs):
        assert kwargs['StorageClass']=='STANDARD' and kwargs['IfNoneMatch']=='*'
        self.objects[Key]=Body;self.puts+=1
    def get_object(self,Key,**kwargs):
        if self.timeouts:self.timeouts-=1;raise TimeoutError()
        return {'Body':BytesIO(b'X'*len(self.objects[Key]) if self.corrupt else self.objects[Key])}


@pytest.mark.parametrize('used,new,status',[(0,1024,'ADMITTED'),(8*r2.GB,1,'BLOCKED_TARGET_REVIEW'),(10*r2.GB,1,'BLOCKED_HARD_LIMIT')])
def test_storage_budget(used,new,status):assert r2.storage_guard(used,new)['status']==status


def test_roundtrip_restore_and_cached_content_no_duplicate_put():
    client=FakeR2();a=approval();result=r2.roundtrip(client,'fake',a,1024)
    assert result['status']=='R2_SYNTHETIC_ROUNDTRIP_PASS' and client.puts==1
    a['account_storage_estimate_bytes']=1024
    second=r2.roundtrip(client,'fake',a,1024)
    assert second['cached_existing_payload'] and client.puts==1 and second['upload_seconds'] is None
    assert r2.restore(client,'fake',result)['session_restore_status']=='NOT_VERIFIED_NEW_SESSION'


def test_transient_retry_and_sha_mismatch(monkeypatch):
    monkeypatch.setattr(r2.time,'sleep',lambda n:None)
    client=FakeR2();client.timeouts=1;result=r2.roundtrip(client,'fake',approval(),1024)
    assert result['retries']==1 and result['attempts']['B']==3
    client.corrupt=True
    with pytest.raises(ValueError,match='SHA256 mismatch'):r2.restore(client,'fake',result)


def test_auth_not_retried():
    class Forbidden:
        def head_object(self,**kw):raise Denied()
    calls=r2.Calls(Forbidden())
    with pytest.raises(Denied):calls.call('head_object','B',Bucket='x',Key='x')
    assert calls.attempts['B']==1 and calls.retries==0


def test_missing_or_expired_approval_refused():
    with pytest.raises(ValueError):r2.validate_approval({})
    a=approval();a['billing_month_utc']='2000-01'
    with pytest.raises(ValueError,match='expired'):r2.validate_approval(a)


def test_unaccounted_multipart_refused_before_put():
    class Pending(FakeR2):
        def list_multipart_uploads(self,**kwargs):return {'Uploads':[{'Key':'partial'}]}
    client=Pending()
    with pytest.raises(ValueError,match='multipart'):r2.roundtrip(client,'fake',approval(),1024)
    assert client.puts==0


def test_request_guard_stops_infinite_listing():
    class Listing:
        def list_multipart_uploads(self,**kwargs):return {}
        def list_objects_v2(self,**kwargs):return {'IsTruncated':True,'NextContinuationToken':str(int(kwargs.get('ContinuationToken','0'))+1)}
    calls=r2.Calls(Listing())
    with pytest.raises(RuntimeError,match='budget'):r2.bucket_usage(calls,'fake')
    assert calls.attempts['A']==100


def test_body_read_timeout_retried(monkeypatch):
    monkeypatch.setattr(r2.time,'sleep',lambda n:None)
    class Body:
        def read(self,n):raise TimeoutError()
        def close(self):pass
    class Client(FakeR2):
        def __init__(self):super().__init__();self.first=True
        def get_object(self,Key,**kwargs):
            if self.first:self.first=False;return {'Body':Body()}
            return super().get_object(Key,**kwargs)
    result=r2.roundtrip(Client(),'fake',approval(),1024)
    assert result['retries']==1


def test_timeout_exhaustion_bounded(monkeypatch):
    monkeypatch.setattr(r2.time,'sleep',lambda n:None)
    client=FakeR2();client.timeouts=100;calls=r2.Calls(client)
    with pytest.raises(TimeoutError):r2.download(calls,'fake','key',1)
    assert calls.attempts['B']==3 and calls.retries==2


def test_storage_target_blocked_before_put():
    a=approval();a['account_storage_estimate_bytes']=8*r2.GB;client=FakeR2()
    with pytest.raises(ValueError,match='guard'):r2.roundtrip(client,'fake',a,1024)
    assert client.puts==0


def test_ambiguous_put_recovered_only_by_matching_readback(monkeypatch):
    monkeypatch.setattr(r2.time,'sleep',lambda n:None)
    class Conflict(Exception):response={'ResponseMetadata':{'HTTPStatusCode':412}}
    class Ambiguous(FakeR2):
        def put_object(self,Key,Body,**kwargs):
            if Key in self.objects:raise Conflict()
            super().put_object(Key,Body,**kwargs);raise TimeoutError()
    client=Ambiguous();result=r2.roundtrip(client,'fake',approval(),1024)
    assert client.puts==1 and result['conditional_conflict_recovered']
    assert result['upload_seconds'] is None and result['retries']==1


def test_infrequent_access_refused_before_data_read():
    class WrongClass(FakeR2):
        wrong_class=False
        def head_object(self,**kwargs):
            head=super().head_object(**kwargs)
            if self.wrong_class:head['StorageClass']='STANDARD_IA'
            return head
    client=WrongClass();r2.roundtrip(client,'fake',approval(),1024)
    client.wrong_class=True;a=approval();a['account_storage_estimate_bytes']=1024
    with pytest.raises(ValueError,match='Standard'):r2.roundtrip(client,'fake',a,1024)
