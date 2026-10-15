#!/usr/bin/env python3
"""Pass 3: link the five collection registries into one, with our own IDs.

Each collection's registry was formed in its own collection's context.
Pass 3 sets them side by side and consolidates them, persons first, then
titles, as pass 2 did within a collection: dossiers, overlapping windows,
a linker (agents/grouping/linker.md), and an apply step. Five steps, run
in this order, the fan-out steps between them:

  --step dossiers-persons  gather every person of every collection
                           registry into dossiers and cut windows,
                           tmp/grouping/<run>/all/p3a-NNN/dossiers.json
  --step persons           unite the linkers' decisions into all/persons.json
  --step dossiers-titles   the same for titles, p3b-NNN, with each title's
                           authors resolved to the linked persons
  --step titles            unite into all/titles.json
  --step registry          mint the IDs (grouping_ids.py) and write
                           data/grouping/: master.csv, titles.csv,
                           persons.csv and review.csv

Every entity of every registry goes before a linker, including those that
share no spelling with another collection. Dossiers gather the entities of
different collections that have the identical canonical name or a shared
variant (ignoring case), or the same pandit_hint; an entity tied to nothing
is a dossier of its own. Ties only gather candidates: the linker splits a
wrong tie, and joins entities no tie connected. Dossiers are sorted by name
and cut into windows that overlap, so that entities spelled alike but tied
by nothing still meet.

What a linker sees of an entity is its registry row and, for its items, the
collection's own catalogue lines as master.csv keeps them, with the item's
Part; a sample of them, with the count, when there are many.

  grouping_link.py --run 2026-10-13-one --step dossiers-persons
"""

import argparse
import collections
import csv
import json
import unicodedata

from common import ROOT
from grouping_apply import (MASTER_COLUMNS, PERSON_COLUMNS, REVIEW_COLUMNS, TITLE_COLUMNS, cell, unite, uniq,
                            write_csv)
from grouping_common import ALL, COLLECTIONS, DATA, Groups, read_json, run_dir, sort_key, windows, write_json
from grouping_ids import assign

PREFIX = {"persons": "p3a", "titles": "p3b"}
# Catalogue lines shown of an entity's items, and of a person's titles.
SAMPLE = 8
# A dossier with more members or catalogue lines than this is read on its own.
LARGE_MEMBERS = 40
LARGE_LINES = 250
# Collections in the order the outputs list them.
ORDER = ["g", "j", "w", "e", "d"]


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def split_cell(value):
    return [v.strip() for v in value.split(",")] if value.strip() else []


def form_key(text):
    return unicodedata.normalize("NFC", text).casefold().strip()


class Registries:
    """The five collection registries: the entities pass 2 kept, with their
    catalogue lines."""

    def __init__(self, run):
        self.persons, self.titles, self.master = {}, {}, {}
        for code in ORDER:
            out = DATA / "collections" / code
            kept = {"person": {r["Person ID"] for r in read_csv(out / "persons.csv")},
                    "title": {r["Title ID"] for r in read_csv(out / "titles.csv")}}
            for kind, store in (("person", self.persons), ("title", self.titles)):
                for e in read_json(run_dir(run, code) / f"{kind}s.json")["entities"]:
                    if e["key"] in kept[kind]:
                        store[e["key"]] = {**e, "collection": code}
            self.master[code] = read_csv(out / "master.csv")
        self.lines = collections.defaultdict(list)
        for code, rows in self.master.items():
            for r in rows:
                line = {"title": r["Text Name"], "native": r["Native Text Name"], "author": r["Author Name"],
                        "editor": r["Editor Name"], "part": r["Part"]}
                for t in split_cell(r["Title IDs"]):
                    self.lines[t].append({k: v for k, v in line.items() if v})
                for p, role in zip(split_cell(r["Person IDs"]), split_cell(r["Person Roles"])):
                    self.lines[p].append({**{k: v for k, v in line.items() if v and k != "part"}, "role": role})
        self.author_of = collections.defaultdict(list)
        for t in self.titles.values():
            for a in t.get("authors", []):
                self.author_of[a["person"]].append(t["name"])


def gather(entities):
    """Dossiers: connected components of the cross-collection ties."""
    groups = Groups()
    by_form, by_hint = collections.defaultdict(set), collections.defaultdict(set)
    for key, e in entities.items():
        groups.find(key)
        for form in [e["name"]] + list(e.get("variants", [])):
            by_form[form_key(form)].add(key)
        if e.get("pandit_hint"):
            by_hint[str(e["pandit_hint"])].add(key)
    for tied in list(by_form.values()) + list(by_hint.values()):
        if len({entities[k]["collection"] for k in tied}) > 1:
            tied = sorted(tied)
            for other in tied[1:]:
                groups.union(tied[0], other)
    return groups.components()


