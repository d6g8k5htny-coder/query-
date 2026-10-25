#!/usr/bin/env python3
"""Math artifact hypergraph (Hypergraph-DB), repo-agnostic. Organization only: credit 0, OBL OPEN, no flags.

One hyperedge per coverage-ledger row (kind=binding) linking unit, source/review files,
implementations, graph nodes, lane and record; plus, for every repo listed in
tools/hypergraph/inputs.json with an `artifacts` section, one hyperedge per artifact
directory (kind=artifact). Every vertex key is prefixed `<repo>:` (main:, Math-:, query-:).
All paths are relative to the repo root (HG_ROOT, else `git rev-parse`, else this file).
Repos whose checkout is absent (private, or not cloned) are skipped with a message.

Usage (from the repo root):
  python -m tools.hypergraph.math_hypergraph build [--png] [--out DIR] [--repos a,b|all] [--check]
  python -m tools.hypergraph.math_hypergraph export DIR [--repos a,b|all] [--png]
  python -m tools.hypergraph.math_hypergraph reach <vertex> [depth]
  python -m tools.hypergraph.math_hypergraph gaps | validate | shared-impl [n] | repos
"""
import argparse, collections, fnmatch, hashlib, json, os, re, subprocess, sys, tempfile
from pathlib import Path
from hyperdb import HypergraphDB

HERE = Path(__file__).resolve().parent


def _root():
    if os.environ.get("HG_ROOT"):
        return Path(os.environ["HG_ROOT"]).resolve()
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE, capture_output=True,
                             text=True, check=True).stdout.strip()
        if out:
            return Path(out).resolve()
    except (OSError, subprocess.CalledProcessError):
        pass
    return HERE.parents[1]


ROOT = _root()
CONFIG = HERE / "inputs.json"
DATA = ROOT / "data" / "hypergraph"
LEDGER = DATA / "math_coverage_ledger_20261023.md"
GRAPH = ROOT / "docs" / "site" / "dependency-source" / "GRAPH.json"
REPORT = DATA / "graph_binding_report_20261023.json"
HUBS = ("lane", "record")
PLACEHOLDER = re.compile(r"in PR head|per census", re.I)
REQUIRED_ROLES = ("unit",)
OUTPUTS = ("math_hypergraph.json", "query_results.json")
SKIP_DIRS = {".git", ".lake", "lake-packages", "node_modules", "__pycache__", ".venv", "external"}


def load_config(path=CONFIG):
    return json.loads(Path(path).read_text())


def _vt(k):
    """vertex type part of '<repo>:<type>:<rest>'"""
    return k.split(":", 2)[1]


def _vid(k):
    return k.split(":", 2)[2]


def parse_ledger(path=LEDGER):
    rows = []
    for line in Path(path).read_text().splitlines():
        if not re.match(r"^\| \d+ \|", line):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        rows.append(dict(n=int(c[0]), rec=c[1], repo=c[2], unit=c[3].strip("`"), lane=c[4],
                         src=c[5], impl=c[6], node=c[7], bound=c[8], status=c[9]))
    return rows


def _split(cell, sep=";"):
    if cell in ("", "—") or cell.upper().startswith("MISSING"):
        return []
    return [s.strip() for s in cell.split(sep) if s.strip()]


def build(ledger=LEDGER, graph=GRAPH, report=REPORT, config=None, repos=None, hg=None, home="main"):
    """Build the hypergraph. With config/repos, also add artifact hyperedges for those repos.
    Returns (hg, G, skipped)."""
    hg = HypergraphDB() if hg is None else hg
    G, skipped = {}, []
    if ledger is not None and Path(graph).exists():
        G = _build_ledger(hg, ledger, graph, report, home,
                          config if config is not None else load_config())
    for name in (repos or []):
        spec = (config or {}).get("repos", {}).get(name)
        if spec is None:
            raise KeyError(f"repo {name!r} not in inputs config")
        base = ROOT / spec.get("checkout", ".")
        if not base.is_dir():
            msg = (f"skip {name}: checkout {spec.get('checkout')} not present "
                   f"(repo private or not cloned; public repos are fetched by actions/checkout)")
            print(msg, file=sys.stderr); skipped.append(name); continue
        if spec.get("artifacts"):
            add_artifacts(hg, name, base, spec)
    return hg, G, skipped


