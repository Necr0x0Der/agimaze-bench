# Benchmark tools

The [`../bench/`](../bench) folder contains small, practical utilities for running **repeatable evaluations** of AGI Maze agents.

The goal of these scripts is not to define a final, canonical benchmark protocol.
Instead, they provide a lightweight harness that is useful during development:

- run many episodes in a row
- collect JSONL logs
- compute quick aggregate statistics

More rigorous benchmark protocols (e.g. standardized splits, reporting conventions, and model-specific evaluation rules) will be developed and added over time.

## Included tools

### `demo_bench_runner.py`
A minimal runner that executes a single agent over a list of maze paths and writes one JSON record per episode (JSONL).

It supports:
- selecting an agent (`random`, `simplest_llm`, `planning_llm`)
- repeating each target multiple times (`--repeats`)
- optional verbosity (useful for debugging)

This is especially handy for collecting basic success-rate statistics for simple baselines such as:
- `demo_random_agent.py`
- `demo_simplest_llm_agent.py`

### `bench_report.py`
A small reporting helper that reads the JSONL logs produced by `demo_bench_runner.py` and prints:
- overall success rate
- breakdown by group (TRAINING/CLASSIC/EXTENDED/TUTORIAL)
- breakdown by path prefix (configurable depth)

It also supports splitting successes into “good” vs “late” given a step threshold (`--good-steps`).

## Typical workflow

1) Run a batch:

```bash
python3 bench/demo_bench_runner.py --agent random --path TRAINING/S0-keys/STAGE-01 --repeats 5 \
  --out logs/random_s0_stage01_r5.jsonl
```

2) Summarize results:

```bash
python3 bench/bench_report.py logs/random_s0_stage01_r5.jsonl
python3 bench/bench_report.py logs/random_s0_stage01_r5.jsonl --good-steps 200
```
