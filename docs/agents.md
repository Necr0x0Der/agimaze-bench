# Agents

This repository ships a small set of **baseline agents** under [`../agents/`](../agents).

They serve two purposes:

1) **Examples** of how to interact with the public **AGI Maze HTTP API** (start an episode, step through it, handle errors).
2) **Baselines** for calibration and sanity-checking: simple policies that help you verify your setup and estimate task difficulty.

These agents are intentionally minimal. They are not meant to be state-of-the-art solvers.

## Included agents

### `demo_random_agent.py`
A pure random policy.

Use it to:
- smoke-test the API end-to-end
- get a rough lower bound on success rates for small mazes
- check that benchmark tooling and logging work under load

### `demo_simplest_llm_agent.py`
A minimal “vanilla LLM” agent.

Characteristics:
- uses the **English** text observation as the main signal
- includes the current inventory in the prompt/context
- tolerates transient LLM timeouts (retries) and server-side `bad_action` responses

Use it to quickly test:
- how a given model behaves with minimal scaffolding
- whether an endpoint/model is stable enough for longer runs

### `demo_planning_llm_agent.py`
A slightly more structured LLM baseline.

Compared to `demo_simplest_llm_agent.py`:
- uses a 2-phase loop (**PLAN** then **ACT**) to encourage deliberate behavior
- includes a lightweight “loop nudge” when the agent repeats the same pattern

Use it when you want a stronger (but still simple) baseline without adding external memory/state.

## Shared helpers

To keep all agents consistent, the `agents/` folder also contains shared utilities:

- `common.py` — shared CLI flags and consistent `/api/start` payload creation
- `http_helpers.py` — stdlib-only JSON HTTP helpers (including reading JSON error payloads)

## Adding a new agent

A new agent should typically:

- reuse `common.py` and `http_helpers.py`
- expose a `run_agent(...) -> dict` function so it can be called by benchmark tools
- handle server-side JSON errors (e.g. `bad_action`) without crashing
- avoid depending on private implementation details of the maze engine
