# Results and calibration

This document collects:

- **calibration** of maze difficulty (step budgets and thresholds),
  using both the **random baseline** and human judgment where applicable;
- **baseline benchmark results** for simple agents.

The intent is to keep the evaluation story transparent:
- which task subsets are meant for development vs evaluation,
- what constitutes a “good” run vs a “late but still successful” run,
- and how to interpret success rates.

---

## Pack groups (intended use)

AGI Maze organizes tasks into several top-level groups.

### TUTORIAL

- **Not used for scoring/evaluating agents.**
- Intended for learning the rules/mechanics.
- The map is **open** (reveals the player position and key objects).
- Using TUTORIAL for training agents is allowed (it matches what a human sees in TUTORIAL).

### TRAINING

TRAINING is designed primarily for **development and calibration**, not for a public leaderboard-style challenge.

Key properties:

- **Small mazes** (typically 3×3 to 5×5), making it convenient for:
  - benchmarking simple baselines,
  - debugging more complex agents,
  - RL-style training (many fast episodes).

- **Generous step budgets.** TRAINING typically uses a deliberately high `max_steps`.
  This helps separate:
  - *qualitative failures* (agent is stuck / does not understand the mechanic), from
  - *quantitative slowness* (agent solves, but inefficiently).

- **Good vs hard threshold.** A convenient rule of thumb:
  - a **good** run is one that finishes within roughly **half** of the configured `max_steps`.
  - exceeding `max_steps` is treated as failure by many harnesses.

### CLASSIC

- Uses the same core rules as TRAINING.
- Mazes are larger and are meant to be interesting/challenging for humans.
- Step budgets and difficulty are calibrated **relative to humans**.

Passing CLASSIC reliably is evidence that an agent is a **strong solver** (not just a toy baseline).

### EXTENDED

- Contains tasks with additional systems / rule extensions.
- Intended to test **generality** (in the AGI sense): can an agent handle new mechanics without brittle specialization?

### HIDDEN

- Not publicly available.
- Used to validate that performance on EXTENDED is not merely dataset-fitting to public tasks.

The existence of HIDDEN underscores the goal of the benchmark:
- not to “beat” CLASSIC/EXTENDED at any cost,
- but to solve them in a way that plausibly transfers beyond the public set.

---

## Calibration

### Training subset

The TRAINING subset is a **controlled reference distribution**: a stable substrate for iteration where
“better than random” is interpretable.

Calibration baseline:

- **Random agent is used as the reference for smoothing difficulty across stages/sizes.**
  The goal is *not* to make the random agent pass every level with equal probability.
  Instead, stages are selected/tuned so that difficulty is reasonably comparable relative to the random baseline.

In practice, calibration uses two thresholds:

- `soft_good_steps` — a soft target step count for a “good” run
- `hard_max_steps` — a hard step budget (exceeding it is treated as failure in many runs)

The tables below also record random-agent success statistics:

- `success` — total success rate
- `good` — success within `soft_good_steps`
- `late` — success but exceeding `soft_good_steps` (still within `hard_max_steps`)

### Calibration tables (random baseline)

#### S0-keys

| Stage | Size | soft_good_steps | hard_max_steps | success | good | late |
|------:|------|----------------:|---------------:|--------:|-----:|-----:|
| STAGE-01 | 3x3 | 35 | 70 | 24.3 | 4.5 | 19.8 |
| STAGE-02 | 3x3 | 35 | 70 | 16.7 | 2.2 | 14.5 |
| STAGE-03 | 4x4 | 80 | 160 | 9.2 | 1.3 | 7.9 |
| STAGE-04 | 3x3 | 35 | 70 | 14.2 | 1.1 | 13.1 |
| STAGE-05 | 4x4 | 80 | 160 | 4.6 | 0.3 | 4.3 |
| STAGE-06 | 4x5 | 100 | 200 | 1.9 | 0.2 | 1.7 |

#### S1-rivers

| Stage | Size | soft_good_steps | hard_max_steps | success | good | late |
|------:|------|----------------:|---------------:|--------:|-----:|-----:|
| STAGE-01 | 3x3 | 35 | 70 | 22.3 | 4.3 | 18.0 |
| STAGE-02 | 3x4 | 50 | 100 | 15.0 | 2.7 | 12.3 |
| STAGE-03 | 4x4 | 80 | 160 | 6.8 | 1.4 | 5.4 |
| STAGE-04 | 4x4 | 80 | 160 | 1.5 | 0.2 | 1.3 |
| STAGE-05 | 4x4 | 80 | 160 | 1.3 | 0.2 | 1.1 |
| STAGE-06 | 5x5 | 125 | 250 | 2.6 | 0.1 | 2.5 |

#### S2-pits

| Stage | Size | soft_good_steps | hard_max_steps | success | good | late |
|------:|------|----------------:|---------------:|--------:|-----:|-----:|
| STAGE-01 | 3x3 | 35 | 70 | 24.8 | 4.8 | 20.0 |
| STAGE-02 | 4x4 | 80 | 160 | 18.1 | 3.2 | 14.9 |
| STAGE-03 | 4x5 | 100 | 200 | 10.1 | 1.3 | 8.8 |
| STAGE-04 | 4x4 | 80 | 160 | 5.9 | 0.7 | 5.2 |
| STAGE-05 | 4x5 | 100 | 200 | 4.3 | 0.4 | 3.9 |
| STAGE-06 | 5x5 | 125 | 250 | 3.6 | 0.3 | 3.3 |

#### S3-full

| Stage | Size | soft_good_steps | hard_max_steps | success | good | late |
|------:|------|----------------:|---------------:|--------:|-----:|-----:|
| STAGE-01 | 3x4 | 50 | 100 | 20.6 | 4.5 | 16.1 |
| STAGE-02 | 4x4 | 80 | 160 | 7.3 | 1.6 | 5.7 |
| STAGE-03 | 4x5 | 100 | 200 | 3.2 | 0.4 | 2.8 |
| STAGE-04 | 5x5 | 125 | 250 | 4.2 | 0.4 | 3.8 |
| STAGE-05 | 5x5 | 125 | 250 | 3.2 | 0.2 | 3.0 |
| STAGE-06 | 4x6 | 125 | 250 | 1.5 | 0.2 | 1.3 |

---

## Baseline benchmark results

(TODO) Add summary runs for baseline agents (random / simplest LLM / planning LLM) on selected subsets.
