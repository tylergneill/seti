#!/usr/bin/env python3
"""List the batch directories of a grouping step that still await their output.

A batch is pending while it has its input file and no output file that
parses. This is what makes a run resumable: run the step again after an
interruption and only the unfinished batches come back.

  grouping_pending.py --run 2026-10-13 --collection g --step read
  grouping_pending.py --run 2026-10-13 --collection g --step read --list
"""

import argparse

from grouping_common import ALL, COLLECTIONS, STEPS, batches


def pending_batches(run, code, step):
    return [batch for batch, done in batches(run, code, step) if not done]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--collection", required=True, choices=sorted(COLLECTIONS) + [ALL])
    ap.add_argument("--step", required=True, choices=sorted(STEPS))
    ap.add_argument("--list", action="store_true", help="one line per pending batch; what the dispatcher reads")
    args = ap.parse_args()

    every = batches(args.run, args.collection, args.step)
    pending = [batch for batch, done in every if not done]
    if args.list:
        print("\n".join(str(b.resolve()) for b in pending) if pending else "nothing pending")
        return
    print(f"{args.step}, {args.collection}: {len(pending)} of {len(every)} batch(es) pending")


if __name__ == "__main__":
    main()
