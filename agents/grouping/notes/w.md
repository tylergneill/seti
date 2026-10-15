Sanskrit Wikisource is a wiki. An item is a page: sometimes a whole work,
sometimes one chapter of it, sometimes a page that is no work at all.

- **Titles are in Devanāgarī**, in the nominative (`कादम्बरी`,
  `न्यायसूत्राणि`, `आत्मबोधोपनिषत्`). Give canonical names in IAST stem
  form as usual, and keep the Devanāgarī as a variant.
- **There is no author field.** The author, where the page gives one, is
  in the title in parentheses (`देवीशतकम् (आनन्दवर्धनकृतम्)`,
  `राजेन्द्रकर्णपूरः (शम्भुविरचितः)`) or in a category
  (`शङ्कराचार्यविरचितानि स्तोत्राणि`). Map such a name as a person, with
  `as_written` as the page has it. A category's ascription to Śaṅkara of a
  stotra is `traditional`. Otherwise authorship comes from what you know,
  and goes on the title only.
- **Parentheses also describe the page**: a commentary carried
  (`मेघदूतम् (वल्लभदेवव्याख्यासमेतम्)`, `(व्याख्यासहितम्)`, `(समूलम्)`),
  a source (`गायत्रीसहस्रनामस्तोत्रम् (देवीभागवतम्)`: a stotra from the
  Devībhāgavata), a recension or reading (`(विस्वरपाठः)`), an extent
  (`(सर्गाः १-४)`). A page with a commentary maps to the commentary and
  to its text.
- **Chapters as pages.** A slash marks a subpage
  (`शतपथ ब्राह्मणम्/काण्डम् १३/अध्यायः २/ब्राह्मण ३`), and so do a
  trailing number or division (`पञ्चतन्त्रम् ०४`,
  `तन्त्रालोकः पञ्चविंशतितममाह्निकम्`, `समराङ्गणसूत्रधार अध्याय ७४`,
  `आर्यमञ्जुश्रीमूलकल्पम्-भागः ३`). Each is a division of its work, with
  the division in `part_label`. `subpages` says how many subpages a page
  has under it: such a page is usually the whole work.
- **Pages that are no work** are `ancillary`: an author page
  (`सर्जकः:वेदव्यासः`), a project or help page (`प्रकल्पः:विषये`), a
  syllabus, a modern essay or news piece (`साहित्यम् > लेखाः`). A scan's
  index page (a title ending `.djvu` or `.pdf`) maps to the work scanned.
- **Categories** are the wiki's own, in Sanskrit, and many pages have
  several. `असम्बद्धवर्गीकृतम्` means the page was filed nowhere in
  particular, and says nothing; a category under it (`बौद्धदर्शनम्`,
  `बृहत्स्तोत्ररत्नाकरः`) does say something.
- **Stotras are many and their titles generic.** Follow the definitions:
  the same title is the same work unless the context (deity, source,
  ascription) says otherwise, and note that context.
- **Spellings slip** (`विवेक्कचूडामणि भाष्याम्`). Restore the standard
  form.
- **`print_sources`** are links to scans; a link's own text may name the
  book. Do not open them.
