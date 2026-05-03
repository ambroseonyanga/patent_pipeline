"""
02_clean_data.py
~~~~~~~~~~~~~~~~
Reads raw TSV files from data/raw/, cleans them with pandas,
and writes clean CSVs to data/clean/.

Steps per table:
  - Drop rows with missing critical fields
  - Normalize text (strip whitespace, title-case names)
  - Parse / validate dates
  - Filter to the configured PATENT_YEAR
  - Deduplicate
  - Save clean CSV

Run:
    python scripts/02_clean_data.py
"""

import os
import zipfile
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

YEAR      = int(os.getenv("PATENT_YEAR", "2023"))
RAW_DIR   = Path("data/raw")
CLEAN_DIR = Path("data/clean")
CLEAN_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def read_tsv_from_zip(zip_path: Path, **kwargs) -> pd.DataFrame:
    """Unzip on-the-fly and read the TSV inside."""
    print(f"  Reading {zip_path.name} …")
    with zipfile.ZipFile(zip_path) as zf:
        tsv_name = [n for n in zf.namelist() if n.endswith(".tsv")][0]
        with zf.open(tsv_name) as f:
            df = pd.read_csv(
                f,
                sep="\t",
                low_memory=False,
                on_bad_lines="skip",
                encoding="utf-8",
                **kwargs,
            )
    print(f"    Loaded {len(df):,} rows, {df.shape[1]} columns")
    return df


def save_clean(df: pd.DataFrame, name: str) -> None:
    path = CLEAN_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"  ✓ Saved {len(df):,} rows → {path}")


# ── Cleaning functions ────────────────────────────────────────────────────────

def clean_patents() -> pd.DataFrame:
    """
    Source: g_patent.tsv.zip
    Columns used: patent_id, patent_title, patent_date, patent_type
    """
    df = read_tsv_from_zip(RAW_DIR / "g_patent.tsv.zip")

    df = df.rename(columns={
        "patent_id":    "patent_id",
        "patent_title": "title",
        "patent_date":  "grant_date",
        "patent_type":  "patent_type",
    })

    df = df[["patent_id", "title", "grant_date", "patent_type"]].copy()

    df["grant_date"] = pd.to_datetime(df["grant_date"], errors="coerce")
    df["year"]       = df["grant_date"].dt.year

    df = df[df["year"] == YEAR].copy()
    df = df.dropna(subset=["patent_id", "title", "grant_date"])
    df["title"] = df["title"].str.strip()
    df = df.drop_duplicates(subset="patent_id")
    df["grant_date"] = df["grant_date"].dt.strftime("%Y-%m-%d")

    save_clean(df, "clean_patents")
    return df


def clean_applications(patent_ids: set) -> pd.DataFrame:
    """
    Source: g_application.tsv.zip
    Columns used: patent_id, filing_date
    """
    zip_path = RAW_DIR / "g_application.tsv.zip"
    if not zip_path.exists():
        print(f"  ⚠  g_application.tsv.zip not found — filing_date will be NULL in DB.")
        print(f"     Download it from: https://patentsview.org/download/data-download-tables")
        empty = pd.DataFrame(columns=["patent_id", "filing_date"])
        save_clean(empty, "clean_applications")
        return empty

    df = read_tsv_from_zip(zip_path, usecols=["patent_id", "filing_date"])
    df = df[df["patent_id"].isin(patent_ids)].copy()
    df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
    df = df.dropna(subset=["patent_id", "filing_date"])
    df["filing_date"] = df["filing_date"].dt.strftime("%Y-%m-%d")
    df = df.drop_duplicates(subset="patent_id")

    save_clean(df, "clean_applications")
    return df


def clean_abstracts(patent_ids: set) -> pd.DataFrame:
    """
    Source: g_patent_abstract.tsv.zip
    Columns used: patent_id, patent_abstract
    """
    candidates = [
        RAW_DIR / f"g_patent_abstract_{YEAR}.tsv.zip",
        RAW_DIR / "g_patent_abstract.tsv.zip",
    ]
    zip_path = next((p for p in candidates if p.exists()), None)

    if zip_path is None:
        print(f"  ⚠  Abstract file not found. Tried: {[p.name for p in candidates]}")
        print(f"     Skipping abstracts — all other steps will still run fine.")
        empty = pd.DataFrame(columns=["patent_id", "abstract"])
        save_clean(empty, "clean_abstracts")
        return empty

    print(f"    Using: {zip_path.name}")
    df = read_tsv_from_zip(zip_path, usecols=["patent_id", "patent_abstract"])

    df = df[df["patent_id"].isin(patent_ids)].copy()
    df = df.dropna(subset=["patent_id", "patent_abstract"])
    df["patent_abstract"] = df["patent_abstract"].str.strip()
    df = df.drop_duplicates(subset="patent_id")
    df = df.rename(columns={"patent_abstract": "abstract"})

    save_clean(df, "clean_abstracts")
    return df


