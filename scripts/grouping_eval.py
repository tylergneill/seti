#!/usr/bin/env python3
"""Compare GRETIL's grouping with SETI's hand-made Pandit IDs.

SETI ties most GRETIL files to Pandit works by hand, which makes GRETIL
the one collection where the grouping can be checked against an
independent answer. The grouping's readers and consolidators never saw
SETI; this script is where the two meet.

It reads data/grouping/collections/g/master.csv (grouping_apply.py --step
registry) and data/seti-master.csv, and joins them on GRETIL's file paths.
SETI gives an item one work: the row's last identified ID, so a parvan
counts as the Mahābhārata. The grouping gives an item every work it
contains. So for each SETI work the script finds the title that answers
it, the one most of the work's items carry (of two carried equally, the
one fewer other items carry), and an item agrees when it carries the
answer to its SETI work. It reports:

  - how many items agree;
  - SETI works the grouping splits: some item lacks the work's answer;
  - SETI works the grouping joins: two works with the same answer;
  - the number of distinct works for those items: SETI's, the titles that
    answer them, and the mechanical first pass's folded titles
    (scripts/atlas_works.py);
  - every disagreement, written to reports/<date>-grouping-eval.csv for
    reading. Some will be SETI's or Pandit's and not the grouping's.

There is no pass mark.

  grouping_eval.py
"""

import argparse
import collections
import csv
import datetime
import json
import re

from atlas_works import GRETIL_TREE, seti_rows, seti_work_id, title_key, to_iast
from common import REPORTS, ROOT, Pandit
from grouping_common import DATA


def seti_truth(item_ids):
    """SETI's work-level Pandit ID for each GRETIL item it identifies. The
    search index names one file per item; the Atlas's tree lists them all,
    and SETI may link any of them."""
    tree = json.loads(GRETIL_TREE.read_text(encoding="utf-8"))
    files_of = {f: w["files"] for w in tree["works"] for f in w["files"]}
    by_path = {}
    for r in seti_rows():
        if r["Collection"] == "GRETIL":
            by_path[re.sub(r"^https?://[^/]+/gretil/", "", r["Link 1 (main)"].strip())] = r
    truth = {}
    for item in item_ids:
        for f in files_of.get(item, [item]):
            if f in by_path:
                wid = seti_work_id(by_path[f])
                if wid:
                    truth[item] = wid
                break
    return truth


def compare(titles_of, truth):
    """The answer to each SETI work, and what follows from it.

    titles_of: item -> set of title IDs. truth: item -> SETI work ID.
    Returns (answer by work, items that agree, split works, joined titles).
    """
    carried = collections.Counter(t for item in truth for t in titles_of[item])
    items_of = collections.defaultdict(list)
    for item, wid in truth.items():
        items_of[wid].append(item)
    answer = {}
    for wid, items in items_of.items():
        within = collections.Counter(t for i in items for t in titles_of[i])
        if within:
            answer[wid] = min(within, key=lambda t: (-within[t], carried[t], t))
    agree = {i for i, wid in truth.items() if answer.get(wid) in titles_of[i]}
    split = {wid for wid, items in items_of.items() if any(i not in agree for i in items)}
    works_of = collections.defaultdict(set)
    for wid, t in answer.items():
        works_of[t].add(wid)
    joined = {t: ws for t, ws in works_of.items() if len(ws) > 1}
    return answer, agree, split, joined


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", default=DATA / "collections" / "g" / "master.csv")
    args = ap.parse_args()

    with open(args.registry, encoding="utf-8", newline="") as f:
        rows = {r["Item ID"]: r for r in csv.DictReader(f)}
    truth = seti_truth(rows)
    pandit = Pandit()

    titles_of, names = {}, {}
    for item in truth:
        ids = [t.strip() for t in rows[item]["Title IDs"].split(",") if t.strip()]
        names.update(zip(ids, [n.strip() for n in rows[item]["Title Names"].split(",")]))
        titles_of[item] = set(ids)
    answer, agree, split, joined = compare(titles_of, truth)
    works = set(truth.values())
    folded = {title_key(to_iast(rows[i]["Text Name"]), True) or i for i in truth}

    print(f"GRETIL items in the registry: {len(rows)}; with a SETI work ID: {len(truth)}")
    print(f"distinct works among them: SETI {len(works)}, titles that answer them {len(set(answer.values()))}, "
          f"mechanical folded titles {len(folded)}")
    print(f"items carrying the title that answers their SETI work: {len(agree)} of {len(truth)} "
          f"({len(agree) / len(truth):.1%})")
    print(f"SETI works the grouping splits: {len(split)}; "
          f"SETI works it joins: {sum(len(ws) for ws in joined.values())} under {len(joined)} title(s)")

    out = []

    def line(kind, cluster, item):
        wid = truth[item]
        out.append([kind, cluster, item, rows[item]["Text Name"], rows[item]["Author Name"], wid,
                    pandit.name_of(wid), names.get(answer.get(wid), ""), "yes" if item in agree else "no",
                    rows[item]["Title IDs"], rows[item]["Title Names"], rows[item]["Confidence"], rows[item]["Note"]])

    for wid in sorted(split, key=lambda w: pandit.name_of(w)):
        for item in sorted(i for i in truth if truth[i] == wid):
            line("split", f"SETI {wid} {pandit.name_of(wid)}", item)
    for t, ws in sorted(joined.items(), key=lambda kv: names.get(kv[0], "")):
        for item in sorted((i for i in truth if truth[i] in ws), key=lambda i: (truth[i], i)):
            line("joined", f"grouping {t} {names.get(t, '')}", item)
    path = REPORTS / f"{datetime.date.today().isoformat()}-grouping-eval.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["Disagreement", "Cluster", "Item ID", "Text Name", "Author Name", "SETI Work ID",
                         "SETI Work Name", "Answering Title", "Item Carries It", "Title IDs", "Title Names",
                         "Confidence", "Note"])
        writer.writerows(out)
    print(f"every disagreement: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