def _resolve(repo, unit, path, config=None):
    """Resolve a ledger path to (repo, repo-root-relative path), deterministically (no filesystem).
    `<repo>:<path>` naming a configured repo is honored as-is. A path that starts with the unit
    directory, or whose first component is one of the repo's configured `root_dirs`, is already
    repo-root-relative; anything else (bare basenames, nested `C7/PROOF.md`) is unit-relative."""
    repos = (config or {}).get("repos", {})
    names = set(repos) | {"main", "Math-", "query-"}
    m = re.match(r"^([A-Za-z0-9_.-]+):(.+)$", path)
    if m and m.group(1) in names:
        return m.group(1), m.group(2)
    unit = unit.strip("/")
    if path == unit or path.startswith(unit + "/"):
        return repo, path
    if "/" in path and path.split("/", 1)[0] in repos.get(repo, {}).get("root_dirs", ()):
        return repo, path
    return repo, f"{unit}/{path}"


def _build_ledger(hg, ledger, graph, report, home, config=None):
    G = json.loads(Path(graph).read_text())["nodes"]
    R = json.loads(Path(report).read_text())
    bound_nodes = {b["node_id"] for b in R["bound"]}

    def V(k, typ, **d):
        if not hg.has_v(k):
            hg.add_v(k, {"type": typ, **d})
        return k

    for nid, nd in G.items():
        V(f"{home}:node:" + nid, "graph_node", layer=nd.get("layer"), kind=nd.get("kind"),
          bound_in_527=nid in bound_nodes)
    for r in parse_ledger(ledger):
        rp = r["repo"]
        u = V(f"{rp}:unit:{r['unit']}", "unit", row=r["n"], status=r["status"], bound=r["bound"] == "Y")
        members = {u: "unit"}
        members[V(f"{home}:record:" + r["rec"], "record")] = "record"
        members[V(f"{home}:lane:" + r["lane"], "lane")] = "lane"
        srcs = _split(r["src"])
        for s in srcs:
            role = "review" if re.search(r"REVIEW", s, re.I) else "source"
            srp, sp = _resolve(rp, r["unit"], s, config)
            members[V(f"{srp}:src:{sp}", "source_file")] = role
        imps = _split(r["impl"])
        placeholders = []
        for s in imps:
            if s.startswith("(") or s.endswith(")") or PLACEHOLDER.search(s):
                placeholders.append(s)  # text, not an artifact
                continue
            irp, ip = _resolve(rp, r["unit"], s, config)
            members[V(f"{irp}:impl:{ip}", "implementation")] = "impl"
        for s in _split(r["node"], ","):
            members[V(f"{home}:node:" + s, "graph_node")] = "node"
        hg.add_e(tuple(members), {
            "kind": "binding", "row": r["n"], "roles": members, "bound": r["bound"] == "Y",
            "has_source": bool(srcs), "has_impl": bool(imps),
            "impl_placeholder": bool(imps) and not any(_vt(k) == "impl" for k in members),
            "placeholders": placeholders, "credit": 0, "obl": "OPEN"})
    return G


ROLE_TYPE = {"source": "source_file", "review": "source_file", "formal": "formal_file",
             "impl": "implementation", "spec": "spec_file", "test": "test_file"}


def _walk(base):
    for dp, dns, fns in os.walk(base):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for f in sorted(fns):
            yield (Path(dp) / f).relative_to(base).as_posix()


def add_artifacts(hg, repo, base, spec):
    """One hyperedge per artifact directory (first `unit_depth` path parts)."""
    depth = int(spec.get("unit_depth", 2))
    pats = spec["artifacts"]
    units = collections.defaultdict(dict)
    for rel in _walk(base):
        role = next((r for r, gl in pats.items() if any(fnmatch.fnmatchcase(rel, g) for g in gl)), None)
        if role is None:
            continue
        parts = rel.split("/")[:-1]
        unit = "/".join(parts[:depth]) if parts else "(root)"
        units[unit][f"{repo}:{'src' if role in ('source', 'review') else role}:{rel}"] = role
    for unit in sorted(units):
        u = f"{repo}:unit:{unit}"
        if not hg.has_v(u):
            hg.add_v(u, {"type": "unit", "row": None, "status": "artifact-scan", "bound": False})
        members = {u: "unit"}
        for k, role in sorted(units[unit].items()):
            if not hg.has_v(k):
                hg.add_v(k, {"type": ROLE_TYPE[role]})
            members[k] = role
        if len(members) > 1 and not hg.has_e(tuple(members)):
            hg.add_e(tuple(members), {"kind": "artifact", "repo": repo, "unit": unit, "row": None,
                                      "roles": members, "credit": 0, "obl": "OPEN"})
    return len(units)


