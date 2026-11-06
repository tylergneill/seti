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

The code's version is in `VERSION`; the master is dated by the copies
taken of it.

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
date in `__pandit_data_version__` in `VERSION`. Pāṇḍitya does the export
and the cleaning; this repo never reads its files directly, except for
`make pandit-copy`.

## Keeping Pāṇḍitya and SETI in step

Each repo keeps a dated copy of the other's data: Pāṇḍitya a copy of the
SETI master, SETI a copy of Pāṇḍitya's cleaned Pandit extract. Each
records the Pandit date it uses as `__pandit_data_version__` in `VERSION`,
and the two should match.

**Every Pandit refresh: these three steps, in this order.**

1. **Pāṇḍitya:** on a new branch, bring in the new Pandit export and clean
   it (`data/manual_cleaning.md`, "Updating the Pandit data", steps 1–5).
   Stop before `make transform`. Don't merge yet.
2. **SETI:** `make pandit-copy DATE=<date>`, then `make check`. Fix every
   ID it reports (most likely deleted or merged in Pandit; look it up with
   `python3 scripts/lookup.py id <id>`), rerun `make check` until it
   passes, and merge.
3. **Pāṇḍitya, same branch:** copy the SETI master over
   (`data/manual_cleaning.md`, "Updating the SETI data"), then
   `make transform` and `make analyze`, and merge.

Step 2 is where Pandit's deletions and merges are caught and fixed. If
`make transform` fails in step 3, step 2 was skipped or incomplete: go back
to it.

**Anything else** (SETI matcher work or new rows, Pāṇḍitya code) touches
one side only: merge it there, and the other side picks it up at its next
update.

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
    make research RUN=<run>               # a Claude session with sub-agents
    make research-apply RUN=<run>

Claude sub-agents, one per batch of ten rows, each search the Pandit
extract with `scripts/lookup.py`, may read the top of the e-text itself,
and write an ID or "not in Pandit" for each slot with a confidence and
their reasoning. `agents/researcher.md` is their prompt and
`agents/dispatcher.md` is the coordinator's. With `SCOPE=all` the IDs
already in a row are withheld from the sub-agent, so that its reading is
independent of the master. A run can be interrupted and resumed; batches
live under `tmp/research/<run>/`.

`scripts/lookup.py` is also useful by hand:

    python3 scripts/lookup.py person Vācaspati Miśra
    python3 scripts/lookup.py work Nyāyakaṇikā
    python3 scripts/lookup.py id 88576
