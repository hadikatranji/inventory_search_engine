"""
populate_aliases.py
Reads products from the inventory database, then uses AI to suggest
keyword alias mappings and upserts them into dbo.TermAliases.

Two sources:
  1. ItemAnotherName — already an alternate name stored in the DB
  2. AI — analyzes product descriptions + categories in batches
     and suggests colloquial / alternate phrases users might search for

Safe to re-run: existing aliases are never duplicated.

Run with:
    cd ~/inventory-search && source .env && python3 populate_aliases.py
"""

import os
import json
import re
import pyodbc
import anthropic

INVENTORY_DB   = os.environ.get('INVENTORY_DB',    'InventoryDB')
SEARCH_DB      = os.environ.get('SEARCH_DB',       'SearchDB')
LOCAL_DB_SERVER = os.environ.get('LOCAL_DB_SERVER', '127.0.0.1,1433')
LOCAL_DB_USER   = os.environ.get('LOCAL_DB_USER',   'SA')
LOCAL_DB_PASS   = os.environ.get('LOCAL_DB_PASS',   'ChangeMe2024!')
AI_SMART_MODEL  = os.environ.get('AI_SMART_MODEL',  'claude-sonnet-4-20250514')

DB_CONN = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={os.environ['DB_SERVER']};"
    f"Database={INVENTORY_DB};"
    f"UID={os.environ['DB_USER']};"
    f"PWD={os.environ['DB_PASS']};"
    "TrustServerCertificate=yes;"
)
LOCAL_CONN = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={LOCAL_DB_SERVER};"
    f"Database={SEARCH_DB};"
    f"UID={LOCAL_DB_USER};"
    f"PWD={LOCAL_DB_PASS};"
    "TrustServerCertificate=yes;"
)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

# ─── Step 1: Fetch product data from inventory database ──────────────────────

print("Connecting to inventory database...")
conn = pyodbc.connect(DB_CONN)
cur = conn.cursor()

# Alternate names already stored in the DB
cur.execute("""
    SELECT DISTINCT
        LTRIM(RTRIM(m.ItemAnotherName)) AS AltName,
        LTRIM(RTRIM(m.Description))     AS Description,
        LTRIM(RTRIM(c.CategoryName))    AS CategoryName
    FROM {INVENTORY_DB}.dbo.Materials m
    LEFT JOIN {INVENTORY_DB}.dbo.MatCategories c ON m.MatCategories_AN = c.AutoNum
    WHERE m.ItemAnotherName IS NOT NULL
      AND LEN(LTRIM(RTRIM(m.ItemAnotherName))) > 3
      AND m.MarkAsDeleted = 0
      AND m.Hidden = 0
    ORDER BY CategoryName, AltName
""")
alt_name_rows = cur.fetchall()
print(f"  Found {len(alt_name_rows)} products with ItemAnotherName")

# Sample of descriptions per category for AI analysis
cur.execute("""
    SELECT TOP 600
        LTRIM(RTRIM(c.CategoryName))    AS CategoryName,
        LTRIM(RTRIM(m.Description))     AS Description,
        LTRIM(RTRIM(m.WebName))         AS WebName
    FROM {INVENTORY_DB}.dbo.Materials m
    LEFT JOIN {INVENTORY_DB}.dbo.MatCategories c ON m.MatCategories_AN = c.AutoNum
    WHERE m.MarkAsDeleted = 0
      AND m.Hidden = 0
      AND c.CategoryName IS NOT NULL
      AND m.Description IS NOT NULL
    ORDER BY NEWID()
""")
sample_rows = cur.fetchall()
print(f"  Fetched {len(sample_rows)} product samples for AI analysis")

conn.close()

# ─── Step 2: Read existing aliases from search database ──────────────────────

print("\nConnecting to search database...")
lconn = pyodbc.connect(LOCAL_CONN)
lcur = lconn.cursor()

# Auto-create table if missing
lcur.execute("""
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'TermAliases')
    CREATE TABLE dbo.TermAliases (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        Alias NVARCHAR(200) NOT NULL,
        MapsToTerm NVARCHAR(200) NOT NULL
    )
""")
lconn.commit()

lcur.execute("SELECT Alias FROM dbo.TermAliases")
existing_aliases = {row[0].strip().lower() for row in lcur.fetchall()}
print(f"  Found {len(existing_aliases)} existing aliases (will be skipped)")

# ─── Step 3: Build aliases from ItemAnotherName ───────────────────────────────

print("\n=== SOURCE 1: ItemAnotherName ===")

def extract_core_term(description: str) -> str:
    """Strip leading brand/model noise, return short searchable term."""
    desc = description.strip()
    # Take first 6 words max
    words = desc.split()[:6]
    return " ".join(words).lower()

alt_name_aliases = []
for alt_name, description, category in alt_name_rows:
    if not alt_name or not description:
        continue
    # ItemAnotherName is often comma-separated tags — skip those
    if ',' in alt_name:
        continue
    alias = alt_name.strip().lower()
    maps_to = extract_core_term(description)
    # Skip if they're basically the same string
    if alias == maps_to or alias[:20] == maps_to[:20]:
        continue
    # Skip very long aliases (likely full descriptions)
    if len(alias.split()) > 8:
        continue
    alt_name_aliases.append((alias, maps_to))

