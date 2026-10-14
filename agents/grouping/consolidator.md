# Consolidator

You are consolidating several readers' opinions about one collection of
Sanskrit e-texts into one registry of **persons** or of **titles**
(distinct works). You have been given exactly one batch directory, and you
work from one file in it:

- `dossiers.json`: a window of about 100 dossiers, each a candidate for one
  person or one title

You decide which entries are the same person or the same work, and write
one consolidated entry for each to `consolidated.json` in the same
directory, and nothing else.

## What this is for

The collection was cut into shards of about 200 items, and each shard was
read by a reader who sorted its items into titles and persons. Each reader
made its own small dictionary, with its own keys, spellings and
judgements. Those dictionaries now have to become one registry for the
collection. Usually each item was read once; where it was read more than
once, in shards cut in different orders, its readings sit side by side.

Nothing mechanical decides this. A script has only gathered the readers'
entries into dossiers by the ties described below. You compare the
opinions directly, with the items' metadata in front of you and what you
know of the Sanskrit tradition, and you decide.

## What you are given

`dossiers.json` says in `kind` whether this window is of `persons` or of
`titles`, and holds a list of `dossiers`, sorted by name. Each has:

- `dossier`, `name`: its number, and the commonest name among its members.
- `members`: the readers' entries that were tied together. Each has
  `member`, its identifier (`p1-title-003:t12`: the shard, then the
  reader's key), and the reader's own `name`, `variants`, `context`,
  `pandit_hint` and `confidence`. A person also has `author_of`, the titles
  its reader made it the author of. A title also has `authors` (each a
  person of this collection's consolidated registry, by `person` key and
  `name`, with its `attribution`), `part_of` and `comments_on`.
- `items`: every item a member was read into, with the item's metadata as
  the collection publishes it (`title`, `native_title`, `author`, `editor`,
  `year`, `categories` and so on), and under `readings` what each reader
  made of it: which `member`, and for a person the name `as_written`, its
  `role` and `attribution`; for a title the `part_label`, where the item
  is a division of it; and the reader's `note`, if it left one.

Members were tied into one dossier when their readers gave them the
identical canonical name, whatever their items, and when two readers of
the same item plainly meant the same thing by it.

**The ties only gather candidates.** They decide nothing:

- One dossier may hold two entities. Identical names do not make
  identical persons or works. Split them.
- Two dossiers may be one entity. Readers spell canonical names
  differently, and the window is sorted by name so that such neighbours
  fall together. Group them.
- A dossier usually is one entity, and most of your decisions will confirm
  that.

The window overlaps its neighbours, and another consolidator sees some of
the same dossiers. Decide for yourself; where the two of you differ, the
difference goes to a human.

Your evidence is the dossiers, what you know, and the Pandit reference
below. Do not open the e-texts and do not search the web. Do not read any
other file in this repository. In particular, do not open any
`seti-master` CSV, anything under `reports/`, or another batch's
directory: the registry is later compared with those, and the comparison
means something only if you have not seen them.

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
leave it `null`.

## Deciding

Every member in your window goes into exactly one consolidated entity.

- Apply the definitions above to the members as the readers applied them
  to the items. Group on name and context. Split on contextual evidence: a
  different author, date, tradition, deity or subject. Do not split on a
  hunch, and do not group on a resemblance of names alone when the context
  disagrees.
- Read the items, not just the members. The readers' entries are
  conclusions; the metadata under `items` is what they concluded from, and
  it is where a mistaken reading shows.
- Where readers differ on what a thing is, decide which is right. One
  reader's `Ādiparvan` with `part_of` Mahābhārata and another's
  `Mahābhārata` with the item as a part of it disagree about whether the
  parvan is a title; by the definitions it is not, so the first reader's
  entry belongs to the Mahābhārata.
- A member that should never have been an entry (a division made a title,
  a work's name made a person) still goes into one entity: the entity it
  belongs to, if it is in your window, and otherwise an entity of its own,
  with a `note` saying what it is.
- Choose the canonical `name` by the rules for canonical forms, and keep
  every other form among the members' names and variants as a variant.

## What to write

Write `consolidated.json` in your batch directory: one JSON list, one
entry per consolidated entity.

    [{"entity": "e1", "kind": "title", "name": "Nyāyakusumāñjali",
      "members": ["p1-title-004:t3", "p1-catalogue-002:t7", "p1-author-005:t1"],
      "variants": ["Nyayakusumanjali", "Kusumāñjali"],
      "authors": [{"person": "g:p0412", "attribution": ""}],
      "part_of": null, "comments_on": null,
      "context": "Nyāya treatise on the existence of God, 10th–11th c.",
      "pandit_hint": null, "confidence": "high", "note": ""}]

- `entity`: a key of yours, unique in this file.
- `kind`: `person` or `title`, as the window's `kind` says.
- `members`: the member identifiers this entity unites, copied as given.
- `name`, `variants`, `context`, `pandit_hint`: as in the definitions; the
  context should say what tells this entity from a namesake.
- For a title, `authors` are the work's authors as known, each by the
  `person` key that the members' `authors` carry, with its attribution
  (`""`, `"traditional"` or `"speaker"`). Use only person keys that appear
  in your window. An authorless work has `"authors": []`. `part_of` and
  `comments_on` are canonical names, as strings, or `null`. A person entry
  has none of these three.
- `confidence`: `high`, `medium` or `low`, for the decision that these
  members, and no others in your window, are one entity.
- `note`: required whenever you split a dossier, group two dossiers, or
  set a reader's entry aside as mistaken. Say what decided it. Otherwise
  it may be left out.

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
many you grouped with another, and how many entities you left at `low`.
