import json
import yaml
from concurrent.futures import ThreadPoolExecutor
from .base import SourceResult,normalize
from ..jobs import fetch_url
BASE='https://raw.githubusercontent.com/northwesternfintech/2027QuantInternships/main/'
TREE='https://api.github.com/repos/northwesternfintech/2027QuantInternships/git/trees/main?recursive=1'
ROLE_NAMES={'QT':'Quantitative Trading','QR':'Quantitative Research','QD':'Quantitative Developer','SWE':'Quant Software Engineering','FPGA':'FPGA Engineering'}

def parse_company(text,url):
    data=yaml.safe_load(text)
    if not isinstance(data,dict) or not data.get('name'):raise ValueError('Invalid company YAML')
    jobs=[]
    for role in data.get('roles') or []:
        if role.get('role_type') not in ROLE_NAMES:continue
        for link in role.get('links') or []:
            if not isinstance(link,dict) or not link.get('url'):continue
            title=ROLE_NAMES[role['role_type']]+' Intern'+(' — '+str(link['label']) if link.get('label') else '')
            raw={'company':data['name'],'title':title,'url':link['url'],'location':data.get('locations','Not stated'),'season':'Summer 2027','active':not link.get('closed',False),'category':'Quant'}
            job=normalize(raw,source_key='quant',source_name='Northwestern FinTech',source_url=url)
            if job:
                job['title_inferred_from_source_category']=True
                jobs.append(job)
    return jobs

def fetch():
    result=SourceResult('quant','Northwestern FinTech',BASE+'data/')
    try:
        tree=json.loads(fetch_url(TREE))
        paths=[r['path'] for r in tree.get('tree',[]) if r.get('type')=='blob' and r['path'].startswith('data/') and r['path'].endswith(('.yaml','.yml'))]
        if not paths:raise ValueError('No company YAML files found')
        if tree.get('truncated') or len(paths)>150:raise ValueError('Incomplete repository tree')
        def get(path):
            try:return parse_company(fetch_url(BASE+path),BASE+path),None
            except Exception as exc:return [],path+': '+str(exc)
        errors=[]
        with ThreadPoolExecutor(max_workers=6) as pool:
            for jobs,error in pool.map(get,paths):
                result.jobs.extend(jobs)
                if error:errors.append(error)
        if errors:result.complete=False;result.error='; '.join(errors[:5])
        if not result.jobs and errors:result.success=False
    except Exception as exc:result.success=False;result.complete=False;result.error=str(exc)
    return result
