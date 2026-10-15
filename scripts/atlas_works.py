"""How many distinct works stand behind each Sāgarasaṅgama Atlas? A rough count.

An Atlas counts *items*: files, pages, catalogue entries. A reader asking how
significant a collection is wants *works*. The two differ in both directions:
one work is often split over several items (eighteen parvans, "Part 1" and
"Part 2", a text's plain and analytic renderings), and several items with the
same title may still be different works (Sanskrit Documents' numbered
"Kavacham 1", "Kavacham 3" are usually different stotras).

This script brackets the answer with three measures per collection, each
cheaper and rougher than the next would be:

  1. items         text-bearing entries, as Sāgarasaṅgama's search index has them
  2. title keys    distinct normalised titles within the collection, computed
                   twice: "strict" keeps numbers, "folded" drops volume and part
                   markers and all numerals. Folded merges real parts of one
                   work but also merges numbered namesakes, so the truth for
                   most collections lies between the two.
  3. Pandit works  distinct Pandit work IDs among the items whose title matches
                   a Pandit work name exactly after normalisation. A floor:
                   Pandit lacks most stotras, modern compositions and Jain
                   prakaraṇas, and exact matching misses variant titles.

For GRETIL there is ground truth: SETI already ties 1,037 GRETIL files to
Pandit IDs by hand, and the GRETIL Atlas's items carry the same file paths.
The calibration section compares measures 2 and 3 with that truth.

For GRETIL, then, measure 2 can be checked: where SETI's IDs are known, true
works run at about 0.85 per folded title, because GRETIL splits works by
chapter under titles the folding cannot join (parvans, kāṇḍas, Yogācārabhūmi's
bhūmis). Take that as the size of folded's remaining overcount in collections
split the same way; Sanskrit Documents, split rather into namesake stotras,
errs the other way.

It then measures overlap between collections by title key (and by Pandit ID
where both sides match), which says how much of each collection is found
nowhere else among the five, and how much SETI's smaller collections add;
asks the same question in bytes; and counts editions where an Atlas
catalogues year or editor (E-bhāratīsampat, Jain Quantum).

Inputs (read-only):
  ../../sagara-sangama/sagara-sangama/docs/data/search.json  all five Atlases' items
  ../../sagara-sangama/atlases/gretil-atlas/docs/data/tree.json  GRETIL file paths
  data/seti-master.csv                                        SETI, with Pandit IDs
  ../panditya/data/*-extracted-entities-cleaned.csv           the Pandit extract

Output: a printed report, plus reports/<date>-atlas-works-items.csv with
every item's keys and match, for spot-checking.

    python3 scripts/atlas_works.py
    python3 scripts/atlas_works.py --show-clusters j 30   # largest folded clusters in Jain Quantum

Self-contained on purpose (standard library only, its own small
Devanāgarī→IAST transliterator) so it runs with the system python3.
"""

import argparse
import collections
import csv
import datetime
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, Pandit, split_cell, OPEN  # noqa: E402

GIT = ROOT.parent.parent
SEARCH = GIT / "sagara-sangama" / "sagara-sangama" / "docs" / "data" / "search.json"
GRETIL_TREE = GIT / "sagara-sangama" / "atlases" / "gretil-atlas" / "docs" / "data" / "tree.json"
MASTER = ROOT / "data" / "seti-master.csv"

ATLAS_NAMES = {"d": "Sanskrit Documents", "w": "Sanskrit Wikisource", "e": "E-bhāratīsampat",
               "j": "Jain Quantum", "g": "GRETIL"}
ORDER = "dwejg"


# ---------------------------------------------------------------- transliteration

_CONS = dict(zip("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहळ",
                 "k kh g gh ṅ c ch j jh ñ ṭ ṭh ḍ ḍh ṇ t th d dh n p ph b bh m y r l v ś ṣ s h ḷ".split()))
_VOWELS = dict(zip("अआइईउऊऋॠऌएऐओऔऑ", "a ā i ī u ū ṛ ṝ ḷ e ai o au o".split()))
_MATRAS = dict(zip("ािीुूृॄॢेैोौॉ", "ā i ī u ū ṛ ṝ ḷ e ai o au o".split()))
_OTHER = {"ं": "ṃ", "ः": "ḥ", "ँ": "ṃ", "ऽ": "", "ॐ": "oṃ", "।": " ", "॥": " ", "़": ""}
_OTHER.update(zip("०१२३४५६७८९", "0123456789"))
_VIRAMA = "्"
DEVANAGARI = re.compile("[ऀ-ॿ]")


