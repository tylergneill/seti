#!/usr/bin/env python3
"""Apply pass 2's decisions: one registry of persons and titles per collection.

Four steps, run in this order, each after the sub-agents of the step
before it have finished:

  --step persons   unite the persons windows' decisions into
                   tmp/grouping/<run>/<code>/persons.json
  --step titles    the same for titles, into titles.json
  --step items     map each item's readings through the consolidated
                   entities and settle it by majority, into settled.json;
                   items without a majority are cut into batches for the
                   adjudicator, p2c-NNN/items.json; agreement.json records
                   how often the readings agreed
  --step registry  write the collection's registry to
                   data/grouping/collections/<code>/: persons.csv,
                   titles.csv, master.csv and review.csv, with provisional
                   keys (g:p0012, g:t0034) in place of IDs

Uniting windows: every member a consolidator put in one entity is joined.
Where two overlapping windows decided the same members differently, the
decision is the union of the two, marked low for review. Members that no
finished window decided stay gathered as their dossier was, marked low.

Settling items: an item read once is what its reading says. An item read
several times keeps the titles and persons that most of its readings name,
with the role and attribution most of them give a person.

  grouping_apply.py --run 2026-10-13 --collection g --step persons
"""

import argparse
import collections
import csv

from common import ROOT, norm
from grouping_common import (COLLECTIONS, DATA, Groups, batches, item_metadata, load_opinions, member_id,
                             read_json, read_jsonl, run_dir, sort_key, write_json)

RANK = {"low": 0, "medium": 1, "high": 2}
ADJUDICATION_BATCH = 30


def lowest(confidences):
    known = [c for c in confidences if c in RANK]
    return min(known, key=RANK.get) if known else "low"


def top(counter):
    """The commonest value and its count, or (None, 0) on a tie for first."""
    ranked = counter.most_common(2)
    if not ranked or (len(ranked) > 1 and ranked[0][1] == ranked[1][1]):
        return None, 0
    return ranked[0]


def uniq(values):
    return list(dict.fromkeys(v for v in values if v))


# ---------- uniting the windows ----------

