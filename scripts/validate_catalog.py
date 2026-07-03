"""
Validates data/catalog.json after scraping.

Usage:
    python scripts/validate_catalog.py

Prints a summary table and exits with code 1 if critical checks fail.
"""
import json, sys
from pathlib import Path
from collections import Counter

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
MIN_ITEMS = 100  # fail if scraper got too few (should be ~383)

def main():
    if not CATALOG_PATH.exists():
        print("ERROR: data/catalog.json not found. Run scrape_catalog.py first.")
        sys.exit(1)

    with open(CATALOG_PATH) as f:
        items = json.load(f)

    print(f"\n{'='*55}")
    print(f"  Catalog Validation Report")
    print(f"{'='*55}")
    print(f"  Total items          : {len(items)}")

    # ── Required fields ────────────────────────────────────────
    missing_name  = [i for i,x in enumerate(items) if not x.get("name")]
    missing_url   = [i for i,x in enumerate(items) if not x.get("url")]
    missing_type  = [i for i,x in enumerate(items) if not x.get("test_type")]
    bad_url       = [x for x in items if not x.get("url","").startswith("https://www.shl.com")]
    dup_urls      = [u for u,c in Counter(x["url"] for x in items).items() if c > 1]
    no_desc       = [x for x in items if not x.get("description")]
    no_levels     = [x for x in items if not x.get("job_levels")]

    print(f"\n  --- Field coverage ---")
    print(f"  Missing name         : {len(missing_name)}")
    print(f"  Missing url          : {len(missing_url)}")
    print(f"  Missing test_type    : {len(missing_type)}")
    print(f"  Non-SHL URLs         : {len(bad_url)}")
    print(f"  Duplicate URLs       : {len(dup_urls)}")
    print(f"  No description       : {len(no_desc)} ({len(no_desc)/len(items)*100:.0f}%)")
    print(f"  No job_levels        : {len(no_levels)} ({len(no_levels)/len(items)*100:.0f}%)")

    # ── Test type distribution ─────────────────────────────────
    type_counter = Counter()
    for x in items:
        for t in x.get("test_type", []):
            type_counter[t] += 1
    print(f"\n  --- Test type distribution ---")
    for t, c in sorted(type_counter.items()):
        bar = "█" * (c // 5)
        print(f"  {t}  {c:>4}  {bar}")

    # ── Sample spot-check ──────────────────────────────────────
    print(f"\n  --- Sample items (first 3) ---")
    for it in items[:3]:
        print(f"  • {it['name'][:50]}")
        print(f"    url        : {it.get('url','')[:70]}")
        print(f"    test_type  : {it.get('test_type')}")
        print(f"    job_levels : {it.get('job_levels', [])[:3]}")
        print(f"    duration   : {it.get('duration_minutes')} min")
        print(f"    desc       : {(it.get('description') or '')[:80]}...")
        print()

    # ── Pass/fail ──────────────────────────────────────────────
    critical_failures = []
    if len(items) < MIN_ITEMS:
        critical_failures.append(f"Only {len(items)} items — expected ≥{MIN_ITEMS}. Re-run the scraper.")
    if missing_name:
        critical_failures.append(f"{len(missing_name)} items with no name.")
    if missing_url:
        critical_failures.append(f"{len(missing_url)} items with no URL.")
    if bad_url:
        critical_failures.append(f"{len(bad_url)} items with non-SHL URLs.")
    if dup_urls:
        critical_failures.append(f"{len(dup_urls)} duplicate URLs: {dup_urls[:3]}")

    print(f"{'='*55}")
    if critical_failures:
        print("  ❌ CRITICAL FAILURES:")
        for f in critical_failures:
            print(f"     • {f}")
        print(f"{'='*55}\n")
        sys.exit(1)
    else:
        pct_desc = (len(items) - len(no_desc)) / len(items) * 100
        print(f"  ✅ All critical checks passed.")
        print(f"     {len(items)} items  |  {pct_desc:.0f}% have descriptions")
        print(f"{'='*55}\n")

if __name__ == "__main__":
    main()
