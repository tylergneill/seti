# Improving the master: the work in hand

A spec for the next stretch of work on `data/seti-master.csv`, written for
the Claude Code session that carries it out. The review tool that will
eventually sit on top of this is specified separately in `review-spec.md`.

## Principles

- **The goal is the master.** SETI exists to give each e-text in
  `data/seti-master.csv` unambiguous Pandit IDs. Everything else is
  instrumental.
- **Two matchers, no more.** `make match` (mechanical) and `make research`
  (LLM agents) are SETI's only tools for writing IDs. Both write straight
  into the master at or above a threshold (default 0.9), and leave the rest
  in `reports/` as notes. No third matcher is to be built.
- **The grouping is evidence, not a pipeline.** The Atlas grouping
  (`grouping-spec.md`, passes 1–3) and its grounding in Pandit
  (`scripts/grouping_ground.py`) were made to help the matchers. Their
  results are handed to the master once. Their code stays in the repo as a
  record of how those IDs were reached. It is not extended, made a regular
  input, or rerun, and the matchers do not read the registry.
- **Tyler vets every change.** Every run leaves the master uncommitted,
  with `applied` and `notes` reports beside it. Runs are cut small enough
  for each to be reviewed in one sitting. Nothing is committed without
  that review.
- **Pandit gets fixed along the way.** The vetting also tests Pandit. Every
  agent and matcher adds the Pandit problems it meets to
  `data/pandit-fixes.csv` (below), so that they can be fixed in Pandit now.

## The Pandit fix list

`data/pandit-fixes.csv` has one row per problem in Pandit. Its columns:

| column | holds |
| --- | --- |
| `Type` | `Work` or `Person` |
| `ID` | the Pandit record, or `(new)` for a missing record |
| `Field` | `Name`, `Aka`, `Author`, `Commentary on`, ... |
| `Current` | the value Pandit has now |
| `Problem` | what is wrong, in a sentence |
| `Fix` | `delete`, `rename to: …`, `create`, `merge with <ID>`, `check: …` |
| `Found By` | which tool or run found it |
| `Found In` | the date of the Pandit export it was found in |
| `Status` | `open`, `done in Pandit`, `confirmed`, `wontfix` |

It began with the export-cleaning problems of 2026-10-08, plus the
Bhavasaṃkrānti records, and it grows from now on:

- **Research agents** report Pandit problems in a separate list in their
  `proposals.json`: duplicates, wrong base texts or authors,
  misattributions, garbled names, missing records. `agents/researcher.md`
  gets a section saying what to report and in what form, and the validator
  checks it. `research-apply` adds the reports to the fix list, skipping
  any that repeat an existing row (same `Type`, `ID`, `Field` and `Fix`).
- **`make match`** adds what it can see mechanically: two Pandit records
  that match one row equally well. Until now these went only into its
  notes, as "possible duplicate in Pandit".
- **Tyler** adds rows by hand. Once the review tool is built, its
  tickets add rows too.

## Step 1: the November grouping into the master's GRETIL rows

Everything in this step uses the 2025-11-07 Pandit extract, which is what
the grouping was grounded in:
`../panditya/data/archive/2025-11-07-extracted-entities-cleaned.csv`.
Pass it to each tool with `--pandit`.

### 1a. What the grounding already settled (done, awaiting review)

`scripts/grouping_to_master.py` joined the master's GRETIL rows to the
registry: 620 of 1,037 rows. It filled 16 open slots with the grounding's
confident IDs (12 works, 4 authors) and noted 51 other slots. See
`reports/2026-10-15-1624-grouping-applied.csv` and `-notes.csv`.

Awaiting Tyler's review:

- the 16 fills, including the judgement that GRETIL's *Tantrākhyāyika 1*
  is the Pañcatantra (112155);
- master row 743 (GRETIL `bsu010`, *Bhavasaṅkrāntisūtra*), which carries
  Nāgārjuna's treatise (88361) and Nāgārjuna as its author. The sūtra is
  not in Pandit, so the proposal is: work `...`, author `—`, and
  "Bhavasamkrāntiśāstra" dropped from its alternative names.

### 1b. LLM research on the rest of the open GRETIL slots

**Scope.** Every open work or author slot in a GRETIL row covered by the
registry, once 1a is reviewed: about 180 work slots and 30 author slots.
This includes the slots that the grounders called absent from Pandit or
held below 0.9, because these agents see more than the grounders did. The
417 GRETIL rows that the registry does not cover are an open decision
(below).

**What the agents get, in addition to what research gives them today**
(the row, its links, and the right to read the top of the e-text):

1. **All of Pandit.** A compact rendering of the extract, one line per
   work (`ID | name | other names | author IDs | base-text IDs |
   discipline | dates`) and per person: about 850,000 characters, roughly
   300k tokens. The agent reads it whole before it starts, so that a name
   it would not have thought to search for can still catch its eye.
   `scripts/lookup.py` stays available for exact searches. This becomes
   standard for `make research` from now on, not just for this run: it is
   the "brute force" that the grounding lacked.
