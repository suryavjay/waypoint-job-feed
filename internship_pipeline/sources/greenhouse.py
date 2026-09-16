import json
import re
from .base import SourceResult, normalize
from ..jobs import fetch_url,html_text,is_relevant

def fetch(board,company):
    url=f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs'
    result=SourceResult('greenhouse:'+board,'Greenhouse',url,authoritative=True)
    try:
        if not re.fullmatch(r'[\w-]+',board):raise ValueError('Invalid Greenhouse board')
        # First fetch compact records; only potential internships need full descriptions.
        data=json.loads(fetch_url(url))
        if not isinstance(data.get('jobs'),list):raise ValueError('Missing Greenhouse jobs array')
        from concurrent.futures import ThreadPoolExecutor
        all_rows=data['jobs'];result.observed_ids=[str(r['id']) for r in all_rows]
        candidates=[r for r in all_rows if is_relevant(r.get('title',''))]
        def detail(raw):
            try:
                detail_url=url+'/'+str(raw['id'])+'?content=true'
                full=json.loads(fetch_url(detail_url))
                if str(full.get('id'))!=str(raw['id']):raise ValueError('Job identity differs')
                job=normalize({**raw,**full},source_key=result.key,source_name=result.name,source_url=detail_url,company=company,authoritative=True)
                if job:job.update(ats='greenhouse',board=board,ats_id=str(raw['id']))
                return job,None
            except Exception as exc:return None,str(exc)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for job,error in pool.map(detail,candidates):
                if job:result.jobs.append(job)
                if error:result.complete=False;result.error=error
        return result
    except Exception as exc:result.success=False;result.complete=False;result.error=str(exc);return result
