#!/usr/bin/env python3
"""Our own IDs for the grouping registry: five lowercase letters, drawn at random.

  persons  p + four letters (pqmve)
  titles   t + four letters (tkzab)

A code is drawn at random rather than built from the name: a name-based
code reads as meaning, collides, and goes stale when the name is
corrected, while an ID must never change. Every code ever minted is kept
in data/grouping/ids.csv with its kind, name and date, and none is reused.
When two entries turn out to be one, the older ID survives and the other
is marked merged_into there, so that links into the registry never break
silently.

Pass 3 mints through assign(): each linked entity of a run keeps the ID it
was given the first time, by its members (the collection registry keys it
unites), recorded in tmp/grouping/<run>/all/ids.json. Writing the registry
again therefore mints nothing new unless an entity is new.

  grouping_ids.py              how many codes are minted, and of what kind
"""

import csv
import datetime
import random
import string

from grouping_common import DATA, read_json, write_json

IDS = DATA / "ids.csv"
COLUMNS = ["ID", "Kind", "Name", "Minted", "Merged Into"]
PREFIX = {"person": "p", "title": "t"}
_draw = random.SystemRandom()


def load():
    if not IDS.exists():
        return []
    with open(IDS, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save(rows):
    IDS.parent.mkdir(parents=True, exist_ok=True)
    with open(IDS, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def assign(kind, entities, memory):
    """An ID for each entity, a dict with 'key', 'name' and 'members'.

    Returns {entity key: ID}. `memory` is the run's ids.json: an entity whose
    members were given an ID before keeps it; any other is minted a new code,
    never one in ids.csv."""
    rows = load()
    taken = {r["ID"] for r in rows}
    known = read_json(memory) if memory.exists() else {}
    today = datetime.date.today().isoformat()
    out, minted = {}, 0
    for e in entities:
        members = ",".join(sorted(e["members"]))
        code = known.get(members)
        if code is None:
            while code is None or code in taken:
                code = PREFIX[kind] + "".join(_draw.choice(string.ascii_lowercase) for _ in range(4))
            taken.add(code)
            known[members] = code
            rows.append({"ID": code, "Kind": kind, "Name": e["name"], "Minted": today, "Merged Into": ""})
            minted += 1
        out[e["key"]] = code
    if minted:
        save(rows)
        write_json(memory, known)
    return out, minted


def main():
    rows = load()
    kinds = {}
    for r in rows:
        kinds[r["Kind"]] = kinds.get(r["Kind"], 0) + 1
    merged = sum(1 for r in rows if r["Merged Into"])
    print(f"{len(rows)} code(s) minted in {IDS}: "
          + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())) + (f"; {merged} merged" if merged else ""))


if __name__ == "__main__":
    main()
