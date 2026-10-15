#!/usr/bin/env python3
"""Check the output of a grouping step, and fail loudly on what is wrong.

Run after every step, and by each sub-agent on its own batch before it
finishes. An error is something the next step cannot work with: an item
unaccounted for, a reference to a missing entity, a value that is not
allowed, a pandit_hint absent from the extract, a file that does not
parse. A warning is something for the writer to look at again.

  grouping_validate.py --batch tmp/grouping/<run>/g/p1-title-003
  grouping_validate.py --run <run> --collection g --step read

With --step, every batch of the step is checked, finished or not, and for
pass 1 also that every item of the collection was read once in each view.
Exits 1 if anything is in error.
"""

import argparse
import collections
import json
import sys
from pathlib import Path

from common import Pandit, norm
from grouping_common import ALL, COLLECTIONS, STEPS, batches, read_jsonl, run_dir, step_of

KINDS = {"work", "ancillary", "unidentified"}
PERSON_ROLES = {"author", "editor", "translator", "compiler"}
ATTRIBUTIONS = {"", "traditional", "speaker"}
CONFIDENCES = {"high", "medium", "low"}

_pandit = None


def pandit():
    global _pandit
    if _pandit is None:
        _pandit = Pandit()
    return _pandit


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, where, message):
        self.errors.append(f"{where}: {message}")

    def warn(self, where, message):
        self.warnings.append(f"{where}: {message}")


def _check_entity(rep, where, entity, kind):
    """What a person or title entry must have, in any pass."""
    if not isinstance(entity.get("name"), str) or not entity["name"].strip():
        rep.error(where, "has no name")
    if entity.get("confidence") not in CONFIDENCES:
        rep.error(where, f"confidence is {entity.get('confidence')!r}, not high, medium or low")
    if not isinstance(entity.get("variants", []), list):
        rep.error(where, "variants is not a list")
    hint = entity.get("pandit_hint")
    if hint not in (None, ""):
        records = pandit().works if kind == "title" else pandit().persons
        if str(hint) not in records:
            rep.error(where, f"pandit_hint {hint!r} is not a {'work' if kind == 'title' else 'person'} "
                             "in the Pandit extract; give an ID the lookup tool showed you, or null")
    if kind == "title":
        for ref in ("part_of", "comments_on"):
            if entity.get(ref) is not None and not isinstance(entity[ref], str):
                rep.error(where, f"{ref} is not a name (a string) or null")


