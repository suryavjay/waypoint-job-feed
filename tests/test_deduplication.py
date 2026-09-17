import tempfile
import unittest
from internship_pipeline.sources.base import normalized_location, identity_fields
from internship_pipeline.storage import Store


def listing(id,url,**extra):
    return dict(id=id,url=url,company='Palantir',title='Software Engineer Intern',location='NYC; San Francisco, CA',open_status='open',**extra)


class DeduplicationTests(unittest.TestCase):
    def test_google_www_link_variants(self):
        self.assertEqual(identity_fields(listing('a','https://www.google.com/about/careers/applications/jobs/results/123'))[0],identity_fields(listing('b','https://google.com/about/careers/applications/jobs/results/123'))[0])

    def test_san_francisco_not_corrupted(self):
        self.assertEqual(normalized_location('San Francisco, CA'),'sanfranciscoca')
        self.assertEqual(normalized_location('San Fran, California, USA'),'sanfranciscoca')

    def test_location_order_and_spelling(self):
        self.assertEqual(normalized_location('NYC; SF'),normalized_location('San Francisco, CA; New York, NY, United States'))
        self.assertNotEqual(normalized_location('Cambridge, MA'),normalized_location('Cambridge, UK'))

    def test_cross_board_aliases_merge_and_keep_private_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);first=listing('first','https://company.example/123')
            second={**first,'id':'second','url':'https://board.example/123','company':'Palantir Technologies','title':'Software Engineering Internship — Summer 2027','location':'San Francisco, CA; New York, NY, United States'}
            self.assertEqual(identity_fields(first)[2],identity_fields(second)[2])
            store.upsert_jobs([first]);store.update('first',notes='Keep my notes',saved=1,status='Applied')
            store.upsert_jobs([second]);rows=store.list_jobs()
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['notes'],'Keep my notes');self.assertEqual(rows[0]['status'],'Applied')

    def test_distinct_same_site_requisitions_are_not_collapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.upsert_jobs([listing('a','https://company.example/jobs/123'),listing('b','https://company.example/jobs/124')])
            self.assertEqual(len(store.list_jobs()),2)

    def test_distinct_ats_and_phd_roles_remain_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.upsert_jobs([listing('a','https://jobs.lever.co/company/123'),listing('b','https://jobs.lever.co/company/124')])
            self.assertEqual(len(store.list_jobs()),2)
        self.assertNotEqual(identity_fields(listing('a','https://company.example/123'))[2],identity_fields({**listing('b','https://board.example/123'),'title':'Software Engineer Intern — PhD'})[2])
