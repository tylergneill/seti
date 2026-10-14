These are GRETIL's TEI files, one item per file. Its legacy files without
a TEI counterpart are not included.

- **File names are evidence.** A file is usually named
  `sa_<author>-<title>`, in GRETIL's ASCII encoding (`A I U` long vowels,
  `R` for ṛ, `z` for ś, `S` for ṣ, `T D N` retroflexes, `G` for ṅ, `J` for
  ñ, `M` for ṃ). The author in the file name may be missing from the
  author field. `-alt` marks another version of the same text, and `-comm`
  a file that carries a commentary.
- **The same work is often in several files**: two versions (`-alt`), a
  plain text and one with a commentary, a whole and its parts. Each file
  is an item of the same work.
- **Annotations in the author field** are evidence, not part of the name:
  `Dīpaṃkaraśrījñāna [= Atīśa]` gives a second name of one person, and
  `Śaṃkara (attrib.)` says the attribution is `traditional`. A field may
  hold two persons, or the name of a larger work and no person at all; a
  name that is no person's goes in `unplaced`.
- **Titles describe the file as well as the work**: `reconstructed text`,
  `fragment`, `(without the svārthānumāna-chapter)`, `with X's
  commentary`, a chapter range (`1-93`, `1, 2.1-144`), a book number
  (`Kāvyādarśa 3`). A version is the same work, noted in `note`. A range
  or number is a division, named in `part_label`. A file "with a commentary" maps to the commentary
  and to its base.
- **Categories** are GRETIL's own sections (`Śāstra > Philosophy ›
  Buddhist`, `Religious literature > Vaiṣṇava`). They tell namesakes
  apart: a Buddhist `Ratnāvalī` is not the play. `TEI without a legacy
  source` says nothing about the work.
