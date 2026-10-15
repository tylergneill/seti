#!/usr/bin/env python3
"""Ground the grouping registry in Pandit, mechanically, and score it against SETI.

The registry's titles and persons each stand for many Atlas items, and each
brings more evidence than any one catalogue line: every spelling the
collections and the agents gave it, its authors linked across the
collections, and the work it comments on. Grounding a title once grounds
every item that carries it.

This is match.py's name matcher pointed at the registry instead of SETI's
rows. Persons go first, so that a work match can be corroborated by its
author:

  persons  the name and every variant (Devanāgarī ones read as IAST) against
           Pandit's persons and their alternative names; a match counts for
           most when Pandit lists the person as author of one of the works
           the registry gives them
  titles   the same against Pandit's works; a match counts for most when
           Pandit's author for the work is a candidate for one of the
           title's authors, or when Pandit's base text for it answers the
           title's comments_on

Names are tried exactly, normalised and through alternative names, and,
when that finds nothing confident, the canonical name fuzzily. A match at
or above --threshold is grounded unless a second candidate is within
AMBIGUITY_MARGIN of it. Nothing in the registry is changed: the result goes
to data/grouping/grounding/{persons,titles}.csv, one row per entity, with
the agents' own pandit_hint beside it for comparison.

  --eval   compare with SETI's hand-made Pandit IDs on the GRETIL items they
           share: how many items each source grounds, and how many of those
           carry SETI's work. The sources are the agents' hints, this
           matcher, and the two together (the matcher where it grounds, the
           hint otherwise). Disagreements go to
           reports/<date>-grounding-eval.csv.

  --authors  titles not grounded whose author is: their names against only
           that author's Pandit works and the author's commentaries on the
           base text they name, to data/grouping/grounding/author-works.csv
  --prep   cut titles for the research pass (agents/grouping/grounder.md)
           into batches, tmp/grouping/<run>/all/p4-NNN/items.json: those
           the matcher scored from --low up to the threshold, by default
           the near misses
  --apply  gather the grounders' proposals into
           data/grouping/grounding/research-titles.csv; --eval then counts
           a research ID at or above the threshold before the matcher's

  grouping_ground.py
  grouping_ground.py --eval
  grouping_ground.py --prep --run 2026-10-13-one [--low 0.8]
  grouping_ground.py --prep --run 2026-10-13-one --low 0.6 --high 0.8 --sample 100
  grouping_ground.py --apply --run 2026-10-13-one
"""

import argparse
import collections
import csv
import datetime
import json
import random
import re
from difflib import SequenceMatcher

from atlas_works import GRETIL_TREE, seti_rows, to_iast
from common import AMBIGUITY_MARGIN, DEFAULT_THRESHOLD, OPEN, REPORTS, ROOT, Pandit, norm, split_cell
from grouping_common import ALL, DATA, batches, read_json, run_dir, write_json
from match import (Q_ALIAS, Q_EXACT, W_AUTHOR_AMBIGUOUS, W_AUTHOR_UNIQUE, W_UNCORROBORATED,
                   W_UNIQUE_AUTHORLESS, build_indexes)

OUT = DATA / "grounding"
# A person candidate at least this good may corroborate a work by authorship.
AUTHOR_FLOOR = 0.4
OTHERS = 3
COLUMNS = ["ID", "Name", "Items", "Collections", "Status", "Pandit ID", "Pandit Name", "Confidence", "Basis",
           "Agent Hint", "Hint Agrees", "Other Candidates"]


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cells(value):
    return [v.strip() for v in value.split(",") if v.strip()]


def queries(row):
    """The name, then every variant; a variant in another script also as IAST."""
    out = [(row["Name"], Q_EXACT)]
    for v in cells(row["Alternative Names"]):
        out.append((v, Q_ALIAS))
        iast = to_iast(v)
        if iast != v:
            out.append((iast, Q_ALIAS))
    return out


