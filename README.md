# seti

Sanskrit E-Text Inventory data and pipeline code.

SETI is a register of where searchable Sanskrit e-texts are online. Each row
of `data/seti-master.csv` is one e-text, tied where possible to a work and
an author in the [Pandit Project](https://www.panditproject.org/).
[Pāṇḍitya](https://github.com/tylergneill/panditya) takes a dated copy of
the master as an input, the same way it takes a Pandit export.

This repo holds the master and the tools that improve its Pandit IDs.

`data/seti-master.csv` here is the master. The public [SETI Google
Sheet](https://docs.google.com/spreadsheets/d/1MpHlU-wnWbTsC-2eWZ-gowsM8oiBeGapcifeFFeaitI/edit?gid=0#gid=0)
used to be, with this file copied from it; that is now reversed, and the
sheet will in time be filled from this file. Make changes here, not in
the sheet.

`VERSION` holds the code's version (`__seti_code_version__`) and the
master's date (`__seti_data_version__`), which Pāṇḍitya takes when it copies the
master in. It is the day of the last commit that changed the master:
`make master-date` sets it from git, and a check on every PR into main
fails if it is out of date.

## The master

`Work ID` and `Author ID` hold Pandit IDs. In either column:

- `...` means not yet identified. These are the open slots.
- `—` in `Author ID` means the text has no author.
- A cell can hold several IDs, separated by commas or newlines. Several
  work IDs run from part to whole (`... , 42078` for a parvan of the
  Mahābhārata); several author IDs follow the order of the author names.

`data/archive/` keeps earlier dated masters.

## The Pandit data

The master's IDs are checked and matched against a dated copy of
Pāṇḍitya's cleaned extract of a Pandit export, in `data/pandit/`, with its
dates in `VERSION`: `__pandit_source_version__`, the export's date, which
names the file, and `__panditya_data_version__`, the day Pāṇḍitya's pipeline
last ran on it. Pāṇḍitya does the export and the cleaning; this repo never
reads its files directly, except for `make pandit-copy` and `make check-ids-exist`.

## Keeping Pāṇḍitya and SETI in step

Each repo copies the other's output and records what it copied in its
`VERSION`: Pāṇḍitya the SETI master (`make seti-import`), SETI
Pāṇḍitya's cleaned Pandit extract (`make pandit-copy`).

**A SETI change, to see in Pāṇḍitya.** Commit it in SETI and run
`make master-date` there. Then, in Pāṇḍitya, `make seti-refresh` and
restart the server. `seti-refresh` refuses a master with uncommitted
changes or an out-of-date date; `FORCE=1` copies it anyway, for work in
progress.

**A new Pandit export.**

1. **Pāṇḍitya,** on a new branch: bring in the export
   (`data/manual_cleaning.md`, "Updating the Pandit data", steps 1–3),
   then `make pipeline`. Its transform checks SETI's work IDs against the
   new data: if any are missing, it lists them and writes nothing. Don't
   merge yet.
2. **SETI:** `make pandit-copy`, then `make check-ids-exist`, which lists every ID
   in the master that the new data lacks (most likely deleted or merged
   in Pandit; look one up with `python3 scripts/lookup.py id <id>`). Fix
   them, commit, run `make master-date`, commit `VERSION`, and merge.
3. **Pāṇḍitya,** same branch: `make seti-refresh`, then `make analyze`.
   Merge.

## Two matchers, one way of working

Both matchers edit the master in place and say what they were less sure of
in `reports/`. Nothing is committed for you: compare the master with the
last commit in PyCharm or Meld, keep what is right, and revert what is not.

Each writes an identification into the master only at or above a confidence
threshold (default 0.9). Below it, the candidates go to
`reports/<date>-<time>-<tool>-notes.csv`, up to three per slot, each with
the reason for it. `...-applied.csv` logs what was written and why, as a
companion to the diff.

Each has two scopes. `open` (the default) only fills `...` slots. `all`
re-identifies every row, and replaces an ID already in the master when a
confident match contradicts it and the current ID does not look plausible.
Where the current ID is plausible and another record matches as well or
better, the master is left alone and the other record is noted as a
possible duplicate in Pandit.

Both read Pandit from `data/pandit/` (see "The Pandit data"); `--pandit`
names another extract.

### Mechanical

    make match                    # open slots
    make match SCOPE=all DRY=1    # every row; list what would change
    make match THRESHOLD=0.85

Matches by name: exactly, then normalised, then through alternative names,
then fuzzily. A work match is confident when Pandit also lists the row's
author as that work's author. It takes seconds. Rows with several work
slots are not attempted.

### Research

    make research-prep LIMIT=50           # prints the run's name
    make research-prep OFFSET=100 LIMIT=100   # rows 101-200 of the selection, as a run of its own
    make research RUN=<run>               # a Claude session with sub-agents; applies the run at the end
    make research RUN=<run> NO_APPLY=1    # the same, but stops before applying
    make research-apply RUN=<run> DRY=1   # what applying would change
    make research-apply RUN=<run>         # apply it yourself (after NO_APPLY=1)

Claude sub-agents, one per batch of ten rows, each search the Pandit
extract with `scripts/lookup.py`, may read the top of the e-text itself,
and write an ID or "not in Pandit" for each slot with a confidence and
their reasoning. `agents/researcher.md` is their prompt and
`agents/dispatcher.md` is the coordinator's. With `SCOPE=all` the IDs
already in a row are withheld from the sub-agent, so that its reading is
independent of the master. A run can be interrupted and resumed; batches
live under `tmp/research/<run>/`.

A big collection is best done in chunks, one run per sitting: `OFFSET`
skips that many of the selected rows (counted within `COLLECTION` and
`SCOPE`, not the whole master), and the run's name ends with the range,
e.g. `...-gretil-all-0101-0200`. Prep prints the `OFFSET` of the next
chunk.

`scripts/lookup.py` is also useful by hand:

    python3 scripts/lookup.py person Vācaspati Miśra
    python3 scripts/lookup.py work Nyāyakaṇikā
    python3 scripts/lookup.py id 88576
