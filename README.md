# AGI Maze Bench

[AGI Maze](https://agimaze.org) is a framework for evaluating **AGI agents** and their ability to build and use **world models** in partially observable environments.

In this context, “world modeling” is meant broadly:
- not just discovering simple regularities in an environment,
- but forming usable descriptions of partially observed worlds and reasoning about them.

This repository contains a clean, public-facing package of materials for developers and researchers:

- a stable, developer-facing **API specification**
- **baseline agent examples** (reference implementations)
- **benchmark utilities** (small runners + reporting scripts)

## Docs

- [API](docs/api.md) — the HTTP+JSON interface for starting episodes, taking actions, and receiving observations.
- [Agents](docs/agents.md) — an overview of included baseline agents and shared helpers.
- [Benchmark tools](docs/bench.md) — lightweight utilities for repeatable runs and quick statistics.
- [Results](docs/results.md) — calibration notes and baseline results (where applicable).

## Repository layout

- `docs/` — documentation (API, agents, benchmark tools, results)
- `agents/` — baseline agents and example clients
- `bench/` — benchmark runner/report scripts and helpers
