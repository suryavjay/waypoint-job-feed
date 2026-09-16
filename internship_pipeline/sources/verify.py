"""Verify public ATS records and their matching application pages, without submission."""
import json
from .base import ats_identity,normalize,identity_fields
from . import lever,ashby
from ..jobs import fetch_url,now_iso,html_text,_CLOSED


def verify(job):
    result=dict(job,active=False,link_working=False,verified_at=now_iso())
    identity=ats_identity(job.get('url',''))
    if not identity and job.get('ats') and job.get('ats_id'):identity=(job['ats'],job.get('board',''),str(job['ats_id']))
    if identity and not identity[1] and job.get('board'):identity=(identity[0],job['board'],identity[2])
    try:
        if not identity or not identity[1]:raise ValueError('No known official board for this application link; manual verification required')
        ats,board,id=identity
        company=job.get('company',board)
        if ats=='greenhouse':
            url=f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}?content=true'
            raw=json.loads(fetch_url(url))
            if str(raw.get('id'))!=id:raise ValueError('Official record identity differs')
            fresh=normalize(raw,source_key='greenhouse:'+board,source_name='Greenhouse',source_url=url,company=company,authoritative=True)
        elif ats=='lever':
            host='api.eu.lever.co' if 'jobs.eu.lever.co/' in job['url'] else 'api.lever.co'
            url=f'https://{host}/v0/postings/{board}/{id}?mode=json'
            raw=json.loads(fetch_url(url))
            if str(raw.get('id'))!=id:raise ValueError('Official record identity differs')
            fresh=lever.parse(raw,board,company,url)
        elif ats=='ashby':
            url=f'https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true'
            payload=json.loads(fetch_url(url))
            if not isinstance(payload.get('jobs'),list):raise ValueError('Missing official jobs array')
            raw=next((r for r in payload['jobs'] if str(r.get('id'))==id or (ats_identity(r.get('jobUrl','')) or ('','',''))[2]==id),None)
            if not raw:raise ValueError('Opening is absent from official board')
            fresh=ashby.parse(raw,board,company,url)
        else:raise ValueError('Unsupported public ATS')
        if not fresh or not fresh['active'] or identity_fields(fresh)[1]!=ats+':'+id:raise ValueError('Official record is closed, mismatched, or does not establish Summer 2027')
        page=fetch_url(job['url']);text=html_text(page)
        if _CLOSED.search(text):result['open_status']='closed';raise ValueError('Employer page says this job is closed')
        if not page.strip() or (id not in page and fresh['title'].lower() not in text.lower()):raise ValueError('Application page does not identify the same opening')
        result.update(fresh,id=job.get('id',fresh['id']),link_working=True,link_evidence='Official ATS record and employer application page identify the same current opening.',board=board,ats=ats,ats_id=id)
    except Exception as exc:
        result.update(active=False,link_working=False,activity_evidence='Verification requires review: '+str(exc),link_evidence=str(exc))
    return result