def check_opinions(batch, rep):
    """Pass 1: one reader's opinions.json against its shard."""
    path = batch / "opinions.json"
    try:
        op = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        rep.error(batch.name, "no opinions.json")
        return
    except json.JSONDecodeError as e:
        rep.error(batch.name, f"opinions.json does not parse: {e}")
        return
    if not isinstance(op, dict) or any(not isinstance(op.get(k), list) for k in ("persons", "titles", "items")):
        rep.error(batch.name, "opinions.json must be an object with lists 'persons', 'titles' and 'items'")
        return

    persons, titles = {}, {}
    for kind, table, entries in (("person", persons, op["persons"]), ("title", titles, op["titles"])):
        for n, entity in enumerate(entries):
            key = entity.get("key") if isinstance(entity, dict) else None
            where = f"{kind} {key or '#%d' % (n + 1)}"
            if not key:
                rep.error(where, "has no key")
                continue
            if key in table:
                rep.error(where, "key is used twice")
            table[key] = entity
            _check_entity(rep, where, entity, kind)
    for key, title in titles.items():
        for a in title.get("authors", []):
            if not isinstance(a, dict) or a.get("person") not in persons:
                rep.error(f"title {key}", f"author {a!r} is not {{'person': <a person key>, 'attribution': ...}}")
            elif a.get("attribution", "") not in ATTRIBUTIONS:
                rep.error(f"title {key}", f"attribution {a.get('attribution')!r} is not '', traditional or speaker")

    shard = {it["item"]: it for it in read_jsonl(batch / "items.jsonl")}
    seen = collections.Counter()
    used_titles, used_persons = set(), set()
    for n, entry in enumerate(op["items"]):
        item = entry.get("item") if isinstance(entry, dict) else None
        where = f"item {item or '#%d' % (n + 1)}"
        if item not in shard:
            rep.error(where, "is not an item of this shard")
            continue
        seen[item] += 1
        meta = shard[item]
        if entry.get("kind") not in KINDS:
            rep.error(where, f"kind is {entry.get('kind')!r}, not work, ancillary or unidentified")
        if entry.get("confidence") not in CONFIDENCES:
            rep.error(where, f"confidence is {entry.get('confidence')!r}, not high, medium or low")

        mapped = 0
        for t in entry.get("titles", []):
            if not isinstance(t, dict) or t.get("title") not in titles:
                rep.error(where, f"title {t!r} does not name a title key")
                continue
            used_titles.add(t["title"])
            mapped += 1
        if entry.get("kind") == "work" and not mapped:
            rep.error(where, "a 'work' item maps to at least one title")
        if entry.get("kind") == "unidentified" and mapped:
            rep.warn(where, "is 'unidentified' but maps to a title")

        # Each field on its own: norm() folds a nasal by the letter after it,
        # which joining the fields would change.
        fields = [norm(str(meta.get(f, ""))) for f in ("author", "editor", "title", "native_title")]
        fields += [norm(c) for c in meta.get("categories", [])]
        for p in entry.get("persons", []):
            if not isinstance(p, dict) or p.get("person") not in persons:
                rep.error(where, f"person {p!r} does not name a person key")
                continue
            used_persons.add(p["person"])
            if p.get("role") not in PERSON_ROLES:
                rep.error(where, f"person role is {p.get('role')!r}, not author, editor, translator or compiler")
            if p.get("attribution", "") not in ATTRIBUTIONS:
                rep.error(where, f"attribution {p.get('attribution')!r} is not '', traditional or speaker")
            if not p.get("as_written"):
                rep.error(where, "a person needs as_written, the name as the metadata has it")
            elif not any(norm(p["as_written"]).rstrip("ṃ") in f for f in fields):
                rep.warn(where, f"as_written {p['as_written']!r} is not in the item's metadata as written")
        for u in entry.get("unplaced", []):
            if not isinstance(u, dict) or not u.get("as_written") or not u.get("reason"):
                rep.error(where, f"unplaced {u!r} is not {{'as_written': ..., 'reason': ...}}")
        if (meta.get("author") or meta.get("editor")) and not entry.get("persons") and not entry.get("unplaced"):
            rep.error(where, "has an author or editor field, but no name from it is in persons or unplaced")

    for item in shard:
        if seen[item] == 0:
            rep.error(f"item {item}", "is in the shard but not in opinions.json")
        elif seen[item] > 1:
            rep.error(f"item {item}", f"appears {seen[item]} times")
    for key in titles.keys() - used_titles:
        rep.warn(f"title {key}", "no item maps to it")
    title_authors = {a.get("person") for t in titles.values() for a in t.get("authors", []) if isinstance(a, dict)}
    for key in persons.keys() - used_persons - title_authors:
        rep.warn(f"person {key}", "no item or title names this person")


def check_coverage(run, code, rep):
    """Pass 1 as a whole: every item read once in each view."""
    base = run_dir(run, code)
    views = json.loads((base / "run.json").read_text(encoding="utf-8"))["views"]
    items = {it["item"] for it in read_jsonl(base / "items.jsonl")}
    for view in views:
        read = collections.Counter()
        for batch in sorted(base.glob(f"p1-{view}-*")):
            try:
                for entry in json.loads((batch / "opinions.json").read_text(encoding="utf-8"))["items"]:
                    read[entry.get("item")] += 1
            except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, AttributeError):
                continue
        missing = [i for i in items if read[i] != 1]
        if missing:
            rep.error(f"view {view}", f"{len(missing)} of {len(items)} items not read exactly once")


