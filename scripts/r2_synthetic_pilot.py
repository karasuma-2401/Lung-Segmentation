"""Opt-in, bounded R2 Standard synthetic pilot. No medical files or provisioning.

Default is offline plan. Execution requires explicit approval/headroom evidence,
existing bucket credentials and a single writer. Never deletes remote objects.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
from importlib import metadata
import json
import os
from pathlib import Path
import re
import platform
import time

GB=10**9
CREDENTIALS=('R2_ACCOUNT_ID','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_BUCKET')


def digest(raw):return hashlib.sha256(raw).hexdigest()


def storage_guard(used,planned,target=8*GB,hard=10*GB):
    if any(type(v) is not int or v<0 for v in (used,planned,target,hard)) or target>hard:raise ValueError('Invalid byte budget')
    projected=used+planned
    return {'current_bytes':used,'planned_new_bytes':planned,'projected_bytes':projected,
            'target_bytes':target,'hard_limit_bytes':hard,
            'status':'BLOCKED_HARD_LIMIT' if projected>hard else 'BLOCKED_TARGET_REVIEW' if projected>target else 'ADMITTED',
            'admitted':projected<=target and projected<=hard}


def validate_approval(value,now=None):
    now=now or datetime.now(timezone.utc)
    if not value.get('approved_synthetic_only') or not value.get('single_writer_attested') or not value.get('account_free_tier_headroom_attested'):
        raise ValueError('Explicit synthetic-only approval, single writer and free tier headroom required')
    stamp=datetime.fromisoformat(value['verified_at_utc'].replace('Z','+00:00'))
    if stamp.tzinfo is None or not 0<=(now-stamp).total_seconds()<=24*3600 or value['billing_month_utc']!=now.strftime('%Y-%m'):
        raise ValueError('Approval/headroom evidence expired or wrong billing month')
    if value.get('incremental_paid_spend_authorized_vnd')!=0:raise ValueError('Pilot supports zero incremental paid spend only')
    for field in ('free_class_a_remaining','free_class_b_remaining'):
        if type(value.get(field)) is not int or value[field]<100:raise ValueError('Need >=100 free request headroom per class')
    if type(value.get('account_storage_estimate_bytes')) is not int or value['account_storage_estimate_bytes']<0:raise ValueError('Missing account-wide storage estimate')
    if value['account_storage_estimate_bytes']>8*GB:raise ValueError('Account storage already above target')


def transient(exc):
    status=getattr(exc,'response',{}).get('ResponseMetadata',{}).get('HTTPStatusCode',0)
    return status in (408,429,500,502,503,504) or isinstance(exc,TimeoutError) or type(exc).__name__ in ('ReadTimeoutError','ConnectTimeoutError','EndpointConnectionError','ConnectionClosedError')


class Calls:
    def __init__(self,client):self.client=client;self.attempts={'A':0,'B':0};self.retries=0
    def call(self,method,category,**kwargs):
        return self.perform(lambda:getattr(self.client,method)(**kwargs),category)
    def perform(self,operation,category):
        for attempt in range(3):
            if self.attempts[category]>=100:raise RuntimeError('Pilot request budget exhausted')
            self.attempts[category]+=1
            try:return operation()
            except Exception as exc:
                if not transient(exc) or attempt==2:raise
                self.retries+=1;time.sleep(.2*2**attempt)


def bucket_usage(calls,bucket):
    # Unfinished multipart bytes cannot be established from object listing alone.
    pending=calls.call('list_multipart_uploads','A',Bucket=bucket,MaxUploads=1)
    if pending.get('Uploads') or pending.get('IsTruncated'):raise ValueError('Unaccounted multipart staging; stop for review')
    total=0;token=None
    while True:
        args={'Bucket':bucket,'MaxKeys':1000}
        if token:args['ContinuationToken']=token
        page=calls.call('list_objects_v2','A',**args)
        total+=sum(o['Size'] for o in page.get('Contents',[]))
        if not page.get('IsTruncated'):return total
        next_token=page.get('NextContinuationToken')
        if not next_token or next_token==token:raise ValueError('Invalid object-list pagination')
        token=next_token


def download(calls,bucket,key,size):
    def fetch():
        response=calls.client.get_object(Bucket=bucket,Key=key);body=response['Body']
        try:raw=body.read(size+1)
        finally:body.close()
        if len(raw)!=size:raise ValueError('Downloaded synthetic size mismatch')
        return raw
    return calls.perform(fetch,'B')


def roundtrip(client,bucket,approval,size=1024**2):
    validate_approval(approval)
    if not 1<=size<=4*1024**2:raise ValueError('Synthetic payload cap is 4 MiB')
    raw=hashlib.shake_256(b'lungseg-synthetic-r2-v1').digest(size);checksum=digest(raw)
    key='pilot/synthetic/sha256/'+checksum+'/payload.bin';calls=Calls(client)
    used=bucket_usage(calls,bucket)
    account_used=approval['account_storage_estimate_bytes']
    if used>account_used:raise ValueError('Bucket listing exceeds attested account total')
    try:
        head=calls.call('head_object','B',Bucket=bucket,Key=key);cached=True
        if head['ContentLength']!=size:raise ValueError('Content-addressed key has wrong size')
        if head.get('StorageClass','STANDARD')!='STANDARD':raise ValueError('Pilot only permits Standard objects')
    except Exception as exc:
        status=getattr(exc,'response',{}).get('ResponseMetadata',{}).get('HTTPStatusCode')
        if status!=404:raise
        cached=False
    decision=storage_guard(max(used,account_used),0 if cached else size)
    if not decision['admitted']:raise ValueError('Storage budget guard blocked upload')
    upload_seconds=None;conditional_conflict_recovered=False
    if not cached:
        start=time.perf_counter()
        try:
            calls.call('put_object','A',Bucket=bucket,Key=key,Body=raw,ContentLength=size,
                       ContentType='application/octet-stream',StorageClass='STANDARD',Metadata={'sha256':checksum,'kind':'synthetic-r2-pilot'},IfNoneMatch='*')
            upload_seconds=time.perf_counter()-start
        except Exception as exc:
            if getattr(exc,'response',{}).get('ResponseMetadata',{}).get('HTTPStatusCode')!=412:raise
            conditional_conflict_recovered=True  # Read-back SHA below must prove same content.
    start=time.perf_counter();restored=download(calls,bucket,key,size);download_seconds=time.perf_counter()-start
    if digest(restored)!=checksum:raise ValueError('R2 read-back SHA256 mismatch')
    return {'status':'R2_SYNTHETIC_ROUNDTRIP_PASS','kind':'synthetic_only','key':key,'bytes':size,'sha256':checksum,
            'cached_existing_payload':cached,'conditional_conflict_recovered':conditional_conflict_recovered,
            'storage_guard':decision,'attempts':calls.attempts,'retries':calls.retries,
            'upload_seconds':upload_seconds,'download_seconds':download_seconds,
            'upload_bytes_per_second':None if upload_seconds is None else size/max(upload_seconds,1e-9),
            'download_bytes_per_second':size/max(download_seconds,1e-9),
            'session_restore_status':'NOT_RUN','monthly_cost_verified':False,'remote_cleanup_performed':False}


def restore(client,bucket,receipt,fresh_session_attested=False):
    if receipt.get('kind')!='synthetic_only' or not 1<=receipt['bytes']<=4*1024**2:raise ValueError('Only synthetic pilot receipts supported')
    key='pilot/synthetic/sha256/'+receipt['sha256']+'/payload.bin'
    if receipt['key']!=key:raise ValueError('Invalid content-addressed key')
    calls=Calls(client)
    head=calls.call('head_object','B',Bucket=bucket,Key=key)
    if head.get('StorageClass','STANDARD')!='STANDARD' or head['ContentLength']!=receipt['bytes']:raise ValueError('Restore requires Standard object and exact size')
    start=time.perf_counter();raw=download(calls,bucket,key,receipt['bytes'])
    if digest(raw)!=receipt['sha256']:raise ValueError('Restored R2 SHA256 mismatch')
    return {'status':'R2_SYNTHETIC_CONTENT_VERIFIED','sha256':receipt['sha256'],'bytes':len(raw),
            'download_seconds':time.perf_counter()-start,'attempts':calls.attempts,'retries':calls.retries,
            'fresh_session_attested':fresh_session_attested,'session_restore_status':'USER_ATTESTATION_REQUIRES_REVIEW' if fresh_session_attested else 'NOT_VERIFIED_NEW_SESSION'}


def client_from_environment():
    missing=[key for key in CREDENTIALS if not os.environ.get(key)]
    if missing:raise ValueError('Required R2 credentials/environment are not configured')
    account=os.environ['R2_ACCOUNT_ID'];bucket=os.environ['R2_BUCKET']
    if not re.fullmatch('[a-fA-F0-9]{32}',account) or not re.fullmatch('[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',bucket):raise ValueError('Invalid R2 account/bucket identifier')
    import boto3
    from botocore.config import Config
    # Retry at one layer only, counted by Calls before every HTTP attempt.
    client=boto3.client('s3',endpoint_url=f'https://{account}.r2.cloudflarestorage.com',region_name='auto',
                        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
                        config=Config(signature_version='s3v4',retries={'mode':'standard','total_max_attempts':1},
                                      connect_timeout=10,read_timeout=30,request_checksum_calculation='when_required',response_checksum_validation='when_required'))
    return client,bucket,digest((account+':'+bucket).encode())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('plan','roundtrip','restore'),default='plan',nargs='?')
    parser.add_argument('--approval-file',type=Path);parser.add_argument('--receipt',type=Path);parser.add_argument('--expected-receipt-sha256')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--fresh-session-attested',action='store_true')
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Report exists; preserve it and use a new output path')
    if args.mode=='plan':
        result={'status':'READY_FOR_USER_EXECUTION','real_r2_status':'NOT_RUN','sdk_available':importlib.util.find_spec('boto3') is not None,
                'credentials_present':{k:bool(os.environ.get(k)) for k in CREDENTIALS},'synthetic_default_bytes':1024**2,
                'storage_target_bytes':8*GB,'application_hard_limit_bytes':10*GB,'account_limits_verified':False}
    else:
        if not args.approval_file:raise ValueError('Explicit existing-bucket synthetic approval file required')
        approval=json.loads(args.approval_file.read_text());validate_approval(approval)
        client,bucket,target=client_from_environment()
        if approval.get('target_id_sha256')!=target:raise ValueError('Approval applies to a different target')
        if args.mode=='roundtrip':result=roundtrip(client,bucket,approval)
        else:
            if not args.receipt or not args.expected_receipt_sha256 or digest(args.receipt.read_bytes())!=args.expected_receipt_sha256:raise ValueError('Externally pinned receipt required')
            receipt=json.loads(args.receipt.read_text())
            if receipt.get('target_id_sha256')!=target:raise ValueError('Receipt target mismatch')
            result=restore(client,bucket,receipt,args.fresh_session_attested)
        result['target_id_sha256']=target
    result['pilot_script_sha256']=digest(Path(__file__).read_bytes())
    result['runtime']={'python':platform.python_version(),'platform':platform.system()}
    result['sdk_versions']={name:metadata.version(name) for name in ('boto3','botocore')} if importlib.util.find_spec('boto3') else {'status':'NOT_INSTALLED'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(result,sort_keys=True,indent=2)+'\n').encode()
    with args.output.open('xb') as handle:handle.write(raw)
    print(json.dumps({'status':result['status'],'report_sha256':digest(raw),'real_network_performed':args.mode!='plan'}))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Avoid SDK exception strings containing endpoint/account/credential details.
        print(json.dumps({'status':'BLOCKED_OR_FAILED','error_type':type(exc).__name__,'details':'Inspect approved config/SDK/target privately; no cleanup performed'}),file=__import__('sys').stderr)
        raise SystemExit(1)
