# Batch C-14 Colab単一セル

既存C-13統合ZIPのDrive上のパスを `baseline_on_drive` に指定する。元のCodex版の場合は期待ハッシュと照合する。空欄の場合は公式資料からC-13も再構築する。その場合は資料の改訂により取得時の版や件数が異なり得る。

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

pin = 'e7813b93862a18d66615575b167a8f0b548e4f9c'
baseline_on_drive = ''
mount = '/content/drive'
stamp = datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d_%H%M%S_%f')
work = Path('/content')/f'c14_{stamp}'
work.mkdir()
repo = work/'repo'
dest = Path(mount)/'MyDrive/COVID19_Research/economy/employment_wage'/work.name
log = {'code_commit':pin,'started_jst':stamp}

def run(*args):
    subprocess.run(args,check=True)

def copy_new(source,target):
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src,dst)

def record(name):
    path = work/(name+'.json')
    with path.open('x',encoding='utf-8') as f:
        json.dump(log,f,ensure_ascii=False,indent=2)
    if dest.is_dir():
        copy_new(path,dest/path.name)
    print(path)

try:
    drive.mount(mount)
    if not (Path(mount)/'MyDrive').is_dir():
        raise RuntimeError('Driveのマウントを確認できません')
    dest.mkdir(parents=True)
    run('apt-get','update','-qq')
    run('apt-get','install','-y','-qq','poppler-utils')
    run(sys.executable,'-m','pip','install','-q','lxml','openpyxl')
    run('git','init','-q',str(repo))
    url = 'https://github.com/0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research.git'
    run('git','-C',str(repo),'fetch','--depth=1',url,pin)
    run('git','-C',str(repo),'checkout','--detach','FETCH_HEAD')
    sys.path.insert(0,str(repo/'scripts'))
    from audit_employment_wage_c14 import C13_SHA, digest, verify
    if baseline_on_drive:
        baseline = work/'c13_integrated.zip'
        copy_new(Path(baseline_on_drive),baseline)
        if digest(baseline)!=C13_SHA:
            raise ValueError('指定されたC-13 ZIPはCodex監査版と異なります')
    else:
        old = work/'c13'
        extended = work/'c13_followup'
        run(sys.executable,str(repo/'scripts/acquire_employment_wage_c13.py'),str(old))
        run(sys.executable,str(repo/'scripts/extend_employment_wage_c13.py'),
            str(old/'employment_wage_c13.zip'),str(extended))
        baseline = extended/'employment_wage_c13_integrated.zip'
    log['c13_sha256'] = digest(baseline)
    log['exact_codex_c13'] = log['c13_sha256']==C13_SHA
    output = work/'audit'
    run(sys.executable,str(repo/'scripts/audit_employment_wage_c14.py'),str(baseline),str(output))
    run(sys.executable,str(repo/'scripts/verify_employment_wage_c14.py'),str(output))
    archive = output/'employment_wage_c14.zip'
    log['sha256'] = digest(archive)
    log['verified_members'] = verify(archive)
    saved = dest/f'employment_wage_c14_{stamp}.zip'
    copy_new(archive,saved)
    for path in sorted(output.glob('*.json')):
        copy_new(path,dest/path.name)
    record('before_unmount')
    drive.flush_and_unmount()
    drive.mount(mount)
    log['remount_sha256'] = digest(saved)
    if log['remount_sha256']!=log['sha256']:
        raise RuntimeError('再マウント後のZIP SHA-256不一致')
    verify(saved)
    record('verified')
    drive.flush_and_unmount()
except Exception:
    log['error'] = traceback.format_exc()
    record('failure')
    raise
```
