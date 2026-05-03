-- schema.sql
-- ──────────────────────────────────────────────────────────────────────────
-- Global Patent Intelligence Database Schema
-- Database: PostgreSQL
-- ──────────────────────────────────────────────────────────────────────────

-- Drop in reverse dependency order (safe re-run)
DROP TABLE IF EXISTS patent_inventors  CASCADE;
DROP TABLE IF EXISTS patent_companies  CASCADE;
DROP TABLE IF EXISTS abstracts         CASCADE;
DROP TABLE IF EXISTS patents           CASCADE;
DROP TABLE IF EXISTS inventors         CASCADE;
DROP TABLE IF EXISTS companies         CASCADE;
DROP TABLE IF EXISTS locations         CASCADE;

-- ── Locations ──────────────────────────────────────────────────────────────
CREATE TABLE locations (
    location_id  TEXT PRIMARY KEY,
    city         TEXT,
    state        TEXT,
    country      CHAR(2),          -- ISO-2 country code
    latitude     NUMERIC(9, 6),
    longitude    NUMERIC(9, 6)
);

-- ── Inventors ──────────────────────────────────────────────────────────────
CREATE TABLE inventors (
    inventor_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    location_id  TEXT REFERENCES locations(location_id)
);

-- ── Companies (Assignees) ──────────────────────────────────────────────────
CREATE TABLE companies (
    company_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    location_id  TEXT REFERENCES locations(location_id)
);

-- ── Patents ────────────────────────────────────────────────────────────────
CREATE TABLE patents (
    patent_id    TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    filing_date  DATE,
    grant_date   DATE,
    year         SMALLINT,
    patent_type  TEXT
);

-- ── Abstracts (separate to keep patents table lean) ────────────────────────
CREATE TABLE abstracts (
    patent_id    TEXT PRIMARY KEY REFERENCES patents(patent_id),
    abstract     TEXT
);

-- ── Relationship: Patents ↔ Inventors ─────────────────────────────────────
CREATE TABLE patent_inventors (
    patent_id    TEXT REFERENCES patents(patent_id),
    inventor_id  TEXT REFERENCES inventors(inventor_id),
    PRIMARY KEY (patent_id, inventor_id)
);

-- ── Relationship: Patents ↔ Companies ─────────────────────────────────────
CREATE TABLE patent_companies (
    patent_id    TEXT REFERENCES patents(patent_id),
    company_id   TEXT REFERENCES companies(company_id),
    PRIMARY KEY (patent_id, company_id)
);

-- ── Indexes for query performance ──────────────────────────────────────────
CREATE INDEX idx_patents_year         ON patents(year);
CREATE INDEX idx_patents_filing_date  ON patents(filing_date);
CREATE INDEX idx_inventors_name       ON inventors(name);
CREATE INDEX idx_companies_name       ON companies(name);
CREATE INDEX idx_locations_country    ON locations(country);
CREATE INDEX idx_patent_inventors_inv ON patent_inventors(inventor_id);
CREATE INDEX idx_patent_companies_co  ON patent_companies(company_id);