def forms(row):
    return {norm(row["Name"])} | {norm(to_iast(v)) for v in cells(row["Alternative Names"])} | \
           {norm(v) for v in cells(row["Alternative Names"])}


def decide(scores, threshold):
    """(status, best id, confidence, basis, others) from {id: (confidence, basis)}."""
    ranked = sorted(scores.items(), key=lambda kv: -kv[1][0])
    if not ranked:
        return "none", "", 0.0, "", []
    (best, (conf, basis)), rest = ranked[0], ranked[1:]
    if conf < threshold:
        status = "candidate"
    elif rest and conf - rest[0][1][0] < AMBIGUITY_MARGIN:
        status = "tie"
    else:
        status = "grounded"
    return status, best, conf, basis, rest[:OTHERS]


class Grounder:
    def __init__(self, pandit, threshold):
        self.pandit, self.threshold = pandit, threshold
        self.works, self.persons = build_indexes(pandit)

    def lookup(self, index, row):
        found = index.lookup(queries(row))
        if not found or max(q for q, _, _ in found.values()) < self.threshold:
            for eid, hit in index.lookup([(row["Name"], Q_EXACT)], fuzzy=True).items():
                if eid not in found or hit[0] > found[eid][0]:
                    found[eid] = hit
        return found

    def person(self, row, authored):
        """authored: the norm forms of the titles the registry makes this person
        the author of."""
        scores = {}
        for pid, (q, matched, how) in self.lookup(self.persons, row).items():
            via = f"person: {how} '{matched}'"
            works = [w for w in self.pandit.persons[pid]["work_ids"] if w in self.pandit.works]
            corroborating = [w for w in works if ({norm(self.pandit.works[w]["name"])}
                                                  | {norm(a) for a in self.pandit.works[w]["aka"]}) & authored]
            if corroborating:
                w = corroborating[0]
                scores[pid] = (q, f"{via}; Pandit lists them as author of '{self.pandit.name_of(w)}' ({w}), "
                                  "one of their titles here")
                continue
            shared = self.persons.count(matched)
            weight = W_AUTHOR_UNIQUE if shared == 1 else W_AUTHOR_AMBIGUOUS
            scores[pid] = (q * weight, f"{via}; no title corroborates; "
                           + ("the only Pandit person of this name" if shared == 1
                              else f"{shared} Pandit persons share this name"))
        return scores

    def title(self, row, author_pool, base_forms):
        """author_pool: {pandit person id: confidence} for the title's authors.
        base_forms: the norm forms of the title's comments_on, if any."""
        has_author = bool(cells(row["Author IDs"]))
        scores = {}
        for wid, (q, matched, how) in self.lookup(self.works, row).items():
            work = self.pandit.works[wid]
            via = f"work: {how} '{matched}'"
            by_author = [(author_pool[a], a) for a in work["author_ids"] if a in author_pool]
            if by_author:
                qa, aid = max(by_author)
                scores[wid] = (min(q, qa), f"{via}; author {self.pandit.name_of(aid)} ({aid}) is a candidate "
                                           "for this title's author")
                continue
            bases = [b for b in work["base_ids"] if b in self.pandit.works and
                     ({norm(self.pandit.works[b]["name"])} | {norm(a) for a in self.pandit.works[b]["aka"]}) & base_forms]
            if bases:
                scores[wid] = (q, f"{via}; Pandit's base text '{self.pandit.name_of(bases[0])}' ({bases[0]}) "
                                  "is what this title comments on")
                continue
            shared = self.works.count(matched)
            if not has_author and not work["author_ids"] and shared == 1:
                scores[wid] = (q * W_UNIQUE_AUTHORLESS, f"{via}; no author on either side; "
                                                        "the only Pandit work of this name")
                continue
            if not has_author:
                why = "the registry names no author" + (
                    f"; Pandit gives {self.authors(work)}" if work["author_ids"] else "")
            elif work["author_ids"]:
                why = f"author not corroborated: Pandit gives {self.authors(work)}"
            else:
                why = "author not corroborated: Pandit gives none"
            if shared > 1:
                why += f"; {shared} Pandit works share this name"
            scores[wid] = (q * W_UNCORROBORATED, f"{via}; {why}")
        return scores

    def authors(self, work):
        return ", ".join(f"{self.pandit.name_of(a)} ({a})" for a in work["author_ids"])


