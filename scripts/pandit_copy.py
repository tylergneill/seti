"""Bring in a new copy of Pāṇḍitya's cleaned Pandit extract.

Pāṇḍitya exports Pandit and cleans it; this repo works against a dated copy
of the result, so that every match and check is tied to a known snapshot.
This copies ../panditya/data/<date>-extracted-entities-cleaned.csv into
data/pandit/, removes the copy it replaces (git keeps it), and puts the date
in VERSION.

    python3 scripts/pandit_copy.py 2026-10-31

Then run scripts/check.py.
"""

import argparse
import re
import shutil

from common import PANDIT_DATA, ROOT, VERSION

SOURCE = ROOT.parent / "panditya" / "data"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("date", help="the date of the Pandit export, as in Pāṇḍitya's filenames (YYYY-MM-DD)")
    args = ap.parse_args()

    name = f"{args.date}-extracted-entities-cleaned.csv"
    source = SOURCE / name
    if not source.exists():
        raise SystemExit(f"No {name} in {SOURCE}. Is Pāṇḍitya on the branch that has it?")

    PANDIT_DATA.mkdir(parents=True, exist_ok=True)
    for old in PANDIT_DATA.glob("*-extracted-entities-cleaned.csv"):
        if old.name != name:
            old.unlink()
            print(f"Removed {old.name}")
    shutil.copyfile(source, PANDIT_DATA / name)
    print(f"Copied {name} into {PANDIT_DATA.relative_to(ROOT)}/")

    text = VERSION.read_text(encoding="utf-8")
    line = f'__pandit_data_version__ = "{args.date}"'
    pattern = r'__pandit_data_version__\s*=\s*"[^"]*"'
    text = re.sub(pattern, line, text) if re.search(pattern, text) else text.rstrip("\n") + "\n" + line + "\n"
    VERSION.write_text(text, encoding="utf-8")
    print(f"Set {line} in VERSION. Now run make check.")


if __name__ == "__main__":
    main()