def deva_to_iast(s):
    """Plain Devanāgarī → IAST. Enough for titles: no Vedic accents, and
    nukta letters fold to their base consonant."""
    out = []
    chars = list(unicodedata.normalize("NFC", s).replace("़", ""))  # drop nukta
    i = 0
    while i < len(chars):
        c = chars[i]
        if c in _CONS:
            out.append(_CONS[c])
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if nxt in _MATRAS:
                out.append(_MATRAS[nxt])
                i += 1
            elif nxt == _VIRAMA:
                i += 1
            else:
                out.append("a")       # inherent vowel
        elif c in _VOWELS:
            out.append(_VOWELS[c])
        elif c in _OTHER:
            out.append(_OTHER[c])
        else:
            out.append(c)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------- normalisation

# Whole words that mark a part or volume rather than name a work. Matched after
# transliteration and casefolding, with or without a nominative ending.
_PART_WORDS = ("bhāga khaṇḍa khand khanda part vol volume saṃpuṭa samput sampuṭa "
               "pūrvārdha uttarārdha prathama dvitīya tṛtīya caturtha pañcama ṣaṣṭha "
               "saptama aṣṭama navama daśama maṇḍala mandala adhyāya adhyaya adhy kāṇḍa no "
               "pariccheda uddyota stavaka ucchvāsa ucchvasa sarga āhnika ahnika skandha chapter chapters").split()
_ROMAN = re.compile(r"^[ivxl]+$")
# Where a title goes on to describe its edition or commentary, the work's own
# name ends: "Sāṃkhyakārikā with Gauḍapāda's Bhāṣya", "Dhvanyāloka (also known as ...)".
_DESCRIPTION = re.compile(r"\s(?:with|by|a commentary|also known as|plain text|sanskrit reconstruction)\b.*$")
_PART_RE = re.compile(r"^(?:%s)(?:ḥ|m|ṃ|a|ā)?$" % "|".join(map(re.escape, _PART_WORDS)))
# The same markers fused onto the end of a title word: "kāvyānuśāsanabhāgaḥ".
_PART_SUFFIX_RE = re.compile(r"(?:prathama|dvitīya|tṛtīya|caturtha|pūrva|uttara)?(?:bhāga|khaṇḍa)(?:ḥ|m|ṃ)?$")
# Before a stop, anusvāra and every class nasal are one sound written several
# ways (Sāṅkhya, Sāṃkhya, Samkhya); fold them all to n. Elsewhere ṃ is m.
_STOPS = "kgcjṭḍtdpb"
_NASAL = re.compile(f"[ṅñṇnmṃ](?=[{_STOPS}])")


def to_iast(title):
    """Titles arrive in Devanāgarī, IAST, or loose roman. Only Devanāgarī is
    converted; roman is passed through for the later folding to deal with."""
    return deva_to_iast(title) if DEVANAGARI.search(title) else title


def title_key(iast, fold_parts):
    """A matching key for a title: casefold, drop parentheses and file
    extensions, optionally drop part markers and numerals, remove spaces and
    punctuation, fold nasals, reduce the nominative ending to a stem, and
    finally strip diacritics so that 'Siksasamuccaya' meets 'Śikṣāsamuccaya'.

    Returns '' for keys too short to be trusted (under four letters)."""
    s = unicodedata.normalize("NFC", iast).casefold()
    s = re.sub(r"\.(pdf|txt|htm|djvu)\b", " ", s)
    s = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", s)       # parentheticals: commentary, source, volume
    s = s.replace("_", " ")
    if fold_parts:
        s = s.split("/")[0]          # Wikisource subpages: "Praśnopaniṣat/tṛtīyaḥ praśnaḥ"
        s = _DESCRIPTION.sub("", s)
    words = re.split(r"[\s,;:/\-–—]+", s)
    if fold_parts:
        words = [w for w in words if not (_PART_RE.match(w) or _ROMAN.match(w))]
        words = [re.sub(r"\d+", "", w) for w in words]
        words = [_PART_SUFFIX_RE.sub("", w) if len(w) > 8 else w for w in words]
    s = "".join(words)
    s = re.sub(r"[^\w]", "", s)                       # remaining punctuation, avagraha marks
    s = re.sub(r"^(śrī|sri|shri|shree|atha)+", "", s)  # honorific or opening particle
    s = _NASAL.sub("n", s).replace("ṃ", "m")
    # Nominative singular → stem: -aḥ -am -aṃ → -a; -iḥ → -i; -uḥ → -u; -t → -d (upaniṣat).
    s = re.sub(r"(?<=a)[ḥmṃ]$", "", s)
    s = re.sub(r"ḥ$", "", s)
    s = re.sub(r"t$", "d", s)
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))
    return s if len(s) >= 4 else ""


