import json
import re
from .base import SourceResult, normalize
from ..jobs import fetch_url,html_text

def parse(raw,board,company,source_url):
    categories=raw.get('categories') or {}
    description=raw.get('descriptionPlain') or raw.get('description') or ''
    for section in raw.get('lists') or []:description+='\n'+str(section.get('text',''))+'\n'+html_text(section.get('content',''))
    description+='\n'+str(raw.get('additionalPlain') or raw.get('additional') or '')
    job=normalize({**raw,'title':raw.get('text'),'description':description,'location':categories.get('location'),'url':raw.get('hostedUrl') or raw.get('applyUrl'),'work_mode':{'on-site':'onsite','remote':'remote','hybrid':'hybrid'}.get(raw.get('workplaceType'))},source_key='lever:'+board,source_name='Lever',source_url=source_url,company=company,authoritative=True)
    if job:job.update(ats='lever',board=board,ats_id=str(raw['id']))
    return job

def fetch(board,company):
    url=f'https://api.lever.co/v0/postings/{board}?mode=json'
    result=SourceResult('lever:'+board,'Lever',url,authoritative=True)
    try:
        if not re.fullmatch(r'[\w-]+',board):raise ValueError('Invalid Lever board')
        skip=0
        while True:
            rows=json.loads(fetch_url(url+f'&limit=100&skip={skip}'))
            if not isinstance(rows,list):raise ValueError('Missing Lever postings array')
            for raw in rows:
                result.observed_ids.append(str(raw['id']))
                job=parse(raw,board,company,url)
                if job:result.jobs.append(job)
            if len(rows)<100:break
            skip+=100
            if skip>=10000:result.complete=False;result.error='Board pagination exceeded 10,000 records';break
        return result
    except Exception as exc:result.success=False;result.complete=False;result.error=str(exc);return result
