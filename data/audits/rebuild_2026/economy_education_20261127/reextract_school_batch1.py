import csv,re,subprocess,sys
from pathlib import Path
from decimal import Decimal
root=Path(sys.argv[1]); old=root/'education_prefecture_batch1.csv'
with old.open() as f: baseline=list(csv.DictReader(f))
keys={(r['source_file'],int(r['prefecture_code']),r['school_type']):r for r in baseline}
fields=['partial_count','whole_count','total_schools','partial_rate_pct','whole_rate_pct']
types=['kindergarten','elementary','junior_high','high','special_support','all']
seen=set(); diffs=[]; results=[]
for name in sorted({r['source_file'] for r in baseline}):
 page=3 if name.startswith('20220520') else 2
 lines=subprocess.check_output(['pdftotext','-f',str(page),'-l',str(page),'-layout',str(root/name),'-'],text=True).splitlines()
 clean=lambda s:re.sub(r'[（(][^）)]*[）)]','',s)
 counts=lambda s:[int(v.replace(',','')) for v in re.findall(r'([\d,]+)校',clean(s))]
 rates=lambda s:[Decimal(v) for v in re.findall(r'([\d.]+)%',clean(s))]
 n=0
 for i,s in enumerate(lines):
  m=re.match(r'\s*(\d+)\s+([^\s]+)',s)
  if not m and '全国平均' not in s:continue
  code=int(m[1]) if m else 0
  if not 0<=code<=47:continue
  a=counts(s); b=rates(lines[i+1])
  if len(a)==6:
   p=counts(lines[i-1]); assert len(p)==12,(name,code,p)
   a=[v for j in range(6) for v in (p[2*j],p[2*j+1],a[j])]
  assert len(a)==18 and len(b)==12,(name,code,a,b)
  for j,t in enumerate(types):
   k=(name,code,t); assert k not in seen;seen.add(k);r=keys[k]
   vals=a[3*j:3*j+3]+b[2*j:2*j+2]
   for field,v in zip(fields,vals):
    if Decimal(r[field])!=v:diffs.append((k,field,r[field],v))
   n+=5
 results.append((name,n))
assert seen==set(keys)
print(results);print('cells',len(seen)*5,'differences',len(diffs));print(diffs[:20])
