# Grouping the collections: titles and persons, before Pandit

A spec for a Claude Code session that builds and runs this job. It is
written for the coordinating agent, which writes the sub-agent prompts and
scripts it calls for.

## What this is for

Sāgarasaṅgama's Atlases count **items**: files, wiki pages, catalogue
entries. To say how significant a collection is, and how much of it is
found nowhere else, we need to count **works** (here called *titles*) and
the **persons** behind them. In the end every title and person should be
grounded in Pandit, as SETI's rows are. But Pandit lacks much of what these
collections hold and holds some works and persons twice, so we do not start
there. We first sort the collections themselves into titles and persons,
from the ground up; that sorted registry is then much easier to ground in
Pandit, in a later job.

The sorting is done by agents who read every item's full metadata and use
their knowledge of the tradition, with Pandit as a guide. No mechanical
normalisation decides anything. Spelling variation is resolved by agents
who know that `Hemchandracharya`, `हेमचन्द्राचार्यः` and `Hemacandrasūri` are one
person, and that `Āgamaśāstra` and `Māṇḍūkyakārikā` are one work.

It runs in three passes:

1. **Reading, within a collection.** The collection is cut into shards, and
   each shard is read by one agent, which builds a small dictionary of the
   titles and persons in its shard and says what each item is.
2. **Consolidation, within a collection.** Agents compare the shards'
   dictionaries directly and consolidate them into one registry for the
   collection.
3. **Linking, across collections.** Agents compare the collection
   registries, each formed in its own collection's context, and consolidate
   them into one registry for everything, with our own IDs.

## Scope

The five Atlases, through Sāgarasaṅgama's search index
(`../../sagara-sangama/sagara-sangama/docs/data/search.json`), text-bearing
items only. Items marked `po` (scans without Unicode text) are out of scope.

| code | collection | items |
| --- | --- | --- |
| `g` | GRETIL (TEI files) | 782 |
| `j` | Jain Quantum (Sanskrit tier) | 1,961 |
| `e` | E-bhāratīsampat | 5,529 |
| `w` | Sanskrit Wikisource | 3,749 |
| `d` | Sanskrit Documents | 9,754 |

GRETIL goes first, as the test (see *Testing on GRETIL*). The order of the
rest does not matter to the method, since collections do not see each other
until pass 3. Of GRETIL only the items with a TEI file are taken: its
legacy-only files are mostly chapter files, pada indexes and analytic
renderings, of no consequence for coverage.

Evidence is the item's metadata, the agent's knowledge, and the Pandit
extract. Agents do **not** open the e-texts in this job. The first pages of
an e-text are often long front matter, and most items do not need it.
Reading the texts is for a later disambiguation step.

## What a title and a person are

These definitions are the heart of the job. Every sub-agent prompt carries
this section word for word, so that agents decide alike.

### Titles

A **title** is a distinct work, at roughly the level a catalogue like Pandit
records.

- **Group by name and context, exactly as with persons.** Items with the
  same title are the same work unless context says otherwise: a different
  author, a different date or tradition, a different deity or subject that
  shows they are different compositions. Without such evidence, group them,
  even when the title is generic (`Kṛṣṇāṣṭaka`, `Śivastotra`, `Tantrasāra`).
  Note in `context` what is known (deity, attribution, source), so that a
  later step can split the group further. Do not split on a hunch: needless
  splits are noise that a later step has to undo.
- **Different names can be one work.** `Tattvārthādhigamasūtra` and
  `Tattvārthasūtra`; `Śārīrakamīmāṃsā` and `Brahmasūtra`. Group them and keep
  every form seen as a variant.
- **Divisions are not titles.** A parvan, kāṇḍa, adhyāya, maṇḍala,
  ucchvāsa, volume, "Part 2" or Wikisource subpage belongs to its work. The
  item maps to the whole work, with the division in `part_label`.
  `Adiparvan` is the Mahābhārata, part `Ādiparvan`.
- **A work embedded in another is a title of its own** when it is known as a
  work in its own right: the Bhagavadgītā, the Viṣṇusahasranāma, the
  Lalitopākhyāna. Its entry names the larger work in `part_of`.
- **A commentary is a title of its own**, naming its base text in
  `comments_on`.
