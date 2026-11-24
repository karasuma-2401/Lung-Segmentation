"""Real local pip-less-venv recovery check; synthetic wheel, no network/install to base."""
import base64
import csv
import hashlib
from io import StringIO
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


def test_parent_pip_targets_pipless_venv_without_polluting_base(tmp_path):
    name='lungseg_recovery_synthetic_fixture'
    assert importlib.util.find_spec(name) is None
    wheel=tmp_path/(name+'-0.0.0-py3-none-any.whl')
    dist=name+'-0.0.0.dist-info'
    content={name+'.py':b'MARKER = "SYNTHETIC_RECOVERY_CHECK"\n',
             dist+'/METADATA':f'Metadata-Version: 2.1\nName: {name}\nVersion: 0.0.0\n'.encode(),
             dist+'/WHEEL':b'Wheel-Version: 1.0\nGenerator: lungseg-synthetic-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
    record=StringIO();writer=csv.writer(record,lineterminator='\n')
    for path,raw in content.items():
        value=base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
        writer.writerow([path,'sha256='+value,len(raw)])
    writer.writerow([dist+'/RECORD','','']);content[dist+'/RECORD']=record.getvalue().encode()
    with zipfile.ZipFile(wheel,'x') as handle:
        for path,raw in content.items():handle.writestr(path,raw)
    target=tmp_path/'pipless'
    subprocess.run([sys.executable,'-I','-m','venv','--without-pip',str(target)],check=True,capture_output=True)
    python=target/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    missing=subprocess.run([str(python),'-I','-c','import pip'],capture_output=True)
    assert missing.returncode!=0
    env={k:v for k,v in os.environ.items() if not k.startswith('PIP_') and k not in ('PYTHONHOME','PYTHONPATH')}
    env.update(PIP_CONFIG_FILE=os.devnull,PIP_DISABLE_PIP_VERSION_CHECK='1')
    install=subprocess.run([sys.executable,'-m','pip','--python',str(python),'install','--no-index','--no-deps',str(wheel)],env=env,text=True,capture_output=True)
    assert install.returncode==0,install.stdout+install.stderr
    code=f'import json,sys,{name} as x; print(json.dumps({{"marker":x.MARKER,"prefix":sys.prefix}}))'
    result=subprocess.run([str(python),'-I','-c',code],check=True,capture_output=True,text=True)
    checked=json.loads(result.stdout)
    assert checked['marker']=='SYNTHETIC_RECOVERY_CHECK' and Path(checked['prefix']).resolve()==target.resolve()
    assert importlib.util.find_spec(name) is None
