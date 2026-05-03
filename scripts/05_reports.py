"""
05_reports.py
~~~~~~~~~~~~~
Runs all 7 analytical SQL queries against the PostgreSQL database
and generates three types of reports:

  A) Console Report   – formatted terminal output
  B) CSV Reports      – top_inventors.csv, top_companies.csv, country_trends.csv
  C) JSON Report      – report.json (summary)

Optionally generates matplotlib charts if matplotlib is installed.

Run:
    python scripts/05_reports.py
"""

import os
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import psycopg2
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

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

TOP_N = 10   # how many rows to show in console report


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def query(conn, sql: str) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn)


def divider(char="─", width=60):
    return char * width


# ── SQL Queries ───────────────────────────────────────────────────────────────

SQL_TOTAL = "SELECT COUNT(*) AS total FROM patents;"

SQL_Q1 = """
SELECT
    i.name                         AS inventor_name,
    COALESCE(l.country,'?')        AS country,
    COUNT(DISTINCT pi.patent_id)   AS patents
FROM inventors i
JOIN patent_inventors pi ON pi.inventor_id = i.inventor_id
LEFT JOIN locations l    ON l.location_id  = i.location_id
GROUP BY i.name, l.country
ORDER BY patents DESC
LIMIT 20;
"""

SQL_Q2 = """
SELECT
    c.name                         AS company_name,
    COALESCE(l.country,'?')        AS country,
    COUNT(DISTINCT pc.patent_id)   AS patents
FROM companies c
JOIN patent_companies pc ON pc.company_id = c.company_id
LEFT JOIN locations l    ON l.location_id = c.location_id
GROUP BY c.name, l.country
ORDER BY patents DESC
LIMIT 20;
"""

SQL_Q3 = """
SELECT
    COALESCE(l.country,'UNKNOWN')  AS country,
    COUNT(DISTINCT pi.patent_id)   AS patents,
    ROUND(100.0 * COUNT(DISTINCT pi.patent_id) /
          SUM(COUNT(DISTINCT pi.patent_id)) OVER(), 2) AS pct_share
FROM patent_inventors pi
JOIN inventors i  ON i.inventor_id  = pi.inventor_id
LEFT JOIN locations l ON l.location_id = i.location_id
GROUP BY l.country
ORDER BY patents DESC
LIMIT 20;
"""

SQL_Q4 = """
SELECT
    year,
    COUNT(*) AS patents_granted
FROM patents
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year;
"""

SQL_Q7 = """
WITH counts AS (
    SELECT
        i.name                         AS inventor_name,
        COALESCE(l.country,'?')        AS country,
        COUNT(DISTINCT pi.patent_id)   AS patents
    FROM inventors i
    JOIN patent_inventors pi ON pi.inventor_id = i.inventor_id
    LEFT JOIN locations l    ON l.location_id  = i.location_id
    GROUP BY i.name, l.country
)
SELECT
    inventor_name, country, patents,
    RANK() OVER (ORDER BY patents DESC) AS global_rank,
    RANK() OVER (PARTITION BY country ORDER BY patents DESC) AS country_rank
FROM counts
ORDER BY global_rank
LIMIT 50;
"""


# ── Report A: Console ─────────────────────────────────────────────────────────

def print_console_report(conn) -> dict:
    """Print formatted console report. Returns summary dict for JSON."""
    W = 62
    print()
    print("=" * W)
    print(f"{'GLOBAL PATENT INTELLIGENCE REPORT':^{W}}")
    print(f"{'Generated: ' + datetime.now().strftime('%Y-%m-%d %H:%M'):^{W}}")
    print("=" * W)

    # Total patents
    total = query(conn, SQL_TOTAL)["total"].iloc[0]
    print(f"\n  📊 Total Patents in Database: {total:,}")

    # ── Top Inventors ──
    print(f"\n  {divider()}")
    print(f"  {'Q1: TOP INVENTORS'}")
    print(f"  {divider()}")
    inv_df = query(conn, SQL_Q1)
    for i, row in inv_df.head(TOP_N).iterrows():
        rank = i + 1
        print(f"  {rank:>2}. {row['inventor_name']:<35} "
              f"{row['patents']:>4} patents  [{row['country']}]")

    # ── Top Companies ──
    print(f"\n  {divider()}")
    print(f"  {'Q2: TOP COMPANIES'}")
    print(f"  {divider()}")
    comp_df = query(conn, SQL_Q2)
    for i, row in comp_df.head(TOP_N).iterrows():
        rank = i + 1
        print(f"  {rank:>2}. {row['company_name']:<35} "
              f"{row['patents']:>5} patents  [{row['country']}]")

    # ── Top Countries ──
    print(f"\n  {divider()}")
    print(f"  {'Q3: TOP COUNTRIES (by inventor)'}")
    print(f"  {divider()}")
    country_df = query(conn, SQL_Q3)
    for i, row in country_df.head(TOP_N).iterrows():
        rank = i + 1
        bar_len = int(row["pct_share"] / 2)
        bar = "█" * bar_len
        print(f"  {rank:>2}. {row['country']:<6} {bar:<25} "
              f"{row['pct_share']:>5}%  ({row['patents']:,})")

    # ── Year Trends ──
    print(f"\n  {divider()}")
    print(f"  {'Q4: PATENTS OVER TIME'}")
    print(f"  {divider()}")
    trend_df = query(conn, SQL_Q4)
    for _, row in trend_df.iterrows():
        print(f"  {int(row['year'])}: {row['patents_granted']:,}")

    # ── Rankings (Q7) ──
    print(f"\n  {divider()}")
    print(f"  {'Q7: INVENTOR RANKINGS (with window functions)'}")
    print(f"  {divider()}")
    rank_df = query(conn, SQL_Q7)
    print(f"  {'Rank':<6} {'Inventor':<35} {'Country':<6} "
          f"{'Patents':>7} {'Ctry Rank':>9}")
    print(f"  {'-'*4:<6} {'-'*33:<35} {'-'*4:<6} {'-'*7:>7} {'-'*9:>9}")
    for _, row in rank_df.head(TOP_N).iterrows():
        print(f"  {int(row['global_rank']):<6} {row['inventor_name']:<35} "
              f"{row['country']:<6} {row['patents']:>7} {int(row['country_rank']):>9}")

    print()
    print("=" * W)

    # Return summary for JSON
    return {
        "total_patents": int(total),
        "top_inventors": [
            {"rank": i+1, "name": r["inventor_name"],
             "country": r["country"], "patents": int(r["patents"])}
            for i, r in inv_df.head(TOP_N).iterrows()
        ],
        "top_companies": [
            {"rank": i+1, "name": r["company_name"],
             "country": r["country"], "patents": int(r["patents"])}
            for i, r in comp_df.head(TOP_N).iterrows()
        ],
        "top_countries": [
            {"country": r["country"], "patents": int(r["patents"]),
             "pct_share": float(r["pct_share"])}
            for _, r in country_df.head(10).iterrows()
        ],
        "yearly_trends": [
            {"year": int(r["year"]), "patents": int(r["patents_granted"])}
            for _, r in trend_df.iterrows()
        ],
    }


