#!/usr/bin/env python3
"""Mechanical matcher: identify Pandit works and authors for SETI rows by name.

A work match counts for most when Pandit agrees on the author too: the SETI
text name matches a Pandit work, the SETI author name matches a Pandit
person, and Pandit lists that person as the work's author. Names are tried
exactly, then normalised, then through alternative names, then fuzzily.

Confident matches are written into the master in place; the rest go to
reports/<date>-mechanical-notes.csv. Review the master as a diff.

  match.py                      # open slots ('...') only
  match.py --scope all          # every row; may replace IDs already there
  match.py --threshold 0.85 --dry-run
"""

import argparse
import re
from collections import defaultdict
from difflib import SequenceMatcher

from common import (AUTHOR_ID, DEFAULT_THRESHOLD, MASTER, NO_AUTHOR, OPEN, WORK_ID, Master, Pandit,
                    apply_proposals, norm, print_summary, proposal, split_cell, split_names)

# How much a name match is worth, before corroboration.
Q_EXACT = 1.0        # main name to main name, character for character
Q_NORMALISED = 0.97  # main name to main name after norm()
Q_ALIAS = 0.93       # an alternative name on either side
Q_SYNTHETIC = 0.8    # a name built from a commentary's base text, e.g. Hetubindu + ṭīkā
Q_SEGMENT = 0.8      # one part of a 'Whole: Part' text name
Q_AFFIX = 0.77       # one name begins or ends with the other
FUZZY_CUTOFF = 0.7
FUZZY_CAP = 0.92     # a fuzzy match never outranks a normalised one

# What an uncorroborated match is worth.
W_UNIQUE_AUTHORLESS = 0.85  # neither side names an author, and the name is unique in Pandit
W_UNCORROBORATED = 0.6
W_AUTHOR_UNIQUE = 0.8       # author matched by name alone, name unique in Pandit
W_AUTHOR_AMBIGUOUS = 0.5
C_SOLE_AUTHOR = 0.75        # Pandit's only author for the work, though the names differ

MAX_SUGGESTIONS = 6  # per slot; the notes file shows the top three


class NameIndex:
    """Look names up among Pandit works or persons."""

    def __init__(self):
        self.exact = defaultdict(list)    # name -> [(id, quality)]
        self.normed = defaultdict(list)   # norm(name) -> [(id, quality, name)]
        self._by_length = None
        self._fuzzy_cache = {}

    def add(self, entity_id, name, quality):
        if not name:
            return
        if quality == Q_EXACT:
            self.exact[name].append(entity_id)
        self.normed[norm(name)].append((entity_id, min(quality, Q_NORMALISED), name))

    def count(self, name):
        """How many distinct entities carry this name as a main name or alias."""
        return len({eid for eid, q, _ in self.normed.get(norm(name), []) if q > Q_SYNTHETIC})

    def lookup(self, names, fuzzy=False):
        """names: [(name, quality cap)]. Returns {id: (quality, matched name, how)}."""
        found = {}

        def offer(eid, quality, matched, how):
            if eid not in found or quality > found[eid][0]:
                found[eid] = (quality, matched, how)

        for name, cap in names:
            # Say so when the match came from something other than the row's main name.
            source = {Q_ALIAS: f" (from SETI alternative name '{name}')",
                      Q_SEGMENT: f" (from part of the SETI name, '{name}')"}.get(cap, "")
            for eid in self.exact.get(name, []):
                offer(eid, min(Q_EXACT, cap), name, "exact name" + source)
            key = norm(name)
            for eid, quality, matched in self.normed.get(key, []):
                how = {Q_NORMALISED: "normalised name", Q_ALIAS: "Pandit alternative name",
                       Q_SYNTHETIC: "base text + commentary name"}[quality]
                offer(eid, min(quality, cap), matched, how + source)
            if fuzzy:
                for ref_key, score, how in self._fuzzy(key):
                    for eid, quality, matched in self.normed[ref_key]:
                        offer(eid, min(score, quality, cap), matched, how + source)
        return found

    def _fuzzy(self, key):
        if key in self._fuzzy_cache:
            return self._fuzzy_cache[key]
        if self._by_length is None:
            self._by_length = defaultdict(list)
            for ref in self.normed:
                self._by_length[len(ref)].append(ref)
        hits = []
        n = len(key)
        if n >= 4:
            matcher = SequenceMatcher(autojunk=False)
            matcher.set_seq2(key)
            for length, refs in self._by_length.items():
                # ratio = 2*matches/(n+length) can only reach the cutoff in this range
                if not (FUZZY_CUTOFF * n / (2 - FUZZY_CUTOFF) <= length <= n * (2 - FUZZY_CUTOFF) / FUZZY_CUTOFF):
                    affix_only = True
                else:
                    affix_only = False
                for ref in refs:
                    if ref == key:
                        continue
                    if length >= 4 and ((ref.startswith(key) and n >= 5) or key.endswith(ref)):
                        hits.append((ref, Q_AFFIX, "one name begins or ends with the other"))
                    if affix_only:
                        continue
                    matcher.set_seq1(ref)
                    if matcher.real_quick_ratio() >= FUZZY_CUTOFF and matcher.quick_ratio() >= FUZZY_CUTOFF:
                        ratio = matcher.ratio()
                        if ratio >= FUZZY_CUTOFF:
                            hits.append((ref, min(ratio, FUZZY_CAP), f"fuzzy {round(ratio * 100)}%"))
        self._fuzzy_cache[key] = hits
        return hits


