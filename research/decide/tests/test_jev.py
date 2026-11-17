"""python -m unittest research.decide.tests.test_jev  -- no network, no key needed."""
import os
import unittest
from unittest import mock

import requests

from research.decide.jev import Jev
from research.decide.why_kind import classify

H = [{"t": "Acme beats estimates, raises full-year guidance"}, {"t": "Acme shares jump after results"}]


def resp(status=200, body=None, headers=None):
    r = mock.Mock(status_code=status, headers=headers or {})
    r.json.return_value = body if body is not None else {}
    return r


def good(kind="report", conf=0.9, about=0.95, score=3.2):
    return {"answers": {"about": {"type": "noul", "noul": about},
                        "kind": {"type": "choice", "choice": kind, "confidence": conf, "probabilities": {kind: conf}},
                        "tone": {"type": "score", "score": score}}}


class T(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}, clear=False)
        self.env.start()
        os.environ.pop("TYPESAFE_DISABLE", None)

    def tearDown(self):
        self.env.stop()

    def jev(self, *responses):
        s = mock.Mock()
        s.post.side_effect = list(responses)
        return Jev(session=s), s

    def test_answer_used(self):
        j, s = self.jev(resp(body=good()))
        c = classify("Acme", H, "report", j)
        self.assertEqual((c["kind"], c["source"], c["confidence"], c["tone"]), ("report", "jev", 0.9, 1.2))
        body = s.post.call_args.kwargs["json"]
        self.assertEqual(set(body["questions"]), {"about", "kind", "tone"})
        self.assertEqual(s.post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_unsure_is_news(self):
        j, _ = self.jev(resp(body=good(kind="deal", conf=0.45)))
        self.assertEqual(classify("Acme", H, "report", j)["kind"], "news")

    def test_not_about_company_is_news(self):
        j, _ = self.jev(resp(body=good(about=0.2)))
        self.assertEqual(classify("Acme", H, "report", j)["kind"], "news")

    def test_fallbacks(self):
        for r in (resp(500), resp(401), requests.Timeout(), requests.ConnectionError(), resp(body={"oops": 1}),
                  resp(body=good(kind="weather"))):
            j, _ = self.jev(r)
            c = classify("Acme", H, "analyst", j)
            self.assertEqual((c["kind"], c["source"]), ("analyst", "rules"), r)
            self.assertIn("fallback_reason", c)

    def test_rate_limit_retried_once(self):
        j, s = self.jev(resp(429, headers={"Retry-After": "0"}), resp(body=good()))
        self.assertEqual(classify("Acme", H, "news", j)["source"], "jev")
        self.assertEqual(s.post.call_count, 2)

    def test_stops_after_repeated_failures(self):
        j, s = self.jev(*([resp(503)] * 10))
        for _ in range(6):
            classify("Acme", H, "news", j)
        self.assertEqual(s.post.call_count, 3)

    def test_off_without_key_or_when_disabled(self):
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            j, s = self.jev(resp(body=good()))
            self.assertEqual(classify("Acme", H, "deal", j)["source"], "rules")
            s.post.assert_not_called()
        with mock.patch.dict(os.environ, {"TYPESAFE_DISABLE": "1"}):
            j, s = self.jev(resp(body=good()))
            self.assertEqual(classify("Acme", H, "deal", j)["source"], "rules")
            s.post.assert_not_called()

    def test_no_headlines_no_call(self):
        j, s = self.jev(resp(body=good()))
        self.assertEqual(classify("Acme", [], None, j)["kind"], None)
        s.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
