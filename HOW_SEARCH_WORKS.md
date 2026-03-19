# How the Search Engine Thinks

A plain-English walkthrough of every step — from the moment a user types a query
to the moment results appear on screen.

---

## The Big Picture

```
User types a query
       ↓
  Step 1 — Alias Check       "12v car plugin" → "car charger"
       ↓
  Step 2 — Rule Engine        Is this a part number? A laptop? An accessory?
       ↓
  Step 3 — AI                 Expand & clarify the intent
       ↓
  Step 4 — Database Search    Fetch matching products from the inventory database
       ↓
  Step 5 — Scoring            Rank results by relevance + stock
       ↓
  Step 6 — Category Boost     Push the right category to the top
       ↓
  Step 7 — Exclude Filter     Remove clearly wrong categories
       ↓
  Results shown to user
```

---

## Step 1 — Alias Check (keyword translation)

**What it does:** Before anything else, the engine checks if the user typed a
phrase that should be translated into a better search term.

**Where the aliases come from:** The admin panel → "Keyword Aliases" tab, or
populated automatically by running `populate_aliases.py`.

**Example:**
```
User types:    "12v car plugin"
Alias table:   "12v car plugin" → "car charger"
Engine uses:   "car charger"  ← this is what actually gets searched
```

The matching goes longest alias first (so "cigarette lighter plug" matches
before "lighter" alone). Only the first matching alias is applied.

If no alias matches, the original query is used as-is.

---

## Step 2 — Rule Engine (fast classification, no AI)

The rule engine looks at the (possibly aliased) query and tries to classify it
using simple logic — no AI involved, happens in milliseconds.

### 2a. Is it a part number?

The engine checks if the query looks like an electronic component code.

**Triggers:**
- Starts with known IC prefixes: `LM`, `NE`, `TL`, `TIP`, `BC`, `74`, `40`...
- Mix of letters and digits in a single word: `LM358`, `BC547`, `74HC595`
- Any single word containing both letters and numbers

**Result:** Searches all fields exactly as typed. No category boost. No AI.

```
"lm358"     → part number search
"arduino"   → NOT a part number (no digits)
"LM7805"    → part number search
```

### 2b. Is it a product + accessory modifier?

The engine checks if the query contains an accessory word alongside a product name.

**Accessory words that trigger this:**
`bag`, `case`, `cover`, `charger`, `adapter`, `cable`, `fan`, `battery`,
`screen protector`, `keyboard`, `stand`, `dock`, `hub`, `socket`, `jack`, `connector`

**Rule:** If the query has MORE than one word AND contains an accessory modifier,
the engine treats it as a specific accessory search.

```
"dell charger"    → accessory search → filter to "Laptop Adapters" category
"hp battery"      → accessory search → filter to "Laptop Batteries" category
"laptop bag"      → accessory search → filter to "Bags & Carry Case"
"laptop"          → NOT triggered (only one word, no modifier)
```

### 2c. Is it a known product type?

The engine checks the **Product Terms table** (managed in admin → "Product Terms"
tab, or populated by `populate_terms.py`).

This table has entries like:
| Term       | Category Boost    | Exclude Terms                              |
|------------|-------------------|--------------------------------------------|
| laptop     | Laptop Computers  | charger, adapter, bag, battery, inverter   |
| ipad       | Tablets           | charger, case, stylus                      |
| router     | Routers           |                                            |
| arduino    | Microcontrollers  |                                            |

**Rule:** If the query contains a known product term AND does NOT contain an
accessory modifier, the engine marks this as a "product type" search.

```
"acer laptop"  → "laptop" found in table → boost to "Laptop Computers"
"dell"         → not in table → falls through to "general"
"ipad case"    → "case" is an accessory modifier → overrides the ipad rule
```

### 2d. General search (nothing matched)

If none of the above matched, the query is marked as a general search.
Everything is searched, no category filters, no boosts.

---

## Step 3 — AI (intent expansion)

The rule engine's classification is sent to an AI model to expand and refine the search.

**What the AI receives:**
- The user's query
- The rule engine's decision ("this is a laptop search", "boost to Laptop Computers", etc.)
- A description of the store's inventory

**What the AI returns:**
```json
{
  "search_terms": ["acer laptop", "acer notebook", "acer aspire"],
  "exclude_terms": ["battery", "inverter"],
  "preferred_category": "Laptop Computers",
  "interpretation_note": "User is looking for an Acer laptop computer"
}
```

