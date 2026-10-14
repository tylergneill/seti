"""Shared pieces of the grouping job: where things live, and the Atlases' items.

The job sorts Sāgarasaṅgama's five Atlases into titles and persons; see
grouping-spec.md. Items come from Sāgarasaṅgama's search index, and from
nothing else: every field here is one an Atlas publishes.
"""

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

from atlas_works import SEARCH, to_iast
from common import ROOT

GROUPING = ROOT / "tmp" / "grouping"
DATA = ROOT / "data" / "grouping"
AGENTS = ROOT / "agents" / "grouping"

COLLECTIONS = {"g": "GRETIL", "j": "Jain Quantum", "e": "E-bhāratīsampat",
               "w": "Sanskrit Wikisource", "d": "Sanskrit Documents"}

# As Sāgarasaṅgama's search.js has them: the sites its rows link to, and the
# ports its Atlases serve their cached text on.
SD_SITE = "https://sanskritdocuments.org"
EB_SITE = "https://www.ebharatisampat.in"
JQ_SITE = "https://jainqq.org"
GRETIL_MIRROR = "https://tylergneill.github.io/gretil-mirror/gretil"
LOCAL_PORTS = {"w": 8001, "e": 8002, "d": 8003, "j": 8004, "g": 8005}


def run_dir(run, code):
    return GROUPING / run / code


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def sort_key(text):
    """A plain alphabetical key for a title or name in any script: IAST,
    casefolded, without diacritics or punctuation. For ordering only."""
    s = unicodedata.normalize("NFD", to_iast(text or "").casefold())
    return re.sub(r"[^a-z0-9]", "", "".join(ch for ch in s if not unicodedata.combining(ch)))


def _category(groups, gid):
    """One group id to its path, root first, as search.js's groupChain does."""
    chain, seen = [], set()
    while gid is not None and 0 <= gid < len(groups) and gid not in seen:
        seen.add(gid)
        chain.append(groups[gid]["t"])
        gid = groups[gid].get("p")
    return " > ".join(reversed(chain))


def _online(x):
    code = x["a"]
    if code == "d":
        return f"{SD_SITE}/{x['i']}.html"
    if code == "e":
        return f"{EB_SITE}/readSearch.php?id={x['i']}"
    if code == "j":
        return f"{JQ_SITE}/explore/{x['i']}/1"
    if code == "g":
        return f"{GRETIL_MIRROR}/{x['i']}"
    return x.get("u", "")


def _local(x):
    """The URL behind search.js's txt badge: blank unless the Atlas published
    has_text ('lt') for the item. The key is the one search.js's localTxtKey
    picks, per Atlas."""
    lt = x.get("lt")
    if not lt:
        return ""
    key = (x["i"] if x["a"] == "d" else x["t"]) if lt == 1 else lt
    path = "/".join(quote(part, safe="") for part in str(key).split("/"))
    return f"http://localhost:{LOCAL_PORTS[x['a']]}/text/{path}"


def load_items(code):
    """A collection's text-bearing items, in the Atlas's own order.

    Items marked 'po' (scans without Unicode text) are out of scope. So are
    GRETIL's items without a TEI file: the legacy-only files are mostly
    chapter files, pada indexes and analytic renderings, and it is the TEI
    corpus whose coverage is of interest. An item's identifier is the
    Atlas's own; Wikisource has none but the page title.
    """
    data = json.loads(SEARCH.read_text(encoding="utf-8"))
    groups = data["groups"]
    items = []
    for x in data["items"]:
        if x["a"] != code or x.get("po") or (code == "g" and not x.get("tei")):
            continue
        item = {
            "item": f"{code}:{x.get('i') or x['t']}",
            "title": x["t"],
            "native_title": x.get("n", ""),
            "author": x.get("au", ""),
            "editor": x.get("ed", ""),
            "year": x.get("y", ""),
            "publisher": x.get("pub", ""),
            "language": x.get("lang", ""),
            "pages": x.get("pg", ""),
            "subpages": x.get("sub", ""),
            "bytes": int(x.get("b") or 0),
            "added": x.get("d", ""),
            "categories": [_category(groups, gid) for gid in x.get("g", [])],
            "print_sources": x.get("scan", []),
            "link_online": _online(x),
            "link_local": _local(x),
        }
        items.append({k: v for k, v in item.items() if v not in ("", [], None) or k in ("item", "title")})
    return items


