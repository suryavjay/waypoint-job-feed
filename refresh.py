"""Public listings only. Never opens the private application workspace."""
import json
import tempfile
from pathlib import Path
from internship_pipeline.ingestion import collect
from internship_pipeline.sources.base import identity_fields
from internship_pipeline.storage import Store, utcnow, write_json

# Explicit allowlists prevent future private application fields entering the feed.
JOB_FIELDS = frozenset('id company title location url category description term season_evidence open_status active verified_at activity_evidence link_working ats board ats_id posted_at deadline work_mode sponsorship sponsorship_status compensation sources source_url discovery_source closed_at title_inferred_from_source_category'.split())
RECORD_FIELDS = frozenset('key name id url status last_seen authoritative'.split())

def public_job(job):
    clean = {k: v for k, v in job.items() if k in JOB_FIELDS}
    clean['source_records'] = [{k: v for k, v in record.items() if k in RECORD_FIELDS} for record in job.get('source_records', [])]
    return clean

def refresh(output, collector=collect):
    output = Path(output)
    previous = json.loads(output.read_text()) if output.exists() else {'jobs': []}
    with tempfile.TemporaryDirectory(prefix='public-jobs-') as scratch:
        store = Store(scratch)
        # Restore only public evidence, so complete official boards can identify closures.
        for row in previous['jobs']:
            store.upsert_jobs([public_job(row['job'])])
            with store.connect() as con:
                con.execute('UPDATE jobs SET first_seen=?,last_seen=? WHERE id=?', (row['first_seen'], row['last_seen'], row['id']))
        results = collector(Path(scratch))
        if not any(r.success for r in results):
            raise RuntimeError('All sources failed; previous published feed left unchanged')
        for result in results:
            if result.success:
                store.upsert_jobs(result.jobs)
            store.record_source_result(result)
        rows = []
        for row in sorted(store.list_jobs(), key=lambda r: r['id']):
            job = public_job(row['job'])
            url, ats, fallback = identity_fields(job)
            rows.append({'id': row['id'], 'job': job, 'first_seen': row['first_seen'], 'last_seen': row['last_seen'], 'canonical_url': url, 'ats_key': ats, 'dedupe_key': fallback})
        sources = [r.summary() for r in results]
        payload = {'schema_version': 1, 'generated_at': utcnow(), 'jobs': rows, 'sources': sources,
                   'observations': [{'key': r.key, 'observed_ids': r.observed_ids} for r in results if r.success and r.complete and r.authoritative]}
        write_json(output, payload)
        print(json.dumps({'roles': len(rows), 'open': sum(r['job']['open_status'] == 'open' for r in rows), 'sources': len(sources), 'unavailable': sum(not r.success for r in results), 'generated_at': payload['generated_at']}))
        return payload

if __name__ == '__main__':
    refresh(Path(__file__).parent / 'feed/jobs.json')
