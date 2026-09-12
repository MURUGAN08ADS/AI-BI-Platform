-- ============================================================
-- AI-Powered BI Platform — Data Warehouse (Star Schema)
--
-- WHY A STAR SCHEMA:
-- Operational (OLTP) tables are normalised for fast writes. Analytics
-- needs the opposite: few, wide joins and fast aggregation. A star
-- schema keeps one central FACT table of measurable events (sales)
-- surrounded by DIMENSION tables that describe them (who/what/where/when).
-- Every analytical query becomes "fact JOIN a few dims GROUP BY dim
-- attribute", which is predictable and index-friendly.
--
-- SURROGATE KEYS: each dimension uses its own generated integer key
-- rather than the source system's ID. Source IDs change, get reused, or
-- collide across uploaded files; surrogate keys keep the warehouse stable.
-- ============================================================

-- ---------- upload / ETL bookkeeping ----------
CREATE TABLE IF NOT EXISTS upload_batch (
    batch_id        SERIAL PRIMARY KEY,
    filename        TEXT        NOT NULL,
    file_hash       CHAR(64)    NOT NULL,          -- SHA-256, blocks duplicate uploads
    row_count       INTEGER     NOT NULL DEFAULT 0,
    rows_rejected   INTEGER     NOT NULL DEFAULT 0,
    status          TEXT        NOT NULL DEFAULT 'pending',  -- pending|success|failed
    message         TEXT,
    uploaded_by     TEXT,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_upload_hash UNIQUE (file_hash)
);

CREATE TABLE IF NOT EXISTS etl_log (
    log_id      SERIAL PRIMARY KEY,
    batch_id    INTEGER REFERENCES upload_batch(batch_id) ON DELETE CASCADE,
    stage       TEXT        NOT NULL,      -- extract|transform|load
    level       TEXT        NOT NULL,      -- info|warning|error
    message     TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------- users ----------
CREATE TABLE IF NOT EXISTS app_user (
    user_id       SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT        NOT NULL,
    role          TEXT        NOT NULL DEFAULT 'analyst',  -- admin|analyst|viewer
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------- dimensions ----------
CREATE TABLE IF NOT EXISTS dim_date (
    date_key    INTEGER PRIMARY KEY,       -- yyyymmdd, readable and joinable
    full_date   DATE    NOT NULL UNIQUE,
    year        SMALLINT NOT NULL,
    quarter     SMALLINT NOT NULL,
    month       SMALLINT NOT NULL,
    month_name  TEXT     NOT NULL,
    day         SMALLINT NOT NULL,
    day_name    TEXT     NOT NULL,
    is_weekend  BOOLEAN  NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key  SERIAL PRIMARY KEY,
    customer_id   TEXT UNIQUE NOT NULL,    -- natural key from the source file
    customer_name TEXT NOT NULL,
    segment       TEXT
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key  SERIAL PRIMARY KEY,
    product_id   TEXT UNIQUE NOT NULL,
    product_name TEXT NOT NULL,
    category     TEXT,
    sub_category TEXT
);

CREATE TABLE IF NOT EXISTS dim_location (
    location_key SERIAL PRIMARY KEY,
    city         TEXT NOT NULL,
    state        TEXT,
    region       TEXT,
    country      TEXT DEFAULT 'India',
    CONSTRAINT uq_location UNIQUE (city, state, region, country)
);

-- ---------- fact ----------
CREATE TABLE IF NOT EXISTS fact_sales (
    sales_key     BIGSERIAL PRIMARY KEY,
    date_key      INTEGER NOT NULL REFERENCES dim_date(date_key),
    customer_key  INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key   INTEGER NOT NULL REFERENCES dim_product(product_key),
    location_key  INTEGER NOT NULL REFERENCES dim_location(location_key),
    batch_id      INTEGER REFERENCES upload_batch(batch_id) ON DELETE CASCADE,
    order_id      TEXT,
    quantity      INTEGER        NOT NULL CHECK (quantity >= 0),
    unit_price    NUMERIC(12,2)  NOT NULL CHECK (unit_price >= 0),
    discount      NUMERIC(5,4)   NOT NULL DEFAULT 0 CHECK (discount BETWEEN 0 AND 1),
    revenue       NUMERIC(14,2)  NOT NULL,   -- derived: qty * price * (1 - discount)
    cost          NUMERIC(14,2)  NOT NULL DEFAULT 0,
    profit        NUMERIC(14,2)  NOT NULL    -- derived: revenue - cost
);

-- ---------- indexes ----------
-- Foreign keys are the join columns of every analytical query, so each
-- one is indexed. Without these, every dashboard query is a seq scan.
CREATE INDEX IF NOT EXISTS ix_fact_date     ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS ix_fact_customer ON fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS ix_fact_product  ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS ix_fact_location ON fact_sales(location_key);
CREATE INDEX IF NOT EXISTS ix_fact_batch    ON fact_sales(batch_id);
CREATE INDEX IF NOT EXISTS ix_date_year_mon ON dim_date(year, month);

-- ---------- read-only role for the AI chatbot ----------
-- The LLM generates SQL. Even with application-level validation, the
-- database itself should refuse to let that SQL write anything. Defence
-- in depth: the chatbot connects as this role, which physically cannot
-- INSERT/UPDATE/DELETE/DROP.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_readonly') THEN
        CREATE ROLE bi_readonly LOGIN PASSWORD 'readonly_pass';
    END IF;
END $$;

GRANT CONNECT ON DATABASE bi_warehouse TO bi_readonly;
GRANT USAGE ON SCHEMA public TO bi_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bi_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bi_readonly;
