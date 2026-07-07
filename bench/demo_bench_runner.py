#!/usr/bin/env python3
"""Demo benchmark runner for baseline agents.

This is a small helper script (not a full benchmark suite).

It runs an agent over a set of pack paths (files or folders) and writes JSONL logs
(one episode per line).

Examples:
  python3 bench/demo_bench_runner.py --agent random --path CLASSIC/EASY/pits/4x4 \
    --repeats 3 --out logs/bench_random.jsonl

  python3 bench/demo_bench_runner.py --agent simplest_llm --path TRAINING/S0-keys/STAGE-01/0000.json \
    --model openrouter/auto --verbose

Notes:
- Paths are PACKS-relative and must include the group as the first segment.
- If a --path is a directory, we expand it by convention into 0000.json..0009.json.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import contextlib

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE_URL = "https://agimaze.org"

# Allow importing agent modules from this repo when running as a script.
sys.path.insert(0, str(ROOT / "agents"))


AGENT_MODULES = {
    "random": "demo_random_agent",
    "simplest_llm": "demo_simplest_llm_agent",
    "planning_llm": "demo_planning_llm_agent",
}


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expand_path(p: str) -> list[str]:
    """Expand a pack path into a list of concrete bundle paths.

    This repo does not ship the full pack files, so we cannot enumerate directories.
    To keep the runner usable with minimal effort, we apply a simple convention:

    - If `p` ends with `.json` or `.cfg`: treat it as a concrete file path.
    - Otherwise: treat it as a directory that contains `0000.json`..`0009.json`.

    This matches the current training pack layout.
    """

    rel = p.strip().lstrip("/").replace("\\", "/")
    if ".." in rel.split("/"):
        raise ValueError(f"bad_path: {p}")

    low = rel.lower()
    if low.endswith(".json") or low.endswith(".cfg"):
        return [rel]

    # Directory -> expand to a fixed set of bundle files.
    return [f"{rel}/{i:04d}.json" for i in range(10)]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    ap.add_argument("--agent", type=str, default="random", choices=sorted(AGENT_MODULES.keys()))
    ap.add_argument(
        "--path",
        type=str,
        action="append",
        required=True,
        help="PACKS-relative path (file or folder) including group prefix. Repeatable.",
    )
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--max-steps", type=int, default=None)
    ap.add_argument("--model", type=str, default=None, help="for LLM agents")
    ap.add_argument("--temperature", type=float, default=None, help="for planning_llm")
    ap.add_argument("--out", type=str, default="logs/bench.jsonl")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="pass verbose=true to agent")
    ap.add_argument("--repeats", type=int, default=1, help="How many times to run each target (default: 1)")
    args = ap.parse_args()

    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")

    out_path = (ROOT / args.out).resolve() if not os.path.isabs(args.out) else Path(args.out)
    _ensure_parent(out_path)

    mod_name = AGENT_MODULES[args.agent]
    mod = importlib.import_module(mod_name)
    if not hasattr(mod, "run_agent"):
        raise SystemExit(f"Agent module {mod_name} does not export run_agent(...)")

    run_agent = getattr(mod, "run_agent")

    targets: list[str] = []
    for p in args.path:
        targets.extend(_expand_path(p))

    targets = sorted(dict.fromkeys(targets))  # stable unique

    total_eps = len(targets) * int(args.repeats)
    print(f"agent={args.agent} targets={len(targets)} repeats={args.repeats} episodes={total_eps} out={out_path}")

    # When verbose is disabled, show a lightweight per-trial progress indicator by
    # capturing agent stdout and parsing step counters from its logs.
    real_stdout = sys.stdout

    class _ProgressSink:
        def __init__(self, *, label: str):
            self.label = label
            self._buf = ""
            self.max_steps: int | None = None
            self.cur_step: int = 0

        def write(self, s: str) -> int:
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                self._handle_line(line)
            return len(s)

        def flush(self) -> None:
            if self._buf:
                self._handle_line(self._buf)
                self._buf = ""

        def _handle_line(self, line: str) -> None:
            # Try to learn max_steps from lines like: "session=... max_steps=200 ..."
            if self.max_steps is None:
                m = re.search(r"\bmax_steps=(\d+)\b", line)
                if m:
                    try:
                        self.max_steps = int(m.group(1))
                    except Exception:
                        pass

            # Step patterns:
            # - simplest/planning agents: "[Step N] ..."
            # - random agent: "[001] ..."
            m = re.match(r"^\[Step\s+(\d+)\]", line)
            if not m:
                m = re.match(r"^\[(\d{1,4})\]", line)
            if m:
                try:
                    self.cur_step = int(m.group(1))
                except Exception:
                    return

            self._render()

        def _render(self) -> None:
            if self.max_steps:
                msg = f"{self.label} step {self.cur_step}/{self.max_steps}"
            else:
                msg = f"{self.label} step {self.cur_step}"
            # Clear to end of line to avoid leftovers.
            real_stdout.write("\r" + msg + " " * 10)
            real_stdout.flush()

    def _run_agent_with_progress(*, payload: dict[str, Any], label: str) -> dict:
        if args.verbose:
            return run_agent(**payload)
        sink = _ProgressSink(label=label)
        with contextlib.redirect_stdout(sink):
            # We still run the agent with verbose=True so that it emits step logs
            # that we can parse for progress.
            return run_agent(**payload)

    with out_path.open("a", encoding="utf-8") as f:
        idx = 0
        for rel in targets:
            for r in range(1, int(args.repeats) + 1):
                idx += 1
                payload: dict[str, Any] = {
                    "base_url": args.base_url,
                    "path": rel,
                    "seed": args.seed,
                    "max_steps": args.max_steps,
                    "agent": args.agent,
                    # We keep agent verbosity enabled; when runner --verbose is off,
                    # output is captured and used only for progress parsing.
                    "verbose": True,
                }
                if args.model is not None:
                    payload["model"] = args.model
                if args.temperature is not None:
                    payload["temperature"] = args.temperature

                rec: dict[str, Any] = {
                    "ts": _utc_ts(),
                    "idx": idx,
                    "episodes": total_eps,
                    "agent": args.agent,
                    "path": rel,
                    "seed": args.seed,
                    "repeat": r,
                    "repeats": int(args.repeats),
                }

                label = f"[{idx:04d}/{total_eps:04d}] rep={r}/{args.repeats}"

                try:
                    res = _run_agent_with_progress(payload=payload, label=label)
                    if not isinstance(res, dict):
                        res = {"result": res}
                    rec.update(res)
                    ok = bool(rec.get("success"))
                    steps = rec.get("steps")
                    if not args.verbose:
                        real_stdout.write("\r" + " " * 120 + "\r")
                    print(f"[{idx:04d}/{total_eps:04d}] {'OK ' if ok else 'FAIL'} rep={r}/{args.repeats} steps={steps} {rel}")
                except Exception as e:
                    rec.update({"success": False, "error": repr(e)})
                    if not args.verbose:
                        real_stdout.write("\r" + " " * 120 + "\r")
                    print(f"[{idx:04d}/{total_eps:04d}] ERROR rep={r}/{args.repeats} {rel}: {e}")
                    if args.fail_fast:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        f.flush()
                        raise

                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()


if __name__ == "__main__":
    main()
