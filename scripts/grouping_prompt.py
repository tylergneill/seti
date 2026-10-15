#!/usr/bin/env python3
"""Print the full sub-agent prompt for one step of the grouping job.

The step's prompt file from agents/grouping/, with this checkout's paths
and the shared definitions (agents/grouping/definitions.md, the spec's
"What a title and a person are", word for word) filled in, followed by the
collection's notes from agents/grouping/notes/<code>.md under "Notes on
this collection" when there are any. The dispatcher hands this output to
every sub-agent verbatim, so the prompt is assembled by code and not by an
agent's reading of instructions.

  grouping_prompt.py --step read --collection g
"""

import argparse
import sys

from common import ROOT
from grouping_common import AGENTS, ALL, COLLECTIONS, STEPS


def build_prompt(step, code):
    text = (AGENTS / STEPS[step]["prompt"]).read_text(encoding="utf-8")
    text = (text.replace("{definitions}", (AGENTS / "definitions.md").read_text(encoding="utf-8").strip())
                .replace("{python}", sys.executable)
                .replace("{lookup}", str(ROOT / "scripts" / "lookup.py"))
                .replace("{validate}", str(ROOT / "scripts" / "grouping_validate.py")))
    codes = sorted(COLLECTIONS) if code == ALL else [code]
    for c in codes:
        notes = AGENTS / "notes" / f"{c}.md"
        if notes.exists():
            heading = "Notes on this collection" if code != ALL else "Notes on the collection"
            text = (text.rstrip() + f"\n\n## {heading}: {COLLECTIONS[c]}\n\n"
                    + notes.read_text(encoding="utf-8").strip() + "\n")
    return text.rstrip() + "\n\nYour batch directory is:\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", required=True, choices=sorted(STEPS))
    ap.add_argument("--collection", required=True, choices=sorted(COLLECTIONS) + [ALL])
    args = ap.parse_args()
    sys.stdout.write(build_prompt(args.step, args.collection))


if __name__ == "__main__":
    main()
