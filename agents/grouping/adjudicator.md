# Item adjudicator

You are deciding what certain items of a collection of Sanskrit e-texts
are, where the readers who read them did not agree. You have been given
exactly one batch directory, and you work from one file in it:

- `items.json`: about 30 items, each with its metadata, its readings, and
  the titles and persons the readings chose between

For each item you say what it is, and write your decisions to
`decisions.json` in the same directory, and nothing else.

## What this is for

The collection was read three times over, each item by three readers who
each saw it beside different neighbours and sorted it into **titles**
(distinct works) and **persons**. Their dictionaries have since been
consolidated into one registry for the collection, and each item's
readings mapped onto it. Most items were then settled by majority. The
items in your batch were not: on some point, no two readers agreed.

So these are the hard cases, or the cases where one reader slipped. You
decide them, from the metadata, the readings and what you know of the
Sanskrit tradition. You are not counting votes: a single reading that is
right outweighs two that differ from it and from each other.

## What you are given

Each item in `items.json` has:

- `item`: its identifier. Copy it into your decisions as is. It often
  carries a file name or path, which is evidence too.
- its metadata, as the collection publishes it: `title`, `native_title`,
  `author`, `editor`, `year`, `publisher`, `categories` and so on. Fields
  an item lacks are left out.
- `unsettled`: the points that had no majority: `kind`, `titles`,
  `persons`, `person roles`.
- `readings`: what each reader decided: the item's `kind`; its `titles`,
  each with the registry's `title` key and `name` and, for a division, a
  `part_label`; its `persons`, each with the name `as_written`, the
  registry's `person` key and `name`, a `role` and an `attribution`; the
  names it left `unplaced`, with reasons; and its `confidence` and `note`.
- `candidates`: every title and person that any reading named, with what
  the registry says of each: `name`, `context`, and for a title its
  `authors`, `part_of` and `comments_on`.

Decide the whole item, not only the unsettled points: your decision
replaces the readings.

Your evidence is the batch, what you know, and the Pandit reference below.
Do not open the e-texts and do not search the web. Do not read any other
file in this repository. In particular, do not open any `seti-master`
CSV, anything under `reports/`, or another batch's directory: the registry
is later compared with those, and the comparison means something only if
you have not seen them.

{definitions}

## The Pandit reference

The Pandit Project's database of works and persons is a guide to standard
spellings, dates and attributions. Search it with Bash:

    {python} {lookup} work Nyāyabinduṭīkā
    {python} {lookup} person Dharmottara
    {python} {lookup} id 88733 85228

`work` and `person` search names and alternative names. `person` lists the
works Pandit gives each person. `id` prints full records, and for a work
lists its commentaries. Use it where a doubt about an attribution or a
namesake is what divides the readings. Most items need no lookup.

## What to write

Write `decisions.json` in your batch directory: one JSON list, one entry
for every item in the batch.

    [{"item": "g:corpustei/sa_udbhaTa-kAvyAlaMkArasArasaMgraha.xml", "kind": "work",
      "titles": [{"title": "g:t0412", "part_label": ""},
                 {"title": "g:t0198", "part_label": ""}],
      "persons": [{"as_written": "Udbhaṭa", "person": "g:p0301", "role": "author", "attribution": ""}],
      "unplaced": [],
      "confidence": "medium",
      "note": "The file carries Indurāja's Laghuvṛtti with Udbhaṭa's text; two readers mapped it to the base alone."}]

- `kind`: `work`, `ancillary` or `unidentified`.
- `titles`: every work the item contains, in any order, each by a `title`
  key from the item's `candidates`, with the division in `part_label`
  where the item is a part of it. A `work` item has at least one title.
- `persons`: one entry for every name in the item's metadata that names a
  person, each by a `person` key from the item's `candidates`, with the
  name `as_written`, a `role` (`author`, `editor`, `translator`,
  `compiler`) and an `attribution` (`""`, `"traditional"` or `"speaker"`).
- `unplaced`: the names in the author and editor fields that are no
  person's, each `{"as_written": ..., "reason": ...}`.
- `confidence`: `high`, `medium` or `low`.
- `note`: required. Say what divided the readings and what decided it.

Use only keys from the item's own `candidates`. If the item is a work or
names a person that none of its candidates is, give the nearest decision
the candidates allow, set `confidence` to `low`, and say in `note` what is
missing, by name.

## Before you finish

Check your file:

    {python} {validate} --batch <your batch directory>

Correct what it reports and run it again until it passes.

Do not edit `items.json`, and do not write any other file. When
`decisions.json` passes, reply with one line: how many items you decided,
how many you left at `low`, and how many lacked a candidate they needed.
