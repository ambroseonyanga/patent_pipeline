"""
03_load_db.py
~~~~~~~~~~~~~
Creates the PostgreSQL database schema and loads all clean CSV files.

Handles:
  - Running schema.sql to create/reset tables
  - Efficient bulk loading using COPY (via psycopg2)
  - Chunked loading for large relationship tables to prevent memory stalls
  - Foreign key pre-validation to avoid silent transaction hangs
  - Foreign key ordering (locations → inventors/companies → patents → relationships)
  - Progress reporting per chunk

Run:
    python scripts/03_load_db.py
"""

import os
import csv
import io
import sys
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

# Tune this based on available RAM; 50k rows ≈ ~10–20 MB per chunk
CHUNK_SIZE = 50_000


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_connection() -> psycopg2.extensions.connection:
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print(f"\n  ✗ Could not connect to database: {e}")
        sys.exit(1)


def run_schema(conn) -> None:
    """Drop and recreate all tables using schema.sql."""
    print("  Applying schema …")
    sql = SCHEMA_SQL.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("  ✓ Schema applied")


def bulk_copy_chunk(cur, df: pd.DataFrame, table: str, columns: list[str]) -> int:
    """
    Stream a single DataFrame chunk into PostgreSQL via COPY.
    Returns number of rows written.
    """
    chunk = df[columns].copy()
    buf = io.StringIO()
    chunk.to_csv(buf, index=False, header=False,
                 na_rep="\\N", quoting=csv.QUOTE_MINIMAL)
    buf.seek(0)
    cur.copy_expert(
        f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH CSV NULL '\\N'",
        buf,
    )
    return len(chunk)


