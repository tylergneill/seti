"""Check every Pandit ID in the master against this repo's Pandit extract.

Each Work ID must be a work in the extract, and each Author ID a person.
An ID that is neither was most likely deleted or merged in Pandit since it
was written; one of the wrong kind was mistyped or put in the wrong column.
Look such IDs up with scripts/lookup.py and correct the master by hand.

It first compares our copy of the extract with Pāṇḍitya's (../panditya),
when that repo is there: a newer export, a later pipeline run on the same
export, or a file that differs all mean the copy is behind, and
`make pandit-copy` brings it up to date.

Run this after every `make pandit-copy`, before the matchers: they assume
the IDs already in the master are real.

    python3 scripts/check.py

Exits 1 if the copy is behind or any ID fails, listing each ID with its
row in the master.
"""

import filecmp
import sys

from common import (AUTHOR_ID, NO_AUTHOR, OPEN, ROOT, WORK_ID, Master, Pandit, pandit_content_version,
                    pandit_data_version, pandit_extract, read_version, split_cell)

PANDITYA = ROOT.parent / "panditya"


def copy_problems():
    """Why our copy is behind Pāṇḍitya's, if it is; [] if current or Pāṇḍitya isn't there."""
    if not (PANDITYA / "VERSION").exists():
        print(f"No {PANDITYA}; not comparing the copy with Pāṇḍitya's.")
        return []
    ours = (pandit_content_version(), pandit_data_version())
    theirs = (read_version("pandit_content_version", PANDITYA / "VERSION"),
              read_version("data_version", PANDITYA / "VERSION"))
    if theirs[0] < ours[0]:
        print(f"Pāṇḍitya is on an older export ({theirs[0]}) than our copy ({ours[0]}); "
              "check out its newer branch to compare.")
        return []
    if theirs[0] > ours[0]:
        return [f"Pāṇḍitya has a newer export, {theirs[0]}; our copy is of {ours[0]}."]
    problems = []
    if theirs[1] != ours[1]:
        problems.append(f"Pāṇḍitya's pipeline last ran {theirs[1]}; our copy is from its run of {ours[1]}.")
    source = PANDITYA / "data" / pandit_extract().name
    if source.exists() and not filecmp.cmp(source, pandit_extract(), shallow=False):
        problems.append(f"{source.name} differs from Pāṇḍitya's.")
    return problems

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
    stale = copy_problems()
    for p in stale:
        print(f"  {p}")
    if stale:
        print("Our copy is behind; run make pandit-copy, then make check again.")
        sys.exit(1)

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
