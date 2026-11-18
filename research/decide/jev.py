"""A small client for Jev (TypeSafe AI's decision model), built so that it can never break the pipeline.

Jev answers closed questions about a text: yes/no ("noul", 0..1), one option of a list ("choice", with probabilities),
or a level on an ordered scale ("score"). It writes no free text. API: POST https://api.typesafe.ai/v1/systemone,
Bearer key, body {model, state, questions}; answers come back under the same keys (format checked 2026-11-17 against
two independent descriptions of the API; TypeSafe's own reference is not public).

Turned on only when it can work:
  TYPESAFE_API_KEY   the key (local runs). Never commit it; never print it.
  TYPESAFE_VIA_PROXY=1  in the cloud, the session's network proxy adds the key itself; a placeholder is sent.
  TYPESAFE_MODEL     default jev-latest. TYPESAFE_DISABLE=1 turns Jev off whatever else is set.
Any failure (no key, timeout, HTTP error, unexpected answer) raises JevUnavailable; the caller then uses its own rules.
After 3 failures in a row the client stops trying for the rest of the run (no slow pipeline when the service is down).
"""
from __future__ import annotations

import os
import time

import requests

URL = os.environ.get("TYPESAFE_URL", "https://api.typesafe.ai/v1/systemone")
TIMEOUT = 8.0
TRIP_AFTER = 3


class JevUnavailable(Exception):
    pass


class Jev:
    def __init__(self, session: requests.Session | None = None):
        self.http = session or requests.Session()
        self.failures = 0
        self.calls = 0
        self.ms = []

    @property
    def enabled(self) -> bool:
        if os.environ.get("TYPESAFE_DISABLE") == "1":
            return False
        return bool(os.environ.get("TYPESAFE_API_KEY")) or os.environ.get("TYPESAFE_VIA_PROXY") == "1"

    @property
    def tripped(self) -> bool:
        return self.failures >= TRIP_AFTER

    def ask(self, state, questions: dict) -> dict:
        """questions: {id: {"type": "noul"|"choice"|"score", "instructions": str, "criteria": ...}} -> answers by id."""
        if not self.enabled:
            raise JevUnavailable("not configured")
        if self.tripped:
            raise JevUnavailable("stopped after repeated failures")
        key = os.environ.get("TYPESAFE_API_KEY") or "placeholder-added-by-proxy"
        body = {"model": os.environ.get("TYPESAFE_MODEL", "jev-latest"), "state": state, "questions": questions}
        for attempt in range(2):
            t0 = time.monotonic()
            try:
                r = self.http.post(URL, json=body, timeout=TIMEOUT,
                                   headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            except requests.RequestException as e:
                self.failures += 1
                raise JevUnavailable(f"network: {type(e).__name__}") from None
            if r.status_code == 429 and attempt == 0:
                time.sleep(float(r.headers.get("Retry-After", 2)))
                continue
            if r.status_code != 200:
                self.failures += 1
                raise JevUnavailable(f"HTTP {r.status_code}")
            try:
                ans = r.json()["answers"]
                for q, spec in questions.items():
                    a = ans[q]
                    if spec["type"] == "noul":
                        a["noul"] = float(a["noul"])
                    elif spec["type"] == "choice" and a["choice"] not in spec["criteria"]:
                        raise ValueError("choice outside the options")
                    elif spec["type"] == "score":
                        a["score"] = float(a["score"])
            except (ValueError, KeyError, TypeError) as e:
                self.failures += 1
                raise JevUnavailable(f"unexpected answer: {e}") from None
            self.failures = 0
            self.calls += 1
            self.ms.append(round((time.monotonic() - t0) * 1000))
            return ans
        self.failures += 1
        raise JevUnavailable("rate limited")
