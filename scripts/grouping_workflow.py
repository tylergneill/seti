#!/usr/bin/env python3
"""Write the workflow that fans one grouping step out over its pending batches.

Writes the step's sub-agent prompt (from grouping_prompt.py, never retyped)
to tmp/workflows/grouping-<step>-<collection>.md, and beside it a Workflow
script, .js, which starts one sub-agent per batch directory it is given
and tells each to read that prompt file and follow it. The prompt is kept
out of the script so that the script is short enough for Claude Code to
show in full when it asks for approval. Then
splits the pending batches into groups and prints one JSON list of batch
directories per line. The dispatcher starts one workflow per line, all at
once.

A single workflow runs at most min(16, CPUs - 2) agents at a time, so the
batches are split into as many workflows as it takes to reach --workers
agents in flight.

  grouping_workflow.py --run 2026-10-13 --collection g --step read [--workers 10]
  grouping_workflow.py ... --only p1-title-003      # just this batch, as a trial
  grouping_workflow.py ... --limit 4                # just the first four pending
"""

import argparse
import json
import math
import os

from common import ROOT
from grouping_common import ALL, COLLECTIONS, STEPS
from grouping_pending import pending_batches
from grouping_prompt import build_prompt

OUT = ROOT / "tmp" / "workflows"

TEMPLATE = """export const meta = {
  name: 'grouping-%s',
  description: 'One %s sub-agent per batch directory',
  phases: [{ title: '%s' }],
}
const PROMPT = 'Your instructions are in the file ' + %s +
  '. Read that file in full before doing anything else, and follow it exactly. ' +
  'It ends by saying that your batch directory follows. Your batch directory is:'
phase('%s')
await parallel(args.map(dir => () =>
  agent(PROMPT + '\\n' + dir, { label: dir.split('/').pop(), phase: '%s', agentType: 'general-purpose' })))
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--collection", required=True, choices=sorted(COLLECTIONS) + [ALL])
    ap.add_argument("--step", required=True, choices=sorted(STEPS))
    ap.add_argument("--workers", type=int, default=10,
                    help="sub-agents in flight across all workflows (default 10)")
    ap.add_argument("--only", action="append", help="dispatch only this batch directory, by name; may repeat")
    ap.add_argument("--limit", type=int, help="dispatch at most this many of the pending batches")
    args = ap.parse_args()

    dirs = [b for b in pending_batches(args.run, args.collection, args.step)
            if not args.only or b.name in args.only][:args.limit]
    if not dirs:
        print("nothing pending")
        return
    dirs = [str(b.resolve()) for b in dirs]

    OUT.mkdir(parents=True, exist_ok=True)
    script = OUT / f"grouping-{args.step}-{args.collection}.js"
    role = STEPS[args.step]["prompt"].removesuffix(".md")
    phase = args.step.capitalize()
    prompt_file = script.with_suffix(".md")
    prompt_file.write_text(build_prompt(args.step, args.collection), encoding="utf-8")
    prompt = json.dumps(str(prompt_file))
    script.write_text(TEMPLATE % (args.step, role, phase, prompt, phase, phase), encoding="utf-8")

    per_workflow = max(1, min(16, (os.cpu_count() or 4) - 2))
    groups = min(len(dirs), math.ceil(args.workers / per_workflow))
    print(f"script: {script}")
    print(f"{len(dirs)} pending batch(es) in {groups} workflow(s), up to {per_workflow} agents each")
    for i in range(groups):
        print(json.dumps(dirs[i::groups]))


if __name__ == "__main__":
    main()