def unite(run, code, kind):
    step = "persons" if kind == "person" else "titles"
    base = run_dir(run, code)
    groups = Groups()
    members, dossier_of, decisions, failed = {}, {}, [], []
    for batch, done in batches(run, code, step):
        window = read_json(batch / "dossiers.json")
        here = set()
        for d in window["dossiers"]:
            for m in d["members"]:
                members[m["member"]] = m
                dossier_of[m["member"]] = d["dossier"]
                here.add(m["member"])
                groups.find(m["member"])
        if not done:
            failed.append(batch.name)
            continue
        consolidated = read_json(batch / "consolidated.json")
        for e in consolidated if isinstance(consolidated, list) else []:
            mine = [m for m in e.get("members", []) if m in here]
            if mine:
                decisions.append({**e, "members": mine, "window": batch.name})
    if not members:
        raise SystemExit(f"No {step} windows under {base.relative_to(ROOT)}; run grouping_dossiers.py first.")

    decided = set()
    for e in decisions:
        decided.update(e["members"])
        for m in e["members"][1:]:
            groups.union(e["members"][0], m)
    # Members no finished window decided stay gathered as their dossier was.
    undecided = collections.defaultdict(list)
    for m in members:
        if m not in decided:
            undecided[dossier_of[m]].append(m)
    for tied in undecided.values():
        for m in tied[1:]:
            groups.union(tied[0], m)

    by_component = collections.defaultdict(list)
    for e in decisions:
        by_component[groups.find(e["members"][0])].append(e)
    known_persons = None
    if kind == "title":
        known_persons = {p["key"] for p in read_json(base / "persons.json")["entities"]}

    entities = []
    for component in groups.components():
        parts = sorted(by_component.get(groups.find(component[0]), []), key=lambda e: -len(e["members"]))
        per_window = collections.Counter(e["window"] for e in parts)
        conflict = any(n > 1 for n in per_window.values())
        notes = uniq(e.get("note", "") for e in parts)
        if parts:
            lead = parts[0]
            name, context = lead["name"], lead.get("context", "")
            confidence = lowest(e.get("confidence") for e in parts)
        else:
            names = collections.Counter(members[m]["name"] for m in component)
            name = names.most_common(1)[0][0]
            context = next((members[m].get("context", "") for m in component if members[m].get("context")), "")
            confidence = "low"
            notes.append("Not consolidated: no finished window decided these members; gathered as their dossier was.")
        if conflict:
            confidence = "low"
            notes.append("Overlapping windows decided these members differently; taken as the union of the two: "
                         + "; ".join(f"{e['window']} {e['name']} ({len(e['members'])})" for e in parts))
        hints = collections.Counter(str(e["pandit_hint"]) for e in parts if e.get("pandit_hint"))
        if len(hints) > 1:
            notes.append("Pandit hints differ: " + ", ".join(hints))
        forms = [e["name"] for e in parts] + [v for e in parts for v in e.get("variants", [])]
        for m in component:
            forms += [members[m]["name"]] + list(members[m].get("variants", []))
        entity = {
            "kind": kind, "name": name, "variants": [v for v in uniq(forms) if v != name],
            "context": context, "pandit_hint": hints.most_common(1)[0][0] if hints else None,
            "confidence": confidence, "conflict": conflict, "note": " | ".join(notes),
            "members": component,
        }
        if kind == "title":
            sources = parts or [members[m] for m in component]
            authors = {}
            for e in sources:
                for a in e.get("authors", []):
                    if isinstance(a, dict) and a.get("person") in known_persons:
                        authors.setdefault(a["person"], a.get("attribution", ""))
            entity["authors"] = [{"person": p, "attribution": a} for p, a in authors.items()]
            entity["part_of"] = next((e.get("part_of") for e in sources if e.get("part_of")), None)
            entity["comments_on"] = next((e.get("comments_on") for e in sources if e.get("comments_on")), None)
        entities.append(entity)

    entities.sort(key=lambda e: (sort_key(e["name"]), e["name"], e["members"]))
    member_of = {}
    for n, e in enumerate(entities, start=1):
        e["key"] = f"{code}:{kind[0]}{n:04d}"
        for m in e["members"]:
            member_of[m] = e["key"]
    write_json(base / f"{step}.json", {"entities": entities, "member_of": member_of, "failed_windows": failed})
    print(f"{step}, {COLLECTIONS[code]}: {len(members)} shard entities united into {len(entities)}; "
          f"{sum(e['conflict'] for e in entities)} window conflict(s), "
          f"{sum(e['confidence'] == 'low' for e in entities)} at low"
          + (f"; {len(failed)} window(s) unfinished: {', '.join(failed)}" if failed else ""))


# ---------- settling the items ----------

def mapped_readings(opinions, persons, titles):
    """Each item's readings, with shard keys replaced by consolidated ones."""
    out = collections.defaultdict(list)
    for shard, op in opinions.items():
        for entry in op["items"]:
            reading = {"shard": shard, "kind": entry.get("kind"), "confidence": entry.get("confidence"),
                       "note": entry.get("note", ""), "titles": [], "persons": [],
                       "unplaced": [u for u in entry.get("unplaced", []) if isinstance(u, dict)]}
            for t in entry.get("titles", []):
                key = titles["member_of"].get(member_id(shard, t.get("title")))
                # Two of a reader's titles may have been consolidated into one.
                if key and key not in [x["title"] for x in reading["titles"]]:
                    reading["titles"].append({"title": key, "part_label": t.get("part_label", "")})
            for p in entry.get("persons", []):
                key = persons["member_of"].get(member_id(shard, p.get("person")))
                if key and key not in [x["person"] for x in reading["persons"]]:
                    reading["persons"].append({"as_written": p.get("as_written", ""), "person": key,
                                               "role": p.get("role", ""), "attribution": p.get("attribution", "")})
            out[entry["item"]].append(reading)
    return out


