# Ledger — AI-Powered BI & Data Warehouse Platform

Upload a business dataset, and it moves through an ETL pipeline into a
star-schema PostgreSQL warehouse. From there: dashboards, plain-English
questions answered by an LLM that writes its own SQL, and revenue forecasting.

**Stack** — React · Chart.js · FastAPI · SQLAlchemy · PostgreSQL · Pandas · Groq (Llama 3) · Docker

---

## Run it

### Docker (everything at once)

```bash
cp .env.example .env         # then add your GROQ_API_KEY
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

### Local development

```bash
# database
docker compose up db -d

# backend
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173
```

### First run

1. Open the app and **create an account** (choose the `analyst` role).
2. Go to **Data** and upload `datasets/sample_sales.csv` (3,000 rows, 2024–2025).
3. **Overview** fills with KPIs and charts.
4. **Ask** — try *"What is the best-selling product?"*
5. **Forecast** — projects the next 6 months.

The chatbot needs a free Groq API key in `.env`. Everything else works without it.

---

## How it fits together

```
React (Chart.js)
      │  REST + JWT
FastAPI
      ├── ETL engine ────────┐
      ├── Analytics engine ──┤
      ├── Forecasting ───────┼──►  PostgreSQL star-schema warehouse
      └── AI service ────────┘     (chatbot uses a READ-ONLY connection)
             │
          Groq LLM
```

### The warehouse (star schema)

One fact table of measurable events, four dimensions that describe them:

```
        dim_date      dim_customer
             \            /
              \          /
               fact_sales          measures: quantity, revenue, cost, profit
              /          \
             /            \
      dim_product     dim_location
```

Every dimension uses a **surrogate key** rather than the source system's ID,
because source IDs get reused and collide across uploaded files. Full DDL,
indexes and constraints: `database/schema.sql`.

### The ETL pipeline (`backend/app/etl/pipeline.py`)

| Stage | What happens |
|---|---|
| Extract | Read CSV/XLSX; reject unreadable files; SHA-256 hash blocks duplicate uploads |
| Transform | Normalise headers (30+ column aliases), coerce types, drop duplicates, rescale percentage discounts, derive `revenue` and `profit`, reject invalid rows |
| Load | Upsert dimensions, resolve surrogate keys, bulk-insert facts |

The whole load runs in **one transaction**. If row 4,999 fails, nothing lands —
the warehouse is never left half-updated. Rejected rows are counted and logged
rather than silently dropped.

### The AI chatbot — and why it's safe

An LLM writes SQL that we then execute. That is untrusted input, so there are
**three independent layers of defence**:

1. **`sql_guard.py`** — strips comments, then rejects anything that isn't a
   single read-only `SELECT`: no stacked statements, no `INSERT/UPDATE/DELETE/
   DROP/ALTER/CREATE/GRANT`, no `SELECT … INTO`, no system catalogues, and only
   the five warehouse tables. A `LIMIT` is forced on if absent.
2. **A read-only Postgres role** (`bi_readonly`) — the chatbot connects as a
   role that has no write privileges at all.
3. **A read-only transaction** — the connection sets
   `default_transaction_read_only=on`.

Any one layer failing still leaves the warehouse safe. The generated SQL is
always returned to the UI so an analyst can audit exactly what ran.

### Forecasting (`backend/app/forecasting/forecast.py`)

Least-squares trend plus a month-of-year seasonal index, with a 95% band from
in-sample RMSE. On the short series one upload usually provides, this is more
stable and easier to defend than a heavier model that would overfit. The
interface is model-agnostic so ARIMA or Prophet can be swapped in.

---

## Project layout

```
ai-bi-platform/
├── docker-compose.yml
├── database/schema.sql          star schema DDL, indexes, read-only role
├── datasets/sample_sales.csv    3,000 rows of realistic sample data
├── backend/
│   └── app/
│       ├── main.py              FastAPI app
│       ├── config.py            env-driven settings
│       ├── api/routes.py        every endpoint
│       ├── auth/security.py     JWT + role checks
│       ├── database/session.py  read/write and read-only engines
│       ├── models/warehouse.py  ORM models
│       ├── etl/pipeline.py      extract / transform / load
│       ├── analytics/kpis.py    dashboard queries + insight rules
│       ├── chatbot/
│       │   ├── sql_guard.py     SQL validation (security-critical)
│       │   └── nl2sql.py        Groq prompt -> SQL -> answer
│       └── forecasting/forecast.py
└── frontend/src/
    ├── pages/{Login,Dashboard,Upload,Chat,Forecast}.jsx
    ├── components/Shell.jsx
    └── styles.css
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` · `/api/auth/login` | Accounts and JWT |
| POST | `/api/upload` | Upload a dataset, run ETL |
| GET | `/api/upload/history` · `/api/upload/{id}/logs` | Audit trail |
| GET | `/api/analytics/kpis` · `/monthly` · `/products` · `/customers` · `/regions` · `/categories` · `/insights` | Dashboard data |
| POST | `/api/chat` | Ask a question in plain English |
| GET | `/api/forecast?periods=6` | Revenue projection |

Interactive docs at `/docs`.

## Roles

| Role | Can do |
|---|---|
| viewer | Read dashboards, ask questions |
| analyst | The above, plus upload datasets |
| admin | Everything |

## Your data file

Required columns (names are flexible — the pipeline recognises common aliases):

| Needed | Recognised as |
|---|---|
| date | `order_date`, `date`, `transaction_date` |
| product | `product_name`, `product`, `item` |
| quantity | `quantity`, `qty`, `units` |
| price | `unit_price`, `price`, `rate` |

Optional but useful: `customer_name`, `segment`, `category`, `city`, `state`,
`region`, `discount`, `cost`. Anything missing gets a sensible default and a
warning on the upload screen.

## Known limits

- Forecasting needs at least 4 months of history.
- Without a cost column, profit is estimated at a 70% cost ratio (flagged in the UI).
- The chatbot only reads the five warehouse tables — by design.
- Single-tenant: all uploads land in one shared warehouse.
