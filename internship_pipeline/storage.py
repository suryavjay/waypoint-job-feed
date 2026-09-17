"""Atomic local storage. Refreshes preserve application decisions and notes."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKER_STAGES = ("Applications", "Saved", "Applying", "Needs Review", "Apply Now", "Applied", "OA", "Interview", "Final Round", "Offer", "Rejected", "Withdrawn", "Ignored", "Closed")
PRIMARY_STAGES = ("Not Applied", "Applied", "Interviewing", "Offer", "Closed")
SUBMITTED_STAGES = frozenset(("Applied", "OA", "Interview", "Final Round", "Offer", "Rejected", "Withdrawn"))


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


class Store:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.data = self.root / "data"
        self.data.mkdir(parents=True, exist_ok=True)
        self.db = self.data / "internships.sqlite3"
        with self.connect() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, payload TEXT NOT NULL, analysis TEXT,
              status TEXT NOT NULL DEFAULT 'Applications', notes TEXT NOT NULL DEFAULT '',
              package TEXT, first_seen TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY, job_id TEXT, event TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            """)
            columns={row[1] for row in con.execute("PRAGMA table_info(jobs)")}
            for name, definition in (("applied_at","TEXT"),("action_due","TEXT"),("saved","INTEGER NOT NULL DEFAULT 0"),("last_seen","TEXT"),("seen_at","TEXT"),("canonical_url","TEXT"),("ats_key","TEXT"),("dedupe_key","TEXT")):
                if name not in columns:
                    con.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
            con.executescript("""
            CREATE INDEX IF NOT EXISTS jobs_canonical_url ON jobs(canonical_url);
            CREATE INDEX IF NOT EXISTS jobs_ats_key ON jobs(ats_key);
            CREATE INDEX IF NOT EXISTS jobs_dedupe_key ON jobs(dedupe_key);
            CREATE TABLE IF NOT EXISTS source_observations (
              source_key TEXT, job_id TEXT, status TEXT, last_seen TEXT,
              PRIMARY KEY(source_key,job_id)
            );
            """)
            from .sources.base import identity_fields
            for row in con.execute("SELECT id,payload FROM jobs WHERE canonical_url IS NULL").fetchall():
                fields=identity_fields(json.loads(row['payload']))
                con.execute('UPDATE jobs SET canonical_url=?,ats_key=?,dedupe_key=?,last_seen=COALESCE(last_seen,updated_at) WHERE id=?',(*fields,row['id']))

    def connect(self):
        con = sqlite3.connect(self.db, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def upsert_jobs(self, jobs):
        from .sources.base import identity_fields, merge_jobs, compatible_fallback
        with self.connect() as con:
            for job in jobs:
                url,ats,fallback=identity_fields(job)
                existing=con.execute("SELECT * FROM jobs WHERE id=?",(job['id'],)).fetchone()
                if not existing:
                    existing=con.execute("SELECT * FROM jobs WHERE canonical_url=? OR (? IS NOT NULL AND ats_key=?) ORDER BY first_seen LIMIT 1",(url,ats,ats)).fetchone()
                if not existing and fallback:
                    candidates=con.execute("SELECT * FROM jobs WHERE dedupe_key=? ORDER BY first_seen",(fallback,)).fetchall()
                    existing=next((r for r in candidates if compatible_fallback(json.loads(r['payload']),job)),None)
                if existing:
                    job=merge_jobs(json.loads(existing['payload']),job)
                    job['id']=existing['id']
                    url,ats,fallback=identity_fields(job)
                    con.execute("UPDATE jobs SET payload=?,canonical_url=?,ats_key=?,dedupe_key=?,last_seen=?,updated_at=? WHERE id=?",
                        (json.dumps(job),url,ats,fallback,utcnow(),utcnow(),existing['id']))
                else:
                    con.execute("INSERT INTO jobs(id,payload,first_seen,updated_at,last_seen,canonical_url,ats_key,dedupe_key) VALUES(?,?,?,?,?,?,?,?)",
                        (job['id'],json.dumps(job),utcnow(),utcnow(),utcnow(),url,ats,fallback))
                if job.get('open_status')=='closed' or not job.get('active'):
                    con.execute("UPDATE jobs SET status='Needs Review' WHERE id=? AND status='Apply Now'",(job['id'],))
        return len(jobs)

    def record_source_result(self,result):
        from .sources.base import identity_fields, merge_jobs
        if not result.success:return
        now=utcnow()
        with self.connect() as con:
            for job in result.jobs:
                url,ats,_=identity_fields(job)
                row=con.execute("SELECT id FROM jobs WHERE canonical_url=? OR (? IS NOT NULL AND ats_key=?) LIMIT 1",(url,ats,ats)).fetchone()
                if row:con.execute("INSERT INTO source_observations VALUES(?,?,?,?) ON CONFLICT(source_key,job_id) DO UPDATE SET status=excluded.status,last_seen=excluded.last_seen",(result.key,row['id'],job.get('open_status','open'),now))
            # Only a complete authoritative board can prove absence. Community
            # lists, pagination caps, partial downloads and errors cannot close jobs.
            if not result.authoritative or not result.complete:return
            ats,board=result.key.split(':',1)
            observed=set(result.observed_ids)
            for row in con.execute("SELECT id,payload FROM jobs").fetchall():
                job=json.loads(row['payload'])
                if job.get('ats')!=ats or job.get('board')!=board or str(job.get('ats_id')) in observed:continue
                record={'key':result.key,'name':result.name,'id':str(job.get('ats_id')),'url':result.url,'status':'closed','last_seen':now,'authoritative':True}
                merged=merge_jobs(job,{'id':row['id'],'source_records':[record],'sources':[result.name]})
                if merged.get('open_status')=='closed':merged.update(active=False,link_working=False,activity_evidence='Absent from a complete current official board',closed_at=now)
                con.execute("UPDATE jobs SET payload=?,updated_at=? WHERE id=?",(json.dumps(merged),now,row['id']))
                con.execute("INSERT INTO source_observations VALUES(?,?,?,?) ON CONFLICT(source_key,job_id) DO UPDATE SET status=excluded.status,last_seen=excluded.last_seen",(result.key,row['id'],'closed',now))
                if merged.get('open_status')=='closed':con.execute("UPDATE jobs SET status='Needs Review' WHERE id=? AND status='Apply Now'",(row['id'],))

    def list_jobs(self):
        with self.connect() as con:
            return [self.decode(row) for row in con.execute("SELECT * FROM jobs ORDER BY first_seen DESC")]

    @staticmethod
    def decode(row):
        return {**dict(row), "job": json.loads(row["payload"]),
                "analysis": json.loads(row["analysis"]) if row["analysis"] else None,
                "package": json.loads(row["package"]) if row["package"] else None}

    def get_job(self, job_id):
        with self.connect() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown internship")
        return self.decode(row)

    def update(self, job_id, **values):
        allowed = {"analysis", "status", "notes", "package", "applied_at", "action_due", "saved"}
        if not values or not set(values) <= allowed:
            raise ValueError("Invalid application fields")
        self.get_job(job_id)
        if "status" in values and values["status"] not in TRACKER_STAGES:
            raise ValueError("Invalid workflow status")
        values = {k: json.dumps(v) if k in {"analysis", "package"} else v for k, v in values.items()}
        values["updated_at"] = utcnow()
        with self.connect() as con:
            con.execute("UPDATE jobs SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?",
                        (*values.values(), job_id))

    def track_status(self,job_id,status,action_due=None,detail=None):
        """Record user-reported progress independently of package preparation."""
        status={"Not Applied":"Applications","Interviewing":"Interview"}.get(status,status)
        if detail:
            allowed={"Interview":{"OA","Interview","Final Round"},"Closed":{"Rejected","Withdrawn"}}
            if detail not in allowed.get(status,set()):raise ValueError('Detailed outcome does not match the selected progress stage')
            status=detail
        if status=="Apply Now":
            raise ValueError("Use package approval to enter Apply Now")
        if status not in TRACKER_STAGES:
            raise ValueError("Unknown application stage")
        if action_due:
            datetime.fromisoformat(action_due)
        row=self.get_job(job_id)
        fields={"status":status,"action_due":action_due}
        if status in SUBMITTED_STAGES and not row.get("applied_at"):
            fields["applied_at"]=utcnow()
        if status=="Saved":fields["saved"]=1
        self.update(job_id,**fields)
        self.event(job_id,"User recorded status: "+status)
        return self.get_job(job_id)

    def visit(self):
        # One atomic read/update: polling never advances the visit watermark.
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute("SELECT value FROM settings WHERE key='last_visit_at'").fetchone()
            previous=json.loads(row[0]) if row else None
            current=utcnow()
            con.execute("INSERT INTO settings VALUES('last_visit_at',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(current),))
        return {'previous_visit':previous,'current_visit':current}

    def mark_seen(self,ids):
        if not isinstance(ids,list) or len(ids)>5000:raise ValueError('Invalid seen role list')
        with self.connect() as con:
            con.executemany('UPDATE jobs SET seen_at=COALESCE(seen_at,?) WHERE id=?',[(utcnow(),str(id)) for id in ids])
        return {'seen':len(ids)}

    def event(self, job_id, message):
        with self.connect() as con:
            con.execute("INSERT INTO events(job_id,event,created_at) VALUES(?,?,?)", (job_id, message, utcnow()))

    def setting(self, key, value=None):
        with self.connect() as con:
            if value is not None:
                con.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,json.dumps(value)))
                return value
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else None
