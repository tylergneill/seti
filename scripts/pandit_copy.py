"""Bring in Pāṇḍitya's current cleaned Pandit extract.

Pāṇḍitya exports Pandit and cleans it; this repo works against a copy of the
result, so that every match and check is tied to a known snapshot. This
reads ../panditya/VERSION for the export's date (__pandit_content_version__)
and the day its pipeline last ran (__data_version__), copies
../panditya/data/<export date>-extracted-entities-cleaned.csv into
data/pandit/, removes the copy it replaces (git keeps it), and records both
dates in VERSION.

    python3 scripts/pandit_copy.py

Then run scripts/check.py.
"""

import re
import shutil

from common import PANDIT_DATA, ROOT, VERSION, read_version

PANDITYA = ROOT.parent / "panditya"


def set_version(text, name, value):
    line = f'__{name}__ = "{value}"'
    pattern = rf'^__{name}__\s*=\s*["\'][^"\']*["\']'
    if re.search(pattern, text, re.M):
        return re.sub(pattern, line, text, flags=re.M)
    return text.rstrip("\n") + "\n" + line + "\n"


def main():
    content = read_version("pandit_content_version", PANDITYA / "VERSION")
    data = read_version("data_version", PANDITYA / "VERSION")
    name = f"{content}-extracted-entities-cleaned.csv"
    source = PANDITYA / "data" / name
    if not source.exists():
        raise SystemExit(f"No {name} in {source.parent}; has Pāṇḍitya cleaned this export yet?")

    PANDIT_DATA.mkdir(parents=True, exist_ok=True)
    for old in PANDIT_DATA.glob("*-extracted-entities-cleaned.csv"):
        if old.name != name:
            old.unlink()
            print(f"Removed {old.name}")
    shutil.copyfile(source, PANDIT_DATA / name)
    print(f"Copied {name} into {PANDIT_DATA.relative_to(ROOT)}/")

    text = VERSION.read_text(encoding="utf-8")
    text = set_version(text, "pandit_content_version", content)
    text = set_version(text, "pandit_data_version", data)
    VERSION.write_text(text, encoding="utf-8")
    print(f"VERSION: Pandit export {content}, Pāṇḍitya's pipeline run {data}. Now run make check.")


if __name__ == "__main__":
    main()