def author_key(name):
    return title_key(to_iast(name), fold_parts=False) if name else ""


# ---------------------------------------------------------------- loading

def load_items():
    """Text-bearing items from Sāgarasaṅgama's search index.

    'po' marks a PDF-only item (a scan without Unicode text); those are left
    out, so the item totals equal each Atlas's published text_count. The title
    used is the Devanāgarī one ('n') where an Atlas gives both, since Sanskrit
    Documents' and Jain Quantum's roman titles are loose Hindi-style spellings."""
    data = json.loads(SEARCH.read_text(encoding="utf-8"))
    items = []
    for x in data["items"]:
        if x.get("po"):
            continue
        raw = x.get("n") or x["t"]
        iast = to_iast(raw)
        items.append({
            "atlas": x["a"],
            "id": x.get("i", ""),
            "title": x["t"],
            "native": x.get("n", ""),
            "iast": iast,
            "author": x.get("au") or "",
            "bytes": int(x.get("b") or 0),
            "year": x.get("y") or "",
            "editor": x.get("ed") or "",
            "strict": title_key(iast, fold_parts=False),
            "folded": title_key(iast, fold_parts=True),
        })
    return items


_PANDIT_TAIL = re.compile(r"\s(?:on|and|-|–)\s.*$")


def pandit_index(pandit):
    """Folded title key → Pandit work IDs, over each work's name and its akas.

    Pandit sometimes names a work descriptively ("Bhāṭṭadīpikā on Jaimini's
    Mīmāṃsāsūtras", "Viṃśatikā and autocommentary"), so the part before
    ' on ' / ' and ' / ' - ' is indexed too, when it is long enough (8+
    letters) not to be a bare genre word like "Ṭīkā"."""
    idx = collections.defaultdict(set)
    for wid, w in pandit.works.items():
        for name in [w["name"]] + w["aka"]:
            name = to_iast(name)
            k = title_key(name, fold_parts=True)
            if k:
                idx[k].add(wid)
            head = _PANDIT_TAIL.sub("", name)
            if head != name:
                k = title_key(head, fold_parts=True)
                if len(k) >= 8:
                    idx[k].add(wid)
    return idx


def person_keys(pandit):
    """Pandit person ID → set of normalised name keys (name and akas)."""
    return {pid: {author_key(n) for n in [p["name"]] + p["aka"] if author_key(n)}
            for pid, p in pandit.persons.items()}


def match(item, idx, pandit, pkeys):
    """Exact folded-key match against Pandit, narrowed by author when the key
    is shared by several works. Returns (sorted candidate IDs, how)."""
    cands = idx.get(item["folded"], set())
    if not cands:
        return [], "none"
    if len(cands) == 1:
        return sorted(cands), "unique"
    akeys = {author_key(a) for a in re.split(r",| and ", item["author"]) if a.strip()} - {""}
    if akeys:
        narrowed = {wid for wid in cands
                    if any(pkeys.get(aid, set()) & akeys for aid in pandit.works[wid]["author_ids"])}
        if narrowed:
            return sorted(narrowed), "author" if len(narrowed) == 1 else "ambiguous"
    return sorted(cands), "ambiguous"


def work_unit(cands):
    """One representative ID per match, so that an ambiguous match (often the
    same work entered twice in Pandit) counts once and consistently across
    collections."""
    return min(cands, key=int) if cands else None