def clean_inventors(patent_ids: set) -> pd.DataFrame:
    """
    Source: g_inventor_disambiguated.tsv.zip
    Columns used: patent_id, inventor_id, disambig_inventor_name_first,
                  disambig_inventor_name_last, location_id
    """
    cols = [
        "patent_id", "inventor_id",
        "disambig_inventor_name_first", "disambig_inventor_name_last",
        "location_id",
    ]
    df = read_tsv_from_zip(RAW_DIR / "g_inventor_disambiguated.tsv.zip",
                           usecols=cols)

    df = df[df["patent_id"].isin(patent_ids)].copy()
    df = df.dropna(subset=["patent_id", "inventor_id"])

    df["name"] = (
        df["disambig_inventor_name_first"].fillna("").str.strip()
        + " "
        + df["disambig_inventor_name_last"].fillna("").str.strip()
    ).str.strip()

    df = df.rename(columns={"location_id": "inventor_location_id"})
    df = df[["patent_id", "inventor_id", "name", "inventor_location_id"]].copy()
    df = df.drop_duplicates()

    save_clean(df, "clean_inventors")
    return df


def clean_assignees(patent_ids: set) -> pd.DataFrame:
    """
    Source: g_assignee_disambiguated.tsv.zip
    Columns used: patent_id, assignee_id, disambig_assignee_organization, location_id
    """
    cols = [
        "patent_id", "assignee_id",
        "disambig_assignee_organization",
        "location_id",
    ]
    df = read_tsv_from_zip(RAW_DIR / "g_assignee_disambiguated.tsv.zip",
                           usecols=cols)

    df = df[df["patent_id"].isin(patent_ids)].copy()
    df = df.dropna(subset=["patent_id", "disambig_assignee_organization"])
    df["name"] = df["disambig_assignee_organization"].str.strip()
    df = df.rename(columns={
        "assignee_id": "company_id",
        "location_id": "assignee_location_id",
    })
    df = df[["patent_id", "company_id", "name", "assignee_location_id"]].copy()
    df = df.drop_duplicates()

    save_clean(df, "clean_assignees")
    return df


def clean_locations() -> pd.DataFrame:
    """
    Source: g_location_disambiguated.tsv.zip
    Columns used: location_id, disambig_city, disambig_state, disambig_country,
                  latitude, longitude
    """
    cols = ["location_id", "disambig_city", "disambig_state", "disambig_country",
            "latitude", "longitude"]
    df = read_tsv_from_zip(RAW_DIR / "g_location_disambiguated.tsv.zip",
                           usecols=cols)

    df = df.dropna(subset=["location_id"])
    df = df.drop_duplicates(subset="location_id")
    df = df.rename(columns={
        "disambig_city":    "city",
        "disambig_state":   "state",
        "disambig_country": "country",
    })
    df["country"] = df["country"].str.strip().str.upper()

    save_clean(df, "clean_locations")
    return df


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"  PatentsView Data Cleaner  |  Year: {YEAR}")
    print("=" * 60)

    print(f"\n[1/6] Cleaning patents …")
    patents_df = clean_patents()
    patent_ids = set(patents_df["patent_id"])
    print(f"      → {len(patent_ids):,} patents for {YEAR}")

    print(f"\n[2/6] Cleaning applications …")
    clean_applications(patent_ids)

    print(f"\n[3/6] Cleaning abstracts …")
    clean_abstracts(patent_ids)

    print(f"\n[4/6] Cleaning inventors …")
    clean_inventors(patent_ids)

    print(f"\n[5/6] Cleaning assignees (companies) …")
    clean_assignees(patent_ids)

    print(f"\n[6/6] Cleaning locations …")
    clean_locations()

    print("\n" + "=" * 60)
    print("  Cleaning complete. Files in:", CLEAN_DIR.resolve())
    print("=" * 60)


if __name__ == "__main__":
    main()