def _load_output(batch, name, rep):
    try:
        return json.loads((batch / name).read_text(encoding="utf-8"))
    except FileNotFoundError:
        rep.error(batch.name, f"no {name}")
    except json.JSONDecodeError as e:
        rep.error(batch.name, f"{name} does not parse: {e}")
    return None


def check_consolidated(batch, rep):
    """Passes 2a, 2b and 3: one window's consolidated.json against its dossiers."""
    out = _load_output(batch, "consolidated.json", rep)
    if out is None:
        return
    if not isinstance(out, list):
        rep.error(batch.name, "consolidated.json must be a list of entities")
        return
    window = json.loads((batch / "dossiers.json").read_text(encoding="utf-8"))
    kind = "person" if window["kind"] == "persons" else "title"
    members = {m["member"] for d in window["dossiers"] for m in d["members"]}
    persons = {a["person"] for d in window["dossiers"] for m in d["members"] for a in m.get("authors", [])}
    placed, keys = collections.Counter(), set()
    for n, entity in enumerate(out):
        key = entity.get("entity") if isinstance(entity, dict) else None
        where = f"entity {key or '#%d' % (n + 1)}"
        if not key:
            rep.error(where, "has no 'entity' key")
            continue
        if key in keys:
            rep.error(where, "key is used twice")
        keys.add(key)
        if entity.get("kind") != kind:
            rep.error(where, f"kind is {entity.get('kind')!r}; this window is of {window['kind']}")
        _check_entity(rep, where, entity, kind)
        if not entity.get("members"):
            rep.error(where, "unites no members")
        for m in entity.get("members", []):
            if m not in members:
                rep.error(where, f"member {m!r} is not in this window")
            placed[m] += 1
        # Pass 3: a collection's own consolidator kept its entities apart, and
        # joining two of them again needs a reason.
        if window.get("collection") == ALL:
            same = collections.Counter(str(m).split(":")[0] for m in entity.get("members", []))
            if any(n > 1 for n in same.values()) and not entity.get("note"):
                rep.error(where, "joins two entities of the same collection, which needs a note saying why")
        if kind == "title":
            for a in entity.get("authors", []):
                if not isinstance(a, dict) or a.get("person") not in persons:
                    rep.error(where, f"author {a!r} is not a person key that appears in this window")
                elif a.get("attribution", "") not in ATTRIBUTIONS:
                    rep.error(where, f"attribution {a.get('attribution')!r} is not '', traditional or speaker")
    for m in sorted(members):
        if placed[m] == 0:
            rep.error(f"member {m}", "is in the window but in no entity")
        elif placed[m] > 1:
            rep.error(f"member {m}", f"is in {placed[m]} entities")


def check_decisions(batch, rep):
    """Pass 2c: one adjudicator's decisions.json against its items."""
    out = _load_output(batch, "decisions.json", rep)
    if out is None:
        return
    if not isinstance(out, list):
        rep.error(batch.name, "decisions.json must be a list of decisions")
        return
    asked = {it["item"]: it for it in json.loads((batch / "items.json").read_text(encoding="utf-8"))}
    seen = collections.Counter()
    for n, d in enumerate(out):
        item = d.get("item") if isinstance(d, dict) else None
        where = f"item {item or '#%d' % (n + 1)}"
        if item not in asked:
            rep.error(where, "is not an item of this batch")
            continue
        seen[item] += 1
        titles = {t["title"] for t in asked[item]["candidates"]["titles"]}
        persons = {p["person"] for p in asked[item]["candidates"]["persons"]}
        if d.get("kind") not in KINDS:
            rep.error(where, f"kind is {d.get('kind')!r}, not work, ancillary or unidentified")
        if d.get("confidence") not in CONFIDENCES:
            rep.error(where, f"confidence is {d.get('confidence')!r}, not high, medium or low")
        if not d.get("note"):
            rep.error(where, "needs a note saying what divided the readings and what decided it")
        mapped = 0
        for t in d.get("titles", []):
            if not isinstance(t, dict) or t.get("title") not in titles:
                rep.error(where, f"title {t!r} is not one of the item's candidates")
                continue
            mapped += 1
        if d.get("kind") == "work" and not mapped:
            rep.error(where, "a 'work' item maps to at least one title")
        for p in d.get("persons", []):
            if not isinstance(p, dict) or p.get("person") not in persons:
                rep.error(where, f"person {p!r} is not one of the item's candidates")
                continue
            if p.get("role") not in PERSON_ROLES:
                rep.error(where, f"person role is {p.get('role')!r}, not author, editor, translator or compiler")
            if p.get("attribution", "") not in ATTRIBUTIONS:
                rep.error(where, f"attribution {p.get('attribution')!r} is not '', traditional or speaker")
            if not p.get("as_written"):
                rep.error(where, "a person needs as_written, the name as the metadata has it")
        for u in d.get("unplaced", []):
            if not isinstance(u, dict) or not u.get("as_written") or not u.get("reason"):
                rep.error(where, f"unplaced {u!r} is not {{'as_written': ..., 'reason': ...}}")
    for item in asked:
        if seen[item] == 0:
            rep.error(f"item {item}", "is in the batch but not in decisions.json")
        elif seen[item] > 1:
            rep.error(f"item {item}", f"appears {seen[item]} times")


