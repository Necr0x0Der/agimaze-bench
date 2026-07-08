#!/usr/bin/env python3
"""World-model-in-prompt LLM baseline agent (OpenAI-compatible / OpenRouter).

This is a variant of the planning baseline aimed at reducing prompt bloat.

Compared to `demo_planning_llm_agent.py`:
- we keep a *clean* action/observation history (like `demo_simplest_llm_agent.py`)
- the agent still makes decisions in two phases: PLAN then ACT
- however, only the **last plan** is carried across steps (not the full list of past plans)

Intuition: the plan acts like an external world model summary that is incrementally updated.

Environment variables:
- `OPENAI_API_KEY` or `OPENROUTER_API_KEY`
- Optional: `OPENAI_BASE_URL` / `OPENROUTER_BASE_URL` (defaults to OpenRouter)

Examples:
  OPENROUTER_API_KEY=... python3 agents/worldmodel_llm_agent.py \
    --path TRAINING/S0-keys/STAGE-01/0000.json --model openrouter/auto
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
    temperature: float = 0.2,
    agent: str = "worldmodel_llm",
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

    steps_limit = int(max_steps) if isinstance(max_steps, int) and max_steps > 0 else None
    if steps_limit is None:
        ms = task_meta.get("max_steps")
        steps_limit = int(ms) if isinstance(ms, int) and ms > 0 else 200

    if verbose:
        print(f"session={sid} max_steps={steps_limit} actions={actions}")

    board_str = ""
    if task_meta.get("board"):
        b = task_meta["board"]
        board_str = f"board size: n={b.get('n')} rows, m={b.get('m')} cols"

    start_str = ""
    if task_meta.get("start"):
        s0 = task_meta["start"]
        start_str = f"start position (row,col): ({s0.get('row')},{s0.get('col')})"

    sys_prompt = (
        desc
        + "\n\n"
        + "Current maze info:\n"
        + board_str
        + "\n"
        + start_str
        + "\n\n"
        + f"Your inventory: {json.dumps(inv0, ensure_ascii=False)}\n\n"
        + "You will interact with a partially observable maze by choosing one action each step.\n"
        + "You should keep and update a compact representation of the current problem state (your external world model summary).\n"
        + "When the server rejects an action, choose another valid action."
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

    # Base history: only actions and environment responses (no accumulating plans)
    messages: list[dict] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": "Game started. Choose your first action."},
    ]

    last_plan = "(empty)"

    def llm_plan() -> str:
        payload = {
            "model": model,
            "temperature": float(temperature),
            "messages": messages
            + [
                {
                    "role": "user",
                    "content": (
                        "WORLD MODEL UPDATE: You are given your previous world model summary below.\n\n"
                        f"Previous summary:\n{last_plan}\n\n"
                        "Update this summary based on the action/observation history so far. "
                        "Keep it compact and actionable. If uncertain, track possibilities."
                    ),
                }
            ],
        }
        resp = openai_chat_completions(base_url=llm_base_url, api_key=api_key, payload=payload)
        return (resp["choices"][0]["message"].get("content") or "").strip()

    def llm_act(*, plan: str) -> tuple[str, str]:
        payload = {
            "model": model,
            "temperature": float(temperature),
            "messages": messages
            + [
                {
                    "role": "user",
                    "content": (
                        "WORLD MODEL SUMMARY (most recent):\n" + plan + "\n\n"
                        "ACT: choose exactly one action."
                    ),
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

        txt = (msg.get("content") or "").strip().lower()
        for a in actions:
            if a in txt:
                return a, "(parsed from text)"
        return random.choice(list(actions)), "(random fallback)"

    done = False
    steps = 0
    last_inv = start.get("inventory")

    for step in range(1, int(steps_limit) + 1):
        steps = step

        # PLAN (update world model summary using only the previous summary)
        plan = llm_plan()
        if plan:
            last_plan = plan
        if verbose:
            print(f"[Step {step}] PLAN: {last_plan[:200]}{'...' if len(last_plan) > 200 else ''}")

        # ACT (use only the current plan)
        action, reason = llm_act(plan=last_plan)
        out = http_post_json(f"{srv}/api/step", {"id": sid, "action": action, "seq": step})

        if out.get("error"):
            if verbose:
                print(f"[Step {step}] action={action} SERVER_ERROR={out.get('error')} payload={json.dumps(out, ensure_ascii=False)}")
            messages.append({"role": "assistant", "content": f"I choose action: {action}. Reason: {reason}"})
            messages.append({"role": "user", "content": f"Server error: {json.dumps(out, ensure_ascii=False)}"})
            continue

        text = out.get("text", "")
        done = bool(out.get("done"))
        last_inv = out.get("inventory")

        if verbose:
            print(
                f"[Step {step}] action={action} reason={reason} text={text} inv={json.dumps(last_inv or {}, ensure_ascii=False)}"
            )

        # Append only action/observation history
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
    ap = make_base_argparser(default_agent_name="worldmodel_llm")
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