def row_out(entity, id_col, decision, pandit):
    status, best, conf, basis, others = decision
    hint = entity["Pandit Hint"]
    return {"ID": entity[id_col], "Name": entity["Name"], "Items": entity["Items"],
            "Collections": entity["Collections"], "Status": status,
            "Pandit ID": best, "Pandit Name": pandit.name_of(best), "Confidence": f"{conf:.2f}" if best else "",
            "Basis": basis, "Agent Hint": hint,
            "Hint Agrees": "" if not hint or status != "grounded" else ("yes" if hint == best else "no"),
            "Other Candidates": "; ".join(f"{pandit.name_of(i)} ({i}) {c:.2f}" for i, (c, _) in others)}


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def summary(kind, rows):
    status = collections.Counter(r["Status"] for r in rows)
    grounded = [r for r in rows if r["Status"] == "grounded"]
    hinted = [r for r in grounded if r["Agent Hint"]]
    agree = sum(1 for r in hinted if r["Hint Agrees"] == "yes")
    print(f"{kind}: {len(rows)}; grounded {status['grounded']}, tie {status['tie']}, "
          f"candidate only {status['candidate']}, nothing found {status['none']}; "
          f"of the grounded with an agent hint, {agree} of {len(hinted)} agree with it")


def ground(threshold):
    pandit = Pandit()
    g = Grounder(pandit, threshold)
    persons = read_csv(DATA / "persons.csv")
    titles = read_csv(DATA / "titles.csv")

    authored = collections.defaultdict(set)
    for t in titles:
        for pid in cells(t["Author IDs"]):
            authored[pid] |= forms(t)
    person_scores, person_rows = {}, []
    for p in persons:
        scores = g.person(p, authored[p["Person ID"]])
        person_scores[p["Person ID"]] = scores
        person_rows.append(row_out(p, "Person ID", decide(scores, threshold), pandit))

    by_id = {t["Title ID"]: t for t in titles}
    title_rows = []
    for t in titles:
        pool = {}
        for pid in cells(t["Author IDs"]):
            for aid, (c, _) in person_scores.get(pid, {}).items():
                if c >= AUTHOR_FLOOR:
                    pool[aid] = max(pool.get(aid, 0), c)
        base = t["Comments On"]
        base_forms = forms(by_id[base]) if base in by_id else ({norm(base)} if base else set())
        title_rows.append(row_out(t, "Title ID", decide(g.title(t, pool, base_forms), threshold), pandit))

    write(OUT / "persons.csv", person_rows)
    write(OUT / "titles.csv", title_rows)
    summary("persons", person_rows)
    summary("titles", title_rows)
    print(f"written to {OUT.relative_to(ROOT)}")


# ---------- against SETI ----------

def seti_ids():
    """SETI's Pandit work IDs for each GRETIL file it identifies: every slot,
    since several slots run from part to whole."""
    tree = json.loads(GRETIL_TREE.read_text(encoding="utf-8"))
    files_of = {f: w["files"] for w in tree["works"] for f in w["files"]}
    by_path = {}
    for r in seti_rows():
        if r["Collection"] == "GRETIL":
            by_path[re.sub(r"^https?://[^/]+/gretil/", "", r["Link 1 (main)"].strip())] = r
    return by_path, files_of


