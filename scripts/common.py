"""Shared pieces: the SETI master, the Pandit reference, and applying proposals.

Every matcher, mechanical or LLM, ends the same way. It produces a list of
proposals, each naming one ID slot in the master and the Pandit ID it thinks
belongs there, with a confidence between 0 and 1. apply_proposals() writes
the ones at or above the threshold into the master in place and puts the
rest in a notes file under reports/. The master is the thing to diff.
"""

import csv
import datetime
import io
import re
import unicodedata
from urllib.parse import quote
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "data" / "seti-master.csv"
REPORTS = ROOT / "reports"
VERSION = ROOT / "VERSION"
PANDIT_DATA = ROOT / "data" / "pandit"   # a dated copy of Pāṇḍitya's cleaned extract

OPEN = "..."       # no Pandit ID identified yet
NO_AUTHOR = "—"    # nothing to identify: the text has no author

WORK_ID = "Work ID"
AUTHOR_ID = "Author ID"

DEFAULT_THRESHOLD = 0.9
# Pandit's own address for a record. /entity/<id>/work and the like are only
# aliases, which records created in bulk (e.g. the 114000s-116000s) lack;
# /node/<id> works for every record.
PANDIT_NODE = "https://panditproject.org/node/{}"
AMBIGUITY_MARGIN = 0.03  # two confident candidates closer than this are a tie
KEEP_FLOOR = 0.6         # an ID already in the master stands if it scores at least this


# ---------- the master ----------

class Master:
    """The master CSV, read and written without disturbing untouched cells."""

    def __init__(self, path=MASTER):
        self.path = Path(path)
        with open(self.path, encoding="utf-8", newline="") as f:
            text = f.read()
        rows = list(csv.reader(io.StringIO(text, newline="")))
        self.header, self.rows = rows[0], rows[1:]
        self.col = {name: i for i, name in enumerate(self.header)}
        self.trailing_newline = text.endswith("\n")
        self._lines = None
        if self.dumps() != text:
            raise SystemExit(
                f"{self.path} does not survive a read/write round trip unchanged, "
                "so writing it would touch cells no matcher meant to change. "
                "Not proceeding."
            )

    def dumps(self):
        buf = io.StringIO(newline="")
        csv.writer(buf, lineterminator="\n").writerows([self.header] + self.rows)
        text = buf.getvalue()
        return text if self.trailing_newline else text.rstrip("\n")

    def save(self):
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            f.write(self.dumps())

    def get(self, r, name):
        return self.rows[r][self.col[name]]

    def set(self, r, name, value):
        self.rows[r][self.col[name]] = value

    def sheet_row(self, r):
        """Row number as a spreadsheet shows it (header is row 1)."""
        return r + 2

    def line(self, r):
        """Line the row starts on in the file, which a diff tool shows.
        It runs ahead of the row number because some cells span lines."""
        if self._lines is None:
            self._lines, line = [], 2
            for row in self.rows:
                self._lines.append(line)
                line += 1 + sum(cell.count("\n") for cell in row)
        return self._lines[r]

    def key(self, r):
        """Enough of a row to recognise it again if the file has shifted."""
        return " | ".join(self.get(r, c) for c in ("Collection", "Text Name", "Link 1 (main)", "Link 2 (underlying)"))


# An ID cell holds one or more slots, separated by commas or newlines. Keep
# the separators so that rewriting one slot leaves the rest of the cell as is.
_SEP = re.compile(r"(\s*[,\n]\s*)")


def split_cell(cell):
    pieces = _SEP.split(cell)
    return pieces[0::2], pieces[1::2]


def join_cell(parts, seps):
    out = [parts[0]]
    for sep, part in zip(seps, parts[1:]):
        out += [sep, part]
    return "".join(out)


def split_names(cell):
    return [n.strip() for n in cell.split(",") if n.strip()]


# ---------- names ----------

_CONSONANTS = "kgṅcjñṭḍṇtdnpbmyrlvśṣsh"
_PUNCT = re.compile(r"[\s\-‐–—.,:;'’\"()\[\]\u00ad\u200b-\u200d]")
_NASAL = re.compile(f"[ṅñṇnmṃ](?=[{_CONSONANTS}])")


