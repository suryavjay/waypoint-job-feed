import copy
import unittest
import tempfile
from internship_pipeline.sources.base import merge_jobs
from internship_pipeline.storage import Store

class EvidencePreservationTests(unittest.TestCase):
    def setUp(self):
        self.official={'id':'original','title':'Software Intern Summer 2027','company':'Example','location':'Austin','url':'https://job-boards.greenhouse.io/example/jobs/123','description':'Employer requirements: graduating in 2028.','verified_at':'2026-09-17T12:00:00Z','active':False,'open_status':'closed','deadline':'2026-09-30','sponsorship_status':'unknown','source_records':[{'key':'greenhouse:example','authoritative':True,'status':'closed'}],'sources':['Greenhouse']}
        self.community={**self.official,'id':'community-copy','description':'Community summary says all graduation years.','verified_at':None,'active':False,'open_status':'open','deadline':'2026-12-01','sponsorship_status':'available','source_records':[{'key':'community','authoritative':False,'status':'open'}],'sources':['Community']}

    def test_closed_employer_evidence_survives_community_refresh(self):
        before=copy.deepcopy(self.official)
        merged=merge_jobs(self.official,self.community)
        for key in ['id','description','verified_at','deadline','sponsorship_status']:
            self.assertEqual(merged[key],self.official[key],key)
        self.assertEqual(merged['open_status'],'closed')
        self.assertFalse(merged['active'])
        self.assertEqual(len(merged['source_records']),2)
        self.assertEqual(self.official,before)

    def test_missing_provenance_cannot_replace_employer_description(self):
        incoming={**self.community};incoming.pop('source_records')
        self.assertEqual(merge_jobs(self.official,incoming)['description'],self.official['description'])

    def test_new_official_description_can_reopen_and_update(self):
        incoming={**self.official,'description':'New employer requirements.','verified_at':'2026-09-18T12:00:00Z','active':True,'open_status':'open','source_records':[{'key':'greenhouse:example','authoritative':True,'status':'open'}]}
        merged=merge_jobs(self.official,incoming)
        self.assertEqual(merged['description'],incoming['description'])
        self.assertEqual(merged['verified_at'],incoming['verified_at'])
        self.assertEqual(merged['open_status'],'open')
        self.assertTrue(merged['active'])

    def test_empty_official_description_does_not_verify_community_text(self):
        incoming={**self.official,'description':''}
        merged=merge_jobs(self.community,incoming)
        self.assertEqual(merged['description'],self.community['description'])
        self.assertIsNone(merged['verified_at'])

    def test_empty_official_description_keeps_prior_checked_employer_text(self):
        incoming={**self.official,'description':'','verified_at':'2026-09-18T12:00:00Z'}
        merged=merge_jobs(self.official,incoming)
        self.assertEqual(merged['description'],self.official['description'])
        self.assertEqual(merged['verified_at'],self.official['verified_at'])

    def test_store_retains_application_history_during_community_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.upsert_jobs([self.official])
            store.update('original',status='Applied',notes='Keep my interview notes',saved=1,applied_at='2026-09-01',action_due='2026-09-20')
            store.upsert_jobs([self.community])
            rows=store.list_jobs();self.assertEqual(len(rows),1)
            row=rows[0]
            self.assertEqual(row['job']['description'],self.official['description'])
            self.assertEqual(row['status'],'Applied');self.assertEqual(row['notes'],'Keep my interview notes')
            self.assertEqual(row['saved'],1);self.assertEqual(row['applied_at'],'2026-09-01');self.assertEqual(row['action_due'],'2026-09-20')
