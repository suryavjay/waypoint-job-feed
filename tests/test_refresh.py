import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from refresh import refresh, public_job
from internship_pipeline.sources.base import SourceResult

class FeedTests(unittest.TestCase):
    def test_allowlist(self):
        clean = public_job({'id': '1', 'company': 'Example', 'notes': 'PRIVATE', 'profile': 'PRIVATE', 'source_records': [{'key': 'x', 'notes': 'PRIVATE'}]})
        self.assertNotIn('PRIVATE', json.dumps(clean))

    def test_retention_closure_and_failed_publish(self):
        job = {'id': 'one', 'company': 'Example', 'title': 'Software Intern Summer 2027', 'location': 'Austin', 'url': 'https://job-boards.greenhouse.io/example/jobs/123', 'ats': 'greenhouse', 'board': 'example', 'ats_id': '123', 'open_status': 'open', 'active': True, 'source_records': [{'key': 'greenhouse:example', 'authoritative': True, 'status': 'open'}]}
        def result(**kwargs):
            return SourceResult('greenhouse:example', 'Example', 'https://boards-api.greenhouse.io/v1/boards/example/jobs', authoritative=True, **kwargs)
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp)/'jobs.json'
            initial = refresh(path, lambda _: [result(jobs=[job], observed_ids=['123'])])
            partial = refresh(path, lambda _: [result(complete=False)])
            self.assertEqual(partial['jobs'][0]['job']['open_status'], 'open')
            self.assertEqual(partial['jobs'][0]['first_seen'], initial['jobs'][0]['first_seen'])
            closed = refresh(path, lambda _: [result()])
            self.assertEqual(closed['jobs'][0]['job']['open_status'], 'closed')
            before = path.read_bytes()
            with self.assertRaises(RuntimeError): refresh(path, lambda _: [result(success=False)])
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn('notes', closed['jobs'][0])

if __name__ == '__main__': unittest.main()
