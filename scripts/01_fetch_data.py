"""
01_fetch_data.py
~~~~~~~~~~~~~~~~
Downloads the required PatentsView TSV files from the USPTO Open Data Portal.

Tables downloaded (full historical dataset — no year filter):
  - g_patent                      → patent_id, title, date
  - g_application                 → filing_date
  - g_patent_abstract             → abstract text (all years)
  - g_inventor_disambiguated      → inventor names + location
  - g_assignee_disambiguated      → assignee/company names
  - g_location_disambiguated      → country / geo info

Run:
    python scripts/01_fetch_data.py
"""

import os
import requests
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
RAW_DIR  = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# PatentsView bulk data base URL (USPTO Open Data Portal mirror)
BASE_URL = "https://s3.amazonaws.com/data.patentsview.org/download"

# All tables — full files, no year split.
TABLES = {
    # (filename on S3, description)
    "g_patent.tsv.zip":                  "Core patent metadata (all years)",
    "g_application.tsv.zip":             "Application filing dates (all years)",
    "g_patent_abstract.tsv.zip":         "Patent abstracts (all years)",
    "g_inventor_disambiguated.tsv.zip":  "Disambiguated inventors",
    "g_assignee_disambiguated.tsv.zip":  "Disambiguated assignees (companies)",
    "g_location_disambiguated.tsv.zip":  "Location / country data",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def download_file(url: str, dest: Path) -> None:
    """Stream-download a file with a progress bar. Skips if already present."""
    if dest.exists():
        print(f"  ✓ Already downloaded: {dest.name}")
        return

    print(f"  ↓ Downloading {dest.name} …")
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    with open(dest, "wb") as fh, tqdm(
        total=total, unit="B", unit_scale=True, desc=dest.name, ncols=80
    ) as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            fh.write(chunk)
            bar.update(len(chunk))

    print(f"  ✓ Saved → {dest}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  PatentsView Data Fetcher")
    print("  Scope: ALL records (no year filter)")
    print("=" * 60)

    for filename, desc in TABLES.items():
        url  = f"{BASE_URL}/{filename}"
        dest = RAW_DIR / filename
        print(f"\n[{desc}]")
        try:
            download_file(url, dest)
        except requests.HTTPError as e:
            print(f"  ✗ HTTP error for {filename}: {e}")
        except Exception as e:
            print(f"  ✗ Failed {filename}: {e}")

    print("\n" + "=" * 60)
    print("  Download complete. Files in:", RAW_DIR.resolve())
    print("=" * 60)


if __name__ == "__main__":
    main()
