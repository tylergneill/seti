#!/usr/bin/env python3
"""Write the workflow that fans the research sub-agents out over a run's batches.

Writes tmp/workflows/research.js, a Workflow script with the sub-agent
prompt built in (agents/researcher.md with this checkout's paths filled
in, never retyped), which starts one sub-agent per batch directory it is
given. Then splits the pending batches into groups and prints one JSON
list of batch directories per line. The dispatcher starts one workflow
per line, all at once.

A batch is pending while it has items.json and no readable proposals.json.

  research_workflow.py --run 2026-10-09-open [--workers 25]
  research_workflow.py --run 2026-10-09-open --list      # just the pending batches
  research_workflow.py --prompt                          # just the sub-agent prompt
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

from common import ROOT, latest_pandit_extract

RESEARCH = ROOT / "tmp" / "research"
OUT = ROOT / "tmp" / "workflows"
PROMPT = ROOT / "agents" / "researcher.md"

TEMPLATE = """export const meta = {
  name: 'research-seti-batches',
  description: 'One research sub-agent per batch of SETI rows',
  phases: [{ title: 'Research' }],
}
const PROMPT = %s
phase('Research')
await parallel(args.map(dir => () =>
  agent(PROMPT + '\\n' + dir, { label: dir.split('/').pop(), phase: 'Research', agentType: 'general-purpose' })))
"""


def build_prompt(pandit=None):
    text = PROMPT.read_text(encoding="utf-8")
    return (text.replace("{python}", sys.executable)
                .replace("{lookup}", str(ROOT / "scripts" / "lookup.py"))
                .replace("{pandit}", str(Path(pandit).resolve() if pandit else latest_pandit_extract())))


def pending_batches(run):
    run_dir = RESEARCH / run
    if not run_dir.is_dir():
        raise SystemExit(f"No run at {run_dir}; make one with research_prep.py.")
    pending = []
    for batch in sorted(run_dir.glob("batch-*")):
        if not (batch / "items.json").exists():
            continue
        try:
            json.loads((batch / "proposals.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            pending.append(batch)
    return pending


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", help="the run to dispatch, as named by research_prep.py")
    ap.add_argument("--pandit", help="cleaned Pandit extract (default: the newest in ../panditya/data)")
    ap.add_argument("--workers", type=int, default=25, help="sub-agents in flight across all workflows (default 25)")
    ap.add_argument("--list", action="store_true", help="list pending batches and stop")
    ap.add_argument("--prompt", action="store_true", help="print the sub-agent prompt and stop")
    args = ap.parse_args()

    prompt = build_prompt(args.pandit)
    if args.prompt:
        sys.stdout.write(prompt)
        return
    if not args.run:
        ap.error("--run is required")

    dirs = [str(b.resolve()) for b in pending_batches(args.run)]
    if args.list:
        print("\n".join(dirs) if dirs else "nothing pending")
        return

    OUT.mkdir(parents=True, exist_ok=True)
    script = OUT / "research.js"
    script.write_text(TEMPLATE % json.dumps(prompt, ensure_ascii=False), encoding="utf-8")

    per_workflow = max(1, min(16, (os.cpu_count() or 4) - 2))
    groups = min(len(dirs), math.ceil(args.workers / per_workflow))
    print(f"script: {script}")
    print(f"{len(dirs)} pending batch(es) in {groups} workflow(s), up to {per_workflow} agents each")
    for i in range(groups):
        print(json.dumps(dirs[i::groups]))


if __name__ == "__main__":
    main()