def build_indexes(pandit):
    works, persons = NameIndex(), NameIndex()
    for wid, work in pandit.works.items():
        works.add(wid, work["name"], Q_EXACT)
        for aka in work["aka"]:
            works.add(wid, aka, Q_ALIAS)
        # 'Ṭīkā on Dharmottara's Nyāyabinduṭīkā' and bare 'Ṭīkā' are how Pandit
        # names many commentaries; SETI calls them by base text + commentary word.
        head = work["name"].split(" on ")[0].strip()
        if work["base_ids"] and " " not in head and (" on " in work["name"] or len(head) <= 12):
            for base_id in work["base_ids"]:
                base = pandit.works.get(base_id)
                if base:
                    works.add(wid, base["name"].split(" on ")[0] + head, Q_SYNTHETIC)
    for pid, person in pandit.persons.items():
        persons.add(pid, person["name"], Q_EXACT)
        for aka in person["aka"]:
            persons.add(pid, aka, Q_ALIAS)
    return works, persons


def work_queries(text_name, alt_names):
    queries = [(text_name, Q_EXACT)] + [(n, Q_ALIAS) for n in alt_names]
    if ": " in text_name:
        for segment in text_name.split(": "):
            queries.append((re.sub(r"^\d+\.\s*", "", segment).strip(), Q_SEGMENT))
    return queries