- **An item maps to every work it contains, and none of them is singled
  out as the main one.** An edition of the
  Nyāyavārttikatātparyaṭīkā maps to the Ṭīkā and also to the Nyāyasūtra, the
  Nyāyabhāṣya and the Nyāyavārttika, insofar as it carries or comments on
  them at length. An anthology maps to each work it names.
- **Versions and recensions are the same work.** Note the version on the
  item.

### Persons

A **person** is a human being, or a traditional author-figure, named in an
item's metadata.

- **One person, many spellings**: group them, and keep every form seen.
- **One name, several persons**: tell them apart by context: the date and
  tradition of the associated works, the discipline, commentarial
  relations. Vācaspati Miśra the Naiyāyika is not Vācaspati Miśra the
  Smārta jurist. Jain Quantum already marks some homonyms (`Yashovijay-2`);
  treat such marks as evidence, not as part of the name.
- **Roles belong to the item, not the person.** For every name in an item's
  author and editor fields, decide whether it names the author of a work
  the item carries, or the edition's editor, translator or compiler.
  Catalogues mix them: Jain Quantum's author field often names the editor
  (`Keshavlal Premchand` for a Tattvārthādhigamasūtra). A modern Sanskrit
  commentary is a work, and its writer is its author.
- **Authorship you know also goes on the title.** A title's `authors` are
  its author(s) as known, whether or not this item's metadata names them
  (Kālidāsa for the Raghuvaṃśa). The item's persons are the names its
  metadata gives, mapped and given roles.
- **No author is a finding.** `Traditional`, `Anonymous`, a blank field: no
  person is created for it.

### Attribution

One flag, on each title–author link and each item–person link, with two
values beside blank:

- *(blank)*: authorship as named, with no reason to qualify it;
- `traditional`: a conventional ascription to a real or semi-legendary
  author (Vyāsa for a purāṇa, Śaṅkarācārya for a popular stotra, Kālidāsa
  for the Śrutabodha);
- `speaker`: a deity, sage or character presented as the text's speaker or
  source (Śiva in a tantra, `devaiḥ kṛtam`, `yājñavalkyaproktam`).

The person entry itself stays one entry: Śaṅkara the commentator and
"Śaṅkarācārya" the stotra author are the same person, and the flag on the
link carries the difference.

### Item kind

Nearly every item is `work`. Two other values:

- `ancillary`: not a Sanskrit work: learning material, a modern essay, an
  index, an explanation in Hindi or Marathi, a site page;
- `unidentified`: the metadata does not say what the item is.

### Canonical forms

- Names are **IAST**, NFC, in **stem form** (`Kāvyaprakāśa`, not
  `Kāvyaprakāśaḥ`), with compounds written as one word, as Pandit does
  (`Nyāyakusumāñjali`, `Bṛhadāraṇyakopaniṣad`).
- Honorifics are dropped (`Śrī`, `Ācārya`, `Mahāmahopādhyāya`, `Pt.`) unless
  they are how the person is known. Jain naming elements that identify a
  monk (`-sūri`, `-vijaya`, `Gaṇi`, `Upādhyāya`) are kept.
- Where a work or person is in Pandit or widely known, use that standard
  spelling. Pandit is a guide, not the target: an obvious Pandit ID may be
  noted as `pandit_hint`, never invented, and never required.

### Confidence

`high`, `medium` or `low`, as in sane-diff:

- `high`: the metadata settles it, or something independent confirms it (a
  known attribution, the same author on both sides);
- `medium`: it follows from what you know, but nothing independent confirms
  it;
- `low`: a judgement call.

`low` is how a human finds the hard cases, so use it whenever it applies.
Every decision is applied, so the registry is complete, and every `low`
goes to the review list.

## Pass 1: reading (within a collection)

### Shards

`scripts/grouping_prep.py --collection <code> --run <run>` writes
`tmp/grouping/<run>/<code>/items.jsonl`, one line per item, with everything
the Atlas publishes about it: titles as written (roman and native), author
and editor fields, year, publisher, size, the online link, the local link
(below), and the Atlas's own category path as one more piece of metadata.

Then it cuts the collection into shards of about 200 items, in **catalogue
order**: the Atlas's own sequence, which often keeps a work's volumes
together (serial numbers, file paths). The order is not evidence and
decides nothing; it only decides which items an agent sees together, and
so which it can group directly. Groupings no single shard could see are
made in pass 2, whose windows are sorted by name, so the two passes see
the collection in two different orders.

