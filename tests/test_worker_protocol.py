import json
import unittest
from codex_phone.worker_protocol import message, decode


class ProtocolBoundary(unittest.TestCase):
    def test_wrong_version_identity_open_consent_and_nondecision_answer_are_rejected(self):
        o = {'call_id': 'test', 'conversation': False}
        valid = message(o, 'outcome', kind='confirmed', answer='X')
        self.assertEqual(decode(json.dumps(valid), o)['answer'], 'X')
        for change in ({'v': 1}, {'call_id': 'other'}, {'kind': 'ended_by_request'}, {'answer': ''}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                decode(json.dumps(dict(valid, **change)), o)
        with self.assertRaises(ValueError):
            decode(json.dumps(valid), dict(o, conversation=True))
        with self.assertRaises(ValueError):
            decode('x'*16385, o)