class Matcher:
    def __init__(self, master, pandit, scope, threshold):
        self.master, self.pandit = master, pandit
        self.scope, self.threshold = scope, threshold
        self.work_index, self.person_index = build_indexes(pandit)
        self.skipped_multi = 0

    def wanted(self, part):
        """Is this slot one the run should try to identify?"""
        part = part.strip()
        if self.scope == "all":
            return part not in ("", NO_AUTHOR)
        return part == OPEN

    def match_row(self, r):
        m = self.master
        work_parts, _ = split_cell(m.get(r, WORK_ID))
        author_parts, _ = split_cell(m.get(r, AUTHOR_ID))
        author_names = [n for n in split_names(m.get(r, "Author Name")) if n != NO_AUTHOR]
        alt_author_names = split_names(m.get(r, "Alternative Author Names"))

        want_work = len(work_parts) == 1 and self.wanted(work_parts[0])
        if len(work_parts) > 1 and any(self.wanted(p) for p in work_parts):
            self.skipped_multi += 1

        # Which author slots line up with which names. A single slot takes
        # every name the row offers; several slots need a name each.
        if len(author_parts) == 1:
            slot_names = {0: [(n, Q_EXACT) for n in author_names] + [(n, Q_ALIAS) for n in alt_author_names]}
        elif len(author_parts) == len(split_names(m.get(r, "Author Name"))):
            names = split_names(m.get(r, "Author Name"))
            slot_names = {i: [(names[i], Q_EXACT)] for i in range(len(names)) if names[i] != NO_AUTHOR}
        else:
            slot_names = {}
        want_authors = [i for i in slot_names if self.wanted(author_parts[i]) and slot_names[i]]

        if not want_work and not want_authors:
            return []

        # In an open-slots run, IDs already in the row are evidence. In a run
        # over everything they are what is being checked, so they are not.
        trust = self.scope == "open"
        known_work = work_parts[0].strip() if trust and len(work_parts) == 1 and work_parts[0].strip() in self.pandit.works else None
        known_authors = {p.strip() for p in author_parts if trust and p.strip() in self.pandit.persons}
        seti_has_author = bool(author_names) or bool(known_authors)

        queries = work_queries(m.get(r, "Text Name"), split_names(m.get(r, "Alternative Text Names")))
        all_author_queries = [q for names in slot_names.values() for q in names]

        proposals = []
        for fuzzy in (False, True):
            works = {known_work: (Q_EXACT, self.pandit.name_of(known_work), "Work ID already in the row")} if known_work \
                else self.work_index.lookup(queries, fuzzy=fuzzy)
            slot_persons = {i: self.person_index.lookup(slot_names[i], fuzzy=fuzzy) for i in slot_names}
            pool = self.person_index.lookup(all_author_queries, fuzzy=fuzzy)
            for aid in known_authors:
                pool[aid] = (Q_EXACT, self.pandit.name_of(aid), "Author ID already in the row")

            work_scores = self.score_works(works, pool, seti_has_author)
            proposals = []
            if want_work:
                for wid, (conf, basis) in sorted(work_scores.items(), key=lambda kv: -kv[1][0])[:MAX_SUGGESTIONS]:
                    proposals.append(proposal(r, WORK_ID, 0, wid, conf, basis, self.pandit.name_of(wid)))
            best_work = max(work_scores.items(), key=lambda kv: kv[1][0], default=(None, (0, "")))
            for i in want_authors:
                proposals += self.author_proposals(r, i, slot_persons[i], works, best_work, len(author_parts))

            # Stop before the fuzzy pass only when every slot has a confident
            # answer, and, where the slot already holds an ID, that ID is it.
            # Otherwise the fuzzy pass gets a chance to recognise the current ID.
            targets = ([(WORK_ID, 0, work_parts[0])] if want_work else []) + \
                      [(AUTHOR_ID, i, author_parts[i]) for i in want_authors]
            settled = all(
                any(p["field"] == f and p["position"] == i and p["confidence"] >= self.threshold
                    and (current.strip() == OPEN or p["suggested"] == current.strip()) for p in proposals)
                for f, i, current in targets)
            if settled:
                break
        return proposals

    def score_works(self, works, author_pool, seti_has_author):
        scores = {}
        for wid, (qw, matched, how) in works.items():
            work = self.pandit.works[wid]
            via = f"work: {how} '{matched}'"
            corroborating = [(author_pool[aid], aid) for aid in work["author_ids"] if aid in author_pool]
            if corroborating:
                (qa, a_matched, a_how), aid = max(corroborating)
                scores[wid] = (min(qw, qa), f"{via}; author: {a_how} '{a_matched}' ({aid}), listed in Pandit as its author")
                continue
            shared = self.work_index.count(matched)
            if not seti_has_author and not work["author_ids"] and shared == 1:
                scores[wid] = (qw * W_UNIQUE_AUTHORLESS, f"{via}; no author on either side; the only Pandit work of this name")
                continue
            if not seti_has_author:
                why = "SETI names no author" + (f"; Pandit gives {self.author_list(work)}" if work["author_ids"] else "")
            elif work["author_ids"]:
                why = f"author not corroborated: Pandit gives {self.author_list(work)}"
            else:
                why = "author not corroborated: Pandit gives none"
            if shared > 1:
                why += f"; {shared} Pandit works share this name"
            scores[wid] = (qw * W_UNCORROBORATED, f"{via}; {why}")
        return scores

    def author_list(self, work):
        return ", ".join(f"{self.pandit.name_of(a)} ({a})" for a in work["author_ids"])

    def author_proposals(self, r, slot, persons, works, best_work, n_slots):
        out = {}
        # Corroborated through any candidate work.
        for wid, (qw, w_matched, w_how) in works.items():
            for aid in self.pandit.works[wid]["author_ids"]:
                if aid in persons:
                    qa, matched, how = persons[aid]
                    conf = min(qw, qa)
                    if aid not in out or conf > out[aid][0]:
                        out[aid] = (conf, f"author: {how} '{matched}'; Pandit lists them as author of "
                                          f"'{self.pandit.name_of(wid)}' ({wid}), matched by {w_how}")
        # Pandit's only author for a confidently matched work, whatever the name.
        best_wid, (best_conf, _) = best_work
        if best_wid and best_conf >= self.threshold and n_slots == 1:
            sole = self.pandit.works[best_wid]["author_ids"]
            if len(sole) == 1 and sole[0] not in out:
                out[sole[0]] = (C_SOLE_AUTHOR, f"Pandit's only author for '{self.pandit.name_of(best_wid)}' ({best_wid}); "
                                               "name does not match the SETI author name")
        # By name alone.
        for aid, (qa, matched, how) in persons.items():
            if aid in out:
                continue
            shared = self.person_index.count(matched)
            weight = W_AUTHOR_UNIQUE if shared == 1 else W_AUTHOR_AMBIGUOUS
            note = "the only Pandit person of this name" if shared == 1 else f"{shared} Pandit persons share this name"
            out[aid] = (qa * weight, f"author: {how} '{matched}'; no work corroborates; {note}")
        ranked = sorted(out.items(), key=lambda kv: -kv[1][0])[:MAX_SUGGESTIONS]
        return [proposal(r, AUTHOR_ID, slot, aid, conf, basis, self.pandit.name_of(aid)) for aid, (conf, basis) in ranked]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--master", default=MASTER)
    ap.add_argument("--pandit", help="cleaned Pandit extract (default: the newest in ../panditya/data)")
    ap.add_argument("--scope", choices=["open", "all"], default="open",
                    help="open: only '...' slots. all: every row, replacing IDs that a confident match contradicts")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--collection", help="only rows of this collection")
    ap.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    args = ap.parse_args()

    master = Master(args.master)
    pandit = Pandit(args.pandit)
    print(f"master: {master.path.name}, {len(master.rows)} rows")
    print(f"pandit: {pandit.path.name}, {len(pandit.works)} works, {len(pandit.persons)} persons")

    matcher = Matcher(master, pandit, args.scope, args.threshold)
    proposals = []
    for r in range(len(master.rows)):
        if args.collection and master.get(r, "Collection") != args.collection:
            continue
        proposals += matcher.match_row(r)

    counts, paths = apply_proposals(master, proposals, "mechanical", args.threshold,
                                    overwrite=args.scope == "all", dry_run=args.dry_run)
    print_summary(counts, paths, args.threshold)
    if matcher.skipped_multi:
        print(f"{matcher.skipped_multi} rows with several Work ID slots not attempted")
    if args.dry_run:
        print("dry run: nothing written")


if __name__ == "__main__":
    main()
