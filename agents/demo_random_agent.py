#!/usr/bin/env python3
"""Demo/mock agent for the AGI Maze HTTP API.

It:
- starts an episode
- performs random moves for N steps (or until done)
- prints observations/messages it receives

This is *not* a solver. It's an API smoke-test and a rough tool for estimating the
relative difficulty of small mazes.

Usage:
  python3 agents/demo_random_agent.py --steps 50

Notes:
- Uses only the Python standard library.
- Assumes the public server is reachable.
"""

from __future__ import annotations

import argparse
import json
import random
import time

from http_helpers import http_get_json, http_post_json


DEFAULT_BASE_URL = "https://agimaze.org"


def run_agent(
    *,
    base_url: str = DEFAULT_BASE_URL,
    path: str | None = None,
    seed: int | None = None,
    max_steps: int | None = None,
    agent: str = "demo_random",
    verbose: bool = True,
) -> dict:
    """Run the random agent for one episode.

    Returns a dict suitable for JSON logging.
    """

    base = base_url.rstrip("/")

    steps_limit = int(max_steps) if isinstance(max_steps, int) and max_steps > 0 else None

    if path:
        start_payload = {
            "path": path,
            "seed": seed,
            "client": "api",
            "agent": agent,
        }
        if verbose:
            print(f"Starting game: path={path}")
    else:
        # If no explicit path is given, we fall back to a curated training default.
        # (Agents used for serious benchmarking should always specify a path.)
        default_path = "TRAINING/S0-keys/STAGE-01"
        start_payload = {
            "path": default_path,
            "seed": seed,
            "client": "api",
            "agent": agent,
        }
        if verbose:
            print(f"Starting game: path={default_path}")

    t0 = time.time()
    resp = http_post_json(base + "/api/start", start_payload)
    sid = resp["id"]

    if verbose and resp.get("text"):
        print("START:", resp.get("text"))
    if verbose and resp.get("info"):
        print("INFO:", resp.get("info"))

    if steps_limit is None:
        task_meta = resp.get("task_meta") or {}
        ms = task_meta.get("max_steps")
        steps_limit = int(ms) if isinstance(ms, int) and ms > 0 else 50

    actions = resp.get("actions") or ["up", "down", "left", "right"]

    last_inv = resp.get("inventory")
    done = False
    steps = 0

    for i in range(1, steps_limit + 1):
        steps = i
        a = random.choice(list(actions))
        out = http_post_json(base + "/api/step", {"id": sid, "action": a, "seq": i})

        # Treat server errors as observation-like responses and continue.
        if out.get("error"):
            if verbose:
                print(f"[{i:03d}] {a:>8} | SERVER_ERROR={out.get('error')} payload={json.dumps(out, ensure_ascii=False)}")
            continue

        txt = out.get("text", "")
        last_inv = out.get("inventory")
        formal = out.get("formal")
        done = bool(out.get("done"))

        if verbose:
            print(f"[{i:03d}] {a:>8} | {txt} | inv={last_inv}")
            if formal is not None:
                print("       formal:", json.dumps(formal, ensure_ascii=False))

        if done:
            if verbose:
                print("DONE")
            break

    return {
        "success": bool(done),
        "steps": int(steps),
        "inventory": last_inv,
        "session_id": sid,
        "elapsed_s": time.time() - t0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    ap.add_argument("--steps", type=int, default=None, help="max steps override")
    ap.add_argument("--seed", type=int, default=None, help="optional task RNG seed override")
    ap.add_argument(
        "--path",
        type=str,
        default=None,
        help=(
            "PACKS-relative path including group, e.g. TRAINING/S0-keys/STAGE-01/0005.json, "
            "CLASSIC/EASY/pits/4x4/0000.json, or a directory like EXTENDED/boat/STAGE-01-4x4"
        ),
    )
    ap.add_argument("--agent", type=str, default="demo_random", help="agent name for logging")
    ap.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="print server messages (default: enabled; use --no-verbose to silence)",
    )
    args = ap.parse_args()

    res = run_agent(
        base_url=args.base_url,
        path=args.path,
        seed=args.seed,
        max_steps=args.steps,
        agent=args.agent,
        verbose=bool(args.verbose),
    )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
