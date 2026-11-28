# Batch C-13 Colab単一セル

Google ColabのPythonセルに貼り付ける。公式資料を取得時点の公開版から再構築し、既存のDrive研究フォルダ内に日時付きで保存する。取得時点が異なるため原資料やZIPのハッシュが変わる場合がある。

```python
from datetime import datetime
from hashlib import file_digest
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from zoneinfo import ZoneInfo
from google.colab import drive

commit = '9e7e0ce0a8f40fd5c761d0638c4c86e2744fd08b'
url = 'https://github.com/0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research.git'
mount = '/content/drive'
stamp = datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d_%H%M%S_%f')
root = Path('/content')/f'c13_{stamp}'
root.mkdir()
dest = Path(mount)/'MyDrive/COVID19_Research/economy/employment_wage'/root.name
log = {'code_commit':commit,'session_jst':stamp,'kind':'colab_reacquisition'}

def run(*args):
    subprocess.run(args,check=True)

def digest(path):
    with path.open('rb') as stream:
        return file_digest(stream,'sha256').hexdigest()

def copy_new(src,dst):
    with src.open('rb') as stream, dst.open('xb') as saved:
        shutil.copyfileobj(stream,saved)

def save_log(phase):
    path = root/f'transfer_{phase}.json'
    with path.open('x',encoding='utf-8') as stream:
        json.dump(log,stream,ensure_ascii=False,indent=2)
    if dest.is_dir():
        copy_new(path,dest/path.name)
    print(path)

try:
    drive.mount(mount)
    if not (Path(mount)/'MyDrive').is_dir():
        raise RuntimeError('Drive mount not available')
    dest.mkdir(parents=True)
    run('apt-get','update','-qq')
    run('apt-get','install','-y','-qq','poppler-utils')
    run(sys.executable,'-m','pip','install','-q','lxml','openpyxl')
    repo = root/'repo'
    run('git','init','-q',str(repo))
    run('git','-C',str(repo),'fetch','--depth=1',url,commit)
    run('git','-C',str(repo),'checkout','--detach','FETCH_HEAD')
    actual = subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    if actual!=commit:
        raise RuntimeError('Code commit mismatch')
    output = root/'output'
    run(sys.executable,str(repo/'scripts/acquire_employment_wage_c13.py'),str(output))
    sys.path.insert(0,str(repo/'scripts'))
    from acquire_employment_wage_c13 import verify
    zipfile = output/'employment_wage_c13.zip'
    log['verified_members'] = verify(zipfile)
    log['sha256'] = digest(zipfile)
    log['bytes'] = zipfile.stat().st_size
    saved = dest/f'employment_wage_c13_{stamp}.zip'
    copy_new(zipfile,saved)
    for p in output.glob('*.json'):
        copy_new(p,dest/p.name)
    save_log('before_unmount')
    drive.flush_and_unmount()
    drive.mount(mount)
    log['remount_sha256'] = digest(saved)
    if log['remount_sha256']!=log['sha256']:
        raise RuntimeError('Drive ZIP SHA-256 mismatch')
    verify(saved)
    save_log('verified')
    drive.flush_and_unmount()
    print(saved,log['sha256'])
except Exception:
    log['error'] = traceback.format_exc()
    save_log('failed')
    raise
```
