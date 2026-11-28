# BK06～BK11 最終補完のColab単一セル

次のセルは、公開公式資料から**再構築した版**を既存研究フォルダの日時付きサブフォルダへ保存する。Codexで監査したZIPの転送とは別の工程で、原資料の再公表や収録日変更によりハッシュが変わり得る。セルは再取得した各ファイルを台帳のハッシュと照合し、差異を記録する。GitHubから取得するコードと台帳のコミットを固定している。

```python
from datetime import datetime
from hashlib import file_digest
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from zipfile import ZipFile
from zoneinfo import ZoneInfo
from google.colab import drive

PIN = '1ea1434be9daaf8bb31de3a21ca422a6802e9396'
CODEX_FINAL_ZIP_SHA256 = 'e314660c67fcb4e767fbb5ef948ee5109950c07b4dcd5571ac35f5a751131cc4'
SUPPLEMENT_SHA256 = '49ec16f50ca44b14aa0bdca8928675ab9bd8056139c41d1ec9e709e965044957'
BASE = 'e43c95e902c250d45658ab56e1dae15829edb98b'
repo_url = 'https://github.com/0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research.git'
mount = '/content/drive'
def jst():
    return datetime.now(ZoneInfo('Asia/Tokyo'))

stamp = jst().strftime('%Y%m%d_%H%M%S_%f')
work = Path('/content') / f'bankruptcy_rebuilt_{stamp}'
work.mkdir()
repo = work/'repo'
dest = Path(mount)/'MyDrive/COVID19_Research/economy/bankruptcy'/work.name
log = {'kind':'colab_rebuilt', 'code_commit':PIN, 'codex_baseline_commit':BASE,
       'codex_final_zip_sha256':CODEX_FINAL_ZIP_SHA256, 'started_jst':jst().isoformat(), 'source_hash_changes':[], 'download_failures':[]}

def run(*args):
    subprocess.run(args, check=True)

def digest(path):
    with path.open('rb') as stream:
        return file_digest(stream,'sha256').hexdigest()

def copy_new(src, dst):
    with src.open('rb') as source, dst.open('xb') as target:
        shutil.copyfileobj(source,target)

def save_log(phase):
    local = work/f'transfer_audit_{phase}.json'
    with local.open('x',encoding='utf-8') as stream:
        json.dump(log,stream,ensure_ascii=False,indent=2)
    if dest.is_dir():
        copy_new(local,dest/local.name)
    print(f'{phase}: {local}')

try:
    drive.mount(mount)
    if not (Path(mount)/'MyDrive').is_dir():
        raise RuntimeError('Google Driveのマウントを確認できません')
    dest.mkdir(parents=True)
    run('apt-get','update','-qq')
    run('apt-get','install','-y','-qq','poppler-utils')
    run(sys.executable,'-m','pip','install','-q','lxml','PyMuPDF')
    run('git','init','-q',str(repo))
    run('git','-C',str(repo),'fetch','--depth=1',repo_url,PIN)
    run('git','-C',str(repo),'checkout','--detach','FETCH_HEAD')
    resolved = subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    if resolved!=PIN:
        raise RuntimeError(f'Unexpected commit: {resolved}')
    sys.path.insert(0,str(repo/'scripts'))
    from audit_bankruptcy_history import download

    history_meta = repo/'data/audits/rebuild_2026/bankruptcy_bk06_11_followup/source_manifest.json'
    archive = json.loads(history_meta.read_text())
    previous, historical = work/'original_batch', work/'historical_batch'
    fresh_previous = None
    for folder,group in ((previous,'previous'),(historical,'new')):
        raw = folder/'raw'
        raw.mkdir(parents=True)
        entries = archive[group]
        for entry in entries:
            if entry.get('http_status')==403:
                (raw/(entry['filename']+'.denied.json')).write_text(json.dumps(entry))
        found = []
        download(raw,{r['filename']:r['url'] for r in entries if r['status']=='acquired'},
                 found,'取得元は元台帳に記載')
        original = {r['filename']:r for r in entries}
        for r in found:
            old = original[r['filename']]
            if r['status']!='acquired':
                log['download_failures'].append(r)
                continue
            if r['sha256']!=old['sha256']:
                log['source_hash_changes'].append({'filename':r['filename'],
                    'expected':old['sha256'],'reacquired':r['sha256']})
            if group=='previous':
                old['historical_sha256'] = old['sha256']
                old.update({k:v for k,v in r.items() if k!='publisher'})
        if group=='previous':
            fresh_previous = work/'reacquired_baseline_manifest.json'
            fresh_previous.write_text(json.dumps(entries,ensure_ascii=False))
    save_log('acquisition')
    if log['download_failures']:
        raise RuntimeError('原資料に再取得失敗あり。取得監査JSONを参照してください。')

    run(sys.executable,str(repo/'scripts/audit_bankruptcy_history.py'),str(historical),
        '--baseline',str(previous),'--baseline-manifest',str(fresh_previous),
        '--audit',str(work/'historical_audit'))
    final, audit = work/'final', work/'final_audit'
    run(sys.executable,str(repo/'scripts/complete_bankruptcy_audit.py'),
        str(historical/'bankruptcy_bk06_11_research.zip'),str(final),str(audit))

    supplemental = final/'raw/tsr_price_original_2023.html'
    if supplemental.exists():
        observed_source = digest(supplemental)
        if observed_source!=SUPPLEMENT_SHA256:
            log['source_hash_changes'].append({'filename':supplemental.name,
                'expected':SUPPLEMENT_SHA256,'reacquired':observed_source})
    else:
        log['download_failures'].append({'filename':supplemental.name,'status':'not_acquired'})

    rebuilt = final/'bankruptcy_final.zip'
    expected_internal = json.loads((final/'internal_hashes.json').read_text())
    with ZipFile(rebuilt) as z:
        if z.testzip() is not None or set(z.namelist())!=set(expected_internal):
            raise RuntimeError('ZIPのCRCまたはファイル一覧が不一致')
        for member, expected in expected_internal.items():
            with z.open(member) as stream:
                if file_digest(stream,'sha256').hexdigest()!=expected:
                    raise RuntimeError(f'ZIP内SHA-256不一致: {member}')
    expected_hash = digest(rebuilt)
    saved = dest/f'bankruptcy_rebuilt_{stamp}.zip'
    copy_new(rebuilt,saved)
    for src in sorted(audit.glob('*.json')):
        copy_new(src,dest/src.name)
    copy_new(final/'internal_hashes.json',dest/'internal_hashes.json')
    log.update(zip_filename=saved.name,local_zip_sha256=expected_hash,zip_bytes=rebuilt.stat().st_size,
               internal_sha256_verified=len(expected_internal),crc='pass')
    save_log('before_unmount')
    drive.flush_and_unmount()
    drive.mount(mount)
    observed = digest(saved)
    log.update(drive_zip_sha256=observed,drive_hash_match=observed==expected_hash,
               finished_jst=jst().isoformat())
    if observed!=expected_hash:
        raise RuntimeError('再マウント後のZIP全体のSHA-256が不一致')
    save_log('verified')
    drive.flush_and_unmount()
    print(f'検証済み {saved} {observed}')
except Exception:
    log.update(failed_jst=jst().isoformat(),failure=traceback.format_exc())
    # Local log is created even if Drive is inaccessible.
    save_log('failure')
    if not dest.is_dir():
        try:
            drive.mount(mount)
            if dest.is_dir():
                copy_new(work/'transfer_audit_failure.json',dest/'transfer_audit_failure.json')
        except Exception as mount_error:
            print(f'Drive監査記録への転送不可: {mount_error}')
    raise
```
