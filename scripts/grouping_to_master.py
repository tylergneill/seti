#!/usr/bin/env python3
"""Carry the grouping's Pandit grounding into the master's GRETIL rows. One-off.

The grouping registry (data/grouping/) and its grounding in Pandit
(data/grouping/grounding/, made against the 2025-11-07 Pandit export) were
built to help the matchers, not as a pipeline of their own. This script
hands their results to the master once, the way the matchers do: a
confident ID fills an open slot, and everything else goes to the notes.

Only GRETIL is in both the registry and the master. A master row is joined
to its registry item through the GRETIL Atlas's list of each item's files.
A work slot is proposed for only when the row has one work slot and its
item one work; an author slot, when the row has one author slot and its
item one author.

For a work, the ID is, in order: the research agents' finding at 0.9 or
above, the name matcher's confident match, or a match through its
authors' works, each with its own confidence. For an author, the name
matcher's confident match. An ID the registry's agents only noted as
obvious (a hint) carries no confidence, and goes to the notes.

  grouping_to_master.py [--dry-run] [--threshold 0.9]
"""

import argparse
import csv
import json
import re

from atlas_works import GRETIL_TREE
from common import (AUTHOR_ID, DEFAULT_THRESHOLD, NO_AUTHOR, OPEN, PANDIT_DATA, WORK_ID, Master, Pandit,
                    apply_proposals, print_summary, proposal, split_cell)
from grouping_common import DATA

GROUNDING = DATA / "grounding"
PANDIT_USED = PANDIT_DATA / "archive" / "2025-11-07-extracted-entities-cleaned.csv"
HINT_CONFIDENCE = 0.0


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def work_candidates(title, grounded, research, author_works):
    """[(Pandit ID, confidence, basis)] for one registry title."""
    out = []
    r = research.get(title)
    if r and r["Pandit ID"]:
        out.append((r["Pandit ID"], float(r["Confidence"]), f"research agent ({r['Batch']}): {r['Reasoning']}"))
    g = grounded[title]
    if g["Status"] == "grounded":
        out.append((g["Pandit ID"], float(g["Confidence"]), f"name matcher: {g['Basis']}"))
    a = author_works.get(title)
    if a:
        out.append((a["Pandit ID"], float(a["Confidence"]), f"through its authors' works: {a['Basis']}"))
    if g["Agent Hint"]:
        out.append((g["Agent Hint"], HINT_CONFIDENCE, "hint only: the registry's agents noted it as obvious; no confidence"))
    return out


def person_candidates(person, grounded):
    g = grounded.get(person)
    out = []
    if g and g["Status"] == "grounded":
        out.append((g["Pandit ID"], float(g["Confidence"]), f"name matcher: {g['Basis']}"))
    if g and g["Agent Hint"]:
        out.append((g["Agent Hint"], HINT_CONFIDENCE, "hint only: the registry's agents noted it as obvious; no confidence"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    titles = {r["ID"]: r for r in read(GROUNDING / "titles.csv")}
    research = {r["Title ID"]: r for r in read(GROUNDING / "research-titles.csv")}
    author_works = {r["Title ID"]: r for r in read(GROUNDING / "author-works.csv") if r["Status"] == "grounded"}
    persons = {r["ID"]: r for r in read(GROUNDING / "persons.csv")}
    items = {r["Item ID"]: r for r in read(DATA / "master.csv") if r["Collection"] == "GRETIL"}

    tree = json.loads(GRETIL_TREE.read_text(encoding="utf-8"))
    files_of = {f: w["files"] for w in tree["works"] for f in w["files"]}
    item_of_file = {f: item for item in items for f in files_of.get(item, [item])}

    master = Master()
    pandit = Pandit(PANDIT_USED)
    proposals, joined = [], 0
    for r in range(len(master.rows)):
        if master.get(r, "Collection") != "GRETIL":
            continue
        path = re.sub(r"^https?://[^/]+/gretil/", "", master.get(r, "Link 1 (main)").strip())
        item = items.get(item_of_file.get(path))
        if not item:
            continue
        joined += 1

        work_slots, _ = split_cell(master.get(r, WORK_ID))
        item_titles = [t for t in item["Title IDs"].split(", ") if t]
        if len(work_slots) == 1 and len(item_titles) == 1:
            t = item_titles[0]
            for pid, conf, basis in work_candidates(t, titles, research, author_works):
                proposals.append(proposal(r, WORK_ID, 0, pid, conf, f"registry title {t} '{titles[t]['Name']}'; {basis}",
                                          pandit.name_of(pid)))

        author_slots, _ = split_cell(master.get(r, AUTHOR_ID))
        item_authors = [p for p, role in zip(item["Person IDs"].split(", "), item["Person Roles"].split(", "))
                        if p and role == "author"]
        if len(author_slots) == 1 and author_slots[0].strip() != NO_AUTHOR and len(item_authors) == 1:
            p = item_authors[0]
            for pid, conf, basis in person_candidates(p, persons):
                proposals.append(proposal(r, AUTHOR_ID, 0, pid, conf, f"registry person {p}; {basis}",
                                          pandit.name_of(pid)))

    print(f"GRETIL rows joined to the registry: {joined}; proposals: {len(proposals)}")
    counts, paths = apply_proposals(master, proposals, "grouping", threshold=args.threshold, dry_run=args.dry_run)
    print_summary(counts, paths, args.threshold)


if __name__ == "__main__":
    main()