def nbr_vertices(hg, v):
    # workaround: hyperdb nbr_v()/nbr_e_of_v() raise on isolated vertices
    if not hg.degree_v(v):
        return set()
    return set().union(*[set(e) for e in hg.nbr_e_of_v(v)]) - {v}


def reach(hg, start, depth=2):
    if not hg.has_v(start):
        raise KeyError(start)
    seen, front = {start}, {start}
    for _ in range(depth):
        nxt = set()
        for v in front:
            if hg.v(v)["type"] in HUBS and v != start:
                continue  # hubs: do not traverse through
            if hg.degree_v(v):
                for e in hg.nbr_e_of_v(v):
                    nxt |= set(e)
        front = nxt - seen
        seen |= nxt
    return seen - {start}


def validate(hg):
    """Role validator: every hyperedge must carry each REQUIRED_ROLES role, and
    every member must have a role. Returns a list of problems."""
    problems = []
    for e in hg.all_e:
        d = hg.e(e)
        roles = d.get("roles", {})
        for req in REQUIRED_ROLES:
            if req not in roles.values():
                problems.append({"row": d.get("row"), "problem": f"missing role {req}"})
        for v in e:
            if v not in roles:
                problems.append({"row": d.get("row"), "problem": f"member without role {v}"})
    return problems


def gaps(hg, G):
    units = [v for v in hg.all_v if hg.v(v)["type"] == "unit" and hg.v(v).get("row") is not None]
    edges = {u: [hg.e(e) for e in hg.nbr_e_of_v(u) if hg.e(e).get("kind") == "binding"] for u in units}
    placeholder = sorted(u for u in units if any(d["impl_placeholder"] for d in edges[u]))
    no_src = sorted(u for u in units if not any(d["has_source"] for d in edges[u]))
    no_impl = sorted(u for u in units if not any(d["has_impl"] for d in edges[u]))
    nodes = [v for v in hg.all_v if hg.v(v)["type"] == "graph_node"]
    unbound = sorted(_vid(v) for v in nodes if _vid(v) in G and not hg.v(v).get("bound_in_527"))
    untouched = sorted(_vid(v) for v in nodes if not any(_vt(x) == "unit" for x in nbr_vertices(hg, v)))
    return {
        "units": len(units), "sourced": len(units) - len(no_src), "no_source": no_src,
        "implemented": len(units) - len(no_impl), "no_impl": no_impl,
        "impl_placeholder_only": placeholder,
        "bound_units": sum(1 for u in units if hg.v(u)["bound"]),
        "graph_nodes": len(G), "unbound_nodes_per_527": unbound,
        "nodes_touched_by_no_unit": untouched,
        "role_problems": validate(hg),
    }


def shared_impl(hg, n=5):
    c = collections.Counter()
    for v in hg.all_v:
        if hg.v(v)["type"] == "implementation":
            c[v] = sum(1 for x in nbr_vertices(hg, v) if _vt(x) == "unit")
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def summary(g):
    return {k: (len(v) if isinstance(v, list) else v) for k, v in g.items()}


def repo_stats(hg):
    c = collections.defaultdict(collections.Counter)
    for v in hg.all_v:
        c[v.split(":", 1)[0]][hg.v(v)["type"]] += 1
    e = collections.Counter((hg.e(x).get("repo") or "ledger") for x in hg.all_e)
    return {r: {"vertices": dict(sorted(t.items())), "artifact_hyperedges": e.get(r, 0)} for r, t in sorted(c.items())}


