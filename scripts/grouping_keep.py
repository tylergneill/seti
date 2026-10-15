#!/usr/bin/env python3
"""Keep what the sub-agents wrote: copy it out of tmp/ into data/grouping/runs/.

Nearly everything under tmp/grouping/<run>/ is rebuilt by script in
seconds: the shards, the dossiers and their windows, the united registries
and the settled items. What cannot be rebuilt without running the agents
again is what they wrote:

  opinions.json       the readers, pass 1
  consolidated.json   the consolidators and linkers, passes 2 and 3
  proposals.json      the grounders, against Pandit
  decisions.json      the item adjudicators, pass 2c

This copies those, batch directory by batch directory, to
data/grouping/runs/<run>/<code>/, with the two files that pin down what
they were written about: items.jsonl, the Atlas's items as the search
index had them on the day, and run.json, which records how the shards and
windows were cut. From these, grouping_restore.py rebuilds the run under
tmp/ and the later steps can be run again.

  grouping_keep.py --run 2026-10-13 --collection g
"""

import argparse
import shutil

from common import ROOT
from grouping_common import ALL, COLLECTIONS, DATA, STEPS, batches, run_dir

RUNS = DATA / "runs"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--collection", required=True, choices=sorted(COLLECTIONS) + [ALL])
    args = ap.parse_args()

    base = run_dir(args.run, args.collection)
    out = RUNS / args.run / args.collection
    out.mkdir(parents=True, exist_ok=True)
    for name in ("items.jsonl", "run.json"):
        if (base / name).exists():
            shutil.copy2(base / name, out / name)
    kept = 0
    for step, spec in STEPS.items():
        if (args.collection == ALL) != (step.startswith("link-") or step == "ground"):
            continue
        for batch, done in batches(args.run, args.collection, step):
            if done:
                (out / batch.name).mkdir(exist_ok=True)
                shutil.copy2(batch / spec["output"], out / batch.name / spec["output"])
                kept += 1
    print(f"kept {kept} sub-agent file(s) of {args.run}, {args.collection}, under {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
