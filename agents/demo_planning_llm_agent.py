#!/usr/bin/env python3
"""Planning LLM baseline agent (OpenAI-compatible / OpenRouter).

This agent is both:
- a demonstration of building an agent on top of the **public AGI Maze HTTP API**, and
- a practical baseline for evaluating vanilla LLM behavior.

It:
- fetches the global game description via `GET /api/description`
- starts an episode via `POST /api/start`
- runs a 2-phase LLM loop: PLAN (free text) then ACT (tool call)
- executes the chosen action via `POST /api/step`

Environment variables:
- `OPENAI_API_KEY` or `OPENROUTER_API_KEY`
- Optional: `OPENAI_BASE_URL` / `OPENROUTER_BASE_URL` (defaults to OpenRouter)

Examples:
  OPENROUTER_API_KEY=... python3 agents/demo_planning_llm_agent.py \
    --path TRAINING/S0-keys/STAGE-01/0000.json --model openrouter/auto

  OPENROUTER_API_KEY=... python3 agents/demo_planning_llm_agent.py \
    --path CLASSIC/EASY/pits/4x4 --model openrouter/auto --max-steps 200
"""

from __future__ import annotations

import json
import os
import random
import re
import socket
import time
import urllib.request
from urllib.error import HTTPError, URLError

from common import DEFAULT_BASE_URL, make_base_argparser, build_start_payload
from http_helpers import http_get_json, http_post_json