def check_proposals(batch, rep):
    """Grounding: one grounder's proposals.json against its titles."""
    out = _load_output(batch, "proposals.json", rep)
    if out is None:
        return
    if not isinstance(out, list):
        rep.error(batch.name, "proposals.json must be a list of findings")
        return
    asked = {it["title"] for it in json.loads((batch / "items.json").read_text(encoding="utf-8"))}
    seen = collections.Counter()
    for n, f in enumerate(out):
        title = f.get("title") if isinstance(f, dict) else None
        where = f"title {title or '#%d' % (n + 1)}"
        if title not in asked:
            rep.error(where, "is not a title of this batch")
            continue
        seen[title] += 1
        wid = f.get("id")
        if wid not in (None, "") and str(wid) not in pandit().works:
            rep.error(where, f"id {wid!r} is not a work in the Pandit extract; give an ID the lookup tool "
                             "showed you, or null")
        try:
            confidence = float(f.get("confidence"))
        except (TypeError, ValueError):
            confidence = -1
        if not 0 <= confidence <= 1:
            rep.error(where, f"confidence {f.get('confidence')!r} is not a number from 0 to 1")
        if not str(f.get("reasoning", "")).strip():
            rep.error(where, "needs reasoning an editor can check")
    for title in sorted(asked):
        if seen[title] == 0:
            rep.error(f"title {title}", "is in the batch but not in proposals.json")
        elif seen[title] > 1:
            rep.error(f"title {title}", f"appears {seen[title]} times")


CHECKS = {"read": check_opinions, "persons": check_consolidated, "titles": check_consolidated,
          "items": check_decisions, "link-persons": check_consolidated, "link-titles": check_consolidated,
          "ground": check_proposals}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", type=Path, help="one batch directory")
    ap.add_argument("--run")
    ap.add_argument("--collection", choices=sorted(COLLECTIONS) + [ALL])
    ap.add_argument("--step", choices=sorted(STEPS))
    args = ap.parse_args()

    rep = Report()
    if args.batch:
        batch = args.batch.resolve()
        CHECKS[step_of(batch)](batch, rep)
        scope = batch.name
    elif args.run and args.collection and args.step:
        for batch, _ in batches(args.run, args.collection, args.step):
            one = Report()
            CHECKS[args.step](batch, one)
            rep.errors += [f"{batch.name}: {e}" for e in one.errors]
            rep.warnings += [f"{batch.name}: {w}" for w in one.warnings]
        if args.step == "read":
            check_coverage(args.run, args.collection, rep)
        scope = f"{args.step}, {args.collection}"
    else:
        ap.error("give --batch, or --run, --collection and --step")

    for w in rep.warnings:
        print(f"warning: {w}")
    for e in rep.errors:
        print(f"ERROR: {e}")
    print(f"{scope}: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)"
          + ("" if rep.errors else "; passes"))
    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()
