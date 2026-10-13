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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "data" / "seti-master.csv"
REPORTS = ROOT / "reports"
PANDIT_DATA = ROOT.parent / "panditya" / "data"

OPEN = "..."       # no Pandit ID identified yet
NO_AUTHOR = "—"    # nothing to identify: the text has no author

WORK_ID = "Work ID"
AUTHOR_ID = "Author ID"

DEFAULT_THRESHOLD = 0.9
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

def latest_pandit_extract():
    found = sorted(PANDIT_DATA.glob("*-extracted-entities-cleaned.csv"))
    if not found:
        raise SystemExit(f"No *-extracted-entities-cleaned.csv in {PANDIT_DATA}; pass --pandit.")
    return found[-1]


class Pandit:
    """Works and persons from Pāṇḍitya's cleaned extract of a Pandit export."""

    def __init__(self, path=None):
        self.path = Path(path) if path else latest_pandit_extract()
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
                  "Suggested ID", "Suggested Name", "Confidence", "Status", "Basis"]


def apply_proposals(master, proposals, tool, threshold=DEFAULT_THRESHOLD, overwrite=False,
                    dry_run=False, extra_notes=()):
    """Write confident proposals into the master; report the rest.

    A slot that is open ('...') is filled when the best proposal for it
    reaches the threshold. A slot that already holds an ID is replaced only
    with overwrite=True, and only by a different ID that reaches the
    threshold. Everything else that disagrees with the master goes to the
    notes file, at most three candidates per slot.
    """
    by_slot = {}
    for p in proposals:
        by_slot.setdefault((p["row"], p["field"], p["position"]), []).append(p)

    applied, notes = [], []
    counts = {"filled": 0, "replaced": 0, "confirmed": 0, "noted": 0}

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
            for p in confident:
                if p["suggested"] != current:
                    notes.append(_report_row(master, p, current, "confident alternative to a plausible current ID (Pandit duplicate?)"))
            continue

        # Several confident candidates and nothing to choose between them.
        if len(confident) > 1 and confident[0]["confidence"] - confident[1]["confidence"] < AMBIGUITY_MARGIN:
            for p in confident[:3]:
                notes.append(_report_row(master, p, current, "ambiguous: several confident candidates"))
            counts["noted"] += 1
            continue

        if best["confidence"] >= threshold and (is_open or overwrite):
            parts[position] = parts[position].replace(current, best["suggested"]) if current else best["suggested"]
            master.set(r, field, join_cell(parts, seps))
            status = "filled" if is_open else "replaced"
            counts[status] += 1
            applied.append(_report_row(master, best, current, status))
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
            notes.append(_report_row(master, p, current, status))
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
    if dry_run:
        for row in applied:
            print(f"  would be {row['Status']}: row {row['Row']} {row['Field']} {row['Current']} -> "
                  f"{row['Suggested ID']} '{row['Suggested Name']}' ({row['Confidence']})  [{row['Text Name']}]")
    return counts, paths


def _report_row(master, p, current, status):
    r = p["row"]
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
    }


def note_row(master, r, field, position, status, basis, current=""):
    """A notes-file row that is not a proposal, e.g. 'not in Pandit'."""
    return _report_row(master, proposal(r, field, position, "", 0, basis), current, status)


def print_summary(counts, paths, threshold):
    print(f"threshold {threshold:.2f}: "
          f"{counts['filled']} filled, {counts['replaced']} replaced, "
          f"{counts['confirmed']} already agree, {counts['noted']} slots left in notes")
    for name, path in paths.items():
        print(f"  {name}: {path.relative_to(ROOT)}")
