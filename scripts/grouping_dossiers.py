#!/usr/bin/env python3
"""Gather pass 1's shard entities into dossiers, and cut them into windows.

A dossier is a candidate for one person or one title: the shard entities
that the readers' opinions tie together.

  persons   persons given the identical canonical name; and, with several
            readings, the readings of the same name, as written, on the
            same item
  titles    titles given the identical canonical name; and, with several
            readings, the titles of an item to which every reading gave
            exactly one

A dossier is a connected component of these ties. It holds every member's
full record and every item it covers, with the item's metadata, so the
consolidator reads the evidence and not just the conclusions. Ties only
gather candidates: a wrong reading can chain two real entities into one
dossier, and the consolidator splits them.

Dossiers are sorted by their most common canonical name and cut into
windows of about --window that overlap by --overlap, written to
tmp/grouping/<run>/<code>/p2a-NNN/dossiers.json for persons and p2b-NNN
for titles. A dossier too large for a window gets its own.

Titles are told apart partly by their authors, so --kind titles needs the
persons consolidated first (grouping_apply.py --step persons).

  grouping_dossiers.py --run 2026-10-13 --collection g --kind persons
  grouping_dossiers.py --run 2026-10-13 --collection g --kind titles
"""

import argparse
import collections
import json

from common import ROOT, norm
from grouping_common import (COLLECTIONS, Groups, item_metadata, load_opinions, member_id, read_json,
                             read_jsonl, run_dir, sort_key, windows, write_json)

PREFIX = {"persons": "p2a", "titles": "p2b"}
# A dossier with more members or item readings than this is read on its own.
LARGE_MEMBERS = 60
LARGE_READINGS = 200


def person_dossiers(opinions):
    groups, members, readings = Groups(), {}, collections.defaultdict(list)
    by_name, by_reading = collections.defaultdict(list), collections.defaultdict(list)
    for shard, op in opinions.items():
        authored = collections.defaultdict(list)
        for t in op["titles"]:
            for a in t.get("authors", []):
                authored[a.get("person")].append(t["name"])
        for p in op["persons"]:
            mid = member_id(shard, p["key"])
            members[mid] = {"member": mid, **{k: v for k, v in p.items() if k != "key"},
                            "author_of": authored.get(p["key"], [])}
            groups.find(mid)
            by_name[p["name"]].append(mid)
        for entry in op["items"]:
            for p in entry.get("persons", []):
                mid = member_id(shard, p["person"])
                if mid not in members:
                    continue
                by_reading[(entry["item"], norm(p.get("as_written", "")))].append(mid)
                # The item's note is about the item as a whole; the title
                # consolidator sees it, and a person's own context is on the member.
                readings[mid].append({"item": entry["item"], "member": mid, "as_written": p.get("as_written", ""),
                                      "role": p.get("role", ""), "attribution": p.get("attribution", "")})
    for tied in list(by_name.values()) + list(by_reading.values()):
        for other in tied[1:]:
            groups.union(tied[0], other)
    return groups, members, readings


