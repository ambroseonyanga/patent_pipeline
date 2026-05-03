-- =============================================================================
-- queries.sql  –  Global Patent Intelligence: Analytical Queries
-- =============================================================================
-- Q1  Top Inventors      – who has the most patents?
-- Q2  Top Companies      – which companies own the most patents?
-- Q3  Countries          – which countries produce the most patents?
-- Q4  Trends Over Time   – patents per year
-- Q5  JOIN Query         – combine patents, inventors, companies
-- Q6  CTE Query          – break complex query into steps
-- Q7  Ranking Query      – rank inventors using window functions
-- =============================================================================


-- ── Q1: Top Inventors ─────────────────────────────────────────────────────
-- Who has the most patents?

SELECT
    i.inventor_id,
    i.name                          AS inventor_name,
    l.country,
    COUNT(DISTINCT pi.patent_id)    AS patent_count
FROM inventors i
JOIN patent_inventors pi ON pi.inventor_id = i.inventor_id
LEFT JOIN locations l    ON l.location_id  = i.location_id
GROUP BY i.inventor_id, i.name, l.country
ORDER BY patent_count DESC
LIMIT 20;


-- ── Q2: Top Companies ─────────────────────────────────────────────────────
-- Which companies own the most patents?

SELECT
    c.company_id,
    c.name                          AS company_name,
    l.country,
    COUNT(DISTINCT pc.patent_id)    AS patent_count
FROM companies c
JOIN patent_companies pc ON pc.company_id  = c.company_id
LEFT JOIN locations l    ON l.location_id  = c.location_id
GROUP BY c.company_id, c.name, l.country
ORDER BY patent_count DESC
LIMIT 20;


-- ── Q3: Countries ─────────────────────────────────────────────────────────
-- Which countries produce the most patents? (by inventor country)

SELECT
    COALESCE(l.country, 'UNKNOWN')  AS country,
    COUNT(DISTINCT pi.patent_id)    AS patent_count,
    ROUND(
        100.0 * COUNT(DISTINCT pi.patent_id)
              / SUM(COUNT(DISTINCT pi.patent_id)) OVER (),
        2
    )                               AS pct_share
FROM patent_inventors pi
JOIN inventors i  ON i.inventor_id  = pi.inventor_id
LEFT JOIN locations l ON l.location_id = i.location_id
GROUP BY l.country
ORDER BY patent_count DESC
LIMIT 20;


-- ── Q4: Trends Over Time ──────────────────────────────────────────────────
-- How many patents are granted each year?

SELECT
    year,
    COUNT(*)                        AS patents_granted,
    COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY year)
                                    AS yoy_change
FROM patents
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year;


-- ── Q5: JOIN Query ────────────────────────────────────────────────────────
-- Combine patents with their inventors and assignee companies.
-- One row per (patent, inventor, company) combination.

SELECT
    p.patent_id,
    p.title,
    p.grant_date,
    p.year,
    i.name                          AS inventor_name,
    il.country                      AS inventor_country,
    c.name                          AS company_name,
    cl.country                      AS company_country
FROM patents p
JOIN patent_inventors pi  ON pi.patent_id  = p.patent_id
JOIN inventors i          ON i.inventor_id = pi.inventor_id
LEFT JOIN locations il    ON il.location_id = i.location_id
LEFT JOIN patent_companies pc ON pc.patent_id = p.patent_id
LEFT JOIN companies c     ON c.company_id  = pc.company_id
LEFT JOIN locations cl    ON cl.location_id = c.location_id
ORDER BY p.grant_date DESC
LIMIT 100;


-- ── Q6: CTE Query ─────────────────────────────────────────────────────────
-- Break a complex question into steps using WITH.
-- Question: Which companies have more than 50 patents, and what share
--           of total patents do they represent?

WITH
-- Step 1: count patents per company
company_counts AS (
    SELECT
        c.company_id,
        c.name                      AS company_name,
        l.country,
        COUNT(DISTINCT pc.patent_id) AS patent_count
    FROM companies c
    JOIN patent_companies pc ON pc.company_id = c.company_id
    LEFT JOIN locations l    ON l.location_id = c.location_id
    GROUP BY c.company_id, c.name, l.country
),

-- Step 2: total patents in the database
totals AS (
    SELECT COUNT(*) AS total_patents FROM patents
),

-- Step 3: filter to significant companies and compute share
significant AS (
    SELECT
        cc.company_name,
        cc.country,
        cc.patent_count,
        ROUND(100.0 * cc.patent_count / t.total_patents, 4) AS pct_of_total
    FROM company_counts cc
    CROSS JOIN totals t
    WHERE cc.patent_count > 50
)

SELECT *
FROM significant
ORDER BY patent_count DESC;


-- ── Q7: Ranking Query ─────────────────────────────────────────────────────
-- Rank inventors using window functions.
-- Shows global rank, rank within their country, and running total.

WITH inventor_counts AS (
    SELECT
        i.inventor_id,
        i.name                          AS inventor_name,
        COALESCE(l.country, 'UNKNOWN')  AS country,
        COUNT(DISTINCT pi.patent_id)    AS patent_count
    FROM inventors i
    JOIN patent_inventors pi ON pi.inventor_id = i.inventor_id
    LEFT JOIN locations l    ON l.location_id  = i.location_id
    GROUP BY i.inventor_id, i.name, l.country
)

SELECT
    inventor_name,
    country,
    patent_count,

    -- Global rank
    RANK() OVER (ORDER BY patent_count DESC)
        AS global_rank,

    -- Rank within each country
    RANK() OVER (PARTITION BY country ORDER BY patent_count DESC)
        AS country_rank,

    -- Running total of patents (by global rank)
    SUM(patent_count) OVER (ORDER BY patent_count DESC ROWS UNBOUNDED PRECEDING)
        AS running_total,

    -- % contribution of this inventor
    ROUND(100.0 * patent_count / SUM(patent_count) OVER (), 4)
        AS pct_contribution

FROM inventor_counts
ORDER BY global_rank
LIMIT 50;
