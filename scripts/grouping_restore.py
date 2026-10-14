#!/usr/bin/env python3
"""Rebuild a collection's run under tmp/ from what grouping_keep.py kept.

Takes data/grouping/runs/<run>/<code>/ (the Atlas's items on the day, how
the run was cut, and what the sub-agents wrote) and replays every
mechanical step around it: the shards, the dossiers and their windows,
the united persons and titles, the settled items and the registry. No
agent runs. The result is the run as it stood, ready for a later step to
be run again or differently.

  grouping_restore.py --run 2026-10-13 --collection g
  grouping_restore.py --run 2026-10-13 --collection g --to 2026-10-13-again
"""

import argparse
import shutil
import subprocess
import sys

from common import ROOT
from grouping_common import COLLECTIONS, read_json, read_jsonl, run_dir, write_jsonl
from grouping_keep import RUNS

SCRIPTS = ROOT / "scripts"


def script(name, run, code, *more):
    subprocess.run([sys.executable, str(SCRIPTS / name), "--run", run, "--collection", code, *more], check=True)


def copy_outputs(kept, base, pattern, name):
    """Put the sub-agents' files back into the batch directories just cut."""
    for batch in sorted(kept.glob(pattern)):
        if (batch / name).exists() and (base / batch.name).is_dir():
            shutil.copy2(batch / name, base / batch.name / name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--collection", required=True, choices=sorted(COLLECTIONS))
    ap.add_argument("--to", help="rebuild under this run name instead (default: the same)")
    args = ap.parse_args()

    kept = RUNS / args.run / args.collection
    if not kept.is_dir():
        raise SystemExit(f"Nothing kept at {kept.relative_to(ROOT)}.")
    run, code = args.to or args.run, args.collection
    base = run_dir(run, code)
    if base.exists():
        raise SystemExit(f"{base.relative_to(ROOT)} already exists. Remove it, or rebuild elsewhere with --to.")
    base.mkdir(parents=True)
    shutil.copy2(kept / "items.jsonl", base / "items.jsonl")
    shutil.copy2(kept / "run.json", base / "run.json")
    cut = read_json(kept / "run.json").get("windows", {})

    # Pass 1: a shard is the items its reader wrote about, in their order.
    items = {it["item"]: it for it in read_jsonl(kept / "items.jsonl")}
    for batch in sorted(kept.glob("p1-*")):
        (base / batch.name).mkdir()
        shutil.copy2(batch / "opinions.json", base / batch.name / "opinions.json")
        read = [e["item"] for e in read_json(batch / "opinions.json")["items"]]
        write_jsonl(base / batch.name / "items.jsonl", [items[i] for i in read if i in items])

    # Pass 2: cut as the run was cut, put the decisions back, apply.
    for kind, prefix in (("persons", "p2a"), ("titles", "p2b")):
        if not any(kept.glob(f"{prefix}-*")):
            print(f"no {kind} decisions kept; stopping after the step before")
            return
        how = cut.get(kind, {})
        script("grouping_dossiers.py", run, code, "--kind", kind,
               *(["--window", str(how["window"]), "--overlap", str(how["overlap"])] if how else []))
        copy_outputs(kept, base, f"{prefix}-*", "consolidated.json")
        script("grouping_apply.py", run, code, "--step", kind)
    script("grouping_apply.py", run, code, "--step", "items")
    copy_outputs(kept, base, "p2c-*", "decisions.json")
    script("grouping_apply.py", run, code, "--step", "registry")


if __name__ == "__main__":
    main()