def seti_rows():
    with open(MASTER, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def seti_work_id(row):
    """The work-level Pandit ID of a SETI row: the last identified slot, since
    several slots run from part to whole ('... , 42078' is a parvan of the
    Mahābhārata, counted here as the Mahābhārata)."""
    parts, _ = split_cell(row["Work ID"])
    ids = [p.strip() for p in parts if p.strip() and p.strip() != OPEN]
    return ids[-1] if ids else None


# ---------------------------------------------------------------- report

def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "–"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--show-clusters", nargs=2, metavar=("ATLAS", "N"),
                    help="print the N largest folded-title clusters of one Atlas (d w e j g) and exit")
    args = ap.parse_args()

    items = load_items()
    pandit = Pandit()
    idx = pandit_index(pandit)
    pkeys = person_keys(pandit)
    for it in items:
        it["cands"], it["how"] = match(it, idx, pandit, pkeys)
        it["work"] = work_unit(it["cands"])

    if args.show_clusters:
        a, n = args.show_clusters[0], int(args.show_clusters[1])
        groups = collections.defaultdict(list)
        for it in items:
            if it["atlas"] == a:
                groups[it["folded"]].append(it)
        for k, g in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:n]:
            print(f"{len(g):4d}  {k or '(no key)'}   e.g. " + " | ".join(x["title"] for x in g[:4]))
        return

    by_atlas = collections.defaultdict(list)
    for it in items:
        by_atlas[it["atlas"]].append(it)

    # --- per-collection measures
    print("Distinct works behind each Atlas (text-bearing items only)\n")
    hdr = f"{'collection':22s} {'items':>6s} {'strict':>7s} {'folded':>7s} {'Pandit-matched':>15s} {'Pandit works':>12s}"
    print(hdr)
    print("-" * len(hdr))
    summary = {}
    for a in ORDER:
        its = by_atlas[a]
        strict = {x["strict"] or f"#{x['id']}" for x in its}   # keyless items count as themselves
        folded = {x["folded"] or f"#{x['id']}" for x in its}
        matched = [x for x in its if x["work"]]
        works = {x["work"] for x in matched}
        summary[a] = dict(items=len(its), strict=len(strict), folded=len(folded),
                          matched=len(matched), works=len(works))
        print(f"{ATLAS_NAMES[a]:22s} {len(its):6d} {len(strict):7d} {len(folded):7d} "
              f"{len(matched):7d} ({pct(len(matched), len(its)):>4s}) {len(works):12d}")
    tot = len(items)
    print(f"{'all five':22s} {tot:6d} {len({x['strict'] for x in items if x['strict']}):7d} "
          f"{len({x['folded'] for x in items if x['folded']}):7d} "
          f"{sum(1 for x in items if x['work']):15d} {len({x['work'] for x in items if x['work']}):12d}")
    print("\n  strict/folded: distinct normalised titles, keeping vs dropping numbers and part markers")
    print("  Pandit works: distinct Pandit IDs among exact title matches (a floor)\n")

    # --- GRETIL calibration against SETI's hand-made IDs
    print("GRETIL calibration against SETI\n")
    tree = json.loads(GRETIL_TREE.read_text(encoding="utf-8"))
    files_by_title = {}
    for w in tree["works"]:
        files_by_title.setdefault(w["title"], []).append(w["files"])
    seti = seti_rows()
    seti_by_path = {}
    for r in seti:
        if r["Collection"] == "GRETIL":
            path = re.sub(r"^https?://[^/]+/gretil/", "", r["Link 1 (main)"].strip())
            seti_by_path[path] = r
    # search.json's GRETIL 'i' is one legacy path; the tree lists every file of an item.
    tree_files = {}
    for w in tree["works"]:
        for f in w["files"]:
            tree_files[f] = w["files"]
    g = by_atlas["g"]
    truth = {}
    for it in g:
        for f in tree_files.get(it["id"], [it["id"]]):
            if f in seti_by_path:
                wid = seti_work_id(seti_by_path[f])
                if wid:
                    truth[it["id"]] = wid
                break
    joined = [it for it in g if it["id"] in truth]
    true_works = {truth[it["id"]] for it in joined}
    folded_joined = {it["folded"] for it in joined}
    agree = sum(1 for it in joined if truth[it["id"]] in it["cands"])
    wrong = sum(1 for it in joined if it["cands"] and truth[it["id"]] not in it["cands"])
    print(f"  GRETIL Atlas items with a SETI Pandit ID: {len(joined)} of {len(g)}")
    print(f"  among them: distinct true works {len(true_works)}, distinct folded titles {len(folded_joined)}")
    print(f"  mechanical match: right {agree} ({pct(agree, len(joined))}), "
          f"wrong {wrong} ({pct(wrong, len(joined))}), none {len(joined) - agree - wrong}")
    ratio = len(true_works) / len(joined) if joined else 0
    print(f"  works per item where truth is known: {ratio:.2f}; "
          f"true works per folded title: {len(true_works) / len(folded_joined):.2f}")
    # Best estimate for the whole of GRETIL: the hand-identified works, plus one
    # per folded title among the remaining items that no identified item shares.
    rest = {it["folded"] or f"#{it['id']}" for it in g if it["id"] not in truth} - folded_joined
    print(f"  GRETIL estimate: {len(true_works)} identified works + {len(rest)} further folded titles "
          f"= ~{len(true_works) + len(rest)} works\n")

    # --- overlap between collections, by folded title
    print("Overlap by folded title (how much of each is found in no other Atlas)\n")
    keysets = {a: {x["folded"] for x in by_atlas[a] if x["folded"]} for a in ORDER}
    seti_other = [r for r in seti if r["Collection"] != "GRETIL"]
    keysets["S"] = {title_key(r["Text Name"], True) for r in seti_other} - {""}
    names = dict(ATLAS_NAMES, S="SETI (non-GRETIL)")
    print(f"{'collection':22s} {'titles':>7s} {'unique':>7s}  shared with")
    for a in ORDER + "S":
        others = set().union(*(keysets[b] for b in keysets if b != a))
        uniq = keysets[a] - others
        shared = "  ".join(f"{b}:{len(keysets[a] & keysets[b])}" for b in ORDER + "S" if b != a)
        print(f"{names[a]:22s} {len(keysets[a]):7d} {len(uniq):7d} ({pct(len(uniq), len(keysets[a])):>4s})  {shared}")
    allkeys = set().union(*keysets.values())
    print(f"\n  union of all: {len(allkeys)} folded titles\n")

    # The same question asked in bytes: how much of each collection's text sits
    # under titles that no other collection (SETI included) has?
    print("Share of each collection's text under titles found in no other\n")
    for a in ORDER:
        others = set().union(*(keysets[b] for b in keysets if b != a))
        total = sum(x["bytes"] for x in by_atlas[a])
        uniq = sum(x["bytes"] for x in by_atlas[a] if x["folded"] and x["folded"] not in others)
        if total:
            print(f"{ATLAS_NAMES[a]:22s} {uniq / 1e6:8.1f} of {total / 1e6:8.1f} MB ({pct(uniq, total)})")
        else:
            print(f"{ATLAS_NAMES[a]:22s}   (no per-item sizes in the search index)")
    print("  sizes are the search index's per-item bytes, in each Atlas's own unit\n")

    # Editions, where an Atlas records them: distinct (title, year, editor).
    print("Editions, where year or editor is catalogued\n")
    for a in ORDER:
        its = [x for x in by_atlas[a] if x["year"] or x["editor"]]
        if its:
            eds = {(x["folded"], x["year"], author_key(x["editor"])) for x in its}
            print(f"{ATLAS_NAMES[a]:22s} {len(its):5d} items with edition data -> {len(eds)} distinct "
                  f"editions of {len({x['folded'] for x in its})} titles")
    print()

    # --- overlap by Pandit work, where matched
    print("Overlap by Pandit work (matched items only)\n")
    worksets = {a: {x["work"] for x in by_atlas[a] if x["work"]} for a in ORDER}
    worksets["S"] = {seti_work_id(r) for r in seti_other} - {None}
    worksets["g"] |= true_works                                 # GRETIL: add SETI's hand IDs
    for a in ORDER + "S":
        others = set().union(*(worksets[b] for b in worksets if b != a))
        uniq = worksets[a] - others
        print(f"{names[a]:22s} {len(worksets[a]):6d} works, {len(uniq):5d} found in no other")
    print(f"\n  union: {len(set().union(*worksets.values()))} Pandit works "
          f"(of {len(pandit.works)} in the extract)")

    # --- per-item dump for spot checks
    out = ROOT / "reports" / f"{datetime.date.today()}-atlas-works-items.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["atlas", "id", "title", "native", "author", "strict", "folded",
                     "pandit_candidates", "match_how", "pandit_name", "seti_truth"])
        for it in items:
            wr.writerow([it["atlas"], it["id"], it["title"], it["native"], it["author"], it["strict"],
                         it["folded"], " ".join(it["cands"]), it["how"],
                         pandit.name_of(it["work"]) if it["work"] else "", truth.get(it["id"], "")])
    print(f"\nper-item table: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