def norm(name):
    """Fold away differences that do not distinguish one name from another:
    case, spacing, hyphens, punctuation, and anusvāra versus a class nasal."""
    s = unicodedata.normalize("NFC", name).casefold()
    s = _PUNCT.sub("", s)
    return _NASAL.sub("ṃ", s)


# ---------- the Pandit reference ----------

def read_version(name, path=VERSION):
    """A __name__ = "value" line from a VERSION file (this repo's, or Pāṇḍitya's)."""
    found = re.search(rf'^__{name}__\s*=\s*["\']([^"\']+)["\']', Path(path).read_text(encoding="utf-8"), re.M)
    if not found:
        raise SystemExit(f"No __{name}__ in {path}.")
    return found.group(1)


def pandit_source_version():
    """When the Pandit data of our copy was sourced: the export's date, which names the file."""
    return read_version("pandit_source_version")


def panditya_data_version():
    """When Pāṇḍitya's pipeline last ran on that export, as of our copy."""
    return read_version("panditya_data_version")


def pandit_extract():
    """This repo's copy of the cleaned Pandit extract, for the export date in VERSION."""
    path = PANDIT_DATA / f"{pandit_source_version()}-extracted-entities-cleaned.csv"
    if not path.exists():
        raise SystemExit(f"No {path.name} in {PANDIT_DATA}; bring it in with make pandit-copy.")
    return path