2. **The group, for rows the registry covers.** The registry title's
   canonical name and every variant, its authors, what it is part of or
   comments on, and the catalogue lines of the same work in the other four
   Atlases. This is supplied through a generic hook: `research_prep.py
   --context <file>`, which attaches a per-row block of extra context that
   the prompt describes. A one-off script, `scripts/grouping_context.py`,
   writes that file from the registry. The hook stays. The script is
   evidence, like `grouping_to_master.py`.

**Batching.** Rows of the same registry group share a batch, so that one
agent decides them together. The remaining rows are batched by author,
then by name, about ten rows a batch.

**Output.** The same as `make research` today: an ID or "not in Pandit"
per slot, with a confidence and reasoning, applied by `research-apply` at
the threshold. Pandit problems go to the fix list.

**Running it.** First a pilot of three batches, which Tyler reviews. Then
the rest, in runs small enough to review.

### Open decision: the 417 GRETIL rows outside the registry

These are GRETIL's files that are not TEI, which the grouping left out on
Tyler's instruction. Either:

- **(a)** include them in the 1b run, with all of Pandit but no group
  context; or
- **(b)** leave them for step 4's run on the 2026-10-08 data.

Recommended: (b). They gain nothing from the November data in particular,
and step 4 would have to re-check them anyway.

## Step 2: rows for three Atlases

Add the items of **E-bhāratīsampat, Sanskrit Wikisource and Jain
Quantum** to the master as new rows. **Sanskrit Documents** is left out
for now: it is too unruly. GRETIL's items are already in the master, as
its own rows.

**Which items.** Items the grouping classed as `work`. Its `ancillary`
and `unidentified` items are not e-texts and are left out. That makes
about 5,440 E-bhāratīsampat items, 3,490 Wikisource items and 1,770 Jain
Quantum items, about 10,700 rows in all.

**Columns**, from the registry's `data/grouping/master.csv`:

| master column | from |
| --- | --- |
| `Collection` | the Atlas's name |
| `Text Name` | the collection's own title (`Text Name`) |
| `Alternative Text Names` | the native-script title, and the registry title's canonical name where it differs |
| `Author Name` | the collection's author field |
| `Alternative Author Names` | the registry persons' canonical names, where they differ |
| `File Size (kb)` | as given |
| `Link 1 (main)` | `Link (online)` |
| `Work ID`, `Author ID` | the November grounding's confident IDs, as in 1a; otherwise `...` (author `—` where the registry has no author) |

**Staging.** The rows are first written to a staging file,
`data/staging/<atlas>.csv`, never straight into the master. Tyler reviews
them in batches (by hand now, through the review tool later). Accepted
batches are appended to the master. This is the one change to the master
that is not a matcher run, and it is reviewed like one.

**Open questions for this step:**

- An item may contain several works (a root text with commentaries). The
  master's convention for several IDs in one cell is "part to whole"
  (`... , 42078`). Several contained works need either another
  convention or one row per work.
- Whether the registry's variants belong in `Alternative Text Names`, or
  only the item's own titles.
- The order of rows: grouped by collection, as the master is now.

## Step 3: the grouping code is kept as evidence

`grouping-spec.md`, `scripts/grouping_*.py`, `agents/grouping/`,
`data/grouping/` and `make group-*` stay as they are, as the record of
how the November IDs and the Atlas rows were reached. Nothing new is
built on them, and they are not rerun. `scripts/grouping_to_master.py` and
`scripts/grouping_context.py` are one-offs in the same spirit.

## Step 4: both matchers on the 2026-10-08 data

Pandit changed little between the two exports (52 works and 72 persons
more, 5 works and 1 person gone). The grouping and the grounding are not
redone. Instead:

1. **Check the master's IDs.** List every ID in the master that is missing
   from the 2026-10-08 extract, and the reason where one can be seen (a
   merged or deleted record). Each one becomes a note and, where it
   points to a Pandit problem, a fix-list row. (One, Rasahṛdayatantra's
   41906, was already corrected to 42387.)
2. **`make match`** on every open slot, against the newest extract (the
   default once `--pandit` is dropped).
3. **`make research`** on the slots still open, with all of Pandit in
   context, in reviewable runs. If option (b) was chosen above, this
   includes the 417 GRETIL rows.
4. After each Pandit export that follows, the fix list's `done in Pandit`
   rows are checked against the new extract (see `review-spec.md`).

## Changes to the code, in short

- `agents/researcher.md`: all of Pandit in context; a section on reporting
  Pandit problems; a section on using a row's extra context, when given.
- `scripts/research_prep.py`: `--context <file>`; writes the compact
  Pandit rendering for the run; batches related rows together.
- The research validator and `scripts/research_apply.py`: the list of
  Pandit problems, merged into `data/pandit-fixes.csv`.
- `scripts/match.py`: possible Pandit duplicates go to the fix list as
  well.
- One-offs: `scripts/grouping_to_master.py` (written),
  `scripts/grouping_context.py` (step 1b), and the Atlas staging script
  (step 2).
- `README.md`: the fix list, and the two specs.