def write_outputs(hg, G, out=DATA, png=False):
    out.mkdir(parents=True, exist_ok=True)
    (out / "math_hypergraph.json").write_text(json.dumps(
        {"note": "organization only; credit 0, OBL OPEN, no flags",
         "vertices": {k: hg.v(k) for k in sorted(hg.all_v)},
         "hyperedges": sorted((hg.e(e) for e in hg.all_e), key=lambda d: (d["row"] is None, d["row"] or 0, d.get("repo") or "", d.get("unit") or ""))},
        sort_keys=True, separators=(",", ":"), default=list) + "\n")
    g = gaps(hg, G)
    q = "main:node:math.d1-component.congruence-erratum"
    res = {"note": "organization only; credit 0, OBL OPEN, no flags",
           "stats": {"vertices": hg.num_v, "hyperedges": hg.num_e,
                     "by_type": dict(sorted(collections.Counter(hg.v(v)["type"] for v in hg.all_v).items()))},
           "gap_counts": summary(g), "gaps": g,
           "by_repo": repo_stats(hg),
           "reach_example": ({"start": q, "1hop": sorted(reach(hg, q, 1)), "2hop_count": len(reach(hg, q, 2))}
                             if hg.has_v(q) else None),
           "shared_impl_top5": shared_impl(hg)}
    (out / "query_results.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=list) + "\n")
    if png:
        try:
            render_png(hg, out / "bindings_hypergraph.png")
        except ImportError:
            print("PNG skipped: Pillow not installed (optional)", file=sys.stderr)
    return res


def render_png(hg, path):
    # library draw() only serves a web page; render with Pillow
    import math
    from PIL import Image, ImageDraw
    E = sorted((e for e in hg.all_e if any(_vt(v) == "node" for v in e)), key=lambda e: hg.e(e)["row"] or 0)
    vs = sorted({v for e in E for v in e if _vt(v) not in HUBS})
    W = 1400; img = Image.new("RGB", (W, W), "white"); d = ImageDraw.Draw(img); cx = cy = W / 2
    pos = {v: (cx + 560 * math.cos(2 * math.pi * i / len(vs)), cy + 560 * math.sin(2 * math.pi * i / len(vs))) for i, v in enumerate(vs)}
    col = {"formal_file": "#9467bd", "spec_file": "#8c564b", "test_file": "#7f7f7f", "unit": "#1f77b4", "graph_node": "#d62728", "source_file": "#2ca02c", "implementation": "#ff7f0e"}
    for e in E:
        m = [v for v in e if v in pos]
        hx = sum(pos[v][0] for v in m) / len(m) * 0.6 + cx * 0.4; hy = sum(pos[v][1] for v in m) / len(m) * 0.6 + cy * 0.4
        c = "#000000" if hg.e(e).get("bound") else "#999999"
        for v in m:
            d.line([pos[v], (hx, hy)], fill=c, width=1)
        d.rectangle([hx - 4, hy - 4, hx + 4, hy + 4], fill=c)
    for v, (x, y) in pos.items():
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=col[hg.v(v)["type"]])
    d.text((20, 20), "Unit-to-graph-node hyperedges (square = 1 binding hyperedge; black bound, grey unbound)", fill="black")
    d.text((20, 40), "blue unit, red graph node, green source, orange impl. Organization only: credit 0, OBL OPEN", fill="black")
    img.convert("P", palette=Image.ADAPTIVE, colors=16).save(path, optimize=True)


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _repos_arg(cfg, val):
    if val is None:
        return list(cfg.get("default_repos", []))
    if val == "all":
        return list(cfg.get("repos", {}))
    return [x for x in val.split(",") if x]


def _make(cfg, repos):
    home = cfg.get("home", "main")
    spec = cfg.get("repos", {}).get(home, {})
    ledger = spec.get("ledger")
    if ledger and home in repos and (ROOT / ledger).exists():
        return build(ROOT / ledger, ROOT / spec["graph"], ROOT / spec["report"], cfg,
                     [r for r in repos if r != home or spec.get("artifacts")], home=home)
    return build(None, None, None, cfg, repos, home=home)


def check(cfg, repos, ref=DATA):
    """Rebuild into a temp dir; return list of committed outputs that differ."""
    hg, G, _ = _make(cfg, repos)
    with tempfile.TemporaryDirectory() as td:
        write_outputs(hg, G, Path(td))
        return [f for f in OUTPUTS if not (ref / f).exists()
                or (Path(td) / f).read_bytes() != (ref / f).read_bytes()]


