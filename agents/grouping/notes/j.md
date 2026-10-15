Jain Quantum catalogues scanned books, and these are the ones it files as
Sanskrit. An item is a book or one volume of a book.

- **Titles are loosely spelled.** The roman title is a Gujarati- or
  Hindi-style spelling without diacritics (`Gyansara`, `Suyagadam`,
  `Trishashti Shalaka Purushcharitam`). The Devanāgarī title is usually
  the better guide, but it too has slips (`हीतोपदेश`). Restore the
  standard form.
- **The author field is a list of everyone the catalogue connects with the
  book**, separated by commas: the author of the text, a commentator, the
  modern editor, a translator, the compiler of a series, sometimes an
  institution. There is no editor field. Decide for each name what it is:
  `Kalidas Makavi, Mallinath, Dharadatta Acharya, Janardan Pandey` on a
  Raghuvaṃśa is the poet, a commentator and two modern hands. A monk of
  the last century or two on an old text is usually its editor. An
  institution is no person, and goes in `unplaced`.
- **Homonym marks.** `Yashovijay-2` is the catalogue's way of telling two
  persons of one name apart. Treat the mark as evidence, not as part of
  the name. The same person may also be entered twice in one field
  (`Nyayavijay, Nyayvijay`).
- **Volumes.** `Part 01`, `Part 2`, `_02`, `Purvarddha` mark volumes of one
  book: the item is a division of the work, with the volume in
  `part_label`.
- **Words that describe the edition**: `Satik` or `Satic` (with a
  commentary), `Vrutti`, `Avchuri`, `Churni`, `Niryukti`, `Bhashya` (kinds
  of commentary), `Sanuvad` (with a translation), `Mul` (the bare text). A
  book of a text with its commentary maps to the commentary and to the
  text.
- **The Āgamas** appear under Prakrit names (`Suyagadam`), Sanskrit names
  (`Sutrakritang`) and series numbers (`Agam 39 Chhed 06 Mahanishith Sutra
  Shwetambar`). They are one work each. `categories` gives the canonical
  text an item is filed under (`Aṅga > Sūtrakṛtāṅga`); most items are
  filed under `Other works`, which says nothing.
- **Prakrit, Apabhraṃśa and Pali works are works**, as are the non-Jain
  ones here (a Raghuvaṃśa, Bhartṛhari's Śatakas). Name them in the
  standard scholarly form. A modern book in Hindi or Gujarati about a
  subject, with no old text in it, is `ancillary`.
- **Series and anthologies** (`Kavyamala`, `Shastra Sandesh Mala Part 08`,
  `Jain Katha Sangraha Part 05`) hold several works. Map the item to each
  work its metadata names. Where it names none, the collection itself is
  the title, and the volume goes in `part_label`.
- **`year` is the edition's**, not the work's.
