"""Structured GitHub records; source season metadata supplies leads, not approval."""
import json
from .base import SourceResult, normalize, timestamp
from ..jobs import fetch_url, is_summer_2027


def fetch_json_feed(key,name,url, *, summer_scope=False):
    result=SourceResult(key,name,url)
    try:
        payload=json.loads(fetch_url(url,max_bytes=30_000_000))
        rows=payload.get('jobs') if isinstance(payload,dict) else payload
        if not isinstance(rows,list):raise ValueError('Expected a structured jobs array')
        for raw in rows:
            if not isinstance(raw,dict):continue
            record=dict(raw)
            # The Vansh repository also contains other seasons and old records.
            # Only its explicitly summer, current-cycle records inherit the year.
            if summer_scope and raw.get('season')=='Summer' and not raw.get('terms'):
                posted=timestamp(raw.get('date_posted'))
                if not posted or posted<'2026-01-01':continue
                record['season']='Summer 2027'
            job=normalize(record,source_key=key,source_name=name,source_url=url)
            if job:result.jobs.append(job)
        return result
    except Exception as exc:
        result.success=False;result.complete=False;result.error=str(exc)
        return result