So every item is read once. `--views 2` or `3` has it read again, in
**title order** (alphabetical, Devanāgarī and roman interleaved) and in
**author order** (alphabetical by the author field, items without one
spread through at random), each item then being seen beside different
neighbours, and pass 2 settling each item by majority. On GRETIL, three
readings scored no better against SETI than one, at three times the cost,
so one is the default. `--shard-size` sets the shard size.

Shards are written to `tmp/grouping/<run>/<code>/p1-<view>-NNN/items.jsonl`.

### The reader (`agents/grouping/reader.md`)

One sub-agent per shard, given the reader prompt and its one shard
directory. It writes `opinions.json`:

    {
      "persons": [
        {"key": "p1", "name": "Umāsvāti", "variants": ["Umaswati"],
         "context": "Jain, c. 4th–5th c., author of the Tattvārthasūtra",
         "pandit_hint": null, "confidence": "high"},
        {"key": "p2", "name": "Keśavalāla Premacanda", "variants": ["Keshavlal Premchand"],
         "context": "modern editor", "confidence": "medium"}
      ],
      "titles": [
        {"key": "t1", "name": "Tattvārthasūtra",
         "variants": ["Tattvārthādhigamasūtra", "तत्त्वार्थाधिगम सूत्रम्", "Tattvarthadhigam Sutram"],
         "authors": [{"person": "p1", "attribution": ""}],
         "part_of": null, "comments_on": null,
         "context": "Jain doctrinal sūtra",
         "pandit_hint": null, "confidence": "high"}
      ],
      "items": [
        {"item": "j:001070", "kind": "work",
         "titles": [{"title": "t1", "part_label": ""}],
         "persons": [{"as_written": "Keshavlal Premchand", "person": "p2",
                      "role": "editor", "attribution": ""}],
         "confidence": "high",
         "note": "The catalogue's author is the editor; the sūtra is Umāsvāti's."}
      ]
    }

- `key`s are local to the shard.
- An item's `titles` are every work it contains, in no particular order.
  Where the item is a division of a work, `part_label` names the division.
- Person `role` on an item: `author`, `editor`, `translator`, `compiler`.
- Every name in the author and editor fields is accounted for: mapped to a
  person, or listed in the item's `unplaced` with a reason ("Traditional",
  "unparseable").
- `part_of` and `comments_on` are canonical names (strings), not keys, since
  the target need not be in the shard. They are resolved to IDs in pass 3.
- `note` is required whenever a decision goes against the surface form: two
  different titles grouped, two identical ones split, an "author" made an
  editor.

Readers may consult the Pandit extract with `scripts/lookup.py work|person|id`
for standard spellings, dates and attributions. They must not open
`data/seti-master.csv` (see *Testing on GRETIL*).

## Pass 2: consolidation (within a collection)

Pass 1 leaves one dictionary per shard, each with its own keys, spellings
and judgements. Pass 2 turns them into one registry for the collection:
persons first, since titles are told apart partly by their authors.

### Dossiers

`scripts/grouping_dossiers.py --collection <code> --kind persons|titles`
gathers the shard entities that the opinions tie together into
**dossiers**, each a candidate for one entity:

- entities the readers gave the identical canonical name (exact string, as
  the agents wrote it);
- with several readings, entities tied by the same item: for persons, the
  readings of the same `as_written` name on the same item; for titles, the
  titles of an item to which every reading gave exactly one.

A dossier is a connected component of these ties. It holds every member
entity's full record and every item it covers, with the item's raw
metadata, so the consolidator reads the evidence and not just the
conclusions. Ties only gather candidates: a wrong reading can chain two
real entities into one dossier, and the consolidator splits them.

Dossiers are sorted by their most common canonical name and cut into
windows of about 100 that **overlap** by about 20, so that neighbours that
no tie connected, spelled differently but close in the alphabet, are still
seen together. A dossier too large for a window (a big generic title)
gets its own.

### The consolidator (`agents/grouping/consolidator.md`)

One sub-agent per window. It decides which members of its dossiers, and
which dossiers, are one entity, and writes `consolidated.json`:

    [{"entity": "e1", "kind": "title", "name": "Nyāyakusumāñjali",
      "members": ["p1-title-004:t3", "p1-catalogue-002:t7", "p1-author-005:t1"],
      "variants": [...], "authors": [...], "part_of": null, "comments_on": null,
      "context": "...", "pandit_hint": null, "confidence": "high",
      "note": ""}]

