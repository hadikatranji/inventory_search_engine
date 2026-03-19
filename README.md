# Inventory Search Engine

An AI-powered inventory search engine for a multi-category electronics retailer. Enables non-technical sales staff to search 94,000+ SKUs across electronics components, laptops, mobile accessories, industrial automation, and car parts — using plain text or product photos.

Built with **FastAPI**, **SQL Server**, and the **Anthropic API**.

---

## Features

- **Natural language search** — type anything from `"acer laptop"` to `"LM358"` and get ranked results
- **AI query interpretation** — expands search intent, suggests related terms, handles typos and abbreviations
- **Image search** — upload a photo of a product; AI vision identifies it and searches the inventory
- **Keyword aliases** — translate colloquial terms (e.g. `"shahin mobile"` → `"mobile charger"`) before searching
- **AI alias generator** — searches Amazon, Alibaba & AliExpress for real product titles and auto-generates alias mappings
- **Substitute suggestions** — when nothing is found, AI recommends the closest alternatives in stock
- **Confidence scoring** — results ranked by field match weight, model number accuracy, stock level, and category relevance
- **Product images** — thumbnails fetched from image databases using TocAN join
- **Admin panel** — manage keyword aliases, product term rules, and category substitutes through a UI
- **Analytics dashboard** — track top searches, zero-result queries, and AI expansion patterns
- **Interactive loading** — animated step-by-step progress while search runs

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python) |
| Database | SQL Server (via pyodbc) |
| AI | Anthropic API (fast model for interpretation, smart model for substitutes & vision) |
| Frontend | Vanilla HTML/CSS/JS |
| Local DB | SQL Server in Docker (search metadata, aliases, analytics) |

---

## How It Works

```
User types a query
      ↓
Step 1 — Alias Check       "12v car plugin" → "car charger"
      ↓
Step 2 — Rule Engine        Is this a part number? A laptop? An accessory?
      ↓
Step 3 — AI                 Expand & clarify the intent
      ↓
Step 4 — Database Search    Fetch matching products from inventory
      ↓
Step 5 — Scoring            Rank results by relevance + stock
      ↓
Step 6 — Category Boost     Push the right category to the top
      ↓
Step 7 — Exclude Filter     Remove clearly wrong categories
      ↓
Results shown to user
```

See [HOW_SEARCH_WORKS.md](HOW_SEARCH_WORKS.md) for a full plain-English walkthrough.

---

## Setup

### Prerequisites

- Python 3.10+
- ODBC Driver 17 for SQL Server
- Docker (for the local search metadata DB)
- An Anthropic API key

### Environment Variables

Create a `.env` file in the project root:

```env
# Main inventory database
DB_SERVER=your_sql_server_host
DB_USER=your_db_user
DB_PASS=your_db_password
INVENTORY_DB=InventoryDB
LIVE_DB=LiveDB

# Local search database (Docker)
SEARCH_DB=SearchDB
LOCAL_DB_SERVER=127.0.0.1,1433
LOCAL_DB_USER=SA
LOCAL_DB_PASS=your_local_db_password

# Image databases (comma-separated)
IMAGE_DBS=ImgDB1,ImgDB2,ImgDB3

# Store domain for product links
STORE_DOMAIN=www.yourstore.com

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# AI model overrides (optional)
AI_FAST_MODEL=claude-haiku-4-5-20251001
AI_SMART_MODEL=claude-sonnet-4-20250514
```

### Install & Run

```bash
pip install fastapi uvicorn pyodbc anthropic python-multipart

cd ~/inventory-search
source .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the included start script:

```bash
./start.sh
```

---

## Pages

| URL | Description |
|-----|-------------|
| `/` | Main search interface |
| `/admin/categories` | Admin panel (aliases, terms, category maps, alias generator) |
| `/analytics` | Search analytics dashboard |

---

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `populate_aliases.py` | Seeds keyword aliases from DB alternate names + AI batch suggestions |
| `populate_terms.py` | Seeds product term rules from real categories and brands |
| `check_images.py` | Diagnostic: discovers image storage structure in inventory DB |
| `test_connection.py` | Tests connectivity to the main database |

---

## Admin — Generate Aliases

The **Generate Aliases** tab in the admin panel lets you type any product name and have the AI automatically search Amazon, Alibaba, and AliExpress for real listings — then extract what buyers actually type and map them to canonical search terms in your inventory.

---

## License

MIT
