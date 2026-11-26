"""Reproduce the cancer comparison populations locally, then publish aggregates."""
import argparse
import csv
import gzip
import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from audit_cancer_integration import LONG, EXPECTED, now, num, sha, write_csv

BASE = Path('data/audits/non_covid_access/cancer')
FIELDS = ('measure', 'year', 'site_code', 'icd10', 'sex', 'age_group', 'standard_population')


def rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as handle:
        yield from csv.DictReader(handle)


def save(path, result):
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


def key(row):
    return tuple(row[field] for field in FIELDS)


def status(a, b, tol):
    if a is None or b is None:
        return 'NONNUMERIC_HELD'
    return 'MATCH' if abs(a-b) <= tol else 'DIFFERENT'


def compare(root, out, details):
    folder = root/'analysis_ready'
    extract = folder/LONG
    assert sha(extract) == EXPECTED
    old_path = folder/'national_prefecture_comparison.csv.gz'
    old_rows = list(rows(old_path))
    old = {key(r): r for r in old_rows}
    assert len(old) == len(old_rows) == 32681
    candidates = defaultdict(dict)
    populations = {}
    for row in rows(extract):
        scope = row['source_scope']
        if scope not in ('incidence_national', 'incidence_prefecture') or row['prefecture_code'] not in ('', '0'):
            continue
        measure, year, site, icd, sex, age, standard = key(row)
        if measure == 'population':
            populations[scope, year, sex, age] = num(row['value'])
        if measure not in ('incidence_rate', 'incidence_count', 'population'):
            continue
        native = measure, year, site, sex, age
        assert scope not in candidates[native], native
        candidates[native][scope] = row
    new = {}
    for pair in candidates.values():
        if len(pair) != 2:
            continue
        a, b = (pair[s] for s in ('incidence_national', 'incidence_prefecture'))
        assert key(a) not in new
        new[key(a)] = a, b
    assert len(new) == 31703, len(new)

    causes = Counter()
    transitions = Counter()
    strata = Counter()
    membership = Counter()
    detail = []
    old_fit = Counter()
    common_lineage = Counter()
    age_definition_pairs = Counter()
    causes_by_measure = defaultdict(Counter)
    alternate_status = Counter()
    for k in sorted(old.keys() | new.keys()):
        measure, year, site, icd, sex, age, standard = k
        previous = old.get(k)
        pair = new.get(k)
        old_status = previous['comparison_status'] if previous else 'ABSENT'
        if previous:
            x, y = (num(previous['value_'+side]) for side in ('national', 'prefecture'))
            for tol in (0, 5e-9, 1e-8, 1e-7):
                old_fit[str(tol)] += status(x, y, tol) != old_status
        a, b = pair or ({}, {})
        x, y = num(a.get('value')), num(b.get('value'))
        current = status(x, y, 1e-7) if pair else 'ABSENT'
        group = 'both' if previous and pair else 'old_only' if previous else 'new_only'
        membership[group] += 1
        if group == 'both':
            alternate_status['new_at_old_proxy_tolerance'] += status(x,y,1e-8)!=old_status
            alternate_status['old_at_new_tolerance'] += status(
                num(previous['value_national']),num(previous['value_prefecture']),1e-7)!=current
            for side, source in zip(('national','prefecture'), pair):
                common_lineage[side+'_coordinate_changed'] += previous['source_cell_'+side] != source['source_cell']
                common_lineage[side+'_value_changed'] += num(previous['value_'+side]) != num(source['value'])
        transitions[old_status, current] += 1
        reprint = '/'.join(sorted({r['age_is_reprint'] for r in pair})) if pair else 'not_checked'
        icd_relation = ('same' if a['icd10'] == b['icd10'] else 'different') if pair else 'not_applicable'
        strata[group,measure,age,standard,reprint,icd_relation] += 1
        cause = ''
        if current == 'DIFFERENT':
            n = candidates.get(('incidence_count',year,site,sex,age), {})
            counts = [num(n.get(r['source_scope'], {}).get('value')) for r in pair]
            denoms = [populations.get((r['source_scope'],year,sex,age)) for r in pair]
            cause = 'unknown'
            if icd_relation == 'different':
                cause = 'key_mismatch'
            elif reprint == 'False/True':
                assert age == '85+'
                cause = 'aggregation_definition'
                age_definition_pairs[tuple(r['age_raw'].strip() for r in pair)] += 1
            elif measure == "population":
                cause = "population_denominator"
            elif measure == 'incidence_count':
                cause = 'numerator'
            elif None not in counts and all(denoms) and all(
                abs(count/denom*100000-rate) <= 1e-7
                for count,denom,rate in zip(counts,denoms,(x,y))
            ):
                if counts[0] == counts[1] and denoms[0] != denoms[1]:
                    cause = 'population_denominator'
                elif counts[0] != counts[1] and denoms[0] == denoms[1]:
                    cause = 'numerator'
                elif counts[0] != counts[1] and denoms[0] != denoms[1]:
                    cause = 'other_multiple_components'
            causes[cause] += 1
            causes_by_measure[measure][cause] += 1
        yield_row = (*k,group,old_status,current,reprint,icd_relation,b.get('icd10',''),cause)
        detail.append(yield_row)
    assert sum(causes.values()) == 5468
    assert sum(n for (_,s),n in transitions.items() if s=='MATCH') == 25304
    assert sum(n for (_,s),n in transitions.items() if s=='NONNUMERIC_HELD') == 931
    write_csv(details/'national_comparison_key_diff.csv', (*FIELDS,'membership','old_status','new_status',
              'new_reprint_flags','new_icd10_relation','new_prefecture_icd10','cause'),detail)
    write_csv(details/'national_comparison_status_transitions.csv', (*FIELDS,'old_status','new_status'),
              [(*r[:len(FIELDS)],r[8],r[9]) for r in detail if r[7]=='both' and r[8]!=r[9]])
    write_csv(out/'national_comparison_key_diff.csv', ('membership','measure','age','standard',
              'new_reprint_flags','new_icd10_relation','count'), [(*k,n) for k,n in sorted(strata.items())])
    write_csv(out/'national_comparison_status_transitions.csv', ('old_status','new_status','count'),
              [(*k,n) for k,n in sorted(transitions.items())])
    for label in ('population_denominator','numerator','standard_population','aggregation_definition',
                  'rounding','key_mismatch','other_multiple_components','unknown'):
        causes.setdefault(label, 0)
    save(out/'national_difference_cause_summary.json', {
        'counts':dict(causes), 'by_measure':causes_by_measure,
        'age_definition_pairs':[{'national_header':a,'prefecture_header':b,'count':n}
                                for (a,b),n in sorted(age_definition_pairs.items())]})
    return {'membership':dict(membership), 'old_sha256':sha(old_path), 'old_tolerance_replay_mismatches':dict(old_fit),
            'common_lineage_checks':dict(common_lineage), 'counterfactual_status_mismatches':dict(alternate_status), 'common_status_changes':sum(n for (a,b),n in transitions.items() if a!=b and 'ABSENT' not in (a,b))}


