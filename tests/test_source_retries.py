import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
from internship_pipeline.jobs import fetch_url

URL='https://boards-api.greenhouse.io/v1/boards/example/jobs'

class SourceRetryTests(unittest.TestCase):
    def run_fetch(self,side_effect,**kwargs):
        opener=MagicMock();opener.open.side_effect=side_effect
        response=MagicMock();response.__enter__.return_value.url=URL;response.__enter__.return_value.read.return_value=b'{"jobs":[]}'
        opener.open.return_value=response
        return opener,response

    def test_timeout_then_success(self):
        for error in [TimeoutError('timed out'),URLError(TimeoutError('timed out')),HTTPError(URL,503,'Unavailable',{},None)]:
            opener,response=self.run_fetch(None);opener.open.side_effect=[error,response]
            with patch('internship_pipeline.jobs.validate_public_url'),patch('internship_pipeline.jobs.build_opener',return_value=opener),patch('internship_pipeline.jobs.time.sleep') as sleep:
                self.assertEqual(fetch_url(URL),'{"jobs":[]}');self.assertEqual(opener.open.call_count,2);sleep.assert_called_once_with(1)

    def test_repeated_timeout_stops_after_one_retry(self):
        opener,_=self.run_fetch(TimeoutError('timed out'))
        with patch('internship_pipeline.jobs.validate_public_url'),patch('internship_pipeline.jobs.build_opener',return_value=opener),patch('internship_pipeline.jobs.time.sleep'):
            with self.assertRaises(TimeoutError):fetch_url(URL)
        self.assertEqual(opener.open.call_count,2)

    def test_permanent_errors_and_rate_limits_are_not_retried(self):
        for code in [400,401,403,404,429]:
            opener,_=self.run_fetch(HTTPError(URL,code,'Error',{},None))
            with patch('internship_pipeline.jobs.validate_public_url'),patch('internship_pipeline.jobs.build_opener',return_value=opener),patch('internship_pipeline.jobs.time.sleep') as sleep:
                with self.assertRaises(HTTPError):fetch_url(URL)
                self.assertEqual(opener.open.call_count,1);sleep.assert_not_called()

    def test_download_limit_is_not_retried(self):
        opener,_=self.run_fetch(None)
        with patch('internship_pipeline.jobs.validate_public_url'),patch('internship_pipeline.jobs.build_opener',return_value=opener),patch('internship_pipeline.jobs.time.sleep') as sleep:
            with self.assertRaises(ValueError):fetch_url(URL,max_bytes=1)
            self.assertEqual(opener.open.call_count,1);sleep.assert_not_called()

    def test_unsafe_url_never_reaches_network(self):
        with patch('internship_pipeline.jobs.build_opener') as opener:
            with self.assertRaises(ValueError):fetch_url('https://127.0.0.1/jobs')
            opener.assert_not_called()
