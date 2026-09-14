"""grantscrape command line: discover, fetch, status, validate, combine, score, extract."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


def _print_chunks(chunks) -> None:
    print(f"{'id':>4}  {'year':>4}  {'chars':>5}  {'kind':<4}  heading")
    for c in chunks:
        print(f"{c.id:>4}  {str(c.year_hint or '-'):>4}  {c.char_count:>5}  {c.kind:<4}  {' > '.join(c.heading_path)[-70:]}")


def _write_run_meta(run_dir: Path, url: str, foundation: str | None) -> None:
    p = run_dir / "run.json"
    meta = json.loads(p.read_text()) if p.exists() else {}
    host = urlsplit(url).netloc
    meta.setdefault("foundation_url", f"{urlsplit(url).scheme}://{host}/")
    if foundation:
        meta["foundation"] = foundation
    meta.setdefault("sources", [])
    if url not in meta["sources"]:
        meta["sources"].append(url)
    run_dir.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=1))


def cmd_fetch(args: argparse.Namespace) -> int:
    from .fetch import ingest_file, ingest_url

    run_dir = Path(args.runs) / args.run
    if args.from_file:
        if not args.url:
            print("--from-file requires --url (the page the text was copied from)", file=sys.stderr)
            return 2
        chunks = ingest_file(run_dir, args.url, Path(args.from_file))
        source_url = args.url
    else:
        if not args.url:
            print("give a URL to fetch", file=sys.stderr)
            return 2
        try:
            fetched, chunks = ingest_url(run_dir, args.url)
        except PermissionError as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            return 3
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        source_url = fetched.final_url
    _write_run_meta(run_dir, source_url, args.foundation)
    _print_chunks(chunks)
    print(f"\n{len(chunks)} chunk(s) written to {run_dir / 'chunks'} (manifest.json updated)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from .merge import load_manifest

    run_dir = Path(args.runs) / args.run
    manifest = load_manifest(run_dir)
    if not manifest:
        print(f"no chunks in {run_dir}; run `grantscrape fetch` first", file=sys.stderr)
        return 1
    done = [m["id"] for m in manifest if (run_dir / "rows" / f"{m['id']}.json").exists()]
    pending = [m["id"] for m in manifest if m["id"] not in done]
    print(f"run {args.run}: {len(manifest)} chunks, {len(done)} extracted, {len(pending)} pending")
    print("pending: " + (" ".join(pending) if pending else "-"))
    if args.verbose:
        for m in manifest:
            state = "done" if m["id"] in done else "todo"
            print(f"  {m['id']}  {state}  {m.get('year_hint') or '-':>4}  {m['char_count']:>5}  chunks/{m['file']}  {m['anchor_url']}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from .merge import validate_run

    run_dir = Path(args.runs) / args.run
    r = validate_run(run_dir)
    print(f"run {args.run}: {len(r.rows)} rows, {len(r.needs_review)} needs_review, {r.duplicates_dropped} duplicates dropped")
    if r.chunks_missing:
        print(f"chunks without rows file: {' '.join(r.chunks_missing)}")
    reasons = Counter(reason.split(":")[0] for a in r.needs_review for reason in a.review_reasons)
    if reasons:
        print("top review reasons:")
        for reason, n in reasons.most_common(8):
            print(f"  {n:>4}  {reason}")
    if r.errors:
        print("ERRORS (fix these rows files and re-run validate):")
        for e in r.errors:
            print(f"  {e}")
    print(f"wrote {run_dir / 'out'}/rows.json, needs_review.json, run.json")
    return 1 if r.errors else 0


def cmd_combine(args: argparse.Namespace) -> int:
    from .export import combine

    runs_root = Path(args.runs)
    run_dirs = [Path(p) for p in args.run_dirs] if args.run_dirs else sorted(p for p in runs_root.iterdir() if (p / "out" / "rows.json").exists())
    if not run_dirs:
        print(f"no validated runs under {runs_root}; run `grantscrape validate` first", file=sys.stderr)
        return 1
    s = combine(run_dirs, Path(args.out))
    print(f"combined {len(run_dirs)} run(s): {s['rows']} rows, {s['needs_review']} needs_review -> {args.out}/combined.csv, combined.json, needs_review.csv, summary.json")
    for name, f in s["by_foundation"].items():
        yrs = f["years"]
        span = f"{yrs[0]}-{yrs[-1]}" if yrs else "-"
        print(f"  {name}: {f['rows']} rows, {f['needs_review']} review, years {span}, total €{f['total_amount']:,.0f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="grantscrape", description="URL in, verifiable grant-award table out.")
    p.add_argument("--runs", default="runs", help="directory holding per-foundation run folders (default: runs)")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download a page/PDF and split it into anchored chunks")
    f.add_argument("url", nargs="?", help="page or PDF URL")
    f.add_argument("--run", required=True, help="run slug, one per foundation, e.g. huber")
    f.add_argument("--foundation", help="foundation's display name, stored in run.json")
    f.add_argument("--from-file", help="ingest a local .md/.txt/.html/.pdf instead of fetching (requires --url for provenance)")
    f.add_argument("--url", dest="url_flag", help="source URL when using --from-file")
    f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("status", help="show which chunks still need a rows file")
    s.add_argument("--run", required=True)
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=cmd_status)

    v = sub.add_parser("validate", help="validate + score rows files, split rows / needs_review")
    v.add_argument("--run", required=True)
    v.set_defaults(func=cmd_validate)

    c = sub.add_parser("combine", help="merge validated runs into one CSV/JSON table")
    c.add_argument("run_dirs", nargs="*", help="run directories (default: every validated run under --runs)")
    c.add_argument("--out", default="out")
    c.set_defaults(func=cmd_combine)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "url_flag", None) and not getattr(args, "url", None):
        args.url = args.url_flag
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