For titles, `authors` refer to the persons consolidated in 2a.

`scripts/grouping_apply.py` unites the windows' decisions. Where two
overlapping windows decided the same members differently, the decision is
taken as the union of the two and marked `low` for review.

### Items

With entities consolidated, the script maps each item's reading through
them, and the item is settled. With several readings, each item is settled
by majority: the titles named by most readings, and so for persons, roles
and attribution. Items without a majority on any of these go to the item
adjudicator (`agents/grouping/adjudicator.md`), in batches of about 30:
it sees the item's metadata and the competing consolidated entities, and
decides.

The collection registry goes to `data/grouping/collections/<code>/`:
`persons.csv`, `titles.csv` and `master.csv` in the final formats below,
with collection-scoped provisional keys (`g:p0012`, `g:t0034`) in place of
IDs, and `review.csv`.

With several readings, pass 2 also reports how often they agreed. It is a
cheap measure of how hard a collection is, and of where the prompts need
work.

## Pass 3: linking (across collections)

Once every collection has a registry, pass 3 consolidates them, persons
first, then titles, in the same way as pass 2: dossiers, overlapping
windows, a consolidator (`agents/grouping/linker.md`), and an apply step.

Every entity of every collection registry goes before a linker, including
those that share no spelling with any other collection. Finding the same
work under different names is the point of the pass, and no exact-string
tie can do it. Mallinātha's commentary on the Raghuvaṃśa is
`Raghuvaṃśasañjīvinī` in Jain Quantum's registry, `Sañjīvinī` in
E-bhāratīsampat's and `Raghuvaṃśasañjīvanī` in Wikisource's. The shared
variant `Sañjīvanī` ties the last two, and wrongly ties in Wikisource's
`Meghadūtasañjīvanī` as well, while Jain Quantum's entry shares no
spelling with any of them. A linker reading them side by side joins the
three and keeps the Meghadūta commentary apart.

- **Dossiers** gather entities from different collections with the
  identical canonical name or a shared variant, or the same `pandit_hint`.
  An entity tied to nothing is a dossier of its own. Ties only gather
  candidates, as in pass 2: the linker splits a wrong tie and joins
  entities no tie connected.
- **What a linker sees of an entity**: its collection registry row (name,
  variants, authors, attribution, `part_of`, `comments_on`, context,
  confidence, note) and, for each of its items, the collection's own
  catalogue line as `master.csv` keeps it (`Text Name`, `Native Text Name`,
  `Author Name`, `Editor Name`), with the item's `Part`. The registry row is
  what the agents concluded; the catalogue line is what the collection
  said, and the linker needs both. Variants are the collection's
  as-written titles mixed with forms the agents added, and some entries are
  inferences alone (Jain Quantum's Sañjīvinī comes from an item titled
  `Raghuvansh Mahakavya` with Mallinātha in its author field). No e-texts,
  no web, as before; the Pandit lookup tool as before.
- **Windows** are sorted by name and overlap, as in pass 2, so that
  entities spelled alike but tied by nothing (a different ending, a
  missing prefix) still meet. A large title dossier gets its own window;
  an entity with many items shows a sample of its catalogue lines, with the
  count.
- **The linker** applies the same rules as the consolidator. Each
  collection's entity brings its own context (authors, variants, the items
  around it), and that context is what tells a shared generic title apart,
  if anything does. The rule is unchanged: group on name and context, split
  on contextual evidence, note what is known. Within one collection, the
  registry's own decisions stand: the linker joins entities across
  collections, and splits a collection's entity only with a note and `low`
  confidence.
- **Persons first.** Title authors are resolved to the linked persons
  before the title windows are cut, so that the same author on two
  collections' entries is evidence the linker can see.
- **`part_of` and `comments_on`** are resolved to IDs where the target is in
  the registry, and left as names where it is not.

Then the IDs are minted, and the final files written.

Scale, from the five registries: 16,268 titles and 5,536 persons. By
shared spelling or Pandit hint, 5,592 titles fall into 1,981
cross-collection dossiers and 2,214 persons into 691; the remaining 10,676
titles and 3,322 persons are tied to nothing. Pass 2 cost about 1,000
tokens per title entity and 700 per person, so pass 3 is about 20M.
Dispatch the persons first and check their cost before the titles.

## IDs

Our own, five lowercase letters:

- persons: `p` followed by four letters (`pqmve`);
- titles: `t` followed by four letters (`tkzab`).