def export(hg, G, out, cfg, repos, skipped, png=False):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    res = write_outputs(hg, G, out, png)
    included = [r for r in repos if r not in skipped]
    (out / "README.md").write_text(EXPORT_README.format(
        repos=", ".join(included) or "(none)", skipped=", ".join(skipped) or "none",
        v=hg.num_v, e=hg.num_e))
    manifest = {"note": "organization only; credit 0, OBL OPEN, no flags", "format": "math-hypergraph/1",
                "repos_included": included, "repos_skipped": skipped,
                "hyperdb": "hypergraph-db==0.4.0",
                "files": {f.name: _sha(f) for f in sorted(out.iterdir()) if f.is_file() and f.name != "MANIFEST.json"}}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")  # written last
    return res


EXPORT_README = """# Math hypergraph export bundle — organization only, NOT A RESULT

credit 0 · OBL OPEN · no flags. Self-contained: needs only Python 3.10+ (and optionally hypergraph-db==0.4.0).

Repos included: {repos}. Skipped: {skipped}. {v} vertices, {e} hyperedges.

- `math_hypergraph.json` — `vertices` (key `<repo>:<type>:<id>` -> attributes) and `hyperedges`
  (each has `roles` {{member -> role}}; members are the role keys; `kind` is `binding` or `artifact`).
- `query_results.json` — gap counts, per-repo stats, reach example, shared implementations.
- `MANIFEST.json` — sha256 of every file in this bundle.

Load anywhere:
```python
import json
from hyperdb import HypergraphDB          # optional; plain dicts work too
d = json.load(open("math_hypergraph.json"))
hg = HypergraphDB()
for k, a in d["vertices"].items(): hg.add_v(k, a)
for e in d["hyperedges"]: hg.add_e(tuple(e["roles"]), e)
```
"""


def load_json(path):
    d = json.loads(Path(path).read_text())
    hg = HypergraphDB()
    for k, a in d["vertices"].items():
        hg.add_v(k, a)
    for e in d["hyperedges"]:
        hg.add_e(tuple(e["roles"]), e)
    return hg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=CONFIG)
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build"); b.add_argument("--png", action="store_true"); b.add_argument("--out", type=Path, default=DATA)
    b.add_argument("--check", action="store_true", help="rebuild to a temp dir; exit 1 if committed outputs differ")
    b.add_argument("--repos", default=None, help="comma list or 'all' (default: config default_repos)")
    x = sp.add_parser("export"); x.add_argument("out", type=Path); x.add_argument("--repos", default="all")
    x.add_argument("--png", action="store_true")
    r = sp.add_parser("reach"); r.add_argument("vertex"); r.add_argument("depth", nargs="?", type=int, default=2)
    sp.add_parser("gaps"); sp.add_parser("validate"); sp.add_parser("repos")
    s = sp.add_parser("shared-impl"); s.add_argument("n", nargs="?", type=int, default=5)
    for p in (r, s, sp.choices["gaps"], sp.choices["validate"]):
        p.add_argument("--repos", default=None)
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    if a.cmd == "repos":
        for n, spec in cfg.get("repos", {}).items():
            print(f"{n}\t{spec.get('checkout')}\t{'present' if (ROOT / spec.get('checkout', '.')).is_dir() else 'absent'}")
        return 0
    repos = _repos_arg(cfg, getattr(a, "repos", None))
    if a.cmd == "build" and a.check:
        diff = check(cfg, repos, a.out)
        if diff:
            print("STALE: " + ", ".join(diff) + " differ from a fresh rebuild; run build and commit", file=sys.stderr)
            return 1
        print("build --check: committed outputs match a fresh rebuild"); return 0
    hg, G, skipped = _make(cfg, repos)
    if a.cmd == "build":
        print(json.dumps(write_outputs(hg, G, a.out, a.png)["gap_counts"], indent=1)); return 0
    if a.cmd == "export":
        export(hg, G, a.out, cfg, repos, skipped, a.png); print(f"exported {hg.num_v} vertices / {hg.num_e} hyperedges to {a.out}"); return 0
    if a.cmd == "reach":
        try:
            print("\n".join(sorted(reach(hg, a.vertex, a.depth))))
        except KeyError:
            print(f"unknown vertex: {a.vertex}", file=sys.stderr); return 2
        return 0
    if a.cmd == "gaps":
        print(json.dumps(summary(gaps(hg, G)), indent=1)); return 0
    if a.cmd == "shared-impl":
        for v, k in shared_impl(hg, a.n):
            print(f"{k}\t{v}")
        return 0
    p = validate(hg)
    print(json.dumps(p, indent=1)); return 1 if p else 0


if __name__ == "__main__":
    sys.exit(main())