def settle(readings):
    """One item from its readings, by majority. Returns the record and the
    aspects that had no majority."""
    need = len(readings) // 2 + 1
    unsettled = []

    kind, votes = top(collections.Counter(r["kind"] for r in readings))
    if votes < need:
        kind = None
        unsettled.append("kind")

    named = collections.Counter(t["title"] for r in readings for t in r["titles"])
    titles = []
    for key in sorted(k for k, n in named.items() if n >= need):
        given = [t for r in readings for t in r["titles"] if t["title"] == key]
        # A part, if most of the readings naming the title call the item one.
        labels = collections.Counter(t["part_label"] for t in given if t["part_label"])
        part = labels.most_common(1)[0][0] if sum(labels.values()) * 2 > len(given) else ""
        titles.append({"title": key, "part_label": part})
    if kind == "work" and not titles:
        unsettled.append("titles")

    named = collections.Counter(p["person"] for r in readings for p in r["persons"])
    persons = []
    for key in sorted((k for k, n in named.items() if n >= need), key=lambda k: (-named[k], k)):
        given = [p for r in readings for p in r["persons"] if p["person"] == key]
        role, _ = top(collections.Counter(p["role"] for p in given))
        attribution, _ = top(collections.Counter(p["attribution"] for p in given))
        if role is None or attribution is None:
            unsettled.append("person roles")
        written = collections.Counter(p["as_written"] for p in given).most_common(1)[0][0]
        persons.append({"as_written": written, "person": key, "role": role or given[0]["role"],
                        "attribution": attribution or ""})
    if sum(1 for r in readings if r["persons"]) >= need and not persons:
        unsettled.append("persons")
    left = collections.Counter(norm(u.get("as_written", "")) for r in readings for u in r["unplaced"])
    unplaced = uniq(u["as_written"] for r in readings for u in r["unplaced"]
                    if left[norm(u.get("as_written", ""))] >= need)

    chosen = {t["title"] for t in titles}
    agreeing = [r for r in readings if r["kind"] == kind and {t["title"] for t in r["titles"]} == chosen] or readings
    record = {"kind": kind, "titles": titles, "persons": persons, "unplaced": unplaced,
              "confidence": lowest(r["confidence"] for r in agreeing),
              "note": max((r["note"] for r in agreeing), key=len, default=""),
              "readings": len(readings)}
    return record, uniq(unsettled)


def agreement(readings):
    """How far an item's readings agree, aspect by aspect: all, most or none."""
    def level(values):
        count = collections.Counter(values).most_common(1)[0][1]
        return "all" if count == len(values) else "most" if count > len(values) / 2 else "none"

    return {
        "kind": level([r["kind"] for r in readings]),
        "titles": level([tuple(sorted(t["title"] for t in r["titles"])) for r in readings]),
        "persons": level([tuple(sorted((p["person"], p["role"]) for p in r["persons"])) for r in readings]),
    }


def settle_items(run, code):
    base = run_dir(run, code)
    if any(base.glob("p2c-*")):
        raise SystemExit(f"{base.relative_to(ROOT)} already has p2c batches. Remove them to settle again.")
    persons, titles = read_json(base / "persons.json"), read_json(base / "titles.json")
    person_of = {e["key"]: e for e in persons["entities"]}
    title_of = {e["key"]: e for e in titles["entities"]}
    readings = mapped_readings(load_opinions(run, code), persons, titles)
    items = read_jsonl(base / "items.jsonl")

    settled, open_items, unread = {}, [], []
    tally = collections.defaultdict(collections.Counter)
    for it in items:
        mine = readings.get(it["item"], [])
        if not mine:
            unread.append(it["item"])
            continue
        record, unsettled = settle(mine)
        if len(mine) > 1:
            for aspect, level in agreement(mine).items():
                tally[aspect][level] += 1
        if not unsettled:
            settled[it["item"]] = record
            continue
        for r in mine:
            for t in r["titles"]:
                t["name"] = title_of[t["title"]]["name"]
            for p in r["persons"]:
                p["name"] = person_of[p["person"]]["name"]
        t_keys = uniq(t["title"] for r in mine for t in r["titles"])
        p_keys = uniq(p["person"] for r in mine for p in r["persons"])
        open_items.append({
            **item_metadata(it), "unsettled": unsettled, "readings": mine,
            "candidates": {
                "titles": [{"title": k, "name": title_of[k]["name"], "context": title_of[k]["context"],
                            "authors": [person_of[a["person"]]["name"] for a in title_of[k]["authors"]],
                            "part_of": title_of[k]["part_of"], "comments_on": title_of[k]["comments_on"]}
                           for k in t_keys],
                "persons": [{"person": k, "name": person_of[k]["name"], "context": person_of[k]["context"]}
                            for k in p_keys],
            },
        })

    for n in range(0, len(open_items), ADJUDICATION_BATCH):
        batch = base / f"p2c-{n // ADJUDICATION_BATCH + 1:03d}"
        batch.mkdir()
        write_json(batch / "items.json", open_items[n:n + ADJUDICATION_BATCH])
    write_json(base / "settled.json", settled)
    write_json(base / "agreement.json", {"items": len(items), "unread": unread,
                                         "settled_by_majority": len(settled), "to_adjudicate": len(open_items),
                                         "agreement": {a: dict(c) for a, c in tally.items()}})
    print(f"items, {COLLECTIONS[code]}: {len(settled)} of {len(items)} settled by majority, "
          f"{len(open_items)} to adjudicate in {len(list(base.glob('p2c-*')))} batch(es)"
          + (f"; {len(unread)} not read at all" if unread else ""))
    for aspect, counts in tally.items():
        total = sum(counts.values())
        print(f"  {aspect:8} all readings agree {counts['all'] / total:6.1%}   most {counts['most'] / total:6.1%}"
              f"   none {counts['none'] / total:6.1%}")