That is 26⁴ = 456,976 codes of each kind. Codes are drawn at random by
`scripts/grouping_ids.py`, not built from the name: a name-based code reads
as meaning, collides, and goes stale when the name is corrected, while the
ID must not change. Every code ever minted is kept in `data/grouping/ids.csv`
with its kind, name and date, and none is reused.

IDs are minted once, at the end of pass 3. Before then, keys are
provisional. After it they are stable: when a later run adds a collection,
its entities attach to existing IDs or receive new ones, and when two
entries turn out to be one, the older ID survives and the other is marked
`merged_into` in `ids.csv`, so that links into the registry never break
silently.

## Outputs

In `data/grouping/`, modelled on the SETI master.

**`master.csv`**, one row per item:

| column | holds |
| --- | --- |
| `Collection` | `GRETIL`, `Jain Quantum`, ... |
| `Item ID` | the Atlas's own identifier |
| `Text Name` | the title as the collection gives it |
| `Native Text Name` | the native-script title, where given |
| `Author Name` | the author field as given |
| `Editor Name` | the editor field as given |
| `File Size (kb)` | from the search index |
| `Link (online)` | the item in its collection |
| `Link (local)` | the locally cached text (below) |
| `Item Kind` | `work`, `ancillary`, `unidentified` |
| `Title IDs` | every title the item maps to, in order of name |
| `Title Names` | their canonical names, same order |
| `Part` | the division, where the item is a part of a title |
| `Person IDs` | the persons the item's metadata names |
| `Person Names` | their canonical names, same order |
| `Person Roles` | `author`, `editor`, `translator`, `compiler`, same order |
| `Attribution` | blank, `traditional` or `speaker`, same order |
| `Confidence` | `high`, `medium`, `low` |
| `Note` | the reason for any decision against the surface form |

Several values in one cell are separated by commas and follow the same
order across their columns, as SETI's author IDs follow the author names.

`Link (local)` is the URL Sāgarasaṅgama's search page builds for its `txt`
badge: the Atlas's own `serve_docs.py --fulltext` at
`http://localhost:<port>/text/<key>`, with the ports from `local-links.js`
(8001–8005) and the per-Atlas key that `search.js` uses (its comment beside
`localTxtKey` explains it). Blank when the Atlas published no `has_text`
for the item. Build it from the same published fields, never from an
Atlas's `data/`.

**`titles.csv`**: `Title ID`, `Name`, `Alternative Names`, `Author IDs`,
`Author Names`, `Attribution`, `Part Of`, `Comments On` (each an ID or, if
not in the registry, a name), `Context`, `Items`, `Collections`,
`Pandit Hint`, `Note`.

**`persons.csv`**: `Person ID`, `Name`, `Alternative Names`, `Context`
(dates, tradition, what distinguishes this person from namesakes),
`Roles Seen`, `Items`, `Collections`, `Pandit Hint`, `Note`.

**`review.csv`**: every `low` decision, every window conflict, every
`unidentified` item, with the pass it came from.

**`reports/<date>-grouping-report.md`**: per collection, items, titles,
persons as authors and as editors, items by kind, titles found in no other
collection and the bytes of text under them; the overlap between
collections, by title; the totals for the corpus; and pass 1 agreement
rates. Beside them, the first-pass mechanical figures from
`scripts/atlas_works.py`, for comparison only.

## Testing on GRETIL

GRETIL runs alone first, through passes 1 and 2. SETI gives Pandit IDs for
427 of its TEI items, which makes it the one collection where the grouping can
be checked against an independent hand-made answer. Readers and
consolidators must not open `data/seti-master.csv`; the comparison means
something only if the grouping is independent of it.

`scripts/grouping_eval.py` compares GRETIL's registry with SETI:

- for each SETI work (a row's last identified ID, so parvans count as the
  Mahābhārata), the title the grouping gives most of its items, and how
  many of its items carry that title: SETI gives an item one work, and the
  grouping every work it contains, so an item agrees when SETI's work is
  among its titles;
- SETI works the grouping splits (no one title on all their items) and
  SETI works it joins (two works answered by the same title);
- the number of distinct works for those items: SETI's, the titles that
  answer them, and the mechanical first pass's folded titles;
- every disagreement, listed for reading. Some will be SETI's or Pandit's
  rather than the grouping's: Pandit's duplicate records, or a Pandit
  record that bundles works the grouping keeps apart.