# Deduplicate within this source
seen = set()
deduped_alt = []
for alias, maps_to in alt_name_aliases:
    if alias not in seen:
        seen.add(alias)
        deduped_alt.append((alias, maps_to))

print(f"  Generated {len(deduped_alt)} candidate aliases from ItemAnotherName")

# ─── Step 4: AI analysis of product descriptions ─────────────────────────────

print("\n=== SOURCE 2: AI analysis ===")

# Group samples by category
by_category = {}
for cat, desc, webname in sample_rows:
    if cat not in by_category:
        by_category[cat] = []
    label = webname.strip() if webname and webname.strip() else desc.strip()
    if label and label not in by_category[cat]:
        by_category[cat].append(label[:80])

# Build a compact summary for AI
category_lines = []
for cat, items in sorted(by_category.items()):
    sample = items[:8]
    category_lines.append(f"  [{cat}]: {' | '.join(sample)}")

product_summary = "\n".join(category_lines[:60])  # cap tokens

PROMPT = f"""You are a search alias generator for an electronics & IT inventory system.

Below are product categories with example product names from the actual database.

YOUR TASK:
Generate keyword alias mappings — pairs of (alias → canonical_term) — where:
- "alias" = a phrase a customer might TYPE when searching (colloquial, regional, alternate spelling, Arabic transliteration, slang, common mistake)
- "canonical_term" = a short English term that ACTUALLY EXISTS or would match products in that category

RULES:
- Focus on terms a Lebanese/Arabic-speaking customer might use
- Include: Arabic transliterations (e.g. "shahin" for "charger"), brand-agnostic generics, alternate spellings, common abbreviations
- Each alias must be different from the canonical term
- canonical_term should be 1-4 words, lowercase, matching something likely in the inventory
- Return ONLY a JSON array, no explanation

EXAMPLE FORMAT:
[
  {{"alias": "12v car plugin", "maps_to": "car charger"}},
  {{"alias": "shahin mobile", "maps_to": "mobile charger"}},
  {{"alias": "type c wire", "maps_to": "usb c cable"}},
  {{"alias": "airpod", "maps_to": "airpods"}}
]

PRODUCT CATEGORIES AND SAMPLES:
{product_summary}

Return 40-80 high-quality alias pairs as a JSON array:"""

print("  Calling AI API...")
try:
    response = client.messages.create(
        model=AI_SMART_MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": PROMPT}]
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```$", "", raw).strip()
    ai_suggestions = json.loads(raw)
    print(f"  AI returned {len(ai_suggestions)} suggestions")
except Exception as e:
    print(f"  [WARN] AI call failed: {e}")
    ai_suggestions = []

ai_aliases = []
for item in ai_suggestions:
    alias = str(item.get("alias", "")).strip().lower()
    maps_to = str(item.get("maps_to", "")).strip().lower()
    if alias and maps_to and alias != maps_to and len(alias) >= 3:
        ai_aliases.append((alias, maps_to))

# ─── Step 5: Combine both sources and deduplicate ─────────────────────────────

ALL_ALIASES = deduped_alt + ai_aliases

seen_all = set()
final_aliases = []
for alias, maps_to in ALL_ALIASES:
    if alias not in seen_all and alias not in existing_aliases:
        seen_all.add(alias)
        final_aliases.append((alias, maps_to))

already_exist = [(a, m) for (a, m) in ALL_ALIASES if a in existing_aliases]

print(f"\n=== SUMMARY ===")
print(f"  From ItemAnotherName : {len(deduped_alt)}")
print(f"  From AI              : {len(ai_aliases)}")
print(f"  Already in DB        : {len(already_exist)}  (will be skipped)")
print(f"  New — to insert      : {len(final_aliases)}")

if not final_aliases:
    print("\n  Nothing new to insert.")
    lconn.close()
    exit()

print(f"\n=== NEW ALIASES TO INSERT (first 60 shown) ===")
for alias, maps_to in final_aliases[:60]:
    print(f"  {alias:35s}  →  {maps_to}")
if len(final_aliases) > 60:
    print(f"  ... and {len(final_aliases) - 60} more")

# ─── Step 6: Confirm and insert ───────────────────────────────────────────────

confirm = input(f"\nInsert {len(final_aliases)} new aliases? (y/n): ")
if confirm.strip().lower() != 'y':
    print("Aborted.")
    lconn.close()
    exit()

inserted = 0
skipped  = 0
for alias, maps_to in final_aliases:
    try:
        lcur.execute("""
            IF NOT EXISTS (SELECT 1 FROM dbo.TermAliases WHERE Alias = ?)
            INSERT INTO dbo.TermAliases (Alias, MapsToTerm) VALUES (?, ?)
        """, (alias, alias, maps_to))
        inserted += 1
    except Exception as e:
        print(f"  [ERROR] {alias}: {e}")
        skipped += 1

lconn.commit()
lconn.close()

print(f"\nDone. Inserted: {inserted}, Skipped errors: {skipped}")
print("Aliases are live immediately — no server restart needed.")
