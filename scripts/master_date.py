"""Date the master in VERSION from git.

Sets __seti_data_version__ to the day of the last commit that changed
data/seti-master.csv (its author date, which rebases keep). Pāṇḍitya takes
this date when it copies the master in.

    python3 scripts/master_date.py           # set the date in VERSION
    python3 scripts/master_date.py --check   # fail if VERSION's date is out of date (CI runs this)

Commit the master first: uncommitted changes to it have no date yet.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = ROOT / "VERSION"
MASTER = "data/seti-master.csv"
LINE = re.compile(r'^__seti_data_version__\s*=\s*["\']([^"\']*)["\']', re.M)


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def main():
    check = "--check" in sys.argv[1:]
    date = git("log", "-1", "--format=%as", "--", MASTER)
    if not date:
        sys.exit(f"No commit has changed {MASTER}.")
    text = VERSION.read_text(encoding="utf-8")
    found = LINE.search(text)
    if not found:
        sys.exit(f"No __seti_data_version__ in {VERSION.name}.")

    if git("status", "--porcelain", "--", MASTER):
        print(f"Warning: {MASTER} has uncommitted changes; the date is that of its last commit.")

    if found.group(1) == date:
        print(f"__seti_data_version__ = {date}, up to date.")
    elif check:
        sys.exit(f"__seti_data_version__ is {found.group(1)}, but {MASTER} last changed on {date}. "
                 f"Run make master-date and commit VERSION.")
    else:
        VERSION.write_text(LINE.sub(f'__seti_data_version__ = "{date}"', text, count=1), encoding="utf-8")
        print(f"__seti_data_version__ = {date} (was {found.group(1)}). Commit VERSION.")


if __name__ == "__main__":
    main()
