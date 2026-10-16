# Reviewing SETI's changes: a ticket board

A spec for a review tool that lives in this repo. Not built yet.

## What this is for

Tyler vets every change to `data/seti-master.csv`. That includes each ID
a matcher writes, each candidate it leaves in the notes, and later the
thousands of rows the Atlases will add. The vetting also tests Pandit:
wherever Pandit turns out to be wrong, it gets fixed there now, and
`data/pandit-fixes.csv` collects what needs fixing.

Today that review happens in a diff tool, with the matchers' `applied` and
`notes` reports open beside it, and Pandit fixes are made by hand on
panditproject.org. This tool turns each item to be resolved into a
**ticket** on a board. An agent can **Prep** a ticket: it gathers the
evidence and proposes a decision. An agent can then **Execute** it: it
carries out the decision, whether that means keeping or reverting a change
in the master, or making an edit in Pandit through Tyler's own browser
session.

It is modelled on wbl (`~/Git/wbl`), Tyler's screenshot-driven backlog,
and borrows its design wherever the two jobs agree.

## What it borrows from wbl

- Standard library only (Python 3.11+), one static `ui.html` with no build
  step, and a thin JSON server over a module that holds the logic.
- The files on disk are the only state, and the CLI and server re-read them
  on every request. The board polls.
- Agents run as `claude -p` subprocesses started by the server, logging to
  a jobs folder, so a server restart never kills one.
- Prep is read-only and returns structured output against a JSON schema.
- Every button that starts an agent carries the token coin, shows the
  observed usage of past runs, and asks first when it acts on several
  tickets. A per-run dollar cap applies.
- The server binds to 127.0.0.1 and accepts only `application/json` POSTs.
- Nothing is committed for Tyler. Review ends in an ordinary commit.

What differs from wbl is where the work happens. SETI has one shared file,
not a repo per ticket, and some of its tickets end on a website, not in
git.

## Tickets

A ticket is one decision. There are three kinds.

**Master change.** One ID slot in one row of the master, as a matcher
left it:

- *applied*: a matcher wrote an ID into the slot (a row of a run's
  `applied` report). The decision is to keep or revert it.
- *noted*: a matcher left candidates for the slot (rows of a run's
  `notes` report: below threshold, ambiguous, or differing from the
  current ID). The decision is to apply one of them, set another ID, mark
  the slot as not in Pandit, or leave it.

**Pandit fix.** One row of `data/pandit-fixes.csv`: a record to correct,
merge, delete, or create in Pandit.

**Atlas rows** (later). A batch of new rows for the master from one
Atlas, cut small enough to read in one sitting, perhaps 20 rows. Each row
can be accepted, edited, or dropped.

Tickets that bear on the same thing are **linked**: the same master row,
or the same Pandit record or ID. The Bhavasaṃkrānti case is the model.
Master row 743 (GRETIL's *Bhavasaṅkrāntisūtra*) wrongly carries 88361.
Today's fill gives 88361 to row 213 (Nāgārjuna's *parikathā*). Pandit
fixes are needed for 88361's base text, for the name of 95212, and for a
missing record of the sūtra. That is five tickets, which the board shows
together, and which are best decided together.

### Where tickets come from

Tickets are derived from files that already exist. The board does not keep
a database of its own.

- **Master changes** come from the `reports/<stamp>-<tool>-applied.csv`
  and `-notes.csv` of runs whose changes are not yet committed.
  Tyler names the runs under review, e.g. on the board's header. A run's
  tickets close when every one is decided.
- **Pandit fixes** come from `data/pandit-fixes.csv`, one ticket per row
  whose `Status` is `open`.
- **Atlas rows** come from the staging file each Atlas import writes before
  anything reaches the master (see `matching-spec.md`).

Each ticket gets a stable ID (e.g. `M-213-work-1`, `P-88361-base`,
`A-ebs-0042`). Its state lives in one file, `review/decisions.csv`: the
ID, the decision, who decided (Tyler, or Tyler accepting an agent's
proposal), when, and a note. Prep's output lives in
`review/prep/<ID>.json`.

## Prep

Prep is read-only. It gathers what Tyler needs in order to decide, and
then proposes a decision with a confidence and its reasons:

- **Master change.**
  - The row and its neighbours. Every other master row with the same ID,
    name, or link stem.
  - The Pandit records involved, and their commentaries and authors, from
    `scripts/lookup.py`.
  - The e-text's header, fetched from its link. The header usually names
    the edition, the author, and the section, as GRETIL's headers did
    for the Bhavasaṃkrānti texts.
  - For a row that the grouping covered, its registry group.
- **Pandit fix.** The record as it now stands in Pandit, read live from
  panditproject.org, since the extract may be stale. The exact edit to
  make: field, old value, new value. For a new record, the values to
  create it with, the duplicates to check for, and the records that
  should then point to it.
- **Atlas rows.** For each row, whether to take it, with its IDs and the
  evidence, as the research agents give it.

Prep may add to `data/pandit-fixes.csv` when it finds a new problem in
Pandit, as the research agents do. That opens a new linked ticket.

## Execute

Execute carries out a decision that Tyler has made or accepted. It writes
the decision to `review/decisions.csv` first, and only then acts.

- **Master change.** Execute edits the slot in `data/seti-master.csv`. It
  keeps the ID, reverts it to the value it had before the run, or writes
  the chosen ID, `...`, or `—`. This is mechanical and needs no agent.
  The master is one file, so edits to it are serialised under a lock,
  never parallel. Executed changes stay uncommitted. A
  **Commit reviewed** action commits the master together with the
  decisions log, with a message that summarises them.
- **Pandit fix.** An agent drives Tyler's Chrome, using Claude in
  Chrome, in a session where Tyler is already signed in to Pandit. The
  agent never handles credentials: if the session is signed out, it stops
  and asks Tyler to sign in. It opens the record, makes the prepared edit,
  and stops before saving. The board then shows the filled form, as a
  screenshot, beside the intended change. Tyler confirms, and the agent
  saves. One edit is made per confirmation, and nothing is saved without
  a confirmation. The agent then reads the record back, and the ticket
  records what was changed and when.
  - The fix list's `Status` goes from `open` to `done in Pandit`. It
    becomes `confirmed` when an export shows the change.
  - A record that cannot be edited as planned is set back to `open`, with
    the reason.
- **Atlas rows.** Accepted rows are appended to the master as one batch,
  under the same lock, and they stay uncommitted like any other master
  change.

## Closing the loop with Pandit exports

A fix made in Pandit reaches SETI only with the next export (see
panditya's `data/manual_cleaning.md`). After each new export, a check
compares every `done in Pandit` fix with the new extract. It marks the
fix `confirmed` when the extract agrees, and reopens it when not. Master
slots that waited on a Pandit fix, such as a record yet to be created,
become open slots again for the matchers.

## Not in scope

- Making Pandit edits without a confirmation per save.
- Any change to the master that does not go through a ticket.
- Multi-user use: this is for Tyler's machine. wbl's notes on reaching it
  over an SSH tunnel apply unchanged.

## Open questions

- Whether this tool should be a SETI-specific copy of wbl's pieces, or a
  second kind of project inside wbl itself, with SETI's tickets supplied
  by an adapter.
- How Pandit's edit forms behave under browser automation: autocomplete
  fields for persons and works, and multi-valued fields. This needs a
  manual trial on one record before Execute is written.
- Whether an *applied* ticket that Tyler leaves undecided should block a
  run's commit, or be committed as accepted by default.
