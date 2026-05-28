"""HTTP helpers (standard library only).

These utilities are shared by baseline agents and benchmark tools.

Design goals:
- zero external dependencies
- JSON in / JSON out
- return structured JSON payloads even on HTTP errors when possible
"""

from __future__ import annotations

import json
import urllib.request
from urllib.error import HTTPError


def http_get_json(url: str, *, timeout_s: float = 30.0) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json(url: str, payload: dict, *, timeout_s: float = 30.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        # Many endpoints return useful JSON error payloads (e.g. bad_action).
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            raise
