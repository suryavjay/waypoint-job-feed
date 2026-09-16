"""Fetch adapters, deduplicate, persist observations, and retain application history."""
from concurrent.futures import ThreadPoolExecutor
from .sources import simplify,applyguy,vansh,quant,greenhouse,lever,ashby
from .sources.base import identity_fields,merge_jobs
from .companies import targets,company_key
from .jobs import DEFAULT_BOARDS,COMPANIES
from .storage import utcnow

FEEDS=(simplify,applyguy,vansh,quant)
ATS={'greenhouse':greenhouse,'lever':lever,'ashby':ashby}


def collect(root, *, max_boards=80):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda adapter:adapter.fetch(),FEEDS))
    watched=targets(root);lookup={company_key(c['name']):c for c in watched}
    boards={('greenhouse',b):COMPANIES.get(b,b.title()) for b in DEFAULT_BOARDS}
    for company in watched:
        for board in company.get('boards',[]):boards[(board['ats'],board['board'])]=company['name']
    # Discover board IDs from actual application links rather than guessing URLs.
    for result in results:
        for job in result.jobs:
            if job.get('board') and job.get('ats') in ATS:
                matched=lookup.get(company_key(job['company']))
                if matched:boards[(job['ats'],job['board'])]=matched['name']
    # Poll non-target boards represented in current feeds as well, within a clear budget.
    for result in results:
        for job in result.jobs:
            if job.get('board') and job.get('ats') in ATS and job['open_status']=='open' and len(boards)<max_boards:
                boards.setdefault((job['ats'],job['board']),job['company'])
    selected=list(boards.items())[:max_boards]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results.extend(pool.map(lambda item:ATS[item[0][0]].fetch(item[0][1],item[1]),selected))
    return results


def refresh(store):
    results=collect(store.root)
    return ingest_results(store,results)


def ingest_results(store,results):
    successful=[r for r in results if r.success]
    if not successful:raise ValueError('All sources are unavailable. Existing roles and application history are preserved.')
    before={r['id'] for r in store.list_jobs()}
    for result in results:
        if result.jobs:store.upsert_jobs(result.jobs)
        store.record_source_result(result)
    rows=store.list_jobs()
    from .packages import analyze_all
    from .master import master_dir
    if (master_dir(store.root)/'manifest.json').exists():analyze_all(store)
    result={'count':len(rows),'open_count':sum(r['job'].get('open_status')=='open' for r in rows),
      'new_count':sum(r['id'] not in before for r in rows),'at':utcnow(),
      'sources':[r.summary() for r in results],
      'diagnostics':[{'source':r.url,'error':r.error} for r in results if r.error]}
    store.setting('last_refresh',result)
    return result
