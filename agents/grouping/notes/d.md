Sanskrit Documents is a site of typed e-texts, mostly stotras and other
devotional texts, with some major works and many modern compositions. An
item is one document.

- **Two titles.** The roman `title` is loosely transliterated, in several
  conventions at once (`Shri Ganeshakundatirtha Stotram`,
  `ku~njavihAryaShTakam 2`, which is ITRANS). The Devanāgarī
  `native_title` is the better guide. Both often begin with `Shri`, which
  is no part of the name.
- **The `item` names the document**: `doc_<topic>/<file>`, the file in
  ITRANS (`doc_vishhnu/dhruvakRRitaMviShNustotram`). A trailing number in
  the file or the title is the site's way of telling apart documents of
  one name.
- **Numbered namesakes are usually different works.** `Naradakritam 1
  Vishnu Stotram` and `Naradakritam 2` are different stotras that share
  a name, not two parts of one; so are `Kunjaviharyashtakam` and
  `Kunjaviharyashtakam 2`. Keep them apart unless the metadata says they
  are the same text. A number that is a range of chapters
  (`Brihatparasharahorashastram 21-30`, `adhyāyāḥ 34-42`) is a division of
  the work, in `part_label`.
- **`kṛtam`, `proktam`.** `Dhruvakritam`, `Devaih Kritam`, `Hayagrivaproktam`
  name who speaks or made the stotra within a purāṇa or tantra: that
  figure is a `speaker`. The name of the source text, where the title
  gives it (`Kurmapurana`, `from Bharatamanjari of Kshemendra`), goes in
  `context`, and the stotra's `part_of` names it.
- **The author field** names an author, a speaker, a modern composer, a
  translator, or whoever typed or contributed the document
  (`(Copyright) Pradipta Kumar Nanda, ... at gmail.com`). Strip contact
  details from names. `Traditional` and `Vedic Tradition` are no person:
  put them in `unplaced`. A modern contributor who typed or translated a
  text is no author of it.
- **Modern compositions** are many: new stotras and poems in Sanskrit by
  living authors. Each is a work by its composer. Pages in Marathi, Hindi
  or English, or with meanings, about a text are still the text where they
  carry it (`with meanings`); a page that is only explanation, a word
  list or a guide is `ancillary`.
- **Categories** are the site's topics (`devii`, `shiva`, `vishnu`,
  `ashtaka`, `kavacha`, `sahasranama`), and a document is often in
  several. They give the deity and the genre, which is what tells generic
  titles apart.
- **Stotras are many and their titles generic.** Follow the definitions:
  the same title is the same work unless the context (deity, source,
  ascription) says otherwise, and note that context.
