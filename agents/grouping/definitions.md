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