def evaluate():
    pandit = Pandit()
    grounding = {r["ID"]: r for r in read_csv(OUT / "titles.csv")}
    items = [r for r in read_csv(DATA / "master.csv") if r["Collection"] == "GRETIL"]
    by_path, files_of = seti_ids()
    truth = {}
    for it in items:
        for f in files_of.get(it["Item ID"], [it["Item ID"]]):
            if f in by_path:
                parts, _ = split_cell(by_path[f]["Work ID"])
                ids = {p.strip() for p in parts if p.strip() and p.strip() != OPEN}
                if ids:
                    truth[it["Item ID"]] = ids
                break
    rows = {it["Item ID"]: it for it in items if it["Item ID"] in truth}

    def matcher(t):
        g = grounding[t]
        return g["Pandit ID"] if g["Status"] == "grounded" else ""

    authorworks = {r["Title ID"]: r["Pandit ID"] for r in read_csv(OUT / "author-works.csv")
                   if r["Status"] == "grounded"} if (OUT / "author-works.csv").exists() else {}
    research = {}
    if (OUT / "research-titles.csv").exists():
        research = {r["Title ID"]: r["Pandit ID"] for r in read_csv(OUT / "research-titles.csv")
                    if r["Pandit ID"] and float(r["Confidence"]) >= DEFAULT_THRESHOLD}
    sources = {"agent hints": lambda t: grounding[t]["Agent Hint"],
               "matcher": matcher,
               "matcher, else hint": lambda t: matcher(t) or grounding[t]["Agent Hint"]}
    if research:
        sources["research, matcher, hint"] = lambda t: research.get(t) or matcher(t) or grounding[t]["Agent Hint"]
    if authorworks:
        sources["all, with authors' works"] = lambda t: (research.get(t) or matcher(t) or grounding[t]["Agent Hint"]
                                                         or authorworks.get(t, ""))
    last = list(sources)[-1]
    print(f"GRETIL items with a SETI work ID: {len(truth)}")
    out = []
    for label, source in sources.items():
        covered = agree = 0
        for item, ids in truth.items():
            titles = cells(rows[item]["Title IDs"])
            got = {source(t) for t in titles} - {""}
            if not got:
                continue
            covered += 1
            if got & ids:
                agree += 1
            elif label == last:
                out.append([item, rows[item]["Text Name"], ", ".join(sorted(ids)),
                            "; ".join(pandit.name_of(i) for i in sorted(ids)), rows[item]["Title Names"],
                            ", ".join(sorted(got)), "; ".join(pandit.name_of(i) for i in sorted(got)),
                            "; ".join(f"{t}: {grounding[t]['Status']} {grounding[t]['Basis']}" for t in titles)])
        print(f"  {label:20} grounds {covered:3} of {len(truth)} items ({covered / len(truth):.0%}); "
              f"SETI's work is among them for {agree} ({agree / covered:.1%} of those grounded)")
    path = REPORTS / f"{datetime.date.today().isoformat()}-grounding-eval.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Item ID", "Text Name", "SETI Work IDs", "SETI Work Names", "Title Names",
                    "Grounded IDs", "Grounded Names", "How"])
        w.writerows(out)
    print(f"disagreements ({last}): {len(out)}, in {path.relative_to(ROOT)}")


# ---------- through the authors' works ----------

AUTHOR_COLUMNS = ["Title ID", "Name", "Status", "Pandit ID", "Pandit Name", "Confidence", "Basis",
                  "Author Pandit IDs", "Works Compared", "Other Candidates"]


def work_forms(pandit, wid):
    """A Pandit work's names, normalised: its name, alternative names, the
    head of an 'X on Y's Z' name, and that head joined to its base text's
    name, as the registry would write the commentary (Nyāyabinduṭīkā)."""
    work = pandit.works[wid]
    names = [work["name"]] + work["aka"]
    head = work["name"].split(" on ")[0].strip()
    names.append(head)
    for b in work["base_ids"]:
        if b in pandit.works:
            names.append(pandit.works[b]["name"].split(" on ")[0] + head)
    return {norm(n) for n in names if n}