There is no pass mark. Tyler reads the results and a sample of the
registry, and the prompts are revised before the other collections run.
Lessons go into the prompts or the per-collection notes, never into a
message to one sub-agent.

## Running it

Dispatch follows **sane-diff** (`../../sane-diff`): its
`agents/dispatcher.md`, `scripts/workflow.py`, `scripts/pending.py` and
`scripts/agent_prompt.py`. That flow has been used heavily and works; copy
its shape. In particular:

- each sub-agent gets its prompt, built by script, and the path of one batch
  directory, and nothing else: no shared state, nothing from a sibling;
- a batch is done when its output file parses, so runs resume on their own;
- a failed batch is retried once and then reported, never done by the
  dispatcher and never filled with a placeholder;
- the run is finished even when some batches failed;
- each workflow runs min(16, CPUs − 2) agents; start several to reach
  `WORKERS` in flight;
- as sane-diff appends `input/notes.md` to its prompt, the grouping prompts
  append `agents/grouping/notes/<code>.md`: what is peculiar to the
  collection (Jain Quantum's author field naming editors; Sanskrit
  Documents' numbered stotra titles; Wikisource subpages as chapters;
  E-bhāratīsampat's many editions of one work).

One dispatcher prompt, `agents/grouping/dispatcher.md`, covers every
fan-out step with one table, as sane-diff's covers its runs:

| step | prompt | batch holds | each sub-agent writes |
| --- | --- | --- | --- |
| pass 1 | `reader.md` | `items.jsonl` | `opinions.json` |
| pass 2a, 2b | `consolidator.md` | `dossiers.json` | `consolidated.json` |
| pass 2c, with several readings | `adjudicator.md` | `items.json` | `decisions.json` |
| pass 3a, 3b | `linker.md` | `dossiers.json` | `consolidated.json` |

Make targets:

    make group-prep COLLECTION=g RUN=<run>                    # shards
    make group-read COLLECTION=g RUN=<run> WORKERS=10         # pass 1
    make group-consolidate COLLECTION=g RUN=<run> WORKERS=10  # pass 2, all steps
    make group-eval RUN=<run>                                 # GRETIL against SETI
    make group-link RUN=<run> WORKERS=10                      # pass 3, IDs, outputs
    make group-report RUN=<run>

`scripts/grouping_validate.py` runs after every step and fails loudly on an
item unaccounted for, a reference to a missing entity, a `pandit_hint`
absent from the extract, or a file that does not parse.

Scale, for planning: with one reading and shards of 200, pass 1 is about
110 sub-agent runs over the five collections (GRETIL 4, Jain Quantum 10,
Wikisource 19, E-bhāratīsampat 28, Sanskrit Documents 49). Pass 2 and 3
depend on how many dossiers there are; GRETIL will show. Look at GRETIL's
cost before committing to the rest.

## What to build, in order

1. `scripts/grouping_prep.py`; run it on GRETIL and read a shard of each
   view.
2. `agents/grouping/reader.md` (carrying *What a title and a person are*
   verbatim), `notes/g.md`, and the prompt, pending and workflow scripts
   after sane-diff's. `scripts/grouping_validate.py`. Read one GRETIL shard
   and validate before reading the rest.
3. `scripts/grouping_dossiers.py`, `agents/grouping/consolidator.md`,
   `agents/grouping/adjudicator.md`, `scripts/grouping_apply.py`. Finish
   GRETIL's pass 2.
4. `scripts/grouping_eval.py`. Stop and report to Tyler.
5. The other four collections, passes 1 and 2.
6. `agents/grouping/linker.md`, `scripts/grouping_ids.py`, pass 3 and the
   outputs.
7. `scripts/grouping_report.py`.

Tyler reviews outputs and diffs, as with the matchers, before they are
committed.

## Progress, 2026-10-14

Run `2026-10-13-one`, one reading per item.

| collection | items | pass 1: reading | pass 2: consolidation | registry |
| --- | --- | --- | --- | --- |
| GRETIL (TEI) | 782 | done, 4 shards | done | `data/grouping/collections/g/` |
| Jain Quantum | 1,961 | done, 10 shards | done | `data/grouping/collections/j/` |
| Sanskrit Wikisource | 3,749 | done, 19 shards | done | `data/grouping/collections/w/` |
| E-bhāratīsampat | 5,529 | done, 28 shards | done | `data/grouping/collections/e/` |
| Sanskrit Documents | 9,754 | done, 49 shards | done | `data/grouping/collections/d/` |

Pass 3 is done, over all five registries, with `agents/grouping/linker.md`,
`scripts/grouping_link.py` and `scripts/grouping_ids.py`.
`scripts/grouping_report.py` is not yet written.

Registries so far: GRETIL 720 titles and 294 persons; Jain Quantum 1,331
and 1,069; Wikisource 2,327 and 648; E-bhāratīsampat 3,234 and 2,228
(1,262 rows for review); Sanskrit Documents 8,656 and 1,297 (1,636 for
review). Neither needed the adjudicator: every item was settled by majority.

Against SETI, GRETIL's one-reading registry agrees on 97.2% of the 427
items SETI identifies (415): its SETI work is among the item's titles. It
splits 8 SETI works and joins 2. SETI has 337 works for those items, the
grouping 336 titles that answer them, the mechanical first pass 371
folded titles.

Sub-agent tokens, by collection:

| collection | reading | consolidation | total |
| --- | --- | --- | --- |
| GRETIL | 0.6M | 1.0M | 1.6M |
| Jain Quantum | 1.8M | 3.0M | 4.7M |
| Sanskrit Wikisource | 2.3M | 3.2M | 5.5M |
| E-bhāratīsampat | 3.6M | 8.0M | 11.6M |
| Sanskrit Documents | 5.4M | about 9M | about 14M |

Sanskrit Documents' titles ran in two sittings (29 windows, then 70 at
6.0M), so its consolidation figure is an estimate.

