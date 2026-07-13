#!/usr/bin/env python3
"""Minimal LLM baseline agent (OpenAI-compatible / OpenRouter).

This script is a *demo* and a practical baseline for testing vanilla LLMs against
**the public AGI Maze HTTP API**.

It:
- fetches the global game description via `GET /api/description`
- starts an episode via `POST /api/start`
- repeatedly calls an LLM to choose the next `action`
- executes that action via `POST /api/step`

Environment variables:
- `OPENAI_API_KEY` or `OPENROUTER_API_KEY`
- Optional: `OPENAI_BASE_URL` / `OPENROUTER_BASE_URL` (defaults to OpenRouter)

Examples:
  OPENROUTER_API_KEY=... python3 agents/demo_simplest_llm_agent.py \
    --path TRAINING/S0-keys/STAGE-01/0000.json --model openrouter/auto

  OPENROUTER_API_KEY=... python3 agents/demo_simplest_llm_agent.py \
    --path CLASSIC/EASY/pits/4x4 --model openrouter/auto --max-steps 200
"""

from __future__ import annotations

import json
import os
import random
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


def run_agent(
    *,
    base_url: str = DEFAULT_BASE_URL,
    path: str = "TRAINING/S0-keys/STAGE-01/0000.json",
    seed: int | None = None,
    model: str = "openrouter/auto",
    max_steps: int | None = None,
    agent: str = "demo_simplest_llm",
    verbose: bool = True,
) -> dict:
    """Run one episode and return a result dict suitable for JSON logging."""

    # LLM endpoint/key
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY or OPENROUTER_API_KEY")

    llm_base_url = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENROUTER_BASE_URL")
        or "https://openrouter.ai/api/v1"
    )

    srv = base_url.rstrip("/")

    # Global English description
    desc = http_get_json(f"{srv}/api/description").get("description", "")

    start_payload = build_start_payload(path=path, seed=seed, agent=agent, verbose=verbose)
    start = http_post_json(f"{srv}/api/start", start_payload)
    sid = start["id"]

    actions = start.get("actions") or ["up", "down", "left", "right"]
    task_meta = start.get("task_meta") or {}

    # Determine step budget
    steps_limit = int(max_steps) if isinstance(max_steps, int) and max_steps > 0 else None
    if steps_limit is None:
        ms = task_meta.get("max_steps")
        steps_limit = int(ms) if isinstance(ms, int) and ms > 0 else 200

    session_info = f"session={sid} max_steps={steps_limit} actions={actions}"
    if verbose:
        print(session_info)

    # System prompt
    board_str = ""
    if task_meta.get("board"):
        b = task_meta["board"]
        board_str = f"board size: n={b.get('n')} rows, m={b.get('m')} cols"

    start_str = ""
    if task_meta.get("start"):
        s0 = task_meta["start"]
        start_str = f"start position (row,col): ({s0.get('row')},{s0.get('col')})"

    inv0 = start.get("inventory") or {}
    # Note: session id is added to make prompts different on repeated runs
    sys_prompt = (
        desc + "\n\n"
        "Current maze info:\n" + board_str + "\n" + start_str + "\n" + session_info + "\n\n"
        f"Your inventory: {json.dumps(inv0, ensure_ascii=False)}\n\n"
        "Choose one action each step.\n"
        "You will receive the result of each action as text."
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

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": "Game started. Choose your first action."},
    ]

    def choose_action() -> str:
        payload = {
            "model": model,
            "messages": messages,
            "tools": [tool],
            "tool_choice": {"type": "function", "function": {"name": "act"}},
        }
        resp = openai_chat_completions(base_url=llm_base_url, api_key=api_key, payload=payload)
        msg = resp["choices"][0]["message"]
        if verbose and "reasoning_content" in msg:
            print("<think>", msg["reasoning_content"], "</think>\n")

        # tool call
        tcs = msg.get("tool_calls") or []
        if tcs:
            args_json = tcs[0]["function"]["arguments"]
            data = json.loads(args_json) if isinstance(args_json, str) else args_json
            return str(data["action"]), str(data["reason"])

        # fallback: parse plain text
        txt = (msg.get("content") or "").strip().lower()
        reason = f"(WARNING tools are not used, parsed from text): {txt}"
        for pref in ["action: ", '"action": "', "choose: ", "act: ", "act: move_", ""]:
            for a in actions:
                if f"{pref}{a}" in txt:
                    return a, reason
        return random.choice(list(actions)), f"(ERROR no action selected): {txt}"

    done = False
    steps = 0
    last_inv = start.get("inventory")

    for step in range(1, int(steps_limit) + 1):
        if verbose:
            print(f"[Step {step}]")
        steps = step
        action, reason = choose_action()

        out = http_post_json(f"{srv}/api/step", {"id": sid, "action": action, "seq": step})

        # If server returns an error (e.g. bad_action), feed it back and continue.
        if out.get("error"):
            if verbose:
                print(f"action={action} SERVER_ERROR={out.get('error')} payload={json.dumps(out, ensure_ascii=False)}")
            messages.append({"role": "assistant", "content": f"I choose: {action}"})
            messages.append({"role": "user", "content": f"Server error: {json.dumps(out, ensure_ascii=False)}"})
            continue

        text = out.get("text", "")
        done = bool(out.get("done"))
        last_inv = out.get("inventory")

        if verbose:
            print(f"action={action} | reason={reason} \n response={text} inv={json.dumps(last_inv or {}, ensure_ascii=False)}")

        messages.append({"role": "assistant", "content": f"I choose: {action}"})
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
    ap = make_base_argparser(default_agent_name="demo_simplest_llm")
    ap.add_argument("--model", type=str, default="openrouter/auto")
    args = ap.parse_args()

    res = run_agent(
        base_url=args.base_url,
        path=args.path or "TRAINING/S0-keys/STAGE-01/0000.json",
        seed=args.seed,
        model=args.model,
        max_steps=args.max_steps,
        agent=args.agent,
        verbose=bool(args.verbose),
    )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
