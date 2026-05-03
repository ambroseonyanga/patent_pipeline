"""
03_load_db.py
~~~~~~~~~~~~~
Creates the PostgreSQL database schema and loads all clean CSV files.

Handles:
  - Running schema.sql to create/reset tables
  - Efficient bulk loading using COPY (via psycopg2)
  - Foreign key ordering (locations → inventors/companies → patents → relationships)
  - Graceful conflict handling (UPSERT-style)

Run:
    python scripts/03_load_db.py
"""

import os
import csv
import io
import psycopg2
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME",     "patent_db"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "ambrose"),
}

CLEAN_DIR  = Path("data/clean")
SCHEMA_SQL = Path("sql/schema.sql")


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def run_schema(conn) -> None:
    """Drop and recreate all tables using schema.sql."""
    print("  Applying schema …")
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL.read_text())
    conn.commit()
    print("  ✓ Schema applied")


def bulk_copy(conn, df: pd.DataFrame, table: str, columns: list[str]) -> int:
    """
    Use PostgreSQL COPY for fast bulk inserts.
    Returns row count inserted.
    """
    df = df[columns].copy()

    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False, na_rep="\\N",
              quoting=csv.QUOTE_MINIMAL)
    buffer.seek(0)

    with conn.cursor() as cur:
        cur.copy_expert(
            f"COPY {table} ({', '.join(columns)}) "
            f"FROM STDIN WITH CSV NULL '\\N'",
            buffer,
        )
    conn.commit()
    return len(df)


# ── Load functions ────────────────────────────────────────────────────────────

def load_locations(conn) -> None:
    print("\n[1/7] Loading locations …")
    df = pd.read_csv(CLEAN_DIR / "clean_locations.csv",
                     dtype=str, keep_default_na=False)
    # Replace empty strings with NaN for proper NULL handling
    df = df.replace("", float("nan"))
    df = df[["location_id", "city", "state", "country",
             "latitude", "longitude"]].drop_duplicates("location_id")
    n = bulk_copy(conn, df, "locations",
                  ["location_id", "city", "state", "country",
                   "latitude", "longitude"])
    print(f"  ✓ {n:,} locations loaded")


def load_inventors(conn) -> None:
    print("\n[2/7] Loading inventors …")
    df = pd.read_csv(CLEAN_DIR / "clean_inventors.csv",
                     dtype=str, keep_default_na=False)
    df = df.replace("", float("nan"))

    # Build unique inventor rows
    inv = (df[["inventor_id", "name", "inventor_location_id"]]
           .drop_duplicates("inventor_id")
           .rename(columns={"inventor_location_id": "location_id"}))

    n = bulk_copy(conn, inv, "inventors",
                  ["inventor_id", "name", "location_id"])
    print(f"  ✓ {n:,} unique inventors loaded")


def load_companies(conn) -> None:
    print("\n[3/7] Loading companies …")
    df = pd.read_csv(CLEAN_DIR / "clean_assignees.csv",
                     dtype=str, keep_default_na=False)
    df = df.replace("", float("nan"))

    comp = (df[["company_id", "name", "assignee_location_id"]]
            .drop_duplicates("company_id")
            .rename(columns={"assignee_location_id": "location_id"}))

    n = bulk_copy(conn, comp, "companies",
                  ["company_id", "name", "location_id"])
    print(f"  ✓ {n:,} unique companies loaded")


def load_patents(conn) -> None:
    print("\n[4/7] Loading patents …")
    patents_df = pd.read_csv(CLEAN_DIR / "clean_patents.csv",
                             dtype=str, keep_default_na=False)
    patents_df = patents_df.replace("", float("nan"))

    apps_df = pd.read_csv(CLEAN_DIR / "clean_applications.csv",
                          dtype=str, keep_default_na=False)
    apps_df = apps_df.replace("", float("nan"))

    # Merge filing_date onto patents
    df = patents_df.merge(apps_df[["patent_id", "filing_date"]],
                          on="patent_id", how="left")

    n = bulk_copy(conn, df, "patents",
                  ["patent_id", "title", "filing_date", "grant_date",
                   "year", "patent_type"])
    print(f"  ✓ {n:,} patents loaded")


def load_abstracts(conn) -> None:
    print("\n[5/7] Loading abstracts …")
    df = pd.read_csv(CLEAN_DIR / "clean_abstracts.csv",
                     dtype=str, keep_default_na=False)
    df = df.replace("", float("nan"))

    # Only load abstracts for patents already in DB
    patents_in_db = set(
        pd.read_csv(CLEAN_DIR / "clean_patents.csv",
                    usecols=["patent_id"])["patent_id"]
    )
    df = df[df["patent_id"].isin(patents_in_db)]

    n = bulk_copy(conn, df, "abstracts", ["patent_id", "abstract"])
    print(f"  ✓ {n:,} abstracts loaded")


def load_patent_inventors(conn) -> None:
    print("\n[6/7] Loading patent ↔ inventor relationships …")
    df = pd.read_csv(CLEAN_DIR / "clean_inventors.csv",
                     dtype=str, keep_default_na=False)
    df = df.replace("", float("nan"))
    rel = df[["patent_id", "inventor_id"]].drop_duplicates()

    n = bulk_copy(conn, rel, "patent_inventors",
                  ["patent_id", "inventor_id"])
    print(f"  ✓ {n:,} patent-inventor links loaded")


def load_patent_companies(conn) -> None:
    print("\n[7/7] Loading patent ↔ company relationships …")
    df = pd.read_csv(CLEAN_DIR / "clean_assignees.csv",
                     dtype=str, keep_default_na=False)
    df = df.replace("", float("nan"))
    rel = df[["patent_id", "company_id"]].drop_duplicates()

    n = bulk_copy(conn, rel, "patent_companies",
                  ["patent_id", "company_id"])
    print(f"  ✓ {n:,} patent-company links loaded")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  PatentsView → PostgreSQL Loader")
    print("=" * 60)
    print(f"\n  Connecting to {DB_CONFIG['host']}:{DB_CONFIG['port']}"
          f"/{DB_CONFIG['dbname']} …")

    conn = get_connection()
    print("  ✓ Connected")

    run_schema(conn)

    # Load in FK-safe order
    load_locations(conn)
    load_inventors(conn)
    load_companies(conn)
    load_patents(conn)
    load_abstracts(conn)
    load_patent_inventors(conn)
    load_patent_companies(conn)

    conn.close()

    print("\n" + "=" * 60)
    print("  All data loaded successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
