# API (AGI Maze)

This document specifies the **public HTTP+JSON API** used to build agents for **AGI Maze**.

The reference deployment is available at:

- https://agimaze.org

The API is intentionally small:
- start an episode
- take steps by sending **actions**
- receive **observations**

The API is stable and designed to be used by:
- baseline agents
- benchmark harnesses
- research agents (LLM, RL, planning, etc.)

---

## Concepts

### Episode / session

An **episode** is a single playthrough of one maze instance.
When you start an episode, the server returns a `session_id` (field name: `id`).
All subsequent steps reference this `id`.

### Actions

Each step, an agent sends an `action` (string). Core movement actions:

- `up`, `down`, `left`, `right`

Some tasks may enable additional actions (the server will explicitly list them in `actions` when you start):

- `look_up`, `look_down`, `look_left`, `look_right`
- `bomb_up`, `bomb_down`, `bomb_left`, `bomb_right`

Agents should treat the server-provided list `actions` as authoritative.

### Observations

Each call to `/api/step` returns an **observation** describing what happened.
The server provides two parallel views of (roughly) the same information:

- `text` — the **primary** English message shown to humans. It is fully usable by LLM agents.
- `formal` — a structured version of the observation. It can be convenient for non-LLM agents
  (or any agent that prefers a normalized schema), but it is not required.

The `formal` object is designed to be agent-friendly and low-spoiler:

- it includes inventory and event types
- it does **not** expose hidden coordinates / full ground-truth state

### Packs and paths

Episodes are started from a **pack path**.
A path is a PACKS-relative string that starts with the group:

- `TUTORIAL/...`
- `TRAINING/...`
- `CLASSIC/...`
- `EXTENDED/...`

You may pass either:
- a **file path** to a specific JSON bundle, or
- a **directory path** (the server will pick a random JSON inside it)

#### How do I discover valid paths?

There are a few practical ways to find pack paths:

- **Web UI browsing**: the easiest approach for development. The public site UI lets you browse
  groups and subfolders and start tasks interactively.

- **Benchmark configs / scripts**: paths used in official experiments are recorded in benchmark
  harness commands and logs. If you are reproducing a benchmark run, the path list usually comes
  from there.

- **Documentation examples**: this document (and other docs in this repo) may list commonly used
  subpaths for convenience.

An API endpoint for enumerating packs could be added in the future, but it is not currently required
for agent development.

---

## Groups and map visibility

### TUTORIAL = open map

The `TUTORIAL` group uses an **open map** setting.
In this mode, the response includes a `map` field that reveals the current player position and key objects.

- On `/api/start`, `map` is returned.
- On every `/api/step`, `map` is also returned.

This is useful for:
- teaching humans the mechanics
- supervised learning (this is allowed: it matches the information available to humans in TUTORIAL)
- debugging and agent development

### TRAINING / CLASSIC / EXTENDED = restricted map

In these groups, `map` may still be present, but it should be treated as **non-informative / restricted**.
Agents should primarily rely on `text` and `formal`.

---

## Endpoints

All requests and responses are JSON.

### `GET /api/description`

Returns a global English description of the game rules.

Response:
```json
{ "description": "..." }
```

### `POST /api/start`

Start a new episode.

Request fields:

- `path` (string, required): pack path including group prefix.
  Examples:
  - `TRAINING/S0-keys/STAGE-01/0005.json`
  - `CLASSIC/EASY/pits/4x4/0000.json`
  - `EXTENDED/boat/STAGE-01-4x4`  *(directory)*

- `seed` (int | null, optional): overrides the task RNG seed in configurations where supported.
  Typically, `seed` is left unset to sample from curated, pre-generated mazes.
  If you set `seed`, the server may generate a fresh maze instance; its difficulty (and even solvability)
  may vary and is not guaranteed. This can still be useful for RL-style training where unique mazes are desired.

- `client` (string, recommended): use `"api"`.

- `agent` (string, required if `client="api"`): an identifier used for logging/benchmarking.

Response (important fields):

- `id` (string): session id
- `actions` (string[]): allowed action strings for this episode
- `task_meta` (object): per-task metadata
  - `max_steps` (int | null): step budget (often treated as a hard limit in harnesses)
  - `board.n`, `board.m` (int): board size
  - `start.row`, `start.col` (int): start position (included for reproducibility)

- `formal` (object): structured “start observation”
- `text` (string): human-readable start message
- `map` (string): rendered map (notably informative in `TUTORIAL`)

Minimal example response shape:
```json
{
  "id": "...",
  "actions": ["up","down","left","right"],
  "task_meta": {"max_steps": 200, "board": {"n": 4, "m": 4}},
  "text": "Game has started.",
  "formal": {"status": "success", "observe": "empty", "events": [], "inventory": {}}
}
```

### `POST /api/step`

Execute one action.

Request:
- `id` (string, required): session id
- `action` (string, required): chosen action
- `seq` (int | null, optional but recommended): client-side sequence number

`seq` helps with robustness:
- if a request is duplicated/out-of-order (retries, network issues), the server may return the last response instead of applying an extra step.

Response:
- `text` (string): narration
- `done` (bool): `true` iff the episode ended successfully
- `formal` (object): structured observation
- `inventory` (object): current inventory snapshot
- `events` (string[]): event list
- `map` (string): rendered map (notably informative in `TUTORIAL`)

`formal` shape (high-level):
```json
{
  "formal": {
    "status": "success" | "blocked",
    "observe": "empty" | "key" | "treasure" | "exit_key" | "boat" | "grenade_pack" | "exit",
    "events": ["picked_key", "opened_treasure", "exit_blocked", "exited", "look", "bomb_success", "river_entered", ...],
    "inventory": {"key": true, "treasure": true, "grenades": 1, ...},
    "details": {"river": {"carried": true, ...}, "landed": {"kind": "..."}, "look": {"...": "..."}}
  }
}
```

#### Error handling

If the action is invalid, the server returns HTTP 400 with JSON:

```json
{
  "error": "bad_action",
  "action": "...",
  "allowed": ["up", "down", "left", "right", ...]
}
```

Agents should treat this as an **observation-like response**:
- do not crash
- choose a new valid action and continue

### `GET /api/session?id=<session_id>`

Fetch the current session snapshot.
This is mainly useful for UIs and debugging.

Response includes `map`, `actions`, and `inventory`.

---

## Recommended agent loop

1) `GET /api/description` (optional; useful for prompts)
2) `POST /api/start` → receive `id`, `actions`, `task_meta`
3) Repeat up to `task_meta.max_steps`:
   - pick `action ∈ actions`
   - `POST /api/step` with `seq=t`
   - if `done=true` → success

Practical notes:
- Use `seq` to avoid accidental double-steps on retries.
- If you use retries for network/LLM calls, keep them client-side; do not assume a failed HTTP request means the step was not applied.
