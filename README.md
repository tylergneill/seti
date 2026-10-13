# seti

Sanskrit E-Text Inventory data and pipeline code.

SETI is a register of where searchable Sanskrit e-texts are online. Each row
of `data/seti-master.csv` is one e-text, tied where possible to a work and
an author in the [Pandit Project](https://www.panditproject.org/).
[Pāṇḍitya](https://github.com/tylergneill/panditya) takes a dated copy of
the master as an input, the same way it takes a Pandit export.

This repo holds the master and the tools that improve its Pandit IDs.

## The master

`Work ID` and `Author ID` hold Pandit IDs. In either column:

- `...` means not yet identified. These are the open slots.
- `—` in `Author ID` means the text has no author.
- A cell can hold several IDs, separated by commas or newlines. Several
  work IDs run from part to whole (`... , 42078` for a parvan of the
  Mahābhārata); several author IDs follow the order of the author names.

`data/archive/` keeps earlier dated masters.

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

Both read Pandit from Pāṇḍitya's newest
`../panditya/data/*-extracted-entities-cleaned.csv`; `--pandit` names
another.

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
