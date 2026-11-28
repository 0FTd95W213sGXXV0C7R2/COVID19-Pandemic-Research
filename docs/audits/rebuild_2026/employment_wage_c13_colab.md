# Batch C-13 統合Colab単一セル

Google ColabのPythonセルに貼り付ける。旧版ZIPのDriveパスを `baseline_on_drive` に指定すると原本をそのまま保持する。未指定時は前回分を公式URLから再取得するため、原資料の版・行数・ハッシュが変わり得る。以前の休業者明細がある場合は `prior_on_drive` に公式座標（table_id、time_code、sex_code、employment_status、industry、age、region、measure、unit、raw）に対応づけたCSVを指定する。賃金の既存明細は、同一版のハッシュと原表座標を確認したうえで原表座標形式に変換したCSVを `prior_wage_on_drive` に指定する。

```python
import csv
import io
from zipfile import ZipFile
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

commit = '5e42315057f51c6df8d615f676067d2386c661b8'
baseline_on_drive = ''
prior_on_drive = ''
prior_wage_on_drive = ''
expected_baseline = 'eda32d11903e395103b2cf9ed37927f190e6dfec39f7dba57869bed58d3f9bab'
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
    if baseline_on_drive:
        baseline = root/'employment_wage_c13_original.zip'
        copy_new(Path(baseline_on_drive),baseline)
        if digest(baseline)!=expected_baseline:
            raise RuntimeError('指定した旧版ZIPのSHA-256がCodex版と異なります')
    else:
        old_output = root/'previous_version_reacquired'
        run(sys.executable,str(repo/'scripts/acquire_employment_wage_c13.py'),str(old_output))
        baseline = old_output/'employment_wage_c13.zip'
    log['baseline_sha256'] = digest(baseline)
    log['original_codex_baseline'] = log['baseline_sha256']==expected_baseline
    reference = json.loads((repo/'data/audits/rebuild_2026/employment_wage_c13/source_manifest.json').read_text())
    with ZipFile(baseline) as z:
        manifest = json.loads(z.read('source_manifest.json'))
    known = {r['filename']:r.get('sha256') for r in reference}
    log['baseline_source_changes'] = [{'file':r['filename'],'expected':known.get(r['filename']),
        'observed':r.get('sha256')} for r in manifest if r.get('sha256')!=known.get(r['filename'])]
    args = []
    if prior_on_drive:
        prior = root/'prior.csv'
        copy_new(Path(prior_on_drive),prior)
        args.extend(['--prior',str(prior)])
    if prior_wage_on_drive:
        prior_wage = root/'prior_wage.csv'
        copy_new(Path(prior_wage_on_drive),prior_wage)
        as_fields = ('source','sheet','cell','period','frequency','region_code','metric','unit','adjustment')
        def indexed(rows):
            result = {}
            for row in rows:
                if row['source']!='wage_index.csv':
                    continue
                key = tuple(row[k] for k in as_fields)
                if key in result:
                    raise ValueError('Duplicate wage coordinate')
                result[key] = row['raw']
            return result
        with ZipFile(baseline) as z:
            left = indexed(csv.DictReader(io.StringIO(z.read('observations.csv').decode())))
            wage_hash = next(r['sha256'] for r in manifest if r['filename']=='wage_index.csv')
        with prior_wage.open(encoding='utf-8-sig',newline='') as stream:
            rows = list(csv.DictReader(stream))
        if not rows or any(r.get('source_sha256')!=wage_hash for r in rows):
            raise ValueError('Prior wage source SHA-256 differs')
        right = indexed(rows)
        common = left.keys() & right.keys()
        log['prior_wage_comparison'] = {'matching':sum(left[k]==right[k] for k in common),
            'different':sum(left[k]!=right[k] for k in common),
            'c13_only':len(left.keys()-right.keys()),'prior_only':len(right.keys()-left.keys())}
    run(sys.executable,str(repo/'scripts/extend_employment_wage_c13.py'),str(baseline),str(output),*args)
    sys.path.insert(0,str(repo/'scripts'))
    from acquire_employment_wage_c13 import verify
    zipfile = output/'employment_wage_c13_integrated.zip'
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
