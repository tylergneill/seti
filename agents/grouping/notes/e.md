E-bhāratīsampat catalogues digitised books, and these are the ones with
Unicode text. An item is a book, or one volume or part of one.

- **Everything is in Devanāgarī**: title, author, editor and publisher, in
  the nominative and often with honorifics (`श्रीमदानन्दतीर्थभगवत्पादाचार्याः`,
  `महामहोपाध्याय-चन्द्रकान्त...`). Give canonical names in IAST stem form,
  without the honorifics, and keep the forms as written as variants.
  `आनन्दतीर्थ` is Madhva, and `शङ्कराचार्यः`, `शङ्करभगवत्पादाः` and
  `शङ्करः` are usually the Advaitin.
- **Fields are sometimes cut short** (`जीवानन्दविद्यासागरभट्टाचा`). A cut
  name is the same name.
- **The author field** usually names the author of the text, but may name
  a commentator, or the author of a modern study; and a field may hold
  two names joined by `च` or `तथा`. The editor field is the edition's
  editor. Decide for each name what it is.
- **The same work in many editions** is common: several printings of the
  Tarkasaṅgraha, of a Upaniṣad, of a play, from different publishers and
  years. Each edition is an item of the same work; `year` and `publisher`
  are the edition's, not the work's.
- **Parentheses describe the book**: a volume (`(प्रथमो भागः)`,
  `(द्वितीयभागः)`), a section (`चरकसंहिता (विमानस्थानम्)`), commentaries
  carried (`तर्कसङ्ग्रहः (टीकात्रयोपेतः)`: with three commentaries,
  unnamed), a larger work it belongs to, or what it answers
  (`कुमतखण्डनम् (तत्त्वोद्योतखण्डनस्य खण्डनम्)`). A volume or section is a
  division of the work, in `part_label`. A book with a commentary maps to
  the commentary and to its text; where the commentaries are not named,
  say so in `note`.
- **A title may be a commentary's own name** (`बालबोधिनी`, `सुगमा`), with
  the text it comments on only in the category or the author. Many works
  share such names; tell them apart by the text commented on.
- **Modern books** are here too: studies, textbooks, mathematics, essays
  in Sanskrit (`आधुनिकसाहित्यम्`, categories ending `सम्बद्धपुस्तकानि`, "books
  related to"). A new Sanskrit composition is a work, with its modern
  author. A study or textbook *about* a text, which does not carry it, is
  `ancillary`.
- **Categories** are the site's own subject tree, in Sanskrit. They tell
  namesakes apart: a `बालबोधिनी` under `न्यायदर्शनम्` is not one under
  `अलङ्कारशास्त्रम्`.