class Pandit:
    """Works and persons from Pāṇḍitya's cleaned extract of a Pandit export."""

    def __init__(self, path=None):
        self.path = Path(path) if path else pandit_extract()
        self.works = {}
        self.persons = {}
        with open(self.path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            if row["Content type"] == "Person":
                self.persons[row["ID"]] = {
                    "id": row["ID"],
                    "name": row["Name"].strip(),
                    "aka": split_names(row["Aka"]),
                    "social": row["Social identifiers"].strip(),
                    "years": _years(row),
                    "work_ids": [],
                }
        for row in rows:
            if row["Content type"] != "Work":
                continue
            author_ids = split_names(row["Authors (IDs)"])
            author_names = split_names(row["Authors (names)"])
            self.works[row["ID"]] = {
                "id": row["ID"],
                "name": row["Name"].strip(),
                "aka": split_names(row["Aka"]),
                "author_ids": author_ids,
                "base_ids": split_names(row["Base texts (IDs)"]),
                "discipline": row["Discipline"].strip(),
                "years": _years(row),
            }
            for aid, aname in zip(author_ids, author_names):
                person = self.persons.setdefault(
                    aid, {"id": aid, "name": aname, "aka": [], "social": "", "years": "", "work_ids": []})
                person["work_ids"].append(row["ID"])

    def name_of(self, entity_id):
        entity = self.works.get(entity_id) or self.persons.get(entity_id)
        return entity["name"] if entity else ""


def _years(row):
    lo, hi = row["Lowest Year"].strip(), row["Highest Year"].strip()
    if not lo and not hi:
        return ""
    return lo if lo == hi else f"{lo}–{hi}"


# ---------- proposals ----------

def proposal(row, field, position, suggested, confidence, basis, suggested_name=""):
    return {
        "row": row,                   # index into Master.rows
        "field": field,               # WORK_ID or AUTHOR_ID
        "position": position,         # which slot of the cell
        "suggested": suggested,       # a Pandit ID
        "suggested_name": suggested_name,
        "confidence": round(float(confidence), 2),
        "basis": basis,
    }


REPORT_COLUMNS = ["Row", "Line", "Collection", "Text Name", "Author Name", "Field", "Slot", "Current",
                  "Suggested ID", "Suggested Name", "Confidence", "Status", "Basis",
                  "Text Links", "Suggested Link", "Current Name", "Current Link", "Related Links"]

# The row's own links to the e-text, for reading what the text really is.
TEXT_LINKS = (("main", "Link 1 (main)"), ("underlying", "Link 2 (underlying)"), ("extract", "Link 3 (extract)"))


def pandit_link(entity_id):
    """The Pandit page of a record, or '' for anything that is not an ID ('...', '—', '')."""
    entity_id = (entity_id or "").strip()
    return PANDIT_NODE.format(entity_id) if entity_id.isdigit() else ""


def related_records(master, pandit, p):
    """The other Pandit records worth opening when judging a proposal, as [(role, ID, name)].

    For a work: the authors Pandit gives the suggested work, so that the
    reviewer can see whether they are the row's author. For an author: the
    works already in the row's Work ID cell, which is usually what
    corroborated the author.
    """
    if pandit is None or not p["suggested"]:
        return []
    if p["field"] == WORK_ID:
        work = pandit.works.get(p["suggested"])
        ids = work["author_ids"] if work else []
        role = "author"
    else:
        ids = [i.strip() for i in split_cell(master.get(p["row"], WORK_ID))[0] if i.strip().isdigit()]
        role = "work"
    return [(role, i, pandit.name_of(i)) for i in ids]


def apply_proposals(master, proposals, tool, threshold=DEFAULT_THRESHOLD, overwrite=False,
                    dry_run=False, extra_notes=(), pandit=None):
    """Write confident proposals into the master; report the rest.

    A slot that is open ('...') is filled when the best proposal for it
    reaches the threshold. A slot that already holds an ID is replaced only
    with overwrite=True, and only by a different ID that reaches the
    threshold. Everything else that disagrees with the master goes to the
    notes file, at most three candidates per slot.

    Every change is printed with the Pandit pages to check it against: the
    suggested record, the record it replaces, and the related records (see
    related_records()), which need `pandit`. The reports carry the same
    links as columns.
    """
    def report(p, current, status):
        return _report_row(master, p, current, status, pandit)

    by_slot = {}
    for p in proposals:
        by_slot.setdefault((p["row"], p["field"], p["position"]), []).append(p)

    applied, notes = [], []
    counts = {"filled": 0, "replaced": 0, "confirmed": 0, "noted": 0,
              # How sure the matcher was of each ID it confirmed; see print_summary().
              "confirmed_confidences": [], "threshold": threshold}

    for (r, field, position), candidates in sorted(by_slot.items()):
        ranked, seen = [], set()
        for p in sorted(candidates, key=lambda p: -p["confidence"]):
            if p["suggested"] not in seen:
                seen.add(p["suggested"])
                ranked.append(p)
        parts, seps = split_cell(master.get(r, field))
        if position >= len(parts):
            continue
        current = parts[position].strip()
        best = ranked[0]

        is_open = current == OPEN
        confident = [p for p in ranked if p["confidence"] >= threshold]

        # Pandit sometimes holds the same work or person twice. When the ID
        # already in the master is one of several confident candidates, it
        # stands, and the others are noted as possible duplicates in Pandit.
        # The same holds when the current ID is a plausible candidate at all:
        # a human put it there, and a second record that matches the names
        # better is more likely a duplicate than a correction.
        current_score = max((p["confidence"] for p in ranked if p["suggested"] == current), default=0)
        if best["suggested"] == current or current_score >= KEEP_FLOOR:
            counts["confirmed"] += 1
            counts["confirmed_confidences"].append(current_score)
            for p in confident:
                if p["suggested"] != current:
                    notes.append(report(p, current, "confident alternative to a plausible current ID (Pandit duplicate?)"))
            continue

        # Several confident candidates and nothing to choose between them.
        if len(confident) > 1 and confident[0]["confidence"] - confident[1]["confidence"] < AMBIGUITY_MARGIN:
            for p in confident[:3]:
                notes.append(report(p, current, "ambiguous: several confident candidates"))
            counts["noted"] += 1
            continue

        if best["confidence"] >= threshold and (is_open or overwrite):
            parts[position] = parts[position].replace(current, best["suggested"]) if current else best["suggested"]
            master.set(r, field, join_cell(parts, seps))
            status = "filled" if is_open else "replaced"
            counts[status] += 1
            applied.append(report(best, current, status))
            continue

        for p in ranked[:3]:
            if p["suggested"] == current:
                continue
            if is_open:
                status = "below threshold"
            elif p["confidence"] >= threshold:
                status = "differs from current (not overwriting)"
            else:
                status = "differs from current"
            notes.append(report(p, current, status))
        counts["noted"] += 1

    notes += list(extra_notes)

    paths = {}
    if not dry_run:
        master.save()
        REPORTS.mkdir(exist_ok=True)
        # To the minute, so a second run in a day does not overwrite the first's log.
        stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
        for name, rows in (("applied", applied), ("notes", notes)):
            paths[name] = REPORTS / f"{stamp}-{tool}-{name}.csv"
            with open(paths[name], "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
    for row in applied:
        print_change(row, dry_run)
    return counts, paths


def clickable(url):
    """A URL with its non-ASCII characters percent-encoded (ś -> %C5%9B).

    Terminals such as PyCharm's end a link at the first diacritic, so a
    link to 'Amaraughaśāsana' would open 'Amaraugha'. The encoded form is
    the same address, and browsers show it decoded again. Characters that
    already carry meaning in a URL, and existing %-escapes, are left alone.
    """
    return quote(url, safe=":/?#[]@!$&'()*+,;=%~")


def print_change(row, dry_run=False):
    """One applied change, with the e-text's links and each Pandit page on a
    line of its own, so that a terminal makes them clickable: read the text,
    compare the records, then keep or revert the change."""
    verb = f"would be {row['Status']}" if dry_run else row["Status"]
    print(f"  {verb}: row {row['Row']} (line {row['Line']}) {row['Collection']} "
          f"'{row['Text Name']}' {row['Field']} slot {row['Slot']} ({row['Confidence']})")
    for line in row["Text Links"].splitlines():
        label, url = line.split(None, 1)
        print(f"      text    {label:<10} {clickable(url)}")
    if row["Current Link"]:
        print(f"      was     {row['Current']} {row['Current Name']}  {row['Current Link']}")
    print(f"      now     {row['Suggested ID']} {row['Suggested Name']}  {row['Suggested Link']}")
    for line in row["Related Links"].splitlines():
        print(f"      {line}")


def _report_row(master, p, current, status, pandit=None):
    r = p["row"]
    related = related_records(master, pandit, p)
    text_links = [(label, master.get(r, col).strip()) for label, col in TEXT_LINKS
                  if col in master.col and master.get(r, col).strip()]
    return {
        "Row": master.sheet_row(r),
        "Line": master.line(r),
        "Collection": master.get(r, "Collection"),
        "Text Name": master.get(r, "Text Name"),
        "Author Name": master.get(r, "Author Name"),
        "Field": p["field"],
        "Slot": p["position"] + 1,
        "Current": current,
        "Suggested ID": p["suggested"],
        "Suggested Name": p["suggested_name"],
        "Confidence": f"{p['confidence']:.2f}" if p["suggested"] else "",
        "Status": status,
        "Basis": p["basis"],
        # One link per line: '<which> <link>'.
        "Text Links": "\n".join(f"{label:<10} {url}" for label, url in text_links),
        "Suggested Link": pandit_link(p["suggested"]),
        # The record being replaced or contradicted, by name, so it can be
        # judged without opening its page (blank if pandit was not given).
        "Current Name": pandit.name_of(current) if pandit is not None and pandit_link(current) else "",
        "Current Link": pandit_link(current),
        # One record per line: '<role> <ID> <name>  <link>'.
        "Related Links": "\n".join(f"{role:<7} {i} {name}  {pandit_link(i)}" for role, i, name in related),
    }


def note_row(master, r, field, position, status, basis, current=""):
    """A notes-file row that is not a proposal, e.g. 'not in Pandit'."""
    return _report_row(master, proposal(r, field, position, "", 0, basis), current, status)


def agreement_bands(confidences, threshold):
    """'(78 at 0.90+, 5 at 0.60-0.90, 1 below 0.60)': how sure the matcher was
    of the IDs it agreed with. Agreement ignores the threshold, so a match
    named at 0.4 counts too; this says how many are like that. Empty bands
    are left out."""
    bands = [(f"at {threshold:.2f}+", sum(c >= threshold for c in confidences)),
             (f"at {KEEP_FLOOR:.2f}-{threshold:.2f}", sum(KEEP_FLOOR <= c < threshold for c in confidences)),
             (f"below {KEEP_FLOOR:.2f}", sum(c < KEEP_FLOOR for c in confidences))]
    shown = [f"{n} {label}" for label, n in bands if n]
    return f" ({', '.join(shown)})" if shown else ""


def print_summary(counts, paths, threshold):
    bands = agreement_bands(counts.get("confirmed_confidences", []), threshold)
    print(f"threshold {threshold:.2f}: "
          f"{counts['filled']} filled, {counts['replaced']} replaced, "
          f"{counts['confirmed']} already agree{bands}, {counts['noted']} slots left in notes")
    for name, path in paths.items():
        print(f"  {name}: {path.relative_to(ROOT)}")
