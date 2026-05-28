"""Common helpers for baseline agents.

These utilities keep agents consistent:
- shared CLI flags (base URL, path, seed, max steps, verbosity)
- consistent /api/start payload creation

Agents can extend the base parser with additional arguments.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = "https://agimaze.org"
DEFAULT_FALLBACK_PATH = "TRAINING/S0-keys/STAGE-01"


def make_base_argparser(*, default_agent_name: str) -> argparse.ArgumentParser:
    """Create a base ArgumentParser with common flags.

    Agents are expected to add their own arguments (if any) and then call parse_args().
    """

    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    ap.add_argument("--max-steps", type=int, default=None, help="max steps override")
    ap.add_argument("--seed", type=int, default=None, help="optional task RNG seed override")
    ap.add_argument(
        "--path",
        type=str,
        default=None,
        help=(
            "PACKS-relative path including group, e.g. TRAINING/S0-keys/STAGE-01/0005.json, "
            "CLASSIC/EASY/pits/4x4/0000.json, or a directory like EXTENDED/boat/STAGE-01-4x4"
        ),
    )
    ap.add_argument("--agent", type=str, default=default_agent_name, help="agent name for logging")
    ap.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="print server messages (default: enabled; use --no-verbose to silence)",
    )
    return ap


def build_start_payload(
    *,
    path: str | None,
    seed: int | None,
    agent: str,
    verbose: bool,
    fallback_path: str = DEFAULT_FALLBACK_PATH,
    client: str = "api",
    extra: dict[str, Any] | None = None,
) -> dict:
    """Build a /api/start payload in a consistent way.

    - If path is None, uses fallback_path.
    - Prints a standard "Starting game" line when verbose.
    - Allows extending payload with `extra`.
    """

    path_to_use = (path or fallback_path).strip()
    if verbose:
        print(f"Starting game: path={path_to_use}")

    payload: dict[str, Any] = {
        "path": path_to_use,
        "seed": seed,
        "client": client,
        "agent": agent,
    }
    if extra:
        payload.update(dict(extra))
    return payload
