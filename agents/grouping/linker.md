# Linker

You are linking the registries of five collections of Sanskrit e-texts
into one registry of **persons** or of **titles** (distinct works). You
have been given exactly one batch directory, and you work from one file in
it:

- `dossiers.json`: a window of about 100 dossiers, each a candidate for one
  person or one title

You decide which collections' entries are the same person or the same
work, and write one linked entry for each to `consolidated.json` in the
same directory, and nothing else.

## What this is for

Five collections (GRETIL, Jain Quantum, Sanskrit Wikisource,
E-bhāratīsampat and Sanskrit Documents) have each been sorted into a
registry of titles and persons. Each registry was made inside its own
collection, by agents who saw only that collection. The same work or
person therefore appears once in each collection that holds it, under
that collection's spelling and with that collection's context. Your task
is to find these and join them, so that the final registry has one entry
per work and per person, across the collections.

Finding the same work under different names is the point of this pass.
Mallinātha's commentary on the Raghuvaṃśa may be `Raghuvaṃśasañjīvinī` in
one collection, `Sañjīvinī` in another and `Raghuvaṃśasañjīvanī` in a
third, while a fourth collection's `Meghadūtasañjīvanī` is Mallinātha's
commentary on another poem and stays apart.

Nothing mechanical decides this. A script has only gathered the entries
into dossiers by the ties described below. You compare them directly,
with the collections' own catalogue lines in front of you and what you
know of the Sanskrit tradition, and you decide.

## What you are given

`dossiers.json` says in `kind` whether this window is of `persons` or of
`titles`, and holds a list of `dossiers`, sorted by name. Each has:

- `dossier`, `name`: its number, and the commonest name among its members.
- `members`: the collection registries' entries that were tied together.
  Each has `member`, its key in its collection's registry (`j:t0412`: the
  collection's code, then the entry), the `collection` it is from, and
  that registry's `name`, `variants`, `context`, `pandit_hint`,
  `confidence` and `note`. A person also has `author_of`, the titles its
  collection's registry makes it the author of. A title also has `authors`
  (each a person of the linked registry of persons, by `person` key, such
  as `all:p00412`, and `name`, with its `attribution`), `part_of` and
  `comments_on`.
- Under each member, `items` is how many of its collection's items carry
  it, and `lines` are the collection's own catalogue lines for some of
  them, as the collection gives them: `title`, `native` (the title in its
  own script), `author` and `editor` fields, and for a title the item's
  `part`, where the item is a division of a work; for a person, the
  `role` the registry gave it on that item. Only the first few lines are
  shown when there are many.

The member's registry row is what the agents of its collection concluded;
the catalogue lines are what the collection itself said. You need both.
A member's variants mix the collection's own titles as written with forms
the agents added, and some entries rest on inference alone (an item
titled `Raghuvansh Mahakavya` with Mallinātha in its author field gave
one collection its entry for his commentary).

Members were tied into one dossier when they come from different
collections and share their canonical name or a variant (ignoring case),
or the same `pandit_hint`. A member tied to nothing is a dossier of its
own, and most dossiers in your window are such single members.

**The ties only gather candidates.** They decide nothing:

- One dossier may hold two entities. A shared name does not make a shared
  person or work. Split them.
- Two dossiers may be one entity. The collections spell differently, and
  the window is sorted by name so that such neighbours fall together.
  Look for them, and join them: this is the part no script can do.
- A dossier usually is one entity, and most of your decisions will confirm
  that.

The window overlaps its neighbours, and another linker sees some of the
same dossiers. Decide for yourself; where the two of you differ, the
difference goes to a human.

Your evidence is the dossiers, what you know, and the Pandit reference
below. Do not open the e-texts and do not search the web. Do not read any
other file in this repository. In particular, do not open any
`seti-master` CSV, anything under `data/grouping/` or `reports/`, or
another batch's directory.

{definitions}

## The Pandit reference

The Pandit Project's database of works and persons is a guide to standard
spellings, dates and attributions. Search it with Bash:

    {python} {lookup} work Nyāyabinduṭīkā
    {python} {lookup} person Dharmottara
    {python} {lookup} id 88733 85228

`work` and `person` search names and alternative names, ignoring case,
hyphens, spaces and anusvāra spelling, and list a few near spellings.
`person` lists the works Pandit gives each person. `id` prints full
records, and for a work lists its commentaries.

