import json
import unittest
from unittest.mock import patch
from internship_pipeline.sources import ashby


class AshbyBoardTests(unittest.TestCase):
    def test_domain_style_board_is_polled(self):
        for board in ['persona.ai', 'rivianvw.tech', 'example-team']:
            with self.subTest(board=board), patch.object(ashby,'fetch_url',return_value=json.dumps({'jobs':[]})) as fetch:
                result=ashby.fetch(board,'Example')
                self.assertTrue(result.success)
                self.assertTrue(result.complete)
                self.assertIn('/'+board+'?',fetch.call_args.args[0])

    def test_invalid_paths_never_reach_network(self):
        for board in ['..', '../other', 'company?x=1', 'company#fragment', 'a/b', '', 'a'*101]:
            with self.subTest(board=board), patch.object(ashby,'fetch_url') as fetch:
                result=ashby.fetch(board,'Example')
                self.assertFalse(result.success)
                self.assertFalse(result.complete)
                fetch.assert_not_called()
