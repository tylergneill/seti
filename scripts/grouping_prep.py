#!/usr/bin/env python3
"""Cut a collection into overlapping shards for the grouping readers.

Writes tmp/grouping/<run>/<code>/items.jsonl, one line per text-bearing
item with everything the Atlas publishes about it, and then cuts the
collection into shards of about --shard-size items, in catalogue order,
the Atlas's own sequence. So every item is read once. With --views 2 or 3
the collection is cut again, in further orders, and every item read again
beside different neighbours:

  catalogue   the Atlas's own sequence
  title       alphabetical by title, Devanāgarī and roman interleaved
  author      alphabetical by the author field; items without one are
              spread through at random

The orders are not evidence. They only decide which items a reader sees
together. On GRETIL three readings scored no better against SETI than one,
so one is the default. Shards go to
tmp/grouping/<run>/<code>/p1-<view>-NNN/items.jsonl, and each reader later
writes opinions.json beside its items.jsonl.

  grouping_prep.py --collection g --run 2026-10-13
  grouping_prep.py --collection j --run 2026-10-13 --views 3 --shard-size 150
"""

import argparse
import math
import random

from common import ROOT
from grouping_common import COLLECTIONS, load_items, run_dir, sort_key, write_json, write_jsonl

VIEWS = ["catalogue", "title", "author"]


def ordered(items, view, code):
    if view == "catalogue":
        return list(items)
    if view == "title":
        return sorted(items, key=lambda it: (sort_key(it.get("native_title") or it["title"]), it["item"]))
    # Author order. An item without an author says nothing about where it
    # belongs, so it is dropped in at random rather than gathered at one end.
    named = sorted((it for it in items if it.get("author")),
                   key=lambda it: (sort_key(it["author"]), it["item"]))
    rng = random.Random(f"{code}-author")
    for it in (it for it in items if not it.get("author")):
        named.insert(rng.randint(0, len(named)), it)
    return named


def cut(items, shard_size):
    """Shards of nearly equal size, about shard_size each, order kept."""
    count = max(1, math.ceil(len(items) / shard_size))
    bounds = [round(i * len(items) / count) for i in range(count + 1)]
    return [items[a:b] for a, b in zip(bounds, bounds[1:])]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", required=True, choices=sorted(COLLECTIONS))
    ap.add_argument("--run", required=True, help="name for this run; shared by every collection in it")
    ap.add_argument("--views", type=int, default=1, choices=[1, 2, 3],
                    help="readings per item: the first N of catalogue, title, author (default 1)")
    ap.add_argument("--shard-size", type=int, default=200, help="items per reader, about (default 200)")
    args = ap.parse_args()

    out = run_dir(args.run, args.collection)
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} already exists. Remove it, or name another run with --run.")
    items = load_items(args.collection)
    if not items:
        raise SystemExit(f"No text-bearing items for collection {args.collection}.")

    out.mkdir(parents=True)
    write_jsonl(out / "items.jsonl", items)
    views = VIEWS[:args.views]
    shards = 0
    for view in views:
        for n, shard in enumerate(cut(ordered(items, view, args.collection), args.shard_size), start=1):
            shard_dir = out / f"p1-{view}-{n:03d}"
            shard_dir.mkdir()
            write_jsonl(shard_dir / "items.jsonl", shard)
            shards += 1
    write_json(out / "run.json", {
        "run": args.run, "collection": args.collection, "name": COLLECTIONS[args.collection],
        "items": len(items), "views": views, "shard_size": args.shard_size, "shards": shards,
    })
    print(f"run {args.run}, {COLLECTIONS[args.collection]}: {len(items)} items, "
          f"{shards} shards in {len(views)} view(s) under {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