def openai_chat_completions(
    *,
    base_url: str,
    api_key: str,
    payload: dict,
    timeout_s: float = 60.0,
    retries: int = 5,
    backoff_s: float = 0.8,
) -> dict:
    """Call OpenAI-compatible Chat Completions with simple retries."""

    url = base_url.rstrip("/") + "/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    def _sleep(attempt: int) -> None:
        t = backoff_s * (2 ** max(0, attempt - 1))
        t = t * (0.8 + 0.4 * random.random())
        time.sleep(t)

    last_err: Exception | None = None
    for attempt in range(1, int(retries) + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                return json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            if e.code in (502, 503, 504) and attempt < retries:
                last_err = e
                _sleep(attempt)
                continue
            raise
        except (URLError, socket.timeout, TimeoutError) as e:
            if attempt < retries:
                last_err = e
                _sleep(attempt)
                continue
            raise

    raise RuntimeError(f"openai_chat_completions failed after {retries} retries: {last_err}")


# (compact signal helper removed)

def run_agent(
    *,
    base_url: str = DEFAULT_BASE_URL,
    path: str = "TRAINING/S0-keys/STAGE-01/0000.json",
    seed: int | None = None,
    model: str = "openrouter/auto",
    max_steps: int | None = None,
    temperature: float = 0.2,
    agent: str = "demo_planning_llm",
    verbose: bool = True,
) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY or OPENROUTER_API_KEY")

    llm_base_url = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENROUTER_BASE_URL")
        or "https://openrouter.ai/api/v1"
    )

    srv = base_url.rstrip("/")

    desc = http_get_json(f"{srv}/api/description").get("description", "")

    start_payload = build_start_payload(path=path, seed=seed, agent=agent, verbose=verbose)
    start = http_post_json(f"{srv}/api/start", start_payload)
    sid = start["id"]

    actions = start.get("actions") or ["up", "down", "left", "right"]
    task_meta = start.get("task_meta") or {}
    inv0 = start.get("inventory") or {}

    # Determine step budget
    steps_limit = int(max_steps) if isinstance(max_steps, int) and max_steps > 0 else None
    if steps_limit is None:
        ms = task_meta.get("max_steps")
        steps_limit = int(ms) if isinstance(ms, int) and ms > 0 else 200

    if verbose:
        print(f"session={sid} max_steps={steps_limit} actions={actions}")

    # System prompt
    board_str = ""
    if task_meta.get("board"):
        b = task_meta["board"]
        board_str = f"board size: n={b.get('n')} rows, m={b.get('m')} cols"

    sys_prompt = (
        "You are playing a grid maze game. Your goal is to win by collecting the treasure and exiting.\n\n"
        "Rules/description:\n" + desc + "\n\n"
        "Task info:\n" + board_str + "\n\n"
        f"Your inventory: {json.dumps(inv0, ensure_ascii=False)}\n\n"
        "Each step, you will receive a text result and an inventory snapshot.\n"
        "Plan briefly, then choose exactly one valid action."  # keep it short
    )

    tool = {
        "type": "function",
        "function": {
            "name": "act",
            "description": "Choose the next action",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": list(actions)},
                    "reason": {"type": "string"},
                },
                "required": ["action"],
            },
        },
    }

    messages: list[dict] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": "Game started. PLAN then ACT."},
    ]

    def llm_plan() -> str:
        payload = {
            "model": model,
            "temperature": float(temperature),
            "messages": messages
            + [
                {
                    "role": "user",
                    "content": "PLAN: briefly describe your current hypothesis/strategy for the next few steps.",
                }
            ],
        }
        resp = openai_chat_completions(base_url=llm_base_url, api_key=api_key, payload=payload)
        return (resp["choices"][0]["message"].get("content") or "").strip()

    def llm_act() -> tuple[str, str]:
        payload = {
            "model": model,
            "temperature": float(temperature),
            "messages": messages
            + [
                {
                    "role": "user",
                    "content": "ACT: choose exactly one action.",
                }
            ],
            "tools": [tool],
            "tool_choice": {"type": "function", "function": {"name": "act"}},
        }
        resp = openai_chat_completions(base_url=llm_base_url, api_key=api_key, payload=payload)
        msg = resp["choices"][0]["message"]

        tcs = msg.get("tool_calls") or []
        if tcs:
            args_json = tcs[0]["function"]["arguments"]
            data = json.loads(args_json) if isinstance(args_json, str) else args_json
            return str(data.get("action")), str(data.get("reason") or "")

        # fallback
        txt = (msg.get("content") or "").strip().lower()
        for a in actions:
            if a in txt:
                return a, "(parsed from text)"
        return random.choice(list(actions)), "(random fallback)"

    # crude loop detection: last few (action,status,observe)
    hist_sig: list[tuple[str, str, str]] = []

    done = False
    steps = 0
    last_inv = start.get("inventory")

    for step in range(1, int(steps_limit) + 1):
        steps = step

        # PLAN phase
        plan = llm_plan()
        if plan:
            messages.append({"role": "assistant", "content": "NOTES: " + plan})

        # Loop nudge
        if len(hist_sig) >= 6 and len(set(hist_sig[-6:])) <= 2:
            messages.append(
                {
                    "role": "user",
                    "content": "You seem to be looping. Change strategy: explore a different direction and avoid repeating the last pattern.",
                }
            )

        # ACT phase
        action, reason = llm_act()
        out = http_post_json(f"{srv}/api/step", {"id": sid, "action": action, "seq": step})

        if out.get("error"):
            if verbose:
                print(
                    f"[Step {step}] action={action} SERVER_ERROR={out.get('error')} payload={json.dumps(out, ensure_ascii=False)}"
                )
            messages.append({"role": "assistant", "content": f"I choose action: {action}. Reason: {reason}"})
            messages.append({"role": "user", "content": f"Server error: {json.dumps(out, ensure_ascii=False)}"})
            continue

        text = out.get("text", "")
        done = bool(out.get("done"))
        last_inv = out.get("inventory")

        if verbose:
            print(
                f"[Step {step}] action={action} reason={reason}\n  text={text}\n  inv={json.dumps(last_inv or {}, ensure_ascii=False)}"
            )

        # Update history signature
        hist_sig.append((action, str(out.get("status")), str(out.get("observe"))))

        # Feed back to model
        messages.append({"role": "assistant", "content": f"I choose action: {action}. Reason: {reason}"})
        messages.append(
            {
                "role": "user",
                "content": f"Result: {text}\nYour inventory: {json.dumps(last_inv or {}, ensure_ascii=False)}",
            }
        )

        if done:
            if verbose:
                print("WIN")
            break

    return {
        "success": bool(done),
        "steps": int(steps),
        "inventory": last_inv,
        "session_id": sid,
    }


def main() -> None:
    ap = make_base_argparser(default_agent_name="demo_planning_llm")
    ap.add_argument("--model", type=str, default="openrouter/auto")
    ap.add_argument("--temperature", type=float, default=0.2)
    args = ap.parse_args()

    res = run_agent(
        base_url=args.base_url,
        path=args.path or "TRAINING/S0-keys/STAGE-01/0000.json",
        seed=args.seed,
        model=args.model,
        max_steps=args.max_steps,
        temperature=float(args.temperature),
        agent=args.agent,
        verbose=bool(args.verbose),
    )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
