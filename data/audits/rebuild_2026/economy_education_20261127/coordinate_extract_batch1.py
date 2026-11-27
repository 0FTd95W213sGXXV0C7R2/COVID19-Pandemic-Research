import csv, re, sys
from pathlib import Path
from decimal import Decimal
import fitz
root=Path(sys.argv[1]); out=Path(sys.argv[2])
dates=['2022-01-26','2022-02-09','2022-02-22','2022-03-09','2022-04-11','2022-05-09']
types=['kindergarten','elementary','junior_high','high','special_support','all']
rows=[]
for f,date in zip(sorted(root.glob('20220[2-5]*pdf')),dates,strict=True):
 with fitz.open(f) as doc:
  p=doc[-1]; words=p.get_text('words'); page=len(doc)
 counts=[w for w in words if re.fullmatch(r'[\d,]+校',w[4])]; rates=[w for w in words if re.fullmatch(r'[\d.]+%',w[4])]
 assert len(counts)==864 and len(rates)==576
 groups=[]
 for w in sorted(rates,key=lambda w:w[1]):
  if not groups or abs(w[1]-groups[-1][0][1])>1:groups.append([])
  groups[-1].append(w)
 assert len(groups)==48 and all(len(g)==12 for g in groups),(f,len(groups))
 buckets=[[] for _ in groups]
 for w in counts:
  i=min(range(48),key=lambda i:abs(w[1]-(groups[i][0][1]-2.5)));buckets[i].append(w)
 for i,(a,b) in enumerate(zip(buckets,groups)):
  assert len(a)==18,(f,i,len(a))
  a=sorted(a,key=lambda w:w[0]);b=sorted(b,key=lambda w:w[0]);code=(i+1)%48
  for j,t in enumerate(types):
   vals=[int(w[4][:-1].replace(',','')) for w in a[3*j:3*j+3]]+[Decimal(w[4][:-1]) for w in b[2*j:2*j+2]]
   rows.append([date,code,t,*vals,f.name,page])
with out.open('w') as f:
 w=csv.writer(f);w.writerow('observation_date,prefecture_code,school_type,partial_count,whole_count,total_schools,partial_rate_pct,whole_rate_pct,source_file,source_page'.split(','));w.writerows(rows)
