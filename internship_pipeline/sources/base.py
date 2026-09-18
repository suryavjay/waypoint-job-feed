"""Shared adapter contract and normalized, evidence-aware job records."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from ..jobs import html_text, is_summer_2027, is_relevant, validate_public_url, now_iso

@dataclass
class SourceResult:
    key: str
    name: str
    url: str
    jobs: list = field(default_factory=list)
    success: bool = True
    complete: bool = True
    authoritative: bool = False
    error: str | None = None
    observed_ids: list = field(default_factory=list)

    def summary(self):
        return {k:getattr(self,k) for k in ('key','name','url','success','complete','authoritative','error')} | {'count':len(self.jobs)}


def timestamp(value):
    if value is None or value=='':return None
    try:
        if isinstance(value,(int,float)):
            return datetime.fromtimestamp(value/1000 if value>10**11 else value,timezone.utc).isoformat()
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).isoformat()
    except (ValueError,TypeError,OverflowError,OSError):return None


def ats_identity(url):
    p=urlparse(str(url));host=(p.hostname or '').lower();parts=p.path.strip('/').split('/');q=dict(parse_qsl(p.query))
    if host in ('boards.greenhouse.io','job-boards.greenhouse.io','job-boards.eu.greenhouse.io') and len(parts)>=3 and parts[1]=='jobs' and parts[2].isdigit():return 'greenhouse',parts[0],parts[2]
    if q.get('gh_jid','').isdigit():return 'greenhouse','',q['gh_jid']
    if host in ('jobs.lever.co','jobs.eu.lever.co') and len(parts)>=2:return 'lever',parts[0],parts[1]
    if host=='jobs.ashbyhq.com' and len(parts)>=2:return 'ashby',parts[0],parts[1]
    return None


def canonical_application_url(url):
    p=urlparse(str(url).strip());host=(p.hostname or '').lower()
    if host=='boards.greenhouse.io':host='job-boards.greenhouse.io'
    if host=='www.google.com':host='google.com'
    path=p.path
    if host in ('jobs.lever.co','jobs.eu.lever.co','jobs.ashbyhq.com'):
        path=re.sub(r'/(?:apply|application)/?$','',path)
    path=path.rstrip('/') or '/'
    ignored={'ref','source','gh_src','lever-source','lever-origin','ashby_jid','jr_id','referral','referrer'}
    query=[(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ignored]
    if host.endswith('greenhouse.io'):query=[(k,v) for k,v in query if k!='gh_jid']
    return urlunparse(('https' if p.scheme in ('http','https') else p.scheme,host,path,'',urlencode(sorted(query)),''))


def normalized_location(value):
    parts=[]
    for location in str(value).lower().split(';'):
        text=re.sub(r'\bnyc\b','new york, ny',location.strip())
        text=re.sub(r'\bsan fran\b','san francisco',text)
        text=re.sub(r'^sf(?=,|$)','san francisco, ca',text)
        text=re.sub(r',\s*(?:united states(?: of america)?|usa|u\.s\.a?\.?)\s*$','',text)
        text=re.sub(r',\s*california\b',', ca',text)
        text=re.sub(r',\s*texas\b',', tx',text)
        text=re.sub(r',\s*new york\b',', ny',text)
        parts.append(re.sub(r'[^a-z0-9]','',text))
    return ';'.join(sorted(set(p for p in parts if p)))


def normalized_title(value):
    text=str(value).lower()
    text=re.sub(r'\bsummer\s*[,/-]?\s*2027\b|\b2027\s*[,/-]?\s*summer\b','',text)
    text=re.sub(r'\binternships?\b','intern',text)
    text=re.sub(r'\bsoftware engineering\b','software engineer',text)
    return re.sub(r'[^a-z0-9]','',text)


def compatible_fallback(old,new):
    """A weak company/title/location match cannot override distinct requisitions."""
    old_url,old_ats,_=identity_fields(old);new_url,new_ats,_=identity_fields(new)
    if old_ats and new_ats:return old_ats==new_ats
    # Same-site different URLs can identify separate Workday/Google/etc. jobs.
    if urlparse(old_url).hostname==urlparse(new_url).hostname and old_url!=new_url:return False
    return True


def identity_fields(job):
    from ..companies import company_key
    url=canonical_application_url(job.get('url') or job.get('applyUrl') or '')
    identity=ats_identity(url)
    if not identity and job.get('ats') and job.get('ats_id'):identity=(job['ats'],job.get('board',''),str(job['ats_id']))
    ats_key=(identity[0]+':'+identity[2]) if identity else None
    title=normalized_title(job.get('title',''))
    location=normalized_location(job.get('location',''))
    fallback='|'.join((company_key(job.get('company','')),title,location)) if title and location else None
    return url,ats_key,fallback


def category_for(title, hint=''):
    # Source headings often combine "Data Science, AI & ML". Prefer the actual
    # role title before using that broad heading as a fallback.
    for text in (title, str(hint)):
        if re.search(r'quant|\btrad(?:er|ing)\b|\bQR\b|\bQT\b|\bQD\b',text,re.I):return 'Quant'
        if re.search(r'machine learning|artificial intelligence|\bAI\b|\bML\b|computer vision|deep learning',text,re.I):return 'ML / AI'
        if re.search(r'data scien|data analy|analytics|data engineer',text,re.I):return 'Data'
        if re.search(r'software|\bSWE\b|backend|front.?end|full.?stack|platform engineer|infrastructure engineer',text,re.I):return 'SWE'
    return 'SWE'


def normalize(raw, *, source_key, source_name, source_url, company=None, term_hint='', authoritative=False):
    title=str(raw.get('title') or raw.get('text') or '').strip()
    company=str(company or raw.get('company') or raw.get('company_name') or '').strip()
    description=html_text(raw.get('description') or raw.get('content') or '')
    terms=raw.get('terms') or raw.get('season') or term_hint
    if isinstance(terms,list):terms=' '.join(str(t) for t in terms)
    explicit=is_summer_2027(title,description+'\n'+str(terms))
    if re.search(r'\b(?:summer\s*202[0-689]|202[0-689]\s*summer)\b',title,re.I):return None
    if not explicit or not is_relevant(title):return None
    url=canonical_application_url(raw.get('listingUrl') or raw.get('url') or raw.get('applyUrl') or raw.get('absolute_url') or raw.get('hostedUrl') or '')
    try:validate_public_url(url,resolve=False)
    except ValueError:return None
    if not company or raw.get('is_visible') is False:return None
    location=raw.get('location') or raw.get('locations') or 'Location not stated'
    if isinstance(location,dict):location=location.get('name','Location not stated')
    if isinstance(location,list):location='; '.join(str(x) for x in location)
    identity=ats_identity(url)
    from ..jobs import _CLOSED
    active=raw.get('active',True) is not False and raw.get('status')!='closed' and not _CLOSED.search(description)
    observed=now_iso();posted=timestamp(raw.get('posted_at') or raw.get('posted') or raw.get('date_posted') or raw.get('publishedAt') or raw.get('createdAt') or raw.get('first_published'))
    sponsor=str(raw.get('sponsorship') or '')
    sponsorship_status='unavailable' if sponsor.lower() in ('no','no sponsorship','not available','us citizenship required') else 'available' if sponsor.lower() in ('yes','sponsorship available','available') else 'unknown'
    text=str(location)+' '+description
    mode=raw.get('work_mode') or ('hybrid' if re.search(r'\bhybrid\b',text,re.I) else 'remote' if re.search(r'\bremote\b',str(location),re.I) else 'onsite' if re.search(r'on.site|on site|in.office|in office',text,re.I) else 'unknown')
    source_id=str(raw.get('id') or (identity[2] if identity else hashlib.sha256(url.encode()).hexdigest()[:20]))
    return {'id':hashlib.sha256((company.lower()+'|'+url).encode()).hexdigest()[:20],
      'company':company,'title':title,'location':str(location),'url':url,'category':category_for(title,raw.get('category','')),
      'description':description,'term':'Summer 2027','season_evidence':'official' if authoritative else source_name,
      'open_status':'open' if active else 'closed','active':bool(active and authoritative),'verified_at':observed if authoritative else None,
      'activity_evidence':'Listed on the current official board' if authoritative else 'Community feed listing; employer verification required',
      'link_working':False,'ats':identity[0] if identity else raw.get('ats'), 'board':identity[1] if identity else raw.get('board'), 'ats_id':identity[2] if identity else raw.get('ats_id'),
      'posted_at':posted,'deadline':timestamp(raw.get('deadline') or raw.get('application_deadline')),
      'work_mode':mode,'sponsorship':sponsor or None,'sponsorship_status':sponsorship_status,'compensation':raw.get('compensation'),
      'sources':[source_name], 'source_url':source_url,'discovery_source':source_url,
      'source_records':[{'key':source_key,'name':source_name,'id':source_id,'url':source_url,'status':'open' if active else 'closed','last_seen':observed,'authoritative':authoritative}]}


def merge_jobs(old,new):
    # Verification describes where the text came from, not whether the job is
    # still open. Keep checked employer evidence after closure or source outage.
    result=dict(old)
    def official(job):
        return bool(job.get('verified_at') and any(s.get('authoritative') for s in job.get('source_records',[])))
    old_verified=official(old) and bool(old.get('description'))
    new_verified=official(new) and bool(new.get('description'))
    protected={'description','title','company','location','url','category','term','season_evidence','verified_at','activity_evidence','active','link_working','link_evidence','ats','board','ats_id','posted_at','deadline','work_mode','sponsorship','sponsorship_status','compensation'}
    for key,value in new.items():
        if key in ('id','sources','source_records'):continue
        if old_verified and not new_verified and key in protected:continue
        if value not in (None,'',[],{}):result[key]=value
    # An empty employer response must not lend its verification stamp to a
    # retained community description. A previous checked description is safe.
    if official(new) and not new.get('description') and not old_verified:result['verified_at']=None
    records={x['key']:x for x in old.get('source_records',[])}
    records.update({x['key']:x for x in new.get('source_records',[])})
    result['source_records']=list(records.values())
    result['sources']=list(dict.fromkeys(old.get('sources',[])+new.get('sources',[])))
    result['id']=old.get('id') or new['id']
    official=[x for x in records.values() if x.get('authoritative')]
    effective=official or list(records.values())
    if effective:result['open_status']='open' if any(x.get('status')=='open' for x in effective) else 'closed'
    if result.get('open_status')=='closed':result.update(active=False,link_working=False)
    return result
