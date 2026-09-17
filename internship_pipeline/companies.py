"""Target companies remain visible even before recruiting opens."""
import re
from pathlib import Path
from .storage import read_json, write_json, utcnow


def company_key(name):
    text=re.sub(r'[^a-z0-9]', '', str(name).lower())
    aliases={'nvidiacorporation':'nvidia','imctrading':'imc','susquehannainternationalgroup':'sig',
      'susquehanna':'sig','jpmorganchaseco':'jpmorganchase','jpmorgan':'jpmorganchase',
      'googlellc':'google','metaplatforms':'meta','amazoncom':'amazon',
      'hudsonrivertradingllc':'hudsonrivertrading','americanexpresscompany':'americanexpress',
      'palantirtechnologies':'palantir','towerresearchcapital':'towerresearch',
      'jumptradinggroup':'jumptrading','susquehannainternationalgroupsig':'sig',
      'cadencedesignsystems':'cadence','veeamsoftware':'veeam'}
    return aliases.get(text,text)


def targets(root):
    path=Path(root)/'data/target_companies.json'
    return read_json(path) or read_json(Path(__file__).parent/'config/target_companies.json')


def add_target(root,name):
    name=str(name).strip()
    if not name or len(name)>100:raise ValueError('Enter a company name under 100 characters')
    rows=targets(root)
    if not any(company_key(x['name'])==company_key(name) for x in rows):
        rows.append({'name':name,'group':'Your companies','categories':['SWE','Data','ML / AI','Quant'],'boards':[]})
        write_json(Path(root)/'data/target_companies.json',rows)
    return rows


def company_summary(root,rows,refresh=None):
    output=[]
    for company in targets(root):
        aliases={company_key(company['name']),*(company_key(x) for x in company.get('aliases',[]))}
        matches=[r for r in rows if company_key(r['job']['company']) in aliases]
        live=[r for r in matches if r['job'].get('open_status', 'open' if r['job'].get('active') else 'unknown')!='closed' and r['status']!='Ignored']
        output.append({**company,'id':company_key(company['name']),'job_ids':[r['id'] for r in live],
          'open_count':len(live),'last_checked':(refresh or {}).get('at'),
          'coverage':'Direct boards and internship feeds' if company.get('boards') else 'Internship feeds'})
    return output