def similarity(a_forms, b_forms):
    best = 0.0
    for a in a_forms:
        for b in b_forms:
            if not a or not b:
                continue
            if a == b:
                return 1.0
            # One name inside another is a lead, not a match: it is how a
            # commentary's name contains its base text's.
            if min(len(a), len(b)) >= 6 and (a in b or b in a):
                best = max(best, 0.8)
            best = max(best, SequenceMatcher(None, a, b, autojunk=False).ratio())
    return best


def by_authors(threshold):
    """Titles the matcher did not ground but whose author is grounded: their
    names against that author's works in Pandit only, and against Pandit's
    commentaries on the base text they name. The author corroborates every
    candidate, so the names may differ more than a matcher over all of
    Pandit could allow."""
    pandit = Pandit()
    grounding = {r["ID"]: r for r in read_csv(OUT / "titles.csv")}
    person_ground = {r["ID"]: r for r in read_csv(OUT / "persons.csv")}
    research = {r["Title ID"] for r in read_csv(OUT / "research-titles.csv")} \
        if (OUT / "research-titles.csv").exists() else set()
    titles = {r["Title ID"]: r for r in read_csv(DATA / "titles.csv")}

    def pandit_person(pid):
        p = person_ground.get(pid, {})
        return (p.get("Pandit ID") if p.get("Status") == "grounded" else "") or p.get("Agent Hint", "")

    def pandit_work(tid):
        g = grounding.get(tid, {})
        return (g.get("Pandit ID") if g.get("Status") == "grounded" else "") or g.get("Agent Hint", "")

    commentaries = collections.defaultdict(list)
    for wid, w in pandit.works.items():
        for b in w["base_ids"]:
            commentaries[b].append(wid)
    rows = []
    for tid, t in titles.items():
        g = grounding[tid]
        if g["Status"] == "grounded" or g["Agent Hint"] or tid in research:
            continue
        authors = [a for a in (pandit_person(p) for p in cells(t["Author IDs"])) if a in pandit.persons]
        if not authors:
            continue
        pool = {w: "a work of " + ", ".join(f"{pandit.name_of(a)} ({a})" for a in authors
                                            if w in pandit.persons[a]["work_ids"])
                for a in authors for w in pandit.persons[a]["work_ids"] if w in pandit.works}
        base = pandit_work(t["Comments On"]) if t["Comments On"] in titles else ""
        for w in commentaries.get(base, []):
            if set(pandit.works[w]["author_ids"]) & set(authors):
                pool[w] = f"a commentary on {pandit.name_of(base)} ({base}) by the title's author"
        mine = forms(t)
        scores = {}
        for w, why in pool.items():
            sim = similarity(mine, work_forms(pandit, w))
            conf = 0.95 if sim >= 0.95 else 0.9 if sim >= 0.9 else 0.8 if sim >= 0.75 else 0
            if conf:
                scores[w] = (conf, f"names {round(sim * 100)}% alike; {why}")
        status, best, conf, basis, others = decide(scores, threshold)
        rows.append({"Title ID": tid, "Name": t["Name"], "Status": status, "Pandit ID": best,
                     "Pandit Name": pandit.name_of(best), "Confidence": f"{conf:.2f}" if best else "",
                     "Basis": basis, "Author Pandit IDs": ", ".join(authors), "Works Compared": len(pool),
                     "Other Candidates": "; ".join(f"{pandit.name_of(i)} ({i}) {c:.2f}" for i, (c, _) in others)})
    path = OUT / "author-works.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, AUTHOR_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    status = collections.Counter(r["Status"] for r in rows)
    print(f"authors' works: {len(rows)} titles with a grounded author; grounded {status['grounded']}, "
          f"tie {status['tie']}, candidate only {status['candidate']}, nothing alike {status['none']}; "
          f"written to {path.relative_to(ROOT)}")


