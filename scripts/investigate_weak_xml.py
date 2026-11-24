"""Bounded official-source investigation. Never interprets XML as production labels."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urljoin,urlparse,unquote
from urllib.request import Request,urlopen
import zipfile
from lungseg.data.msd_acquire import require_space
from lungseg.runs import utc_now,write_json

PAGE='https://www.cancerimagingarchive.net/tcia-downloads/lung-pet-ct-dx-da-other/lung-pet-ct-dx-annotations-xml-files-rev12222020/'
COLLECTION='https://www.cancerimagingarchive.net/collection/lung-pet-ct-dx/'
DIRECTORY='https://www.cancerimagingarchive.net/wp-content/uploads/?C=M%3BO%3DA'
NAME='lung-pet-ct-dx-annotations-xml-files-rev12222020'
CAP=24*1024**2


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.links.extend(v for k,v in attrs if k=='href' and v)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir',type=Path,default=Path('docs/evidence/p1_3_1'))
    parser.add_argument('--archive-dir',type=Path,default=Path('data/cache/weak_xml_investigation'))
    args=parser.parse_args();target=args.evidence_dir/'xml_source_investigation.json'
    result={'timestamp_utc':utc_now(),'status':'OPEN','archive_byte_cap':CAP,'attempts':[],
            'requested_official_page':PAGE,'archive_identity_verified':False,'XML_SR_equivalence_verified':False}
    candidates=[]
    for url in (PAGE,COLLECTION,DIRECTORY):
        event={'url':url,'method':'GET','timeout_seconds':20,'body_limit_bytes':2*1024**2}
        try:
            with urlopen(Request(url,headers={'User-Agent':'Lungseg-source-validation/1.0'}),timeout=20) as response:
                body=response.read(2*1024**2+1);event.update(http_status=response.status,final_url=response.url,
                    content_type=response.headers.get('Content-Type'),content_length=response.headers.get('Content-Length'))
                if len(body)>2*1024**2:raise ValueError('Page exceeds bounded read limit')
                event.update(body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest())
                links=Links();links.feed(body.decode('utf-8',errors='replace'))
                matches=[urljoin(response.url,href) for href in links.links if NAME in unquote(href).lower()]
                event['matching_links']=matches
                candidates.extend(link for link in matches if '.zip' in urlparse(link).path.lower()
                                  and urlparse(link).hostname in ('www.cancerimagingarchive.net','wiki.cancerimagingarchive.net'))
        except Exception as exc:event.update(error_type=type(exc).__name__,error=str(exc))
        result['attempts'].append(event);write_json(target,result)
        if candidates:break
    for url in list(dict.fromkeys(candidates))[:1]:
        event={'url':url,'method':'GET','timeout_seconds':20,'body_limit_bytes':CAP}
        try:
            require_space(args.archive_dir,CAP+4*1024**3)
            with urlopen(url,timeout=20) as response:
                length=response.headers.get('Content-Length');event.update(http_status=response.status,final_url=response.url,
                    content_length=length,content_type=response.headers.get('Content-Type'))
                if length is None or int(length)>CAP:raise ValueError('Archive length absent or exceeds explicit cap')
                raw=response.read(int(length))
                if len(raw)!=int(length):raise ValueError('Incomplete archive')
            args.archive_dir.mkdir(parents=True,exist_ok=True)
            path=args.archive_dir/'Lung-PET-CT-Dx-Annotations-XML-Files-rev12222020.zip'
            with path.open('xb') as handle:handle.write(raw)
            with zipfile.ZipFile(path) as archive:
                members=archive.infolist()
                event.update(archive_path=path.as_posix(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                             members=len(members),uncompressed_bytes=sum(m.file_size for m in members),
                             xml_members=sum(m.filename.lower().endswith('.xml') for m in members))
            result.update(status='ARCHIVE_ACQUIRED_COMPARISON_OPEN',archive_identity_verified=True)
        except Exception as exc:event.update(error_type=type(exc).__name__,error=str(exc))
        result['attempts'].append(event)
    if not result['archive_identity_verified']:result.update(status='BLOCKED_SOURCE',blocker='No accessible verified official ZIP acquired in bounded attempts')
    write_json(target,result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