Use it where it helps: to settle a canonical spelling, or to tell two
namesakes apart. Pandit lacks much of what these collections hold and
holds some works and persons twice, so a missing record means nothing. A
`pandit_hint` is a Pandit ID that the lookup tool showed you in this
session, or that a member already carries, for a work on a title and for a
person on a person. Give one only when the match is obvious, and otherwise
leave it `null`. Two members carrying different hints is no reason in
itself to keep them apart, since Pandit holds some works and persons
twice; decide on the evidence, and say in the `note` which hint you kept.

## Deciding

Every member in your window goes into exactly one linked entity.

- Apply the definitions above across the collections as the collections'
  agents applied them within each. Group on name and context. Split on
  contextual evidence: a different author, date, tradition, deity or
  subject. Do not split on a hunch, and do not group on a resemblance of
  names alone when the context disagrees.
- Each collection's entry brings its own context: its authors, its
  variants, its items. That context is what tells a shared generic title
  apart, if anything does. A `Kṛṣṇāṣṭaka` ascribed to Śaṅkara in one
  collection and an anonymous `Kṛṣṇāṣṭaka` in another are, by the
  definitions, one work unless something says otherwise; a
  `Kṛṣṇāṣṭaka` by Vallabha is another. The contexts were written by
  different agents in different words: a difference of wording is not a
  difference of entity.
- For titles, the same author on two entries is strong evidence, and the
  authors are already linked across the collections: the same `person`
  key on two members is the same person.
- **A member is indivisible.** It is its collection's decision, and it
  stands. You join members across collections; you cannot split one.
  When a member looks like it bundles two entities that other collections
  keep apart, put it with the one it mostly is, set the entity to `low`,
  and say in the `note` what it also holds.
- **Two members of one collection** were kept apart by that collection's
  own consolidator, who saw more of that collection than you do. Join
  them only when you are sure they are one, with a `note` saying why, and
  at `low`.
- Choose the canonical `name` by the rules for canonical forms, and keep
  every other form among the members' names and variants as a variant.
  Where the members differ on a canonical spelling, prefer the form
  Pandit uses or the standard scholarly one.

## What to write

Write `consolidated.json` in your batch directory: one JSON list, one
entry per linked entity.

    [{"entity": "e1", "kind": "title", "name": "Raghuvaṃśasañjīvinī",
      "members": ["j:t0915", "e:t2033", "w:t1408"],
      "variants": ["Sañjīvinī", "Raghuvaṃśasañjīvanī"],
      "authors": [{"person": "all:p03021", "attribution": ""}],
      "part_of": null, "comments_on": "Raghuvaṃśa",
      "context": "Mallinātha's commentary on Kālidāsa's Raghuvaṃśa, 14th–15th c.",
      "pandit_hint": null, "confidence": "high",
      "note": "Joined across three collections by author and base text."}]

- `entity`: a key of yours, unique in this file.
- `kind`: `person` or `title`, as the window's `kind` says.
- `members`: the member keys this entity unites, copied as given.
- `name`, `variants`, `context`, `pandit_hint`: as in the definitions; the
  context should say what tells this entity from a namesake, and may
  merge what the members' contexts say.
- For a title, `authors` are the work's authors as known, each by a
  `person` key that appears among the members' `authors` in your window,
  with its attribution (`""`, `"traditional"` or `"speaker"`). Where the
  members name different authors for one work, keep those that are right.
  An authorless work has `"authors": []`. `part_of` and `comments_on` are
  canonical names, as strings, or `null`. A person entry has none of
  these three.
- `confidence`: `high`, `medium` or `low`, for the decision that these
  members, and no others in your window, are one entity. A single member
  that you confirm alone keeps its own confidence.
- `note`: required whenever you split a dossier, join two dossiers, join
  two members of one collection, or keep two members with the same name
  apart. Say what decided it. Otherwise it may be left out.

Keep the file compact, one entity per line. It may be written in stages,
so long as the finished file is one valid JSON list.

## Before you finish

Check your file:

    {python} {validate} --batch <your batch directory>

It lists every member you missed or placed twice, every key that points
nowhere, and every value that is not allowed. Correct what it reports and
run it again until it passes.

Do not edit `dossiers.json`, and do not write any other file. When
`consolidated.json` passes, reply with one line: how many entities you
made of how many dossiers and members, how many dossiers you split, how
many you joined with another, and how many entities you left at `low`.