def bulk_copy(conn, df: pd.DataFrame, table: str, columns: list[str],
              chunk_size: int = CHUNK_SIZE) -> int:
    """
    Bulk-load a DataFrame into a table in chunks.
    Commits after every chunk so progress is never lost on failure.
    Returns total rows inserted.
    """
    total = 0
    n_chunks = max(1, (len(df) + chunk_size - 1) // chunk_size)

    for i in range(0, len(df), chunk_size):
        chunk_df = df.iloc[i : i + chunk_size]
        chunk_num = (i // chunk_size) + 1
        try:
            with conn.cursor() as cur:
                rows = bulk_copy_chunk(cur, chunk_df, table, columns)
            conn.commit()
            total += rows
            if n_chunks > 1:
                print(f"    chunk {chunk_num}/{n_chunks} — {total:,} rows so far …",
                      end="\r", flush=True)
        except Exception as e:
            conn.rollback()
            print(f"\n  ✗ Failed on chunk {chunk_num}/{n_chunks} for table '{table}': {e}")
            raise

    if n_chunks > 1:
        print()  # newline after \r progress

    return total


def read_csv(filename: str, usecols: list[str] | None = None) -> pd.DataFrame:
    """Read a clean CSV, coercing empty strings to NaN."""
    path = CLEAN_DIR / filename
    df = pd.read_csv(path, dtype=str, keep_default_na=False,
                     usecols=usecols)
    return df.replace("", float("nan"))


def filter_fk(df: pd.DataFrame, fk_col: str, valid_ids: set,
              label: str) -> pd.DataFrame:
    """
    Drop rows whose FK column value is not in valid_ids.
    Prints a warning if any rows are dropped.
    """
    before = len(df)
    df = df[df[fk_col].isin(valid_ids)]
    dropped = before - len(df)
    if dropped:
        print(f"  ⚠  {dropped:,} rows dropped from {label} "
              f"(orphaned {fk_col})")
    return df


# ── Load functions ────────────────────────────────────────────────────────────

def load_locations(conn) -> set:
    print("\n[1/7] Loading locations …")
    df = read_csv("clean_locations.csv")
    df = (df[["location_id", "city", "state", "country", "latitude", "longitude"]]
          .drop_duplicates("location_id"))
    n = bulk_copy(conn, df, "locations",
                  ["location_id", "city", "state", "country",
                   "latitude", "longitude"])
    print(f"  ✓ {n:,} locations loaded")
    return set(df["location_id"].dropna())


def load_inventors(conn, valid_location_ids: set) -> set:
    print("\n[2/7] Loading inventors …")
    df = read_csv("clean_inventors.csv")
    inv = (df[["inventor_id", "name", "inventor_location_id"]]
           .drop_duplicates("inventor_id")
           .rename(columns={"inventor_location_id": "location_id"}))
    inv = filter_fk(inv, "location_id", valid_location_ids, "inventors")
    n = bulk_copy(conn, inv, "inventors",
                  ["inventor_id", "name", "location_id"])
    print(f"  ✓ {n:,} unique inventors loaded")
    # Return only IDs that were actually inserted (inv, not df).
    # df contains ALL inventor_ids from the CSV, including those dropped by the
    # FK filter — returning df["inventor_id"] would include IDs absent from the
    # inventors table, causing FK violations in load_patent_inventors.
    return set(inv["inventor_id"].dropna())


def load_companies(conn, valid_location_ids: set) -> set:
    print("\n[3/7] Loading companies …")
    df = read_csv("clean_assignees.csv")
    comp = (df[["company_id", "name", "assignee_location_id"]]
            .drop_duplicates("company_id")
            .rename(columns={"assignee_location_id": "location_id"}))
    comp = filter_fk(comp, "location_id", valid_location_ids, "companies")
    n = bulk_copy(conn, comp, "companies",
                  ["company_id", "name", "location_id"])
    print(f"  ✓ {n:,} unique companies loaded")
    # Same reasoning as load_inventors — return comp, not df.
    return set(comp["company_id"].dropna())


def load_patents(conn) -> set:
    print("\n[4/7] Loading patents …")
    patents_df = read_csv("clean_patents.csv")
    apps_df    = read_csv("clean_applications.csv",
                          usecols=["patent_id", "filing_date"])
    df = patents_df.merge(apps_df, on="patent_id", how="left")
    n = bulk_copy(conn, df, "patents",
                  ["patent_id", "title", "filing_date", "grant_date",
                   "year", "patent_type"])
    print(f"  ✓ {n:,} patents loaded")
    return set(df["patent_id"].dropna())


def load_abstracts(conn, valid_patent_ids: set) -> None:
    print("\n[5/7] Loading abstracts …")
    df = read_csv("clean_abstracts.csv")
    df = filter_fk(df, "patent_id", valid_patent_ids, "abstracts")
    n = bulk_copy(conn, df, "abstracts", ["patent_id", "abstract"])
    print(f"  ✓ {n:,} abstracts loaded")


def load_patent_inventors(conn,
                           valid_patent_ids: set,
                           valid_inventor_ids: set) -> None:
    print("\n[6/7] Loading patent ↔ inventor relationships …")
    df = read_csv("clean_inventors.csv")
    rel = df[["patent_id", "inventor_id"]].drop_duplicates()

    # Validate both FK columns before attempting the COPY
    rel = filter_fk(rel, "patent_id",   valid_patent_ids,   "patent_inventors(patent_id)")
    rel = filter_fk(rel, "inventor_id", valid_inventor_ids, "patent_inventors(inventor_id)")

    n = bulk_copy(conn, rel, "patent_inventors",
                  ["patent_id", "inventor_id"])
    print(f"  ✓ {n:,} patent-inventor links loaded")


def load_patent_companies(conn,
                           valid_patent_ids: set,
                           valid_company_ids: set) -> None:
    print("\n[7/7] Loading patent ↔ company relationships …")
    df = read_csv("clean_assignees.csv")
    rel = df[["patent_id", "company_id"]].drop_duplicates()

    # Validate both FK columns before attempting the COPY
    rel = filter_fk(rel, "patent_id",  valid_patent_ids,  "patent_companies(patent_id)")
    rel = filter_fk(rel, "company_id", valid_company_ids, "patent_companies(company_id)")

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

    # Each load function returns the set of valid IDs for downstream FK checks.
    # Load order follows FK dependency chain:
    #   locations → inventors / companies → patents → abstracts → junction tables
    try:
        valid_location_ids = load_locations(conn)
        valid_inventor_ids = load_inventors(conn, valid_location_ids)
        valid_company_ids  = load_companies(conn, valid_location_ids)
        valid_patent_ids   = load_patents(conn)

        load_abstracts(conn, valid_patent_ids)
        load_patent_inventors(conn, valid_patent_ids, valid_inventor_ids)
        load_patent_companies(conn, valid_patent_ids, valid_company_ids)

    except Exception as e:
        print(f"\n  ✗ Load aborted: {e}")
        conn.close()
        sys.exit(1)

    conn.close()

    print("\n" + "=" * 60)
    print("  All data loaded successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()