# ---------- the fan-out steps ----------

# One row per step that sub-agents do, as in agents/grouping/dispatcher.md:
# the prompt, the batch directories it runs over, what a batch holds and
# what its sub-agent writes there. Pass 3 runs over every collection at
# once, under the pseudo-collection 'all'.
STEPS = {
    "read":         {"prompt": "reader.md",       "glob": "p1-*",  "input": "items.jsonl",   "output": "opinions.json"},
    "persons":      {"prompt": "consolidator.md", "glob": "p2a-*", "input": "dossiers.json", "output": "consolidated.json"},
    "titles":       {"prompt": "consolidator.md", "glob": "p2b-*", "input": "dossiers.json", "output": "consolidated.json"},
    "items":        {"prompt": "adjudicator.md",  "glob": "p2c-*", "input": "items.json",    "output": "decisions.json"},
    "link-persons": {"prompt": "linker.md",       "glob": "p3a-*", "input": "dossiers.json", "output": "consolidated.json"},
    "link-titles":  {"prompt": "linker.md",       "glob": "p3b-*", "input": "dossiers.json", "output": "consolidated.json"},
}
ALL = "all"


def step_of(batch):
    """The step a batch directory belongs to, from its name."""
    for step, spec in STEPS.items():
        if Path(batch).match(spec["glob"]):
            return step
    raise SystemExit(f"{batch} is not a batch directory of any grouping step.")


def batches(run, code, step):
    """A step's batch directories, each with whether its output parses."""
    spec = STEPS[step]
    base = run_dir(run, code)
    if not base.is_dir():
        raise SystemExit(f"No run at {base}.")
    out = []
    for batch in sorted(base.glob(spec["glob"])):
        if not (batch / spec["input"]).exists():
            continue
        try:
            json.loads((batch / spec["output"]).read_text(encoding="utf-8"))
            done = True
        except (FileNotFoundError, json.JSONDecodeError):
            done = False
        out.append((batch, done))
    return out


# ---------- reading back what the passes wrote ----------

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_opinions(run, code):
    """Pass 1's opinions, by shard name. Shards whose file is missing or
    does not parse are left out: an unfinished shard is a gap, not an error."""
    out = {}
    for batch, done in batches(run, code, "read"):
        if done:
            op = read_json(batch / "opinions.json")
            if isinstance(op, dict):
                out[batch.name] = op
    return out


def member_id(shard, key):
    """A shard's person or title, named across the collection."""
    return f"{shard}:{key}"


def item_metadata(item):
    """What a later pass is shown of an item: the metadata a reader judged
    from, without the links and sizes that tell nothing about identity."""
    return {k: v for k, v in item.items()
            if k not in ("link_online", "link_local", "print_sources", "bytes", "added")}


def windows(dossiers, size, overlap, is_large):
    """Cut sorted dossiers into windows of about `size` that overlap by
    `overlap`, so that neighbours no tie connected are still seen together.
    A dossier that is_large gets a window of its own."""
    small = [d for d in dossiers if not is_large(d)]
    out, start, stride = [], 0, max(1, size - overlap)
    while start < len(small):
        out.append(small[start:start + size])
        if start + size >= len(small):
            break
        start += stride
    return out + [[d] for d in dossiers if is_large(d)]


class Groups:
    """Union-find over hashable things."""

    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def components(self):
        out = {}
        for x in list(self.parent):
            out.setdefault(self.find(x), []).append(x)
        return [sorted(v) for v in out.values()]
