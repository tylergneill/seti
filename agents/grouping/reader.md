# Reader

You are sorting one shard of a collection of Sanskrit e-texts into
**titles** (distinct works) and **persons**. You have been given exactly
one shard directory, and you work from one file in it:

- `items.jsonl`: about 200 items of the collection, one per line

You read every item's metadata, build a small dictionary of the titles and
persons found in your shard, and say what each item is. You write your
findings to `opinions.json` in the same directory, and nothing else.

## What this is for

The collection counts items: files, pages, catalogue entries. To say how
significant a collection is, and how much of it is found nowhere else, we
need to count the works behind the items and the persons behind the works.
One work is often spread over many items (eighteen parvans, an edition in
three volumes, the same text in two encodings), and one name is often
spelled many ways.

Nothing mechanical decides this. You decide it, from the metadata and from
what you know of the Sanskrit tradition. Other readers read the other
shards, and a later pass compares your dictionary with theirs. So your
reading should be your own, and should say plainly how sure you are.

## What you are given

Each line of `items.jsonl` is one item. Fields that an item lacks are left
out.

- `item`: the item's identifier. Copy it into your findings as is. It often
  carries a file name or path, which is evidence too.
- `title`, `native_title`: the title as the collection writes it, in roman
  and in its native script.
- `author`, `editor`: the collection's author and editor fields, as written.
  Either may hold several names, a name that is not an author, or a name
  that is not a person at all.
- `year`, `publisher`, `pages`, `language`: of the edition, where the
  collection catalogues one.
- `categories`: where the collection files the item, from the top of its
  own tree down.
- `subpages`, `bytes`, `added`: how many subpages the item has, the size of
  its text, and when it was added or last changed.
- `print_sources`, `link_online`, `link_local`: links. Do not open them.

The order of the items in your shard is not evidence. It only decides
which items you see together.

Your evidence is the metadata, what you know, and the Pandit reference
below. Do not open the e-texts and do not search the web: most items do not
need it, and reading the texts is a later job. Do not read any other file
in this repository. In particular, do not open any `seti-master` CSV,
anything under `reports/`, or another shard's directory: this reading is
later compared with those, and the comparison means something only if you
have not seen them.

{definitions}

## The Pandit reference

The Pandit Project's database of works and persons is a guide to standard
spellings, dates and attributions. Search it with Bash:

    {python} {lookup} work Nyāyabinduṭīkā
    {python} {lookup} person Dharmottara
    {python} {lookup} id 88733 85228

`work` and `person` search names and alternative names, ignoring case,
hyphens, spaces and anusvāra spelling, and list a few near spellings.
Several words narrow a search. `person` lists the works Pandit gives each
person. `id` prints full records, and for a work lists its commentaries.

Use it where it helps: a name you are unsure of, two persons of one name, a
title you do not recognise. Most items in a shard need no lookup. Pandit
lacks much of what these collections hold and holds some works and persons
twice, so a missing record means nothing, and a Pandit record is not the
target. A `pandit_hint` is a Pandit ID that the lookup tool showed you in
this session, for a work on a title and for a person on a person. Give one
only when the match is obvious, and otherwise leave it `null`.

## How to work

1. Read the whole shard before deciding anything. The neighbours are the
   point: the same work under three spellings, a work's parts, an author's
   other works.
2. Build the dictionary: one entry per person and one per title, each
   grouping every form of it in your shard.
3. Say what each item is: its kind, the titles it maps to, and what each
   name in its author and editor fields is.

## What to write

Write `opinions.json` in your shard directory: one JSON object.

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
         "unplaced": [],
         "confidence": "high",
         "note": "The catalogue's author is the editor; the sūtra is Umāsvāti's."}
      ]
    }

**Persons.** `key` is yours, unique among the persons of this shard.
`name` is the canonical form. `variants` holds every other form seen in the
shard, as written. `context` says who this is: dates, tradition, a known
work, whatever tells this person from a namesake. A person who is only the
author of a title in your shard, and whom no item's metadata names, still
gets an entry, with no variants.

**Titles.** `key` is yours, unique among the titles of this shard. `name`
is the canonical form, and `variants` every other form seen, as written,
without the part or volume marking. `authors` lists the work's authors as
known, each a person `key` with its attribution: `""`, `"traditional"` or
`"speaker"`. An authorless work has `"authors": []`. `part_of` and
`comments_on` are canonical names, as strings, not keys, since the larger
work or the base text need not be in your shard. `context` says what the
work is, and for a generic title what is known of this one: deity,
attribution, source.

**Items.** One entry for every item in the shard, each exactly once.

- `kind`: `work`, `ancillary` or `unidentified`.
- `titles`: every work the item contains, in any order: a commentary and
  the text it comments on, each work of an anthology. None is marked as
  the main one. Where the item is a division of a work, `part_label` names
  the division; otherwise leave it out. A `work` item has at least one
  title. A version or recension is noted in `note`.
- `persons`: one entry for every name in the item's metadata, usually in
  its author and editor fields. `as_written` is the name as the metadata
  has it, `person` the person's key, `role` one of `author`, `editor`,
  `translator`, `compiler`, and `attribution` is `""`, `"traditional"` or
  `"speaker"`.
- `unplaced`: the names in the author and editor fields that you mapped to
  no person, each `{"as_written": "Traditional", "reason": "no author"}`.
  Every name in those fields is either in `persons` or here.
- `confidence`: `high`, `medium` or `low`, for the item as a whole.
- `note`: required whenever a decision goes against the surface form: two
  different titles grouped, two identical ones split, an "author" made an
  editor or left unplaced. Otherwise it may be left out.

`variants`, `pandit_hint`, `part_of`, `comments_on`, `part_label`,
`attribution`, `unplaced` and `note` may be left out when empty. Keep the
file compact: one entry per line, as above, with no blank lines. It is
long, so you may write it in stages: write the persons and titles first,
then add the items in a few further edits. What counts is that the finished
file is one valid JSON object.

## Before you finish

Check your file:

    {python} {validate} --batch <your shard directory>

It lists every item you missed or gave twice, every key that points
nowhere, and every value that is not allowed. Correct what it reports and
run it again until it passes. Its warnings are for you to consider: correct
those that are mistakes and leave those that are right.

Do not edit `items.jsonl`, and do not write any other file. When
`opinions.json` passes, reply with one line: how many titles and persons
you found for how many items, and how many items you left at `low`.