# ── Report B: CSV Files ───────────────────────────────────────────────────────

def save_csv_reports(conn) -> None:
    print("\n  Saving CSV reports …")

    inv_df = query(conn, SQL_Q1)
    inv_df.to_csv(REPORTS_DIR / "top_inventors.csv", index=False)
    print(f"  ✓ top_inventors.csv  ({len(inv_df)} rows)")

    comp_df = query(conn, SQL_Q2)
    comp_df.to_csv(REPORTS_DIR / "top_companies.csv", index=False)
    print(f"  ✓ top_companies.csv  ({len(comp_df)} rows)")

    country_df = query(conn, SQL_Q3)
    country_df.to_csv(REPORTS_DIR / "country_trends.csv", index=False)
    print(f"  ✓ country_trends.csv ({len(country_df)} rows)")

    trend_df = query(conn, SQL_Q4)
    trend_df.to_csv(REPORTS_DIR / "yearly_trends.csv", index=False)
    print(f"  ✓ yearly_trends.csv  ({len(trend_df)} rows)")

    rank_df = query(conn, SQL_Q7)
    rank_df.to_csv(REPORTS_DIR / "inventor_rankings.csv", index=False)
    print(f"  ✓ inventor_rankings.csv ({len(rank_df)} rows)")


# ── Report C: JSON ────────────────────────────────────────────────────────────

def save_json_report(summary: dict) -> None:
    out = REPORTS_DIR / "report.json"
    summary["generated_at"] = datetime.now().isoformat()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n  ✓ report.json saved → {out}")


# ── Optional: Charts ──────────────────────────────────────────────────────────

def save_charts(conn) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")           # non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mtick
    except ImportError:
        print("\n  (matplotlib not installed – skipping charts)")
        return

    print("\n  Generating charts …")

    # Chart 1: Top Companies bar chart
    comp_df = query(conn, SQL_Q2).head(15)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(comp_df["company_name"][::-1], comp_df["patents"][::-1],
            color="steelblue")
    ax.set_xlabel("Number of Patents")
    ax.set_title("Top 15 Assignee Companies by Patent Count")
    plt.tight_layout()
    fig.savefig(REPORTS_DIR / "chart_top_companies.png", dpi=150)
    plt.close(fig)
    print("  ✓ chart_top_companies.png")

    # Chart 2: Yearly trend line
    trend_df = query(conn, SQL_Q4)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(trend_df["year"], trend_df["patents_granted"],
            marker="o", linewidth=2, color="darkorange")
    ax.set_xlabel("Year")
    ax.set_ylabel("Patents Granted")
    ax.set_title("US Patents Granted by Year")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(
        lambda x, _: f"{int(x):,}"))
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(REPORTS_DIR / "chart_yearly_trends.png", dpi=150)
    plt.close(fig)
    print("  ✓ chart_yearly_trends.png")

    # Chart 3: Top Countries pie chart
    c_df = query(conn, SQL_Q3).head(8)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(c_df["patents"], labels=c_df["country"],
           autopct="%1.1f%%", startangle=140)
    ax.set_title("Patent Share by Country (Top 8)")
    plt.tight_layout()
    fig.savefig(REPORTS_DIR / "chart_countries.png", dpi=150)
    plt.close(fig)
    print("  ✓ chart_countries.png")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    conn = get_conn()

    # A: Console
    summary = print_console_report(conn)

    # B: CSV
    save_csv_reports(conn)

    # C: JSON
    save_json_report(summary)

    # Optional: Charts
    save_charts(conn)

    conn.close()
    print(f"\n  All reports saved to: {REPORTS_DIR.resolve()}")


if __name__ == "__main__":
    main()
