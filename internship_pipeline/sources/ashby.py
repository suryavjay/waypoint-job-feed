import json
import re
from .base import SourceResult,normalize,ats_identity
from ..jobs import fetch_url

def parse(raw,board,company,source_url):
    if raw.get('isListed') is False:return None
    raw={**raw,'id':raw.get('id') or (ats_identity(raw.get('jobUrl','')) or ('','',''))[2]}
    location=raw.get('location') or ''
    secondary=[v.get('location','') for v in raw.get('secondaryLocations') or []]
    job=normalize({**raw,'description':raw.get('descriptionPlain') or raw.get('descriptionHtml'), 'url':raw.get('jobUrl') or raw.get('applyUrl'),'location':'; '.join([location,*secondary]),'active':raw.get('isListed',True),'work_mode':str(raw.get('workplaceType','')).lower() or ('remote' if raw.get('isRemote') else None)},source_key='ashby:'+board,source_name='Ashby',source_url=source_url,company=company,authoritative=True)
    if job:job.update(ats='ashby',board=board,ats_id=str(raw['id']))
    return job

def fetch(board,company):
    url=f'https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true'
    result=SourceResult('ashby:'+board,'Ashby',url,authoritative=True)
    try:
        # Ashby uses domain-style board names too, e.g. persona.ai. Keep the
        # value a single bounded path segment; no traversal/query/fragment.
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?',board):raise ValueError('Invalid Ashby board')
        data=json.loads(fetch_url(url))
        if not isinstance(data.get('jobs'),list):raise ValueError('Missing Ashby jobs array')
        for raw in data['jobs']:
            result.observed_ids.append(str(raw.get('id') or (ats_identity(raw.get('jobUrl','')) or ('','',''))[2]))
            job=parse(raw,board,company,url)
            if job:result.jobs.append(job)
        return result
    except Exception as exc:result.success=False;result.complete=False;result.error=str(exc);return result
