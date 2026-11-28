# BK06～BK11 Colab再現セル

以下をColabのPythonセル1つに貼り付けて実行する。マウントしたマイドライブに日時付きの研究用フォルダを作成する。GitHubの作業ブランチを読める環境が必要。

```python
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import subprocess
import sys
from google.colab import drive

drive.mount('/content/drive')
subprocess.run(['apt-get', 'install', '-y', '-qq', 'poppler-utils'], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'lxml'], check=True)
stamp = datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d_%H%M%S_%f')
work = Path('/content') / f'bk06_11_{stamp}'
work.mkdir()
repo = work / 'repo'
subprocess.run(['git', 'clone', '--depth', '1', '--branch', 'audit/economy-bankruptcy-bk06-11',
                'https://github.com/0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research.git',
                str(repo)], check=True)
sys.path.insert(0, str(repo/'scripts'))
from education_sources import acquire

old = repo/'data/audits/rebuild_2026/bankruptcy_bk06_11/source_manifest.json'
records = json.loads(old.read_text())
sources = {r['filename']: r['url'] for r in records if r['status']=='acquired'}
baseline = work/'baseline'
fresh = {r['filename']: r for r in acquire(baseline/'raw', sources)}
if any(r['status']!='acquired' for r in fresh.values()):
    raise RuntimeError(f'前回資料の再取得が未完了です。保存先 {baseline}')
for entry in records:
    if entry['status']=='acquired':
        previous = entry['sha256']
        entry.update({k:v for k,v in fresh[entry['filename']].items() if k!='publisher'})
        entry['historical_sha256'] = previous
        entry['historical_hash_matches'] = entry['sha256']==previous
manifest = work/'baseline_manifest.json'
manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
destination = Path('/content/drive/MyDrive/COVID19-Pandemic-Research') / f'BK06-11_{stamp}'
destination.mkdir(parents=True)
subprocess.run([sys.executable, str(repo/'scripts/audit_bankruptcy_history.py'),
                str(destination), '--baseline', str(baseline), '--baseline-manifest', str(manifest),
                '--audit', str(destination/'audit')], check=True)
archive = destination/'bankruptcy_bk06_11_research.zip'
with archive.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
print(archive, archive.stat().st_size, digest)
```