Pass 3 linked the 5,536 registry persons into 4,222 (51 windows, 4.4M
tokens; 660 at low, 4 window conflicts) and the 16,268 registry titles into
13,140 (159 windows, about 13M; 1,469 at low, 10 window conflicts). Of the
titles, 2,068 are in more than one collection: 1,222 in two, 689 in three,
136 in four and 21 in all five. The registry is in `data/grouping/`, with
21,775 items, 17,362 IDs minted in `ids.csv` and 6,265 rows for review.
Of 1,808 `Part Of` and 889 `Comments On`, 1,632 and 827 resolve to IDs.

Still to come: `scripts/grouping_report.py`.

### Decisions made along the way

- **GRETIL is its TEI files only** (782 of 1,123 items), on Tyler's
  instruction: the legacy-only files are chapter files, pada indexes and
  analytic renderings.
- **No main work.** An item maps to every work it contains, in no order;
  the `primary`, `base` and `contained` roles were dropped, and with them
  the `Title Roles` column. A division keeps its `part_label`.
- **One reading per item.** A first GRETIL run read every item three times
  (catalogue, title and author order), at 4.5M tokens. Re-scored without a
  main work, one reading with consolidation agreed with SETI as well as
  three (97.2–97.7% against 97.4%), at about a third of the cost. That
  run is kept as `2026-10-13`.
- **Consolidation windows** are about 100 dossiers overlapping by 20, and
  are written compact, without the edition's publisher and page count and
  without the item's note on person readings.
- **The comparison with SETI** finds, for each SETI work, the title most of
  its items carry, and counts an item as agreeing when it carries it.
- **What the agents wrote is kept**: `scripts/grouping_keep.py` copies each
  run's opinions, consolidations and decisions, with the items as the
  index had them and how the run was cut, to `data/grouping/runs/`
  (gitignored). `scripts/grouping_restore.py` rebuilds everything else
  from them; restoring GRETIL reproduced its registry byte for byte.
- **In pass 3 a collection's entity is indivisible.** A linker joins
  entities, and cannot split one, since that would mean dividing its items;
  where an entity seems to bundle two, it says so in a note at `low`. Two
  entities of one collection are joined only with a note, at `low`.
- **Pass 3 ties** are a shared canonical name or variant, ignoring case,
  between entities of different collections, or a shared `pandit_hint`. No
  dossier grew past 23 entities, so no tie needed capping.
- **Workflow scripts** hand each sub-agent the path of an assembled prompt
  file rather than the prompt itself, so that Claude Code can show the
  script when asking for approval.

## Later, not now

- Opening the e-texts, to split generic titles and confirm doubtful
  groupings.
- Grounding the registry in Pandit.
- SETI's own collections as a sixth registry in pass 3.
- E-bhāratīsampat's scans without text.