def member(reg, e, kind, linked_persons=None):
    """What the linker sees of one collection entity."""
    lines = reg.lines[e["key"]]
    out = {"member": e["key"], "collection": COLLECTIONS[e["collection"]], "name": e["name"],
           "variants": e.get("variants", []), "context": e.get("context", ""),
           "pandit_hint": e.get("pandit_hint"), "confidence": e.get("confidence", ""), "note": e.get("note", "")}
    if kind == "persons":
        works = reg.author_of[e["key"]]
        out["author_of"] = works[:SAMPLE] + ([f"... {len(works)} in all"] if len(works) > SAMPLE else [])
    else:
        authors = []
        for a in e.get("authors", []):
            key = linked_persons["member_of"].get(a["person"])
            if key:
                authors.append({"person": key, "name": linked_persons["by_key"][key]["name"],
                                "attribution": a.get("attribution", "")})
        out.update({"authors": authors, "part_of": e.get("part_of"), "comments_on": e.get("comments_on")})
    out["items"] = len(lines)
    out["lines"] = lines[:SAMPLE]
    return {k: v for k, v in out.items() if v not in ("", [], None) or k in ("member", "name", "items")}


def cut(run, kind, size, overlap):
    base = run_dir(run, ALL)
    prefix = PREFIX[kind]
    if any(base.glob(f"{prefix}-*")):
        raise SystemExit(f"{base.relative_to(ROOT)} already has {prefix} windows. Remove them to cut again.")
    reg = Registries(run)
    linked = None
    if kind == "titles":
        if not (base / "persons.json").exists():
            raise SystemExit("Titles need the persons linked first: grouping_link.py --step persons.")
        linked = read_json(base / "persons.json")
        linked["by_key"] = {e["key"]: e for e in linked["entities"]}
    entities = reg.persons if kind == "persons" else reg.titles

    dossiers = []
    for component in gather(entities):
        names = collections.Counter(entities[k]["name"] for k in component)
        dossiers.append({"name": names.most_common(1)[0][0],
                         "members": [member(reg, entities[k], kind, linked) for k in component]})
    dossiers.sort(key=lambda d: (sort_key(d["name"]), d["name"]))
    for n, d in enumerate(dossiers, start=1):
        d["dossier"] = f"d{n:05d}"

    def is_large(d):
        return len(d["members"]) > LARGE_MEMBERS or sum(len(m.get("lines", [])) for m in d["members"]) > LARGE_LINES

    base.mkdir(parents=True, exist_ok=True)
    cut_windows = windows(dossiers, size, overlap, is_large)
    for n, window in enumerate(cut_windows, start=1):
        batch = base / f"{prefix}-{n:03d}"
        batch.mkdir()
        head = json.dumps({"kind": kind, "collection": ALL}, ensure_ascii=False)[:-1]
        lines = [json.dumps({"dossier": d["dossier"], "name": d["name"], "members": d["members"]},
                            ensure_ascii=False, separators=(",", ":")) for d in window]
        (batch / "dossiers.json").write_text(head + ',"dossiers":[\n' + ",\n".join(lines) + "\n]}\n",
                                             encoding="utf-8")
    record = read_json(base / "run.json") if (base / "run.json").exists() else {}
    record.setdefault("windows", {})[kind] = {"window": size, "overlap": overlap}
    write_json(base / "run.json", record)
    tied = [d for d in dossiers if len(d["members"]) > 1]
    print(f"{kind}, all collections: {len(entities)} registry entities in {len(dossiers)} dossiers "
          f"({sum(len(d['members']) for d in tied)} in {len(tied)} tied across collections), "
          f"{len(cut_windows)} window(s) under {base.relative_to(ROOT)}")


# ---------- the final registry ----------

def resolver(titles, ids):
    """part_of and comments_on: a name to an ID where exactly one title
    answers it, by canonical name or else by variant."""
    by_name, by_variant = collections.defaultdict(set), collections.defaultdict(set)
    for e in titles:
        by_name[form_key(e["name"])].add(ids[e["key"]])
        for v in e["variants"]:
            by_variant[form_key(v)].add(ids[e["key"]])

    def resolve(name):
        if not name:
            return ""
        for index in (by_name, by_variant):
            found = index.get(form_key(name), set())
            if len(found) == 1:
                return next(iter(found))
            if found:
                return name
        return name
    return resolve


