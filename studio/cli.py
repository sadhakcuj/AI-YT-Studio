"""Command line entry point.

  python -m studio.cli topic "The strange history of the Voynich manuscript"
  python -m studio.cli discover            # research trends, you pick an idea
  python -m studio.cli discover --auto     # fully automatic: top idea is chosen for you
  python -m studio.cli resume <run_id>     # continue a stopped run
"""
from __future__ import annotations

import argparse
import sys

from .config import load_settings
from .graph import run_pipeline
from .llm import BudgetExceeded, LLMRouter
from .state import RunState


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="studio")
    p.add_argument("--config", default="config/settings.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("topic", help="Mode B: you give the topic")
    t.add_argument("topic")
    d = sub.add_parser("discover", help="Mode A: find the best idea from live trends")
    d.add_argument("--auto", action="store_true", help="skip the pick prompt and take the top idea")
    d.add_argument("--pick", type=int, help="choose opportunity number without prompting")
    r = sub.add_parser("resume", help="resume a run by id")
    r.add_argument("run_id")

    args = p.parse_args(argv)
    cfg = load_settings(args.config)
    llm = LLMRouter(cfg)

    if args.cmd == "topic":
        state = RunState(mode="topic", topic=args.topic)
        pick, auto = None, True
    elif args.cmd == "discover":
        state = RunState(mode="discover")
        pick, auto = args.pick, args.auto
    else:
        state = RunState.load(args.run_id)
        llm.used = state.tokens_used
        pick, auto = None, True

    print(f"Run {state.run_id} ({state.mode})")
    try:
        state = run_pipeline(state, llm, cfg, pick=pick, auto=auto)
    except BudgetExceeded:
        print(f"Stopped on token budget. Resume with: python -m studio.cli resume {state.run_id}")
        return 2
    print(f"\nDone: {state.status}. Output in {state.dir}/ (script.md, script.json, report.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
