"""
Scrapes SHL Individual Test Solutions catalog into data/catalog.json.

Confirmed structure (July 2026):
  - Both tables live on ONE page: Pre-packaged (type=2) first, Individual (type=1) second
  - Pagination links for each table use their own type param
  - Individual test solutions: start=0,12,24...372, type=1  (32 pages, ~383 items)
  - Detail page: https://www.shl.com/products/product-catalog/view/<slug>/
"""
import json, re, time, sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE     = "https://www.shl.com"
LIST_URL = BASE + "/products/product-catalog/"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; SHLResearchBot/1.0)"}
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

def get_soup(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=25)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  Retry {attempt+1}: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)

def get_individual_table(soup):
    """
    The page has TWO <table> elements:
      tables[0] = Pre-packaged Job Solutions  (type=2)
      tables[1] = Individual Test Solutions   (type=1)  <-- we want this one
    We identify it by its preceding <h2> heading.
    """
    tables = soup.find_all("table")
    # Method 1: find by heading text immediately above
    for table in tables:
        prev = table.find_previous(["h2", "h3"])
        if prev and "Individual Test Solutions" in prev.get_text():
            return table
    # Method 2: fallback - second table is always Individual
    if len(tables) >= 2:
        return tables[1]
    return None

def discover_last_start_for_type1(soup):
    """
    Find the highest ?start=N&type=1 value in pagination links.
    Must filter specifically for type=1 to avoid picking up type=2 pagination.
    """
    max_start = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Must contain type=1 specifically
        m = re.search(r"start=(\d+)[^&]*&.*type=1|type=1.*&.*start=(\d+)", href)
        if not m:
            # also check simpler pattern ?start=N&type=1
            m = re.search(r"\?start=(\d+)&type=1", href)
        if m:
            val = int(next(v for v in m.groups() if v is not None))
            max_start = max(max_start, val)
    return max_start

def parse_table_rows(table):
    """Extract (name, url, test_type_codes) from a catalog table."""
    rows = []
    for tr in table.find_all("tr"):
        a = tr.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        url = (BASE + href) if href.startswith("/") else href
        # Skip non-product links
        if "/product-catalog/view/" not in url:
            continue
        cells = tr.find_all("td")
        # Last <td> holds the test type letters (e.g. "K" or "A E B C D P")
        type_codes = []
        if cells:
            raw = cells[-1].get_text(separator=" ", strip=True)
            type_codes = [c for c in raw.split() if c in "ABCDEKPS"]
        rows.append({
            "name": a.get_text(strip=True),
            "url": url,
            "test_type": type_codes,
        })
    return rows

def scrape_listing():
    print("Pass 1: scraping listing pages...")
    soup0 = get_soup(LIST_URL, params={"start": 0, "type": 1})
    last  = discover_last_start_for_type1(soup0)
    total_pages = (last // 12) + 1
    print(f"  type=1 pagination: last start={last}, total pages={total_pages}")

    table0 = get_individual_table(soup0)
    if table0 is None:
        print("ERROR: Could not find Individual Test Solutions table on page 1!", file=sys.stderr)
        sys.exit(1)
    items = parse_table_rows(table0)
    print(f"  Page 1/{total_pages}: {len(items)} items")

    for page in range(1, total_pages):
        start = page * 12
        time.sleep(0.5)
        soup  = get_soup(LIST_URL, params={"start": start, "type": 1})
        table = get_individual_table(soup)
        if table:
            new = parse_table_rows(table)
            items.extend(new)
            print(f"  Page {page+1}/{total_pages} (start={start}): +{len(new)} items, total={len(items)}")
        else:
            print(f"  Page {page+1}: WARNING no table found", file=sys.stderr)

    # De-duplicate by URL
    seen, deduped = set(), []
    for it in items:
        if it["url"] not in seen:
            seen.add(it["url"])
            deduped.append(it)
    print(f"\n  Total unique items: {len(deduped)}")
    return deduped

def parse_detail(soup):
    """Pull description, job_levels, languages, duration, remote_testing from a detail page."""
    out = dict(description="", job_levels=[], languages=[], duration_minutes=None, remote_testing=False)
    full = soup.get_text(" ", strip=True)

    # Description: grab the first substantial <p> inside the main content
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if len(text) > 60 and "cookie" not in text.lower() and "browser" not in text.lower():
            out["description"] = text[:500]
            break

    # Job levels
    jl = re.search(r"(?:Job Levels?|Applicable (?:Job )?Levels?)[:\s]+([\w ,\-/&]+?)(?=\s*(?:Language|Remote|Adaptive|Test Type|Industry|$))", full)
    if jl:
        raw_levels = jl.group(1)
        out["job_levels"] = [x.strip() for x in raw_levels.split(",") if len(x.strip()) > 2]

    # Languages
    lang = re.search(r"Languages?[:\s]+([\w ()\-,]+?)(?=\s*(?:Remote|Adaptive|Test Type|Job Level|$))", full)
    if lang:
        raw_lang = lang.group(1)
        out["languages"] = [x.strip() for x in raw_lang.split(",") if x.strip()][:10]

    # Duration
    dur = re.search(r"Completion Time[^=\n]*=\s*(\d+)", full)
    if dur:
        out["duration_minutes"] = int(dur.group(1))

    # Remote testing (look for checkmark icon or explicit "Yes")
    if re.search(r"Remote Testing[:\s]*Yes", full, re.IGNORECASE):
        out["remote_testing"] = True

    return out

def enrich_with_details(items):
    print(f"\nPass 2: enriching {len(items)} items with detail pages...")
    enriched = []
    for i, item in enumerate(items, 1):
        try:
            time.sleep(0.35)
            print(f"  [{i}/{len(items)}] {item['name']}")
            soup   = get_soup(item["url"])
            detail = parse_detail(soup)
            enriched.append({**item, **detail})
        except Exception as e:
            print(f"    WARNING skipped: {e}", file=sys.stderr)
            enriched.append(item)
    return enriched

def main():
    items = scrape_listing()
    if not items:
        print("ERROR: Got 0 items from listing. Check your internet connection.", file=sys.stderr)
        sys.exit(1)
    items = enrich_with_details(items)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    print(f"\nDone. Wrote {len(items)} assessments → {OUT_PATH}")

if __name__ == "__main__":
    main()
