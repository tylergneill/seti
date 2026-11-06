"""Check every Pandit ID in the master against this repo's Pandit extract.

Each Work ID must be a work in the extract, and each Author ID a person.
An ID that is neither was most likely deleted or merged in Pandit since it
was written; one of the wrong kind was mistyped or put in the wrong column.
Look such IDs up with scripts/lookup.py and correct the master by hand.

Run this after every `make pandit-copy`, before the matchers: they assume
the IDs already in the master are real.

    python3 scripts/check.py

Exits 1 if any ID fails, listing each with its row in the master.
"""

import sys

from common import AUTHOR_ID, NO_AUTHOR, OPEN, WORK_ID, Master, Pandit, split_cell

EXPECTED = {WORK_ID: "works", AUTHOR_ID: "persons"}


def find_problems(master, pandit):
    problems, checked = [], 0
    for r in range(len(master.rows)):
        for field, kind in EXPECTED.items():
            parts, _ = split_cell(master.get(r, field))
            for eid in (p.strip() for p in parts):
                if eid in ("", OPEN, NO_AUTHOR):
                    continue
                checked += 1
                if eid in getattr(pandit, kind):
                    continue
                other = "persons" if kind == "works" else "works"
                found = f"a {other[:-1]}, not a {kind[:-1]}" if eid in getattr(pandit, other) else "not in Pandit"
                problems.append((master.line(r), field, eid, found, master.get(r, "Collection"), master.get(r, "Text Name")))
    return problems, checked


def main():
    master, pandit = Master(), Pandit()
    problems, checked = find_problems(master, pandit)
    print(f"Checked {checked} IDs in {master.path.name} against {pandit.path.name}.")
    for line, field, eid, found, collection, name in problems:
        print(f"  line {line}: {field} {eid} is {found} ({collection}: {name})")
    if problems:
        print(f"{len(problems)} problem(s).")
        sys.exit(1)
    print("All IDs found.")


if __name__ == "__main__":
    main()
