# Architecture notes

Written to answer the "why did you build it this way?" questions.

## Why a star schema instead of normalised tables?

Operational databases are normalised for fast, safe writes. Analytics has the
opposite workload: few writes, huge reads, lots of aggregation. A star schema
denormalises deliberately so that every analytical question becomes the same
shape — `fact JOIN a few dimensions GROUP BY some attribute`. That shape is
predictable, so it can be indexed well and reasoned about.

The cost is redundancy (a customer's name repeats across dimension rows rather
than being looked up). For a warehouse that is the correct trade: storage is
cheap, analyst waiting time is not.

## Why surrogate keys?

Each dimension has its own generated integer key rather than reusing the source
system's ID. Source IDs are unreliable: they get reused after deletion, they
collide when two files come from different systems, and they change format.
A surrogate key is owned by the warehouse, so the fact table's foreign keys
never break when the source changes.

## Why two database connections?

`session.py` builds two engines:

- `engine` — read/write, used by ETL, auth and the hand-written analytics queries.
- `readonly_engine` — used **only** to execute LLM-generated SQL.

This is defence in depth. The application-level SQL guard is the first line, but
security that depends on one check is fragile. The read-only role and read-only
transaction mean that even a guard bug cannot produce a write.

## Why is the ETL one transaction?

A partially loaded file is worse than a failed one: the dashboards show numbers
that are wrong in a way nobody can see. Wrapping the load in a single
transaction means the outcome is binary — the file is fully in, or fully out.

## Why are dashboard queries hand-written rather than LLM-generated?

The numbers a business reports on must be exact and repeatable. An LLM is
non-deterministic; the same question could produce slightly different SQL and
therefore different numbers. So the LLM handles *exploration* (ad-hoc questions,
where the SQL is shown and auditable) and hand-written SQL handles the
*reported* figures.

## Why are insights rule-based, not LLM-generated?

`generate_insights()` derives statements directly from query results
("region X trails at Rs N"). If an LLM wrote these freely it could produce
plausible-sounding figures that aren't in the data. The LLM's job is to explain
numbers it has been given, never to invent them.

## Why linear regression for forecasting?

A single uploaded file typically gives 12-36 monthly points. On that little
data, ARIMA and Prophet have more parameters than the series can support and
tend to fit noise. A linear trend plus a month-of-year seasonal index is honest
about how much signal is actually present, and the reported R² and RMSE let the
user judge whether to trust it. The function returns a plain dict, so a
different model can be substituted without touching the API or the UI.

## What would need to change to scale this up

- **Multi-tenancy** — add a tenant key to every dimension and fact row, and
  filter on it in every query.
- **Incremental loads** — the current ETL appends a whole file per batch. Large
  daily feeds would want partition-by-date plus an upsert on a business key.
- **Slowly changing dimensions** — customer segments change over time. Today the
  dimension is overwritten (SCD type 1); tracking history needs type 2 with
  valid-from/valid-to columns.
- **Query caching** — dashboard queries re-aggregate the fact table on every
  load. Materialised views refreshed after each ETL run would cut this sharply.
- **Async ETL** — uploads are processed in the request. Beyond a few hundred
  thousand rows this belongs in a background worker (Celery/RQ) with a job
  status endpoint.