The `search_terms` list means the database will be searched up to 3 times —
once per term — to catch more results.

**Exception — part numbers:** AI is NOT called for part number searches.
The part number is used directly, saving time and cost.

---

## Step 4 — Database Search

For each search term the AI returned, the engine runs a SQL query against
the inventory database.

### What fields are searched

| Field            | Match type      | Why                                      |
|------------------|-----------------|------------------------------------------|
| Description      | Word boundary   | Main product name                        |
| DescriptionArabic| Word boundary   | Arabic product name                      |
| ItemAnotherName  | Word boundary   | Alternate names / tags                   |
| WebDescription   | Word boundary   | Extended description                     |
| ItemNote         | Word boundary   | Extra notes                              |
| Brand name       | Word boundary   | Brand matching                           |
| Original_No      | Substring       | Part numbers / model numbers             |
| Item (SKU code)  | Substring       | Internal product codes                   |
| Barcode          | Substring       | Barcode scanning                         |

**Word boundary** means "acer" will NOT match inside "spacer" or "tracer".
It must appear as a standalone word.

**Substring** is used for codes because part numbers are often partial
(searching "LM35" should find "LM35DZ").

### Filters applied in SQL

- Hidden products → excluded
- Deleted products → excluded
- If a **category filter** was set (e.g., "Laptop Adapters") → only that category
- Results ordered by: (1) does it match the target category? (2) is it in stock? (3) highest balance

---

## Step 5 — Scoring (confidence calculation)

After fetching results from the database, each product gets a **confidence score**
from 0 to 100.

### How the score is calculated

Each field that contains a search word adds points:

| Field            | Points |
|------------------|--------|
| ItemAnotherName  | 40     |
| Original_No      | 35     |
| Item (SKU)       | 30     |
| Description      | 25     |
| Brand            | 20     |
| CategoryName     | 15     |
| WebDescription   | 10     |
| ItemNote         |  5     |
| Barcode          |  5     |

**Match ratio multiplier:** If the query has 2 words and only 1 is found,
the score is multiplied by 0.5 (half the words matched).

**Stock adjustment:**
- Product is in stock → +10
- Product has zero stock → −15
- Product has negative balance → −25

**Example:**
```
Query: "acer laptop"

Product: "Acer Aspire 5 Laptop, Core i5"
  Description matched "acer" + "laptop" → +25
  Brand matched "acer"                  → +20
  Both words found (ratio = 1.0)        → score = 45 × 1.0 = 45
  In stock                              → +10
  Final score: 55
```

---

## Step 6 — Category Boost

After scoring, if the rule engine identified a **target category**, the scores
are adjusted:

- Products **in** the target category → **+50 points**
- Products **outside** the target category → **−25 points**

This is why searching "acer laptop" should surface actual Acer laptops
(in "Laptop Computers") above Acer laptop batteries (in "Laptop Batteries"),
even if the batteries textually match both words.

---

## Step 7 — Exclude Filter

After scoring and boosting, certain results are removed entirely.

The exclude terms come from:
1. The **Product Terms table** (e.g., "laptop" excludes categories containing
   "battery", "inverter", "backlight")
2. AI interpretation (if the AI is very confident certain categories
   are wrong)

**How it works:** If any exclude term appears inside a product's **CategoryName**,
that product is dropped from results.

```
Query: "laptop"
Exclude terms: ["battery", "inverter", "backlight"]

"Laptop Batteries"          → CategoryName contains "battery" → REMOVED
"Laptop Inverters"          → CategoryName contains "inverter" → REMOVED
"Laptop Computers"          → no match → KEPT
"Laptop Fans"               → no match → KEPT
```

---

## Final Ranking

Results are sorted by confidence score (highest first), then the top 20 are
returned.

---

## Image Search (bonus)

When a user uploads a photo instead of typing:

1. The image is sent to an AI vision model
2. The AI looks at the physical form, connector type, or any printed part number
3. The AI returns a short search term (max 6 words), e.g. `"cigarette lighter male plug"`
4. That term is passed into the normal search pipeline from Step 1 onward

---

## Admin Controls

Everything about how the search behaves can be tuned without touching code:

| What you control              | Where                        |
|-------------------------------|------------------------------|
| Keyword aliases               | Admin → Keyword Aliases      |
| Product term → category rules | Admin → Product Terms        |
| Category substitutions        | Admin → Category Substitutes |
| Bulk-populate aliases from DB | Run `populate_aliases.py`    |
| Bulk-populate product terms   | Run `populate_terms.py`      |
