#!/usr/bin/env python3
"""YouTube search via yt-dlp with structured output and insights."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone


TIME_RANGES = {
    "week": 7,
    "month": 30,
    "3months": 90,
    "6months": 180,
    "year": 365,
    "all": 0,
}


def parse_args():
    p = argparse.ArgumentParser(description="Search YouTube via yt-dlp")
    p.add_argument("query", nargs="+", help="Search terms")
    p.add_argument("-n", "--count", type=int, default=20, help="Number of results (default: 20)")
    p.add_argument(
        "-t", "--time",
        default="6months",
        choices=TIME_RANGES.keys(),
        help="Time range filter (default: 6months)",
    )
    p.add_argument("--sort", choices=["relevance", "views", "date"], default="relevance")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.add_argument("--no-insights", action="store_true", help="Skip the insights section")
    return p.parse_args()


def run_search(query: str, count: int, time_range: str) -> list[dict]:
    """Run yt-dlp search and return parsed results."""
    # Fetch extra results to compensate for date filtering
    fetch_count = count if time_range == "all" else count + 10

    cmd = [
        "yt-dlp",
        f"ytsearch{fetch_count}:{query}",
        "--dump-json",
        "--skip-download",
        "--no-warnings",
    ]

    if time_range != "all":
        days = TIME_RANGES[time_range]
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
        cmd.extend(["--dateafter", cutoff])

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    results = []
    for line in proc.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            d = json.loads(line)
            results.append({
                "title": d.get("title", "Unknown"),
                "url": d.get("webpage_url", ""),
                "channel": d.get("channel") or d.get("uploader", "Unknown"),
                "views": d.get("view_count", 0),
                "duration": d.get("duration_string", "?"),
                "duration_seconds": d.get("duration", 0),
                "upload_date": d.get("upload_date", ""),
                "description": (d.get("description") or "")[:200],
            })
        except json.JSONDecodeError:
            continue

    return results[:count]


def format_views(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def format_date(date_str: str) -> str:
    if not date_str or len(date_str) != 8:
        return "Unknown"
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        return dt.strftime("%b %d")
    except ValueError:
        return date_str


def format_duration_friendly(seconds: float) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m {s}s" if s else f"{m}m"


def print_results(results: list[dict], query: str, args):
    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f'Here are the top {len(results)} YouTube results for "{query}"')
    if args.time != "all":
        print(f"(filtered to last {args.time})")
    print()

    for i, r in enumerate(results, 1):
        print(f"  #{i}")
        print(f"  {r['title']}")
        print(f"  {r['url']}")
        print(f"  Channel: {r['channel']}")
        print(f"  Views: {format_views(r['views'])}  |  Length: {r['duration']}  |  Date: {format_date(r['upload_date'])}")
        print()


def generate_insights(results: list[dict]) -> str:
    if not results:
        return ""

    lines = ["\n--- Insights ---\n"]

    # Most viewed
    by_views = sorted(results, key=lambda r: r["views"], reverse=True)
    top = by_views[0]
    lines.append(f"Most viewed: #{results.index(top)+1} \"{top['title']}\" ({format_views(top['views'])} views)")

    # Most recent
    by_date = sorted(
        [r for r in results if r["upload_date"]],
        key=lambda r: r["upload_date"],
        reverse=True,
    )
    if by_date:
        newest = by_date[0]
        lines.append(f"Most recent: #{results.index(newest)+1} \"{newest['title']}\" ({format_date(newest['upload_date'])})")

    # Long-form deep dives (>20 min)
    deep = [r for r in results if (r.get("duration_seconds") or 0) > 1200]
    if deep:
        best_deep = max(deep, key=lambda r: r["views"])
        lines.append(
            f"Deep dive: #{results.index(best_deep)+1} \"{best_deep['title']}\" "
            f"({format_views(best_deep['views'])} views, {format_duration_friendly(best_deep['duration_seconds'])})"
        )

    # Quick watches (<10 min)
    quick = [r for r in results if 0 < (r.get("duration_seconds") or 0) < 600]
    if quick:
        best_quick = max(quick, key=lambda r: r["views"])
        lines.append(
            f"Quick watch: #{results.index(best_quick)+1} \"{best_quick['title']}\" "
            f"({format_views(best_quick['views'])} views, {format_duration_friendly(best_quick['duration_seconds'])})"
        )

    # View distribution
    total_views = sum(r["views"] for r in results)
    avg_views = total_views // len(results) if results else 0
    lines.append(f"Avg views: {format_views(avg_views)} across {len(results)} results")

    return "\n".join(lines)


def main():
    args = parse_args()
    query = " ".join(args.query)

    results = run_search(query, args.count, args.time)

    if args.sort == "views":
        results.sort(key=lambda r: r["views"], reverse=True)
    elif args.sort == "date":
        results.sort(key=lambda r: r.get("upload_date", ""), reverse=True)

    if not results:
        print(f'No results found for "{query}"')
        sys.exit(0)

    print_results(results, query, args)

    if not args.no_insights and not args.json:
        print(generate_insights(results))


if __name__ == "__main__":
    main()
