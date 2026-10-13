#!/usr/bin/env python3
"""Cut SETI rows into batches for the research sub-agents.

Writes tmp/research/<run>/batch-NNN/items.json, one batch per sub-agent,
and tmp/research/<run>/run.json recording what the run covers. Each
sub-agent later writes proposals.json beside its items.json.

  research_prep.py                          # every row with an open slot
  research_prep.py --limit 50               # the first 50 of them
  research_prep.py --scope all --collection SARIT

With --scope open, IDs already in a row are shown to the sub-agent as
context. With --scope all they are withheld, so that each identification
is an independent reading that can then be compared with the master.
"""

import argparse
import datetime
import json
from pathlib import Path

from common import AUTHOR_ID, MASTER, NO_AUTHOR, OPEN, ROOT, WORK_ID, Master, split_cell

RESEARCH = ROOT / "tmp" / "research"
LINKS = ["Link 1 (main)", "Link 2 (underlying)", "Link 3 (extract)"]


def wanted_slots(parts, scope):
    if scope == "all":
        return [i for i, p in enumerate(parts) if p.strip() not in ("", NO_AUTHOR)]
    return [i for i, p in enumerate(parts) if p.strip() == OPEN]


def item_for(master, r, scope):
    work_parts, _ = split_cell(master.get(r, WORK_ID))
    author_parts, _ = split_cell(master.get(r, AUTHOR_ID))
    want_work = wanted_slots(work_parts, scope)
    want_author = wanted_slots(author_parts, scope)
    if not want_work and not want_author:
        return None

    def shown(parts, want):
        # What the sub-agent sees in each slot: '?' where it is asked, the
        # current value where that is context, nothing more.
        return ["?" if i in want else (p.strip() if scope == "open" or p.strip() == NO_AUTHOR else "(withheld)")
                for i, p in enumerate(parts)]

    return {
        "row": r,
        "key": master.key(r),
        "collection": master.get(r, "Collection"),
        "text_name": master.get(r, "Text Name"),
        "alternative_text_names": master.get(r, "Alternative Text Names"),
        "author_name": master.get(r, "Author Name"),
        "alternative_author_names": master.get(r, "Alternative Author Names"),
        "links": [master.get(r, c) for c in LINKS if master.get(r, c)],
        "work_slots": shown(work_parts, want_work),
        "author_slots": shown(author_parts, want_author),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--master", default=MASTER)
    ap.add_argument("--scope", choices=["open", "all"], default="open")
    ap.add_argument("--collection", help="only rows of this collection")
    ap.add_argument("--limit", type=int, help="at most this many rows")
    ap.add_argument("--batch-size", type=int, default=10, help="rows per sub-agent (default 10)")
    ap.add_argument("--run", help="name for this run (default: <date>-<scope>)")
    args = ap.parse_args()

    master = Master(args.master)
    items = []
    for r in range(len(master.rows)):
        if args.collection and master.get(r, "Collection") != args.collection:
            continue
        item = item_for(master, r, args.scope)
        if item:
            items.append(item)
        if args.limit and len(items) >= args.limit:
            break

    run = args.run or f"{datetime.date.today().isoformat()}-{args.scope}"
    run_dir = RESEARCH / run
    if run_dir.exists():
        raise SystemExit(f"{run_dir.relative_to(ROOT)} already exists. Finish it with research_apply.py, "
                         "remove it, or name another with --run.")
    if not items:
        raise SystemExit("No rows to research.")

    batches = [items[i:i + args.batch_size] for i in range(0, len(items), args.batch_size)]
    for n, batch in enumerate(batches, start=1):
        batch_dir = run_dir / f"batch-{n:03d}"
        batch_dir.mkdir(parents=True)
        (batch_dir / "items.json").write_text(json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps({
        "run": run, "scope": args.scope, "master": str(Path(args.master).resolve()),
        "rows": len(items), "batches": len(batches),
    }, indent=1), encoding="utf-8")

    print(f"run {run}: {len(items)} rows in {len(batches)} batches under {run_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