# ---------- the research pass ----------

LINES = 5
RESEARCH_COLUMNS = ["Title ID", "Name", "Pandit ID", "Pandit Name", "Confidence", "Reasoning", "Matcher ID",
                    "Agrees With Matcher", "Agent Hint", "Batch"]


def prep(run, low, high, size, sample, authors=False):
    """Cut titles the matcher scored from low up to high into batches, after
    any batches already there, leaving out titles already in one. With
    sample, a random draw of that many, the same draw each time. With
    authors, the titles the authors'-works matcher left as a candidate or a
    tie, with their author's works as the candidates."""
    base = run_dir(run, ALL)
    existing = sorted(base.glob("p4-*"))
    done = {it["title"] for b in existing for it in read_json(b / "items.json")}
    grounding = read_csv(OUT / "titles.csv")
    if authors:
        grounding = [{**r, "ID": r["Title ID"], "Status": "candidate" if r["Status"] == "tie" else r["Status"]}
                     for r in read_csv(OUT / "author-works.csv")]
        low, high = 0.0, 1.01
    titles = {r["Title ID"]: r for r in read_csv(DATA / "titles.csv")}
    persons = {r["ID"]: r for r in read_csv(OUT / "persons.csv")}
    lines = collections.defaultdict(list)
    for r in read_csv(DATA / "master.csv"):
        line = {k: v for k, v in (("collection", r["Collection"]), ("title", r["Text Name"]),
                                  ("native", r["Native Text Name"]), ("author", r["Author Name"]),
                                  ("editor", r["Editor Name"])) if v}
        for t in cells(r["Title IDs"]):
            lines[t].append(line)
    def named(ref):
        """part_of and comments_on hold a title ID where the target is in the registry."""
        return titles[ref]["Name"] if ref in titles else ref

    chosen = [g for g in grounding if g["Status"] == "candidate" and low <= float(g["Confidence"]) < high
              and g["ID"] not in done]
    if sample and sample < len(chosen):
        chosen = random.Random(f"{low}-{high}").sample(chosen, sample)
    items = []
    for g in chosen:
        t = titles[g["ID"]]
        authors = []
        for pid, name, attr in zip(cells(t["Author IDs"]), cells(t["Author Names"]),
                                   cells(t["Attribution"]) or [""] * 99):
            p = persons.get(pid, {})
            grounded = p.get("Pandit ID") if p.get("Status") == "grounded" else p.get("Agent Hint")
            authors.append({k: v for k, v in (("name", name), ("attribution", attr),
                                              ("pandit_person", grounded)) if v})
        candidates = [{"id": g["Pandit ID"], "name": g["Pandit Name"], "score": float(g["Confidence"]),
                       "why": g["Basis"]}]
        for other in g["Other Candidates"].split("; ") if g["Other Candidates"] else []:
            m = re.match(r"(.*) \((\d+)\) ([\d.]+)$", other)
            if m:
                candidates.append({"id": m.group(2), "name": m.group(1), "score": float(m.group(3))})
        item = {"title": t["Title ID"], "name": t["Name"], "variants": cells(t["Alternative Names"]),
                "authors": authors, "part_of": named(t["Part Of"]), "comments_on": named(t["Comments On"]),
                "context": t["Context"], "collections": t["Collections"], "items": int(t["Items"]),
                "lines": lines[t["Title ID"]][:LINES], "candidates": candidates, "agent_hint": t["Pandit Hint"]}
        items.append({k: v for k, v in item.items() if v not in ("", [], None) or k in ("title", "name")})
    first = len(existing) + 1
    for n in range(0, len(items), size):
        batch = base / f"p4-{first + n // size:03d}"
        batch.mkdir(parents=True)
        write_json(batch / "items.json", items[n:n + size])
    print(f"ground: {len(items)} titles scored from {low} to below {high}, in "
          f"{len(range(0, len(items), size))} batch(es), p4-{first:03d} on, under {base.relative_to(ROOT)}")


