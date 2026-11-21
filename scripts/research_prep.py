#!/usr/bin/env python3
"""Cut SETI rows into batches for the research sub-agents.

Writes tmp/research/<run>/batch-NNN/items.json, one batch per sub-agent,
and tmp/research/<run>/run.json recording what the run covers. Each
sub-agent later writes proposals.json beside its items.json.

  research_prep.py                          # every row with an open slot
  research_prep.py --limit 50               # the first 50 of them
  research_prep.py --offset 100 --limit 100  # the next 100: one reviewable chunk
  research_prep.py --scope all --collection SARIT

With --scope open, IDs already in a row are shown to the sub-agent as
context. With --scope all they are withheld, so that each identification
is an independent reading that can then be compared with the master.
"""

import argparse
import datetime
import json
import re
import unicodedata
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


def slug(text):
    """A file-name-safe form of a collection name: 'Vātāyana and Pramāṇa NLP'
    becomes 'vatayana-and-pramana-nlp'."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def default_run_name(collection, scope, first=None, last=None):
    """<date>-<HHMM>-<collection or 'all-collections'>-<scope>[-<first>-<last>],
    so that runs on the same day, or on different collections, do not collide,
    and a chunk's name says which rows it holds (counted from 1 among the rows
    the selection covers, e.g. -0101-0200)."""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    name = f"{stamp}-{slug(collection) if collection else 'all-collections'}-{scope}"
    if first is not None:
        name += f"-{first:04d}-{last:04d}"
    return name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--master", default=MASTER)
    ap.add_argument("--scope", choices=["open", "all"], default="open")
    ap.add_argument("--collection", help="only rows of this collection")
    ap.add_argument("--offset", type=int, default=0,
                    help="skip this many of the selected rows first (with --limit, cuts a run into chunks)")
    ap.add_argument("--limit", type=int, help="at most this many rows")
    ap.add_argument("--batch-size", type=int, default=10, help="rows per sub-agent (default 10)")
    ap.add_argument("--run", help="name for this run (default: <date>-<HHMM>-<collection>-<scope>)")
    args = ap.parse_args()

    master = Master(args.master)
    items = []
    for r in range(len(master.rows)):
        if args.collection and master.get(r, "Collection") != args.collection:
            continue
        item = item_for(master, r, args.scope)
        if item:
            items.append(item)

    # Rows are counted among those the selection covers (collection and scope),
    # not among all rows of the master, so that OFFSET=0,100,200... with
    # LIMIT=100 tiles a collection exactly.
    selected = len(items)
    end = args.offset + args.limit if args.limit else selected
    items = items[args.offset:end]
    chunked = bool(args.offset or args.limit)
    first, last = args.offset + 1, args.offset + len(items)

    run = args.run or default_run_name(args.collection, args.scope,
                                       *((first, last) if chunked and items else ()))
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
        "collection": args.collection, "first": first, "last": last, "of": selected,
    }, indent=1), encoding="utf-8")

    print(f"run {run}: rows {first}-{last} of {selected} selected, "
          f"in {len(batches)} batches under {run_dir.relative_to(ROOT)}")
    if last < selected:
        print(f"next chunk: OFFSET={last}" + (f" LIMIT={args.limit}" if args.limit else "")
              + f" (--offset {last} for the script)")


if __name__ == "__main__":
    main()
