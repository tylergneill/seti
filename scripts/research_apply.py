#!/usr/bin/env python3
"""Apply a research run: gather the sub-agents' proposals into the master.

Reads every batch's proposals.json for the run. Identifications at or
above the threshold are written into the master in place; the rest, and
every 'not in Pandit' finding, go to reports/<date>-research-notes.csv.
A run prepared with --scope all may replace IDs already in the master; a
run prepared with --scope open only fills '...' slots.

An ID a sub-agent gives that is not a Pandit work or person of the right
kind is never written. It is reported instead.

  research_apply.py --run 2026-10-09-open [--threshold 0.9] [--dry-run]
"""

import argparse
import json

from common import (AUTHOR_ID, DEFAULT_THRESHOLD, ROOT, WORK_ID, Master, Pandit, apply_proposals, note_row,
                    print_summary, proposal, split_cell)

RESEARCH = ROOT / "tmp" / "research"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--pandit", help="cleaned Pandit extract (default: the newest in ../panditya/data)")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    args = ap.parse_args()

    run_dir = RESEARCH / args.run
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    master = Master(meta["master"])
    pandit = Pandit(args.pandit)

    proposals, extra, problems = [], [], []
    done = missing = 0
    for batch in sorted(run_dir.glob("batch-*")):
        items = {item["row"]: item for item in json.loads((batch / "items.json").read_text(encoding="utf-8"))}
        try:
            found = json.loads((batch / "proposals.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            missing += 1
            continue
        done += 1
        for f in found:
            try:
                r, field, position = int(f["row"]), f["field"], int(f["slot"]) - 1
                confidence = float(f.get("confidence") or 0)
                reasoning = str(f.get("reasoning", "")).strip()
            except (KeyError, TypeError, ValueError):
                problems.append(f"{batch.name}: unreadable entry {f!r}")
                continue
            if r not in items or field not in (WORK_ID, AUTHOR_ID):
                problems.append(f"{batch.name}: entry for a row or field it was not given: {f!r}")
                continue
            if master.key(r) != items[r]["key"]:
                problems.append(f"{batch.name}: master row {master.sheet_row(r)} has changed since the run was prepared; skipped")
                continue
            slots = items[r]["work_slots" if field == WORK_ID else "author_slots"]
            if not 0 <= position < len(slots) or slots[position] != "?":
                problems.append(f"{batch.name}: row {master.sheet_row(r)} {field} slot {position + 1} was not asked for")
                continue
            parts, _ = split_cell(master.get(r, field))
            current = parts[position].strip() if position < len(parts) else ""

            suggested = f.get("id")
            if suggested in (None, "", "null"):
                extra.append(note_row(master, r, field, position, "not found in Pandit", reasoning, current))
                continue
            suggested = str(suggested).strip()
            known = pandit.works if field == WORK_ID else pandit.persons
            if suggested not in known:
                extra.append(note_row(master, r, field, position,
                                      f"sub-agent gave {suggested}, which is not a Pandit {'work' if field == WORK_ID else 'person'}",
                                      reasoning, current))
                continue
            proposals.append(proposal(r, field, position, suggested, confidence, reasoning, pandit.name_of(suggested)))

    print(f"run {args.run} ({meta['scope']}): {done} batches read" + (f", {missing} still pending" if missing else ""))
    counts, paths = apply_proposals(master, proposals, "research", args.threshold,
                                    overwrite=meta["scope"] == "all", dry_run=args.dry_run, extra_notes=extra)
    print_summary(counts, paths, args.threshold)
    not_found = sum(1 for e in extra if e["Status"] == "not found in Pandit")
    print(f"{not_found} slots reported as not in Pandit; {len(extra) - not_found} invalid IDs set aside")
    for line in problems:
        print("  problem:", line)
    if args.dry_run:
        print("dry run: nothing written")


if __name__ == "__main__":
    main()