def hashes(root, out):
    integrity = json.loads((BASE/'cancer_integrity_audit.json').read_text())
    drive = json.loads((BASE/'hbcr_drive_preservation_20261126.json').read_text())['files']
    colab = json.loads((BASE/'colab_preservation_20261126_234547.json').read_text())['files']
    first = {r['file']:r for r in integrity}
    second = {r['filename']:r for r in drive}
    third = {r['filename']:r for r in colab if r['group']=='hbcr'}
    result = []
    for name in sorted(third):
        path = root/'hbcr_priority_review'/name
        actual = sha(path)
        historical = [first[name]['sha256'],third[name]['expected_sha256'],third[name]['actual_sha256']]
        sizes = [first[name]['bytes'],second[name]['bytes'],second[name]['expected_bytes'],third[name]['expected_bytes']]
        result.append({'file':name,'measured_sha256':actual,'historical_sha256':historical,
                       'historical_bytes':sizes,'measured_bytes':path.stat().st_size,
                       'match': all(h==actual for h in historical) and all(s==path.stat().st_size for s in sizes)})
    assert len(result)==16
    save(out/'hbcr_historical_hash_verification.json',result)
    return sum(r['match'] for r in result)

# Manual reading of the two report PDFs. Blank age means the sentence gives
# no age cutoff. Page fragments locate the cohort, not just the number.
INTERVALS = [
    ('cT1aN0M0','','内視鏡的治療（ESD/EMR）','診断日','手術','cT1aN0M0の患者'),
    ('cM0','','手術','診断日','手術','cM0で手術を受けた者'),
    ('pⅡ・Ⅲ（pT1、pT3N0を除く）','','手術後化学療法','手術','化学療法','pT1とpT3N0を除く'),
    ('pⅡ・Ⅲ（pT1、pT3N0を除く）','75–84歳','手術後化学療法','手術','化学療法','75-84歳では'),
    ('pⅡ・Ⅲ（pT1、pT3N0を除く）','85歳以上','手術後化学療法','手術','化学療法','85歳以上では'),
    ('cM1','','切除不能（手術・鏡視下治療なし）で化学療法','診断','化学療法実施','切除不能胃癌例'),
    ('cTis/T1N0M0','','内視鏡的治療（ESD/EMR）','診断','手術','cTis/T1N0M0で内視鏡的治療'),
    ('c0～Ⅲ','','手術','診断日','手術','c0～Ⅲ期で手術を受けた者'),
    ('pⅢ','','手術後化学療法','手術','化学療法','PⅢで、手術から化学療法'),
    ('pⅢ','85歳以上','手術後化学療法','手術','化学療法','85歳以上では'),
    ('cⅠ・Ⅱ','','外科手術','診断日','手術','cI、II期で外科手術'),
    ('c0・IA','','手術','診断','手術','c0、IAで手術'),
    ('cⅠ・Ⅱ','','手術','診断','手術','cI、II期で手術'),
    ('cⅠ・Ⅱ','','手術','診断','手術','cI、II期で手術'),
    ('c0・Ⅰ','','手術','診断','手術','c0、I期で手術'),
    ('cⅡ','','手術','診断','手術','cII期では'),
    ('c0・Ⅰ','','手術','診断','治療（方法の明記なし）','c0、I期で手術'),
    ('cⅢ','','手術','診断','治療（方法の明記なし）','cIII期で手術'),
    ('c0・Ⅰ','','手術','診断','手術','c0、I期で手術'),
    ('cⅡ','','手術','診断','手術','cII期では'),
    ('cⅢ','','手術','診断','手術','cIII期では'),
    ('cT1aN0M0','','内視鏡的治療（ESD/EMR）','診断日','手術','cT1aN0M0の患者'),
    ('cT1aN0M0','','内視鏡的治療（ESD/EMR）','診断日','手術','cT1aN0M0の患者'),
    ('cM0','','手術','診断日','手術','cM0で手術を受けた者'),
    ('pⅡ・Ⅲ（pT1、pT3N0を除く）','','手術後化学療法','手術','化学療法','pT1とpT3N0を除く'),
    ('pⅡ・Ⅲ（pT1、pT3N0を除く）','75–84歳','手術後化学療法','手術','化学療法','75-84歳では'),
    ('pⅡ・Ⅲ（pT1、pT3N0を除く）','85歳以上','手術後化学療法','手術','化学療法','85歳以上では'),
    ('cM1','','化学療法（切除不能条件の明記なし）','診断','化学療法実施','cM1患者で化学療法'),
    ('cM0','','手術','診断日','手術','cM0で手術を受けた者'),
]
DAY_VALUES = (46,47,46,49,52,24,20,38,45,47,41,64,45,66,30,32,63,46,53,54,56,37,43,35,41,44,44,19,28)


