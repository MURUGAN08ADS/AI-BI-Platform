# Ledger — AI-Powered BI & Data Warehouse Platform

Ledger is an AI-powered Business Intelligence (BI) and Data Warehouse platform that combines ETL, analytics, data visualization, natural-language SQL querying, and revenue forecasting into a single application.

The current version focuses on **sales analytics** using a PostgreSQL star-schema data warehouse. The platform is designed with a future goal of becoming a flexible, schema-aware analytics system capable of supporting multiple business domains.

---

## 🚀 Key Features

- Upload CSV/XLSX business datasets
- Automated ETL pipeline using Pandas
- Data cleaning, validation, transformation, and loading
- SHA-256 based duplicate file detection
- PostgreSQL star-schema data warehouse
- KPI dashboards with interactive charts
- Product, customer, category, and regional analysis
- Rule-based business insights
- Natural-language business questions using an LLM
- AI-generated SQL with security validation
- Read-only database access for AI-generated queries
- Revenue forecasting using trend and seasonal analysis
- JWT-based authentication
- Role-based access control
- Docker support

---

## 🏗️ Architecture

```text
                    ┌─────────────────────┐
                    │     React Frontend  │
                    │     + Chart.js      │
                    └──────────┬──────────┘
                               │
                         REST API / JWT
                               │
                               ▼
                    ┌─────────────────────┐
                    │    FastAPI Backend  │
                    ├─────────────────────┤
                    │ Authentication      │
                    │ ETL Engine          │
                    │ Analytics Engine    │
                    │ AI Service          │
                    │ Forecasting         │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ PostgreSQL          │
                    │ Star Schema         │
                    └─────────────────────┘
                               ▲
                               │
                         Read-only access
                               │
                    ┌─────────────────────┐
                    │ Groq + Llama 3      │
                    │ Natural Language →  │
                    │ SQL                 │
                    └─────────────────────┘
🛠️ Technology Stack
Frontend
- React
- Vite
- Chart.js
- Axios
Backend
- Python
- FastAPI
- SQLAlchemy
- Pandas
- Uvicorn
Database
- PostgreSQL
- Star Schema
- SQL
AI
- Groq API
- Llama 3
- Natural Language to SQL
Security
- JWT Authentication
- bcrypt password hashing
- SQL validation
- PostgreSQL read-only role
- Read-only transactions
Deployment
- Docker
- Docker Compose
- Nginx
📊 Data Warehouse
The current warehouse uses a star schema.
                    dim_date
                       │
                       │
dim_customer ───── fact_sales ───── dim_product
                       │
                       │
                 dim_location
Fact Table
fact_sales
Contains measurable business metrics:
- Quantity
- Revenue
- Cost
- Profit
Dimension Tables
dim_date
- Date
- Month
- Quarter
- Year
dim_customer
- Customer
- Segment
dim_product
- Product
- Category
dim_location
- City
- State
- Region
🔄 ETL Pipeline
The ETL pipeline converts raw business files into structured warehouse data.
CSV / XLSX
    ↓
Extract
    ↓
Validate
    ↓
Clean & Normalize
    ↓
Transform
    ↓
Resolve Dimension Keys
    ↓
Load PostgreSQL
Extract
The application accepts CSV and XLSX files.
The ETL engine identifies supported column aliases such as:
order_date / date / transaction_date
product_name / product / item
quantity / qty / units
unit_price / price / rate
Transform
The pipeline:
- Normalizes column names
- Converts data types
- Removes duplicate rows
- Handles missing optional fields
- Converts discount percentages
- Calculates revenue
- Calculates profit
- Validates required fields
- Rejects invalid rows
Load
Clean data is loaded into the PostgreSQL star schema.
Dimension records are resolved first, and the resulting surrogate keys are used when inserting fact records.
The entire load occurs inside a database transaction.
If the load fails:
ROLLBACK
This prevents partially loaded datasets from appearing in the dashboard.
🔐 Duplicate Detection
Ledger uses SHA-256 hashing to identify duplicate uploaded files.
Uploaded File
     ↓
Read File Content
     ↓
SHA-256
     ↓
Unique Hash
     ↓
Compare With Previous Uploads
If the same file content is uploaded again, it produces the same hash and can be rejected as a duplicate.
If the file content changes, even slightly, the SHA-256 hash changes.
🤖 AI-Powered SQL
Users can ask business questions in natural language.
Example:
"What is the best-selling product?"
The request follows this flow:
User Question
      ↓
FastAPI
      ↓
Groq / Llama 3
      ↓
Generated SQL
      ↓
SQL Guard
      ↓
Read-only PostgreSQL
      ↓
Query Result
      ↓
React UI
The generated SQL is displayed to the user for transparency and auditability.
🛡️ AI SQL Security
LLM-generated SQL is treated as untrusted input.
Ledger applies multiple security layers.
Layer 1 — SQL Validation
The SQL guard:
- Allows only SELECT
- Blocks multiple statements
- Removes SQL comments
- Blocks INSERT
- Blocks UPDATE
- Blocks DELETE
- Blocks DROP
- Blocks ALTER
- Blocks CREATE
- Blocks GRANT
- Blocks TRUNCATE
- Blocks SELECT INTO
- Restricts accessible warehouse tables
- Automatically adds LIMIT when required
Layer 2 — Database Permissions
The chatbot uses a separate PostgreSQL read-only role.
LLM SQL
   ↓
SQL Guard
   ↓
Read-only DB role
   ↓
PostgreSQL
Even if the application-level validation misses something, the database permissions provide another security boundary.
Layer 3 — Read-only Transactions
AI-generated queries are executed using read-only transactions.
This provides defense in depth.
📈 Business Intelligence Dashboard
The dashboard provides predefined KPIs and analytical views.
Examples include:
- Total Revenue
- Total Profit
- Total Orders
- Monthly Revenue
- Top Products
- Customer Analysis
- Regional Performance
- Category Performance
Official dashboard metrics use hand-written SQL rather than dynamically generated LLM SQL.
This ensures that important business metrics are:
- Deterministic
- Repeatable
- Consistent
- Auditable
The LLM is primarily used for ad-hoc exploration.
💡 Business Insights
Ledger generates rule-based insights directly from analytical query results.
For example:
North region generated the highest revenue.
Electronics is the best-performing category.
Product X has the highest sales volume.
The numbers come directly from PostgreSQL query results rather than being invented by an LLM.
This reduces the risk of hallucinated business metrics.
🔮 Revenue Forecasting
Ledger provides future revenue forecasting using:
Historical Monthly Revenue
          ↓
Linear Trend
          +
Seasonal Index
          ↓
Future Revenue Forecast
The forecasting model uses:
- Least-squares linear trend
- Month-of-year seasonal index
- RMSE-based uncertainty
- 95% prediction band
The current approach is intentionally simple because typical uploaded datasets contain only around 12–36 monthly observations.
The forecasting interface is model-agnostic, allowing more advanced models such as ARIMA or Prophet to be introduced later.
🔑 Authentication & Roles
Ledger uses JWT-based authentication.
Users can have different roles:
Viewer
Can:
- View dashboards
- Ask analytical questions
- View forecasts
Analyst
Can:
- View dashboards
- Ask questions
- Upload datasets
Admin
Can perform all available operations.
🔗 Frontend–Backend Communication
React communicates with FastAPI through REST APIs.
React
  ↓
Axios
  ↓
REST API
  ↓
FastAPI
  ↓
SQLAlchemy
  ↓
PostgreSQL
During local development:
React / Vite
http://localhost:5173

        ↓

Vite Proxy

        ↓

FastAPI
http://localhost:8000
The browser never connects directly to PostgreSQL.
📡 API Endpoints
Authentication
POST /api/auth/register
POST /api/auth/login
Upload
POST /api/upload
GET  /api/upload/history
GET  /api/upload/{id}/logs
Analytics
GET /api/analytics/kpis
GET /api/analytics/monthly
GET /api/analytics/products
GET /api/analytics/customers
GET /api/analytics/regions
GET /api/analytics/categories
GET /api/analytics/insights
AI Chat
POST /api/chat
Forecast
GET /api/forecast?periods=6
📁 Project Structure
ai-bi-platform/
│
├── docker-compose.yml
├── database/
│   └── schema.sql
│
├── datasets/
│   └── sample_sales.csv
│
├── backend/
│   └── app/
│       ├── main.py
│       ├── config.py
│       │
│       ├── api/
│       │   └── routes.py
│       │
│       ├── auth/
│       │   └── security.py
│       │
│       ├── database/
│       │   └── session.py
│       │
│       ├── models/
│       │   └── warehouse.py
│       │
│       ├── etl/
│       │   └── pipeline.py
│       │
│       ├── analytics/
│       │   └── kpis.py
│       │
│       ├── chatbot/
│       │   ├── sql_guard.py
│       │   └── nl2sql.py
│       │
│       └── forecasting/
│           └── forecast.py
│
└── frontend/
    └── src/
        ├── pages/
        │   ├── Login.jsx
        │   ├── Dashboard.jsx
        │   ├── Upload.jsx
        │   ├── Chat.jsx
        │   └── Forecast.jsx
        │
        ├── components/
        │   └── Shell.jsx
        │
        └── styles.css
▶️ Running the Project
Using Docker
From the project root:
docker compose up --build
The application will be available at:
Frontend:
http://localhost:3000

FastAPI:
http://localhost:8000

FastAPI Swagger:
http://localhost:8000/docs

PostgreSQL:
localhost:5432
Local Development
Start PostgreSQL
Run PostgreSQL using Docker:
docker compose up db
Start Backend
cd backend
uvicorn app.main:app --reload --port 8000
Start Frontend
Open another terminal:
cd frontend
npm install
npm run dev
Frontend:
http://localhost:5173
Backend:
http://localhost:8000
🧪 Sample Dataset
The repository includes:
datasets/sample_sales.csv
The sample dataset contains approximately 3,000 sales records covering 2024–2025.
After uploading it:
Upload CSV
    ↓
ETL
    ↓
PostgreSQL Warehouse
    ↓
Dashboard
    ↓
AI Questions
    ↓
Forecast
Example AI question:
What is the best-selling product?
Example forecast:
Forecast the next 6 months of revenue.
🎯 Design Decisions
Why Star Schema?
The star schema is optimized for analytical workloads.
Instead of highly normalized operational tables, the warehouse provides a simple structure:
Fact
 +
Dimensions
This makes aggregation and BI queries easier to write and understand.
Why Surrogate Keys?
Warehouse-generated integer keys are used instead of depending directly on source-system IDs.
Source IDs can:
- Change
- Be reused
- Conflict between datasets
- Come from different systems
Surrogate keys give the warehouse control over entity identity.
Why Hand-written SQL for KPIs?
Business KPIs must be consistent.
For example:
Total Revenue
Total Profit
Monthly Revenue
should not change because an LLM interpreted a question differently.
Therefore:
Official KPI → Hand-written SQL

Ad-hoc exploration → LLM-generated SQL
Why Defense in Depth for AI SQL?
An LLM can generate incorrect or unsafe SQL.
Therefore, Ledger does not rely on the LLM itself to behave safely.
Instead:
LLM
 ↓
SQL Validation
 ↓
Allowed Tables
 ↓
Read-only Database Role
 ↓
Read-only Transaction
Multiple layers reduce the impact of a failure in any single layer.
🔮 Future Improvements
The current version is sales-focused. Future versions can evolve Ledger into a flexible, schema-aware business analytics platform.
Potential improvements:
- Support HR analytics
- Support inventory analytics
- Support marketing analytics
- Support finance analytics
- Automatic schema detection
- Domain-specific warehouse models
- Multi-tenancy
- Incremental ETL
- Slowly Changing Dimensions
- Query caching
- Materialized views
- Background ETL workers
- More advanced forecasting models
- Parser-based SQL validation using AST/SQLGlot
📚 What I Learned
This project provided hands-on experience with:
- ETL pipeline design
- Data cleaning and validation
- Data warehouse architecture
- Star schemas
- Fact and dimension tables
- Surrogate keys
- PostgreSQL
- REST API development
- FastAPI
- React–backend integration
- JWT authentication
- LLM-powered applications
- Natural-language-to-SQL systems
- AI security
- Database access control
- Business Intelligence
- Forecasting
- Docker
👨‍💻 Project Goal
Ledger was built to explore how traditional data engineering and modern AI can work together.
The core idea is:
Raw Business Data
       ↓
      ETL
       ↓
Data Warehouse
       ↓
   BI Analytics
       ↓
 ┌─────┴─────┐
 ↓           ↓
LLM        Forecast
 ↓
Natural Language
Business Exploration
The goal is not to replace BI systems or general-purpose LLMs, but to combine structured data engineering, deterministic analytics, and controlled AI exploration into one platform.
```