def title_dossiers(opinions, member_of):
    groups, members, readings = Groups(), {}, collections.defaultdict(list)
    by_name, by_item = collections.defaultdict(list), collections.defaultdict(list)
    persons = {p["key"]: p for p in member_of["entities"]}
    for shard, op in opinions.items():
        for t in op["titles"]:
            mid = member_id(shard, t["key"])
            authors = []
            for a in t.get("authors", []):
                key = member_of["member_of"].get(member_id(shard, a.get("person")))
                if key:
                    authors.append({"person": key, "name": persons[key]["name"],
                                    "attribution": a.get("attribution", "")})
            members[mid] = {"member": mid, **{k: v for k, v in t.items() if k not in ("key", "authors")},
                            "authors": authors}
            groups.find(mid)
            by_name[t["name"]].append(mid)
        for entry in op["items"]:
            mine = [member_id(shard, t["title"]) for t in entry.get("titles", [])
                    if member_id(shard, t.get("title")) in members]
            # Only an item with one title says, across readings, which title
            # answers which.
            by_item[entry["item"]].append(mine[0] if len(mine) == 1 else None)
            for t in entry.get("titles", []):
                mid = member_id(shard, t["title"])
                if mid in members:
                    readings[mid].append({"item": entry["item"], "member": mid,
                                          "part_label": t.get("part_label", ""), "note": entry.get("note", "")})
    for tied in list(by_name.values()) + [t for t in by_item.values() if None not in t]:
        for other in tied[1:]:
            groups.union(tied[0], other)
    return groups, members, readings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--collection", required=True, choices=sorted(COLLECTIONS))
    ap.add_argument("--kind", required=True, choices=sorted(PREFIX))
    ap.add_argument("--window", type=int, default=100, help="dossiers per consolidator, about (default 100)")
    ap.add_argument("--overlap", type=int, default=20, help="dossiers shared by neighbouring windows (default 20)")
    args = ap.parse_args()

    base = run_dir(args.run, args.collection)
    prefix = PREFIX[args.kind]
    if any(base.glob(f"{prefix}-*")):
        raise SystemExit(f"{base.relative_to(ROOT)} already has {prefix} windows. Remove them to cut again.")
    opinions = load_opinions(args.run, args.collection)
    if not opinions:
        raise SystemExit("No opinions to gather; run pass 1 first.")
    if args.kind == "persons":
        groups, members, readings = person_dossiers(opinions)
    else:
        registry = base / "persons.json"
        if not registry.exists():
            raise SystemExit("Titles need the persons consolidated first: grouping_apply.py --step persons.")
        groups, members, readings = title_dossiers(opinions, read_json(registry))

    # The edition's publisher and page count tell nothing about who or what
    # an entity is; leaving them out keeps the windows small.
    metadata = {it["item"]: {k: v for k, v in item_metadata(it).items() if k not in ("publisher", "pages")}
                for it in read_jsonl(base / "items.jsonl")}
    dossiers = []
    for component in groups.components():
        names = collections.Counter(members[m]["name"] for m in component)
        by_item = collections.defaultdict(list)
        for m in component:
            for r in readings[m]:
                by_item[r["item"]].append({k: v for k, v in r.items() if k != "item" and v != ""})
        dossiers.append({
            "name": names.most_common(1)[0][0],
            "members": [members[m] for m in component],
            "items": [{**metadata[item], "readings": rs} for item, rs in sorted(by_item.items())],
        })
    dossiers.sort(key=lambda d: (sort_key(d["name"]), d["name"]))
    for n, d in enumerate(dossiers, start=1):
        d["dossier"] = f"d{n:04d}"

    def is_large(d):
        return len(d["members"]) > LARGE_MEMBERS or sum(len(i["readings"]) for i in d["items"]) > LARGE_READINGS

    cut = windows(dossiers, args.window, args.overlap, is_large)
    for n, window in enumerate(cut, start=1):
        batch = base / f"{prefix}-{n:03d}"
        batch.mkdir()
        # Compact, one dossier per line: the window is read by an agent, and
        # indentation is only cost.
        head = json.dumps({"kind": args.kind, "collection": args.collection}, ensure_ascii=False)[:-1]
        lines = [json.dumps({"dossier": d["dossier"], "name": d["name"], "members": d["members"],
                             "items": d["items"]}, ensure_ascii=False, separators=(",", ":")) for d in window]
        (batch / "dossiers.json").write_text(head + ',"dossiers":[\n' + ",\n".join(lines) + "\n]}\n",
                                             encoding="utf-8")
    # How the windows were cut, so that grouping_restore.py can cut them again.
    record = read_json(base / "run.json") if (base / "run.json").exists() else {}
    record.setdefault("windows", {})[args.kind] = {"window": args.window, "overlap": args.overlap}
    write_json(base / "run.json", record)
    print(f"{args.kind}, {COLLECTIONS[args.collection]}: {len(members)} shard entities from {len(opinions)} "
          f"shard(s) in {len(dossiers)} dossiers, {len(cut)} window(s) under {base.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