def apply(run):
    pandit = Pandit()
    grounding = {r["ID"]: r for r in read_csv(OUT / "titles.csv")}
    rows, problems, pending = [], [], []
    for batch, done in batches(run, ALL, "ground"):
        asked = {it["title"]: it for it in read_json(batch / "items.json")}
        if not done:
            pending.append(batch.name)
            continue
        for f in read_json(batch / "proposals.json"):
            t = f.get("title") if isinstance(f, dict) else None
            if t not in asked:
                problems.append(f"{batch.name}: a finding for a title it was not given: {f!r}")
                continue
            wid = str(f.get("id") or "")
            if wid and wid not in pandit.works:
                problems.append(f"{batch.name}: {t} was given {wid}, which is not a Pandit work; set aside")
                wid = ""
            g = grounding[t]
            rows.append({"Title ID": t, "Name": asked[t]["name"], "Pandit ID": wid,
                         "Pandit Name": pandit.name_of(wid), "Confidence": f"{float(f.get('confidence') or 0):.2f}",
                         "Reasoning": str(f.get("reasoning", "")).strip(), "Matcher ID": g["Pandit ID"],
                         "Agrees With Matcher": "" if not wid else ("yes" if wid == g["Pandit ID"] else "no"),
                         "Agent Hint": g["Agent Hint"], "Batch": batch.name})
    path = OUT / "research-titles.csv"
    old = {r["Title ID"]: r for r in read_csv(path)} if path.exists() else {}
    old.update({r["Title ID"]: r for r in rows})
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, RESEARCH_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(old.values(), key=lambda r: r["Title ID"]))
    ids = [r for r in rows if r["Pandit ID"]]
    confident = [r for r in ids if float(r["Confidence"]) >= DEFAULT_THRESHOLD]
    print(f"ground: {len(rows)} findings; {len(confident)} IDs at or above {DEFAULT_THRESHOLD}, "
          f"{len(ids) - len(confident)} below, {len(rows) - len(ids)} not in Pandit; "
          f"of the confident, {sum(r['Agrees With Matcher'] == 'yes' for r in confident)} agree with the "
          f"matcher's best candidate; written to {path.relative_to(ROOT)}"
          + (f"; {len(pending)} batch(es) pending: {', '.join(pending)}" if pending else ""))
    for line in problems:
        print("  problem:", line)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--eval", action="store_true", help="score the grounding against SETI on GRETIL")
    ap.add_argument("--authors", action="store_true",
                    help="match titles with a grounded author against that author's Pandit works")
    ap.add_argument("--prep", action="store_true", help="cut the near misses into batches for the research pass")
    ap.add_argument("--apply", action="store_true", help="gather the research pass's proposals")
    ap.add_argument("--run", help="the grouping run whose all/ directory holds the batches")
    ap.add_argument("--low", type=float, default=0.8, help="lowest matcher score to research (default 0.8)")
    ap.add_argument("--high", type=float, help="score to research up to, not including (default the threshold)")
    ap.add_argument("--sample", type=int, help="research only a random sample of this many")
    ap.add_argument("--from-authors", action="store_true",
                    help="with --prep: the authors'-works matcher's candidates and ties instead")
    ap.add_argument("--batch-size", type=int, default=10, help="titles per grounder (default 10)")
    args = ap.parse_args()
    if (args.prep or args.apply) and not args.run:
        ap.error("--prep and --apply need --run")
    if args.authors:
        by_authors(args.threshold)
    elif args.prep:
        prep(args.run, args.low, args.high or args.threshold, args.batch_size, args.sample, args.from_authors)
    elif args.apply:
        apply(args.run)
    elif args.eval:
        evaluate()
    else:
        ground(args.threshold)


if __name__ == "__main__":
    main()
