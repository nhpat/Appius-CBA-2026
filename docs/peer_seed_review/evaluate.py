"""Evaluate peer and seed name matching."""
import csv
import itertools
import json
import sqlite3
from pathlib import Path
import os
import sys
import importlib.metadata
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from prospector.names import normalize, similarity
os.chdir(ROOT)
OUT = ROOT / 'outputs/peer_seed_review'
OUT.mkdir(parents=True, exist_ok=True)
clients = {c: yaml.safe_load(Path('config/clients/' + c + '.yaml').read_text()) for c in ['nyspha', 'appius']}
inventory = []
for client, cfg in clients.items():
    for role in ['peers', 'validation_seeds']:
        for name in cfg[role]:
            inventory.append({'client': client, 'role': role, 'name': name})

def writeCsv(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

writeCsv('client_inventory.csv', inventory)
pairs = []
def add(a, b, expected, kind, source, note=''):
    pairs.append(dict(name_a=a, name_b=b, expected_match=expected, kind=kind, source=source, note=note))

add('New York Health Foundation', 'New York State Health Foundation', True, 'documented_alias', 'https://nyhealthfoundation.org/2022/05/17/an-updated-name-the-same-commitment/')
add('Health Foundation for Western and Central New York', 'Community Health Foundation of Western and Central New York', True, 'documented_alias', 'https://hfwcny.org/about/our-story/')
add('Adirondack Foundation', 'Adirondack Community Foundation', True, 'documented_alias', 'https://adkcommunityfoundation.org/about-us/our-history/')
add('Adirondack Foundation', 'Adirondack Community Trust', True, 'documented_alias', 'https://adkcommunityfoundation.org/about-us/our-history/')
add('Common Ground Health', 'Finger Lakes Health Systems Agency', True, 'documented_alias', 'https://commongroundhealth.org/privacy-policy')
add('Public Health Solutions', 'Medical and Health Research Association', True, 'documented_alias', 'https://healthsolutions.org/about/')
add('New York State Association of County Health Officials', 'NYSACHO', True, 'documented_alias', 'https://www.nysenate.gov/sites/default/files/new_york_state_association_of_county_health_officials_nysacho.pdf')
add('New York State Association for Rural Health', 'NYSARH', True, 'documented_alias', 'https://nysarh.org/newsletters/nysarh-newsletter-spring-2023-print-version/')
add('American Public Health Association', 'APHA', True, 'documented_alias', 'https://www.apha.org/')
add('Connecticut Public Health Association', 'CPHA', True, 'documented_alias', 'https://cpha.info/')
add('New Jersey Public Health Association', 'NJPHA', True, 'documented_alias', 'https://www.njpha.org/home/')
add('Massachusetts Public Health Association', 'MPHA', True, 'documented_alias', 'https://masspublichealth.org/')
add('John R. Oishei Foundation', 'Oishei Foundation', True, 'documented_alias', 'https://oishei.org/')
add('Peter and Elizabeth C. Tower Foundation', 'Peter & Elizabeth Tower Foundation', True, 'documented_alias', 'https://thetowerfoundation.org/app/uploads/2020/08/TF20001_2019_Annual_Highlights_Digital_V2-Final.pdf')

orgs = [('New York Health Foundation','https://nyhealthfoundation.org/2022/05/17/an-updated-name-the-same-commitment/'),('Health Foundation for Western and Central New York','https://hfwcny.org/about/our-story/'),('Adirondack Foundation','https://adkcommunityfoundation.org/about-us/our-history/'),('John R. Oishei Foundation','https://oishei.org/'),('Peter and Elizabeth C. Tower Foundation','https://thetowerfoundation.org/the-foundation/history-founders/'),('Community Foundation of Tompkins County','https://www.cftompkins.org/'),('Community Foundation of Elmira-Corning and the Finger Lakes','https://communityfund.org/')]
for (a, sa), (b, sb) in itertools.combinations(orgs, 2):
    add(a,b,False,'distinct_organizations',sa+' ; '+sb)
for a, b, sa, sb in [('American Public Health Association','New Jersey Public Health Association','https://www.apha.org/','https://www.njpha.org/home/'),('American Public Health Association','Connecticut Public Health Association','https://www.apha.org/','https://cpha.info/'),('New Jersey Public Health Association','Connecticut Public Health Association','https://www.njpha.org/home/','https://cpha.info/'),('Massachusetts Public Health Association','Connecticut Public Health Association','https://masspublichealth.org/','https://cpha.info/')]:
    add(a,b,False,'distinct_organizations',sa+' ; '+sb)
add('Connecticut Public Health Association', 'Connecticut Association of Health Plans', False, 'distinct_organizations', 'https://cpha.info/ ; https://www.ctahp.com/aboutus.htm', 'Discovered as nearest BMF candidate; different public health and insurer associations.')
add('Community Foundation of the Southern Finger Lakes','Finger Lakes Community Foundation',False,'repository_guardrail','README.md; prospector/score.py:315', 'Expected non-match mandated by repository; not independently verified as two real legal entities. Excluded from empirical metrics.')
for name in sorted({r['name'] for r in inventory}):
    add(name, 'THE ' + name.upper() + ', INC.', True, 'constructed_control', 'config/clients/*.yaml', 'Constructed case and suffix control, not an observed alias. Excluded from empirical metrics.')
for p in pairs:
    p['normalized_a'],p['normalized_b']=normalize(p['name_a']),normalize(p['name_b'])
    p['similarity']=similarity(p['normalized_a'],p['normalized_b'])
    for t in [15,40,70,75,80,85,88,89,90,95,100]:
        p['match_at_'+str(t)]=p['similarity']>=t
writeCsv('labeled_pairs.csv',pairs)
empirical=[p for p in pairs if p['kind'] in ['documented_alias','distinct_organizations']]
metrics=[]
for t in [15,40,70,75,80,85,88,89,90,95,100]:
    tp=sum(p['expected_match'] and p['similarity']>=t for p in empirical)
    fn=sum(p['expected_match'] and p['similarity']<t for p in empirical)
    fp=sum(not p['expected_match'] and p['similarity']>=t for p in empirical)
    tn=sum(not p['expected_match'] and p['similarity']<t for p in empirical)
    metrics.append(dict(threshold=t,tp=tp,fn=fn,fp=fp,tn=tn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn)))
writeCsv('threshold_metrics.csv',metrics)
if Path('data/prospector.db').is_file():
    # Candidates need identity verification.
    c=sqlite3.connect('file:data/prospector.db?mode=ro',uri=True)
    filings=c.execute('select distinct name from filings where name is not null order by name').fetchall()
    bmf=c.execute('select distinct name from bmf where name is not null order by name').fetchall()
    filings=[(n[0],normalize(n[0])) for n in filings]
    bmf=[(n[0],normalize(n[0])) for n in bmf]
    candidates=[]
    for r in inventory:
        pool=filings if r['role']=='validation_seeds' else bmf
        target=normalize(r['name'])
        best=max(pool,key=lambda x: similarity(target,x[1]), default=('', ''))
        candidates.append(dict(**r,candidate=best[0],similarity=similarity(normalize(r['name']),normalize(best[0])),pool='filings' if r['role']=='validation_seeds' else 'bmf',identity_verified=False))
    writeCsv('database_candidates.csv',candidates)
    c.close()
summary={'inventory_entries':len(inventory),'unique_names':len({r['name'] for r in inventory}),'empirical_pairs':len(empirical),'metrics':metrics, 'rapidfuzz_version':importlib.metadata.version('rapidfuzz')}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
