# Draft: AGI Maze as a benchmark framework for world-modeling agents

> Status: **early draft / outline**. This is not polished prose yet.

## 0. Abstract (draft)

Large language models (LLMs) are powerful pattern-completion systems, but their default operating mode—predicting the next token from a static context—does not reliably produce persistent, manipulable representations of an external world. Many tasks that look like “reasoning” in text become substantially harder once the environment is **partially observable**, **stateful**, and requires **memory** and **structured hypotheses** about hidden state.

AGI Maze is a lightweight framework for building such environments without requiring high-dimensional sensory inputs. It provides a family of grid-based maze tasks with a clean API and multiple difficulty regimes (tutorial/training/classic/extended/hidden). The goal is to create benchmarks where agents must learn and use **world state representations**, not just infer a local rule.

## 1. Motivation: from LLM limitations to world models

### 1.1 LLMs are static predictors, not persistent world simulators

A core limitation of current LLM-only agents is that the model itself is *static*: the only “dynamics” typically come from:
- adding text to the prompt (message history as working memory),
- retrieving external text (RAG),
- and feeding tool outputs back as text.

This creates two intertwined problems:

1) **Memory as text is inefficient.** Some tasks require explicit state tracking, revisiting earlier observations, and performing multi-step search. Encoding everything as unstructured text leads to brittle behavior and high token cost.

2) **Representation is not guaranteed.** Next-token prediction encourages extracting whatever information is needed to produce the next output, not maintaining a stable, manipulable representation of “what is true in the world.” In language tasks this deficiency is partially hidden because language already *is* a world description; in interactive environments, it becomes obvious.

> Related perspective: *LLMs’ Role in AGI* (reference to add)

A complementary angle comes from empirical observations that internal activations can encode much of the final output early in the network, which supports the view that many models are best described as efficient predictors rather than explicit world-state modelers. See e.g. <https://arxiv.org/pdf/2605.23872> (the discussion around intermediate-layer information content).

### 1.2 Why “world models” need more than rule discovery

“World modeling” is often reduced to “discover the rule of a game.” But for agents, a full notion of world modeling also includes:
- representing **latent state** (what you cannot currently observe),
- maintaining **beliefs** under uncertainty,
- updating those beliefs with new evidence,
- reasoning over representations (maps, graphs, causal schemas),
- and using memory efficiently (working memory, episodic memory, long-term knowledge).

In other words: world models are about **state and representation**, not only about rules.

## 2. Why AGI-ARC-3 is not enough (for this specific target)

AGI-ARC-3 is an important benchmark for *generalization across tasks* and for inferring hidden generative rules. However, many ARC-like settings:
- are effectively **fully observable**,
- do not require agents to maintain a persistent, queryable **world state** across time,
- and do not pressure-test partial observability, localization, mapping, and long-horizon memory.

ARC-3 targets an important slice of AGI, but it is not a direct test of “can the agent construct and use a representation of an evolving world state?”

This is exactly the gap AGI Maze is designed to fill.

## 3. AGI Maze: a lightweight testbed for state, memory, and representation

### 3.1 Design goals

AGI Maze aims to be:
- **interactive and stateful**, but with low bandwidth (no pixels required),
- **partially observable** by default (except tutorial mode),
- simple enough for humans to play,
- extensible to new mechanics,
- and usable via a stable HTTP API.

### 3.2 The base environment: grid + walls + monolith + exit

The agent lives on a grid. Each step it chooses an action from:
- up / down / left / right

The maze has:
- internal walls,
- an unbreakable border (“monolith”) with exactly one opening (the exit),
- a treasure chest and its key.

Key constraints:
- stepping into a wall/monolith does not change position but consumes a step,
- treasure requires the key,
- exiting requires the treasure,
- some instances also require an exit key.

This alone already creates a POMDP-like situation when the map is hidden: the same observation can correspond to multiple locations, and the agent must maintain a belief over where it might be.

### 3.3 Dynamics that amplify partial observability

To make state inference and representation genuinely necessary, AGI Maze includes mechanics such as:

- **Rivers**: stepping onto a river cell triggers forced downstream movement (e.g., 2 cells, or 1 near the mouth). The agent must reason about both the intentional move and the forced transition.

- **Pit cycles**: stepping into a pit teleports the agent to the next pit in a cycle (wrapping around). Multiple cycles may exist.

These mechanics are deliberately chosen because naive “grid exploration” strategies break down: localization and mapping require explicit hypotheses.

### 3.4 Extensions as a generality test

Beyond the core rules, the framework supports extensions that introduce:
- new items (e.g., boat, grenades, flashlight),
- new cell types,
- new actions (e.g., blast, shine).

Crucially, extensions can create situations where reaching the goal is impossible without understanding the new mechanic (e.g., an exit behind a river that is only crossable with a boat; a key sealed behind a blastable wall).

This makes “general world understanding” (in a narrow but meaningful sense) observable: does the agent infer new mechanics from interaction, or does it rely on brittle hardcoding?

## 4. Task groups and what they are for

This section should align with the public docs, but the article can motivate the choice.

- **TUTORIAL**: open map; for teaching humans/agents the mechanics; not used for scoring.

- **TRAINING**: small mazes + generous step budgets; useful for iteration, calibration, RL training, and baseline benchmarking.

- **CLASSIC**: larger mazes under core rules; calibrated against humans; passing indicates a strong solver.

- **EXTENDED**: tests generality via new mechanics.

- **HIDDEN**: private hold-out; validates that EXTENDED performance is not merely dataset-fitting.

The presence of HIDDEN reframes the goal: not to “beat the benchmark” at any cost, but to demonstrate general mechanisms that transfer.

## 5. What AGI Maze measures (and what it does not)

### 5.1 What it pressures

- belief tracking under partial observability
- map-building / representation learning
- memory use and compression (what to remember, how)
- long-horizon planning under uncertainty
- inferring new mechanics from outcomes

### 5.2 What it avoids (by design)

- pixel-level perception
- continuous control

The claim is not that pixels are unimportant, but that removing them isolates the *representation and reasoning* problem.

## 6. Baseline observations (preliminary)

High-level qualitative findings to expand:

- A pure **random agent** provides a calibration baseline for TRAINING difficulty.

- A “vanilla LLM” agent that only sees the same text as humans often fails even on small mazes.
  Some models can be *systematically worse than random*.

- Adding a simple “planning/notes” phase (LLM writes a short plan before acting) can help some stronger models by turning the message history into a crude working memory.

This section should later include a minimal set of tables/figures summarizing success rates across subsets.

## 7. Implications and future directions

- Better baselines: heuristic SLAM-like agents, probabilistic belief trackers, search over map hypotheses.
- Agent architectures: explicit memory modules, learned state abstractions, tool-based world models.
- Benchmark protocol: standardized splits, reporting, and evaluation costs.
- Extending mechanics: new objects/cells to test fast adaptation.

## 8. Appendix: references and links (placeholder)

- AGI Maze website: https://agimaze.org
- API + baseline code: https://github.com/Necr0x0Der/agimaze-bench
- Reference to: “LLMs’ Role in AGI” (add exact citation)
- Reference to: https://arxiv.org/pdf/2605.23872
- Reference to: AGI-ARC-3 (add exact link)
