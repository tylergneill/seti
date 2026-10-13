#!/usr/bin/env python3
"""Search the Pandit reference by name or ID. Made for the research sub-agents.

  lookup.py work Nyāyabinduṭīkā        # works whose name or alias matches
  lookup.py person Dharmottara         # persons, each with the works Pandit gives them
  lookup.py id 88733 85228             # full records; a work lists its commentaries

Matching ignores case, hyphens, spaces and anusvāra/class-nasal spelling.
It lists exact matches first, then names containing the query, then a
short list of names that only share its opening stem or are spelled
similarly. Several words narrow the search: each must be found.
"""

import argparse
from difflib import SequenceMatcher

from common import Pandit, norm

LIMIT = 25
WEAK_LIMIT = 8


def describe_work(pandit, wid):
    w = pandit.works[wid]
    authors = ", ".join(f"{pandit.name_of(a)} ({a})" for a in w["author_ids"]) or "no author in Pandit"
    line = f"work {wid}  {w['name']}  |  by {authors}"
    if w["aka"]:
        line += f"  |  aka {', '.join(w['aka'])}"
    if w["base_ids"]:
        line += "  |  commentary on " + ", ".join(f"{pandit.name_of(b)} ({b})" for b in w["base_ids"])
    if w["discipline"]:
        line += f"  |  {w['discipline']}"
    if w["years"]:
        line += f"  |  {w['years']}"
    return line


def describe_person(pandit, pid, works=True):
    p = pandit.persons[pid]
    line = f"person {pid}  {p['name']}"
    if p["aka"]:
        line += f"  |  aka {', '.join(p['aka'])}"
    if p["social"]:
        line += f"  |  {p['social']}"
    if p["years"]:
        line += f"  |  {p['years']}"
    if works:
        titles = [f"{pandit.name_of(w)} ({w})" for w in p["work_ids"]]
        shown = "; ".join(titles[:40]) + (f"; … {len(titles) - 40} more" if len(titles) > 40 else "")
        line += f"\n    works: {shown or 'none in Pandit'}"
    return line


def shared_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def search(entities, query):
    """Rank entity IDs by how well their name or an alias matches the query.

    Returns (strong, weak): exact and containing matches, then names that
    only share a long opening stem or a similar spelling. A title often
    differs from Pandit's in its last member alone (-parikathā, -śāstra),
    which is what the stem match is for.
    """
    words = [norm(w) for w in query.split() if norm(w)]
    whole = norm(query)
    scored = []
    for eid, entity in entities.items():
        best = 0
        for name in [entity["name"]] + entity["aka"]:
            key = norm(name)
            if not key:
                continue
            if key == whole:
                score = 3
            elif all(w in key for w in words):
                score = 2 + len(whole) / (len(key) + 1) / 2
            else:
                ratio = SequenceMatcher(None, whole, key, autojunk=False).ratio()
                stem = shared_prefix(whole, key)
                score = ratio if ratio >= 0.8 else 0
                if stem >= 8 and stem >= 0.6 * min(len(whole), len(key)):
                    score = max(score, 0.8 + stem / (len(whole) + len(key)) / 10)
            best = max(best, score)
        if best:
            scored.append((best, eid))
    ranked = sorted(scored, key=lambda s: (-s[0], s[1]))
    return [eid for s, eid in ranked if s >= 2], [eid for s, eid in ranked if s < 2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["work", "person", "id"])
    ap.add_argument("query", nargs="+")
    ap.add_argument("--pandit", help="cleaned Pandit extract (default: the newest in ../panditya/data)")
    args = ap.parse_args()
    pandit = Pandit(args.pandit)

    if args.kind == "id":
        for eid in args.query:
            if eid in pandit.works:
                print(describe_work(pandit, eid))
                for cid, c in pandit.works.items():
                    if eid in c["base_ids"]:
                        print("    commentary: " + describe_work(pandit, cid))
            if eid in pandit.persons:
                print(describe_person(pandit, eid))
            if eid not in pandit.works and eid not in pandit.persons:
                print(f"{eid}: not a work or person in this Pandit extract")
        return

    query = " ".join(args.query)
    entities = pandit.works if args.kind == "work" else pandit.persons
    strong, weak = search(entities, query)
    if not strong and not weak:
        print(f"nothing in Pandit resembles '{query}'; try a shorter stem of the name")
    for eid in strong[:LIMIT]:
        print(describe_work(pandit, eid) if args.kind == "work" else describe_person(pandit, eid))
    if len(strong) > LIMIT:
        print(f"… {len(strong) - LIMIT} more; add a word to narrow the search")
    # Near misses are listed briefly, so that they cannot bury a real match.
    if weak:
        print("similar names only:" if strong else f"no name contains '{query}'; similar names only:")
        for eid in weak[:WEAK_LIMIT]:
            print("  " + (describe_work(pandit, eid) if args.kind == "work" else describe_person(pandit, eid, works=False)))


if __name__ == "__main__":
    main()