def compact(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC',value))


def intervals(root,out,details):
    candidates = list(rows(root/'hbcr_priority_review/HBCR_treatment_interval_candidates.csv'))
    statistics = Counter()
    pages = {}
    detailed = []
    assert len(candidates)==len(INTERVALS)==len(DAY_VALUES)==29
    for i,(row,definition,days) in enumerate(zip(candidates,INTERVALS,DAY_VALUES),2):
        year, site, stat, page = (row[k] for k in ('year','site','statistic','pdf_page'))
        stage, age, treatment, start, end, anchor = definition
        if (year,page) not in pages:
            pdf = root/'raw/hospital_registry'/f"{row['source_sha256'][:12]}_{row['source_filename']}"
            assert sha(pdf)==row['source_sha256']
            pages[year,page] = compact(subprocess.check_output(
                ['pdftotext','-layout','-f',page,'-l',page,str(pdf),'-'],text=True))
        body = pages[year,page]
        anchor_at = body.index(compact(anchor))
        expression = rf'{stat}(?:日数は、)?{days}日'
        if i == 19:
            expression = rf'平均日数は、やや短く{days}日'
        if i in (17,21,22):
            expression = rf'{compact(anchor)}{days}日'
        assert int(row['days'])==days and re.search(expression,body[anchor_at:anchor_at+210]), i
        definition_status = 'endpoint_unspecified' if end.startswith('治療（') else 'text_definition_located'
        statistics[year,site,stat,definition_status] += 1
        detailed.append((i,year,site,f'{site}の{stage}で{treatment}を受けた登録例',stage,
                         age or '該当記述に年齢条件の明記なし',treatment,start,end,stat,days,
                         page,row['source_url'],anchor,definition_status))
    write_csv(details/'hbcr_interval_definition_audit.csv',
              ('csv_row','year','site','population','stage','age','treatment','start','end','statistic',
               'days','pdf_page','url','evidence_locator','status'), detailed)
    write_csv(out/'hbcr_interval_definition_audit.csv',('year','site','statistic','status','count'),
              [(*k,n) for k,n in sorted(statistics.items())])
    return {'rows':len(detailed),'endpoint_unspecified':sum(r[-1]=='endpoint_unspecified' for r in detailed),
            'definition_level_comparable_pairs':[
                {'source_csv_rows':[2,24],'site':'胃','stage':'cT1aN0M0','statistic':'平均',
                 'criterion':'ESD/EMR実施例、診断日から手術、両年とも本文の年齢条件明記なし',
                 'restriction':'施設構成や算出対象の完全同一性は未確認。全施設の公表値の記述比較に限定'}]}


def main():
    parser = argparse.ArgumentParser()
    for name in ('root','out','details'):
        parser.add_argument(name,type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    args.details.mkdir(parents=True,exist_ok=True)
    assert args.details.resolve() != args.out.resolve()
    started = now()
    summary = {'started_at_jst':started, 'comparison':compare(args.root,args.out,args.details),
               'hbcr_hash_matches':hashes(args.root,args.out), 'intervals':intervals(args.root,args.out,args.details),
               'finished_at_jst':now(),'adoption_status':'PENDING_QA'}
    save(args.out/'residual_qa_summary.json', summary)


if __name__=='__main__':
    main()