def registry(run):
    base = run_dir(run, ALL)
    reg = Registries(run)
    persons, titles = read_json(base / "persons.json"), read_json(base / "titles.json")
    pid, minted_p = assign("person", persons["entities"], base / "ids-persons.json")
    tid, minted_t = assign("title", titles["entities"], base / "ids-titles.json")
    person_of = {pid[e["key"]]: e for e in persons["entities"]}
    title_of = {tid[e["key"]]: e for e in titles["entities"]}
    to_person = {m: pid[k] for m, k in persons["member_of"].items()}
    to_title = {m: tid[k] for m, k in titles["member_of"].items()}
    linked_person = {k: pid[k] for k in pid}

    rows, review = [], []
    items = collections.Counter()
    seen_in = collections.defaultdict(set)
    roles_seen = collections.defaultdict(set)
    for code in ORDER:
        for r in reg.master[code]:
            t_ids = uniq(to_title.get(t) for t in split_cell(r["Title IDs"]))
            t_ids.sort(key=lambda i: (sort_key(title_of[i]["name"]), i))
            persons_here, written = [], set()
            for p, role, attribution in zip(split_cell(r["Person IDs"]), split_cell(r["Person Roles"]),
                                            split_cell(r["Attribution"]) or [""] * 99):
                i = to_person.get(p)
                if i and i not in written:
                    written.add(i)
                    persons_here.append((i, role, attribution))
            for i in t_ids:
                items[i] += 1
                seen_in[i].add(code)
            for i, role, _ in persons_here:
                items[i] += 1
                seen_in[i].add(code)
                roles_seen[i].add(role)
            rows.append({**r,
                         "Title IDs": cell(t_ids), "Title Names": cell(title_of[i]["name"] for i in t_ids),
                         "Person IDs": cell(i for i, _, _ in persons_here),
                         "Person Names": cell(person_of[i]["name"] for i, _, _ in persons_here),
                         "Person Roles": cell(role for _, role, _ in persons_here),
                         "Attribution": cell(a for _, _, a in persons_here)
                         if any(a for _, _, a in persons_here) else ""})

    # The collection reviews carry over, their entity keys mapped to IDs.
    for code in ORDER:
        for r in read_csv(DATA / "collections" / code / "review.csv"):
            key = r["Key"]
            mapped = to_person.get(key) or to_title.get(key)
            review.append({"Pass": r["Pass"], "Kind": r["Kind"], "Key": mapped or key, "Name": r["Name"],
                           "Collection": COLLECTIONS[code], "Reason": r["Reason"],
                           "Detail": (f"{key}: " if mapped else "") + r["Detail"]})

    resolve = resolver(titles["entities"], tid)
    title_rows = []
    for i, e in sorted(title_of.items(), key=lambda kv: (sort_key(kv[1]["name"]), kv[0])):
        authors = [a for a in e["authors"] if a["person"] in linked_person]
        for a in authors:
            roles_seen[linked_person[a["person"]]].add("author")
        title_rows.append({
            "Title ID": i, "Name": e["name"], "Alternative Names": cell(e["variants"]),
            "Author IDs": cell(linked_person[a["person"]] for a in authors),
            "Author Names": cell(person_of[linked_person[a["person"]]]["name"] for a in authors),
            "Attribution": cell(a["attribution"] for a in authors) if any(a["attribution"] for a in authors) else "",
            "Part Of": resolve(e["part_of"]), "Comments On": resolve(e["comments_on"]), "Context": e["context"],
            "Items": items[i], "Collections": cell(COLLECTIONS[c] for c in ORDER if c in seen_in[i] or any(
                m.startswith(c + ":") for m in e["members"])),
            "Pandit Hint": e["pandit_hint"] or "", "Note": e["note"]})
    person_rows = []
    for i, e in sorted(person_of.items(), key=lambda kv: (sort_key(kv[1]["name"]), kv[0])):
        person_rows.append({
            "Person ID": i, "Name": e["name"], "Alternative Names": cell(e["variants"]), "Context": e["context"],
            "Roles Seen": cell(sorted(r for r in roles_seen[i] if r)), "Items": items[i],
            "Collections": cell(COLLECTIONS[c] for c in ORDER if any(m.startswith(c + ":") for m in e["members"])),
            "Pandit Hint": e["pandit_hint"] or "", "Note": e["note"]})
    for ids, entities, step in ((pid, persons["entities"], "3a"), (tid, titles["entities"], "3b")):
        for e in entities:
            if e["conflict"] or e["confidence"] == "low":
                review.append({"Pass": step, "Kind": e["kind"], "Key": ids[e["key"]], "Name": e["name"],
                               "Collection": "", "Reason": "window conflict" if e["conflict"] else "low confidence",
                               "Detail": e["note"]})

    write_csv(DATA / "master.csv", MASTER_COLUMNS, rows)
    write_csv(DATA / "titles.csv", TITLE_COLUMNS, title_rows)
    write_csv(DATA / "persons.csv", PERSON_COLUMNS, person_rows)
    write_csv(DATA / "review.csv", REVIEW_COLUMNS[:4] + ["Collection"] + REVIEW_COLUMNS[4:], review)
    shared = sum(1 for r in title_rows if "," in r["Collections"])
    print(f"registry: {len(rows)} items, {len(title_rows)} titles ({shared} in more than one collection), "
          f"{len(person_rows)} persons, {len(review)} for review, under {DATA.relative_to(ROOT)}; "
          f"{minted_p + minted_t} ID(s) newly minted")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--step", required=True,
                    choices=["dossiers-persons", "persons", "dossiers-titles", "titles", "registry"])
    ap.add_argument("--window", type=int, default=100, help="dossiers per linker, about (default 100)")
    ap.add_argument("--overlap", type=int, default=20, help="dossiers shared by neighbouring windows (default 20)")
    args = ap.parse_args()
    if args.step.startswith("dossiers-"):
        cut(args.run, args.step.removeprefix("dossiers-"), args.window, args.overlap)
    elif args.step == "persons":
        unite(args.run, ALL, "person", step="link-persons")
    elif args.step == "titles":
        unite(args.run, ALL, "title", step="link-titles")
    else:
        registry(args.run)


if __name__ == "__main__":
    main()