# ---------- the collection's registry ----------

MASTER_COLUMNS = ["Collection", "Item ID", "Text Name", "Native Text Name", "Author Name", "Editor Name",
                  "File Size (kb)", "Link (online)", "Link (local)", "Item Kind", "Title IDs", "Title Names",
                  "Part", "Person IDs", "Person Names", "Person Roles", "Attribution",
                  "Confidence", "Note"]
TITLE_COLUMNS = ["Title ID", "Name", "Alternative Names", "Author IDs", "Author Names", "Attribution",
                 "Part Of", "Comments On", "Context", "Items", "Collections", "Pandit Hint", "Note"]
PERSON_COLUMNS = ["Person ID", "Name", "Alternative Names", "Context", "Roles Seen", "Items", "Collections",
                  "Pandit Hint", "Note"]
REVIEW_COLUMNS = ["Pass", "Kind", "Key", "Name", "Reason", "Detail"]


def write_csv(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows([[row.get(c, "") for c in columns] for row in rows])


def cell(values):
    return ", ".join(str(v) for v in values)


def registry(run, code):
    base = run_dir(run, code)
    name = COLLECTIONS[code]
    person_of = {e["key"]: e for e in read_json(base / "persons.json")["entities"]}
    title_of = {e["key"]: e for e in read_json(base / "titles.json")["entities"]}
    settled = read_json(base / "settled.json")
    review = []

    decided, pending = {}, {}
    for batch, done in batches(run, code, "items"):
        asked = {it["item"]: it for it in read_json(batch / "items.json")}
        answers = read_json(batch / "decisions.json") if done else []
        for d in answers if isinstance(answers, list) else []:
            if isinstance(d, dict) and d.get("item") in asked:
                decided[d["item"]] = d
        pending.update({k: v for k, v in asked.items() if k not in decided})
    for item, asked in pending.items():
        # Not adjudicated: the catalogue-order reading stands, for review.
        first = asked["readings"][0]
        decided[item] = {**first, "confidence": "low",
                         "note": "No majority among the readings and not adjudicated; one reading taken as is."}

    rows, item_count, roles_seen = [], collections.Counter(), collections.defaultdict(set)
    for it in read_jsonl(base / "items.jsonl"):
        item = it["item"]
        record, source = (settled[item], "2 majority") if item in settled else (decided.get(item), "2c adjudicated")
        if record is None:
            review.append({"Pass": "1", "Kind": "item", "Key": item, "Name": it["title"],
                           "Reason": "not read", "Detail": "No reading of this item finished."})
            record = {"kind": "unidentified", "titles": [], "persons": [], "confidence": "low",
                      "note": "No reading of this item finished."}
        titles = sorted((t for t in record.get("titles", []) if t.get("title") in title_of),
                        key=lambda t: (sort_key(title_of[t["title"]]["name"]), t["title"]))
        persons = [p for p in record.get("persons", []) if p.get("person") in person_of]
        for t in titles:
            item_count[t["title"]] += 1
        for p in persons:
            item_count[p["person"]] += 1
            roles_seen[p["person"]].add(p.get("role", ""))
        rows.append({
            "Collection": name, "Item ID": item.split(":", 1)[1], "Text Name": it["title"],
            "Native Text Name": it.get("native_title", ""), "Author Name": it.get("author", ""),
            "Editor Name": it.get("editor", ""), "File Size (kb)": f"{it['bytes'] / 1024:.1f}",
            "Link (online)": it.get("link_online", ""), "Link (local)": it.get("link_local", ""),
            "Item Kind": record.get("kind") or "unidentified",
            "Title IDs": cell(t["title"] for t in titles),
            "Title Names": cell(title_of[t["title"]]["name"] for t in titles),
            "Part": "; ".join(t["part_label"] for t in titles if t.get("part_label")),
            "Person IDs": cell(p["person"] for p in persons),
            "Person Names": cell(person_of[p["person"]]["name"] for p in persons),
            "Person Roles": cell(p.get("role", "") for p in persons),
            "Attribution": cell(p.get("attribution", "") for p in persons) if any(
                p.get("attribution") for p in persons) else "",
            "Confidence": record.get("confidence", "low"), "Note": record.get("note", ""),
        })
        if record.get("kind") == "unidentified" and source:
            review.append({"Pass": source, "Kind": "item", "Key": item, "Name": it["title"],
                           "Reason": "unidentified", "Detail": record.get("note", "")})
        elif record.get("confidence") == "low":
            review.append({"Pass": source, "Kind": "item", "Key": item, "Name": it["title"],
                           "Reason": "low confidence", "Detail": record.get("note", "")})

    kept_titles = [e for e in title_of.values() if item_count[e["key"]]]
    for e in kept_titles:
        for a in e["authors"]:
            roles_seen[a["person"]].add("author")
    kept_persons = [e for e in person_of.values() if roles_seen[e["key"]]]
    for e in kept_titles + kept_persons:
        step = "2a" if e["kind"] == "person" else "2b"
        if e["conflict"]:
            review.append({"Pass": step, "Kind": e["kind"], "Key": e["key"], "Name": e["name"],
                           "Reason": "window conflict", "Detail": e["note"]})
        elif e["confidence"] == "low":
            review.append({"Pass": step, "Kind": e["kind"], "Key": e["key"], "Name": e["name"],
                           "Reason": "low confidence", "Detail": e["note"]})

    out = DATA / "collections" / code
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "master.csv", MASTER_COLUMNS, rows)
    write_csv(out / "titles.csv", TITLE_COLUMNS, [{
        "Title ID": e["key"], "Name": e["name"], "Alternative Names": cell(e["variants"]),
        "Author IDs": cell(a["person"] for a in e["authors"]),
        "Author Names": cell(person_of[a["person"]]["name"] for a in e["authors"]),
        "Attribution": cell(a["attribution"] for a in e["authors"]) if any(
            a["attribution"] for a in e["authors"]) else "",
        "Part Of": e["part_of"] or "", "Comments On": e["comments_on"] or "", "Context": e["context"],
        "Items": item_count[e["key"]], "Collections": name, "Pandit Hint": e["pandit_hint"] or "",
        "Note": e["note"]} for e in kept_titles])
    write_csv(out / "persons.csv", PERSON_COLUMNS, [{
        "Person ID": e["key"], "Name": e["name"], "Alternative Names": cell(e["variants"]),
        "Context": e["context"], "Roles Seen": cell(sorted(r for r in roles_seen[e["key"]] if r)),
        "Items": item_count[e["key"]], "Collections": name, "Pandit Hint": e["pandit_hint"] or "",
        "Note": e["note"]} for e in kept_persons])
    write_csv(out / "review.csv", REVIEW_COLUMNS, review)
    print(f"registry, {name}: {len(rows)} items, {len(kept_titles)} titles, {len(kept_persons)} persons, "
          f"{len(review)} for review, under {out.relative_to(ROOT)}"
          + (f"; {len(pending)} item(s) not adjudicated" if pending else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--collection", required=True, choices=sorted(COLLECTIONS))
    ap.add_argument("--step", required=True, choices=["persons", "titles", "items", "registry"])
    args = ap.parse_args()
    if args.step == "persons":
        unite(args.run, args.collection, "person")
    elif args.step == "titles":
        unite(args.run, args.collection, "title")
    elif args.step == "items":
        settle_items(args.run, args.collection)
    else:
        registry(args.run, args.collection)


if __name__ == "__main__":
    main()
