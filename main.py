import os
import pyodbc
import anthropic
from fastapi import FastAPI, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import base64
import json
import time
import re

# ── Configuration (override via environment variables) ──────────────────────
INVENTORY_DB     = os.environ.get('INVENTORY_DB', 'InventoryDB')
LIVE_DB          = os.environ.get('LIVE_DB', 'LiveDB')
SEARCH_DB        = os.environ.get('SEARCH_DB', 'SearchDB')
LOCAL_DB_SERVER  = os.environ.get('LOCAL_DB_SERVER', '127.0.0.1,1433')
LOCAL_DB_USER    = os.environ.get('LOCAL_DB_USER', 'SA')
LOCAL_DB_PASS    = os.environ.get('LOCAL_DB_PASS', 'ChangeMe2024!')
IMAGE_DBS        = [d.strip() for d in os.environ.get('IMAGE_DBS', '').split(',') if d.strip()]
STORE_DOMAIN     = os.environ.get('STORE_DOMAIN', '')
AI_FAST_MODEL    = os.environ.get('AI_FAST_MODEL',  'claude-haiku-4-5-20251001')
AI_SMART_MODEL   = os.environ.get('AI_SMART_MODEL', 'claude-sonnet-4-20250514')
# ────────────────────────────────────────────────────────────────────────────

IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "product_images")
os.makedirs(IMAGES_DIR, exist_ok=True)

def seed_search_intelligence():
    try:
        conn = get_local_conn()
        cursor = conn.cursor()

        # ── KEYWORD SYNONYMS ──────────────────────────────────────
        synonyms = [
            # Tier 1 — Consumer
            ('cover', 'Cases & Covers', 'Mobile'),
            ('case', 'Cases & Covers', 'Mobile'),
            ('phone case', 'Cases & Covers', 'Mobile'),
            ('mobile cover', 'Cases & Covers', 'Mobile'),
            ('iphone case', 'Cases & Covers', 'Mobile'),
            ('samsung case', 'Cases & Covers', 'Mobile'),
            ('laptop', 'Laptops', 'Computer'),
            ('notebook', 'Laptops', 'Computer'),
            ('macbook', 'Laptops', 'Computer'),
            ('earphone', 'Earbuds & Headsets', 'Audio'),
            ('headphone', 'Earbuds & Headsets', 'Audio'),
            ('airpods', 'Earbuds & Headsets', 'Audio'),
            ('tws', 'Earbuds & Headsets', 'Audio'),
            ('buds', 'Earbuds & Headsets', 'Audio'),
            ('usb cable', 'USB Cables', 'Cables'),
            ('charging cable', 'USB Cables', 'Cables'),
            ('type-c cable', 'USB Cables', 'Cables'),
            ('type c cable', 'USB Cables', 'Cables'),
            ('hdmi', 'HDMI Cables', 'Cables'),
            ('hdmi cable', 'HDMI Cables', 'Cables'),
            ('power bank', 'Power Banks', 'Accessories'),
            ('portable charger', 'Power Banks', 'Accessories'),
            ('battery pack', 'Power Banks', 'Accessories'),
            ('speaker', 'Bluetooth Speakers', 'Audio'),
            ('bluetooth speaker', 'Bluetooth Speakers', 'Audio'),
            ('wireless speaker', 'Bluetooth Speakers', 'Audio'),
            ('screen protector', 'Mobile Screen Protectors', 'Mobile'),
            ('tempered glass', 'Mobile Screen Protectors', 'Mobile'),
            ('screen glass', 'Mobile Screen Protectors', 'Mobile'),
            ('flash drive', 'External Storage', 'Storage'),
            ('usb drive', 'External Storage', 'Storage'),
            ('memory stick', 'External Storage', 'Storage'),
            ('pendrive', 'External Storage', 'Storage'),
            ('pen drive', 'External Storage', 'Storage'),
            ('wireless charger', 'Wireless Chargers', 'Charging'),
            ('qi charger', 'Wireless Chargers', 'Charging'),
            ('magsafe', 'Wireless Chargers', 'Charging'),
            ('smartwatch', 'Smart Watches', 'Wearables'),
            ('smart watch', 'Smart Watches', 'Wearables'),
            ('fitness watch', 'Smart Watches', 'Wearables'),
            ('car key', 'Car Keys', 'Automotive'),
            ('remote key', 'Car Keys', 'Automotive'),
            ('key fob', 'Car Keys', 'Automotive'),
            ('charger', 'Adapters', 'Power'),
            ('laptop charger', 'Adapters', 'Power'),
            ('power adapter', 'Power Adapters', 'Power'),
            ('wall charger', 'Power Adapters', 'Power'),
            ('travel adapter', 'Travel Accessories', 'Accessories'),
            ('universal plug', 'Travel Accessories', 'Accessories'),
            ('network cable', 'Ethernet Patch Cords', 'Network'),
            ('lan cable', 'Ethernet Patch Cords', 'Network'),
            ('ethernet cable', 'Ethernet Patch Cords', 'Network'),
            ('cat6', 'Ethernet Patch Cords', 'Network'),
            ('wifi router', 'Routers', 'Network'),
            ('wireless router', 'Routers', 'Network'),
            ('led strip', 'LED Strip', 'Lighting'),
            ('rgb strip', 'LED Strip', 'Lighting'),
            ('light strip', 'LED Strip', 'Lighting'),
            # Tier 2 — Semi-technical
            ('psu', 'Power Supplies', 'Electronics'),
            ('smps', 'Power Supplies', 'Electronics'),
            ('switching supply', 'Power Supplies', 'Electronics'),
            ('multimeter', 'Multimeter', 'Test'),
            ('voltmeter', 'Multimeter', 'Test'),
            ('digital meter', 'Multimeter', 'Test'),
            ('arduino', 'Arduino Microcontrollers', 'Maker'),
            ('raspberry pi', 'Raspberry Pi Microcontrollers', 'Maker'),
            ('rpi', 'Raspberry Pi Microcontrollers', 'Maker'),
            ('relay', 'Relays', 'Industrial'),
            ('contactor', 'Contactors', 'Industrial'),
            ('mcb', 'Breakers', 'Industrial'),
            ('circuit breaker', 'Breakers', 'Industrial'),
            ('stepper motor', 'Stepper Motors', 'Industrial'),
            ('servo', 'Servo Motors', 'Industrial'),
            ('servo motor', 'Servo Motors', 'Industrial'),
            ('plc', 'PLCs', 'Industrial'),
            ('sonoff', 'Smart Switches & Control', 'Smart'),
            ('smart switch', 'Smart Switches & Control', 'Smart'),
            # Tier 3 — Technical aliases
            ('op-amp', 'ICs & Voltage Regulators', 'Components'),
            ('opamp', 'ICs & Voltage Regulators', 'Components'),
            ('operational amplifier', 'ICs & Voltage Regulators', 'Components'),
            ('bjt', 'Transistors', 'Components'),
            ('mosfet', 'Transistors', 'Components'),
            ('cap', 'Capacitors', 'Components'),
            ('electrolytic', 'Capacitors', 'Components'),
            ('res', 'Resistors', 'Components'),
            ('carbon film', 'Resistors', 'Components'),
            ('xtal', 'Crystal Oscillators', 'Components'),
            ('crystal', 'Crystal Oscillators', 'Components'),
            ('fuse', 'Glass & Ceramic Fuses', 'Components'),
            ('glass fuse', 'Glass & Ceramic Fuses', 'Components'),
            ('inductor', 'Coils, Inductors & Chokes', 'Components'),
            ('coil', 'Coils, Inductors & Chokes', 'Components'),
            ('zener', 'Zener Diodes', 'Components'),
            ('tvs', 'Suppressor Diodes', 'Components'),
            ('triac', 'Triacs & Thyristors', 'Components'),
            ('thyristor', 'Triacs & Thyristors', 'Components'),
            ('scr', 'Triacs & Thyristors', 'Components'),
            ('proximity sensor', 'Inductive', 'Sensors'),
            ('inductive sensor', 'Inductive', 'Sensors'),
            ('vfd', 'VFD', 'Industrial'),
            ('variable frequency drive', 'VFD', 'Industrial'),
            ('inverter drive', 'VFD', 'Industrial'),
        ]

        inserted = 0
        skipped = 0
        for term, synonym, category in synonyms:
            cursor.execute("""
                IF NOT EXISTS (
                    SELECT 1 FROM dbo.KeywordSynonyms
                    WHERE Term = ? AND Synonym = ?
                )
                INSERT INTO dbo.KeywordSynonyms (Term, Synonym, Category)
                VALUES (?, ?, ?)
            """, term, synonym, term, synonym, category)
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1

        # ── PRODUCT TERM MAP ──────────────────────────────────────
        product_terms = [
            ('macbook pro',      'Laptops',                        'adapter,bag,case,battery,charger,socket,fan,keyboard,screen',                  1),
            ('macbook air',      'Laptops',                        'adapter,bag,case,battery,charger,socket,fan,keyboard,screen',                  2),
            ('macbook',          'Laptops',                        'socket,jack,adapter,bag,case,fan,battery,charger,keyboard,stand,connector,power,screen,lamp,hinge,lock', 3),
            ('laptop',           'Laptops',                        'socket,jack,adapter,bag,case,fan,battery,charger,keyboard,stand,connector,power,screen,lamp,hinge,lock', 4),
            ('notebook',         'Laptops',                        'socket,jack,adapter,bag,case,fan,battery,charger,keyboard',                    5),
            ('iphone case',      'Cases & Covers',                 '',                                                                             6),
            ('samsung case',     'Cases & Covers',                 '',                                                                             7),
            ('phone case',       'Cases & Covers',                 '',                                                                             8),
            ('phone cover',      'Cases & Covers',                 '',                                                                             9),
            ('iphone cover',     'Cases & Covers',                 '',                                                                             10),
            ('screen protector', 'Mobile Screen Protectors',       '',                                                                             11),
            ('tempered glass',   'Mobile Screen Protectors',       '',                                                                             12),
            ('power bank',       'Power Banks',                    '',                                                                             13),
            ('bluetooth speaker','Bluetooth Speakers',             '',                                                                             14),
            ('wireless speaker', 'Bluetooth Speakers',             '',                                                                             15),
            ('earphone',         'Earbuds & Headsets',             '',                                                                             16),
            ('earbuds',          'Earbuds & Headsets',             '',                                                                             17),
            ('headphone',        'Earbuds & Headsets',             'jack,connector,socket',                                                        18),
            ('flash drive',      'External Storage',               '',                                                                             19),
            ('pendrive',         'External Storage',               '',                                                                             20),
            ('usb drive',        'External Storage',               '',                                                                             21),
            ('wireless charger', 'Wireless Chargers',              '',                                                                             22),
            ('smartwatch',       'Smart Watches',                  '',                                                                             23),
            ('smart watch',      'Smart Watches',                  '',                                                                             24),
            ('car key',          'Car Keys',                       '',                                                                             25),
            ('travel adapter',   'Travel Accessories',             '',                                                                             26),
            ('resistor',         'Resistors',                      '',                                                                             27),
            ('capacitor',        'Capacitors',                     '',                                                                             28),
            ('transistor',       'Transistors',                    '',                                                                             29),
            ('relay',            'Relays',                         'module',                                                                       30),
            ('arduino',          'Arduino Microcontrollers',       '',                                                                             31),
            ('raspberry pi',     'Raspberry Pi Microcontrollers',  '',                                                                             32),
            ('raspberry',        'Raspberry Pi Microcontrollers',  '',                                                                             33),
            ('multimeter',       'Multimeter',                     '',                                                                             34),
            ('oscilloscope',     'Oscilloscope',                   '',                                                                             35),
            ('motor',            'Motors',                         'laptop,cooling',                                                               36),
            ('stepper motor',    'Stepper Motors',                 '',                                                                             37),
            ('servo motor',      'Servo Motors',                   '',                                                                             38),
            ('plc',              'PLCs',                           '',                                                                             39),
            ('circuit breaker',  'Breakers',                       '',                                                                             40),
            ('soldering iron',   'Soldering Iron',                 '',                                                                             41),
            ('power supply',     'Power Supplies',                 '',                                                                             42),
            ('led strip',        'LED Strip',                      '',                                                                             43),
            ('drill',            'PCB Drill Bits',                 '',                                                                             44),
            ('sensor',           None,                             '',                                                                             45),
            ('router',           'Routers',                        '',                                                                             46),
            ('smart switch',     'Smart Switches & Control',       '',                                                                             47),
            ('vfd',              'VFD',                            '',                                                                             48),
            ('contactor',        'Contactors',                     '',                                                                             49),
            ('imac',             'Desktop Computers',              '',                                                                             50),
            ('desktop',          'Desktop Computers',              'socket,jack,connector',                                                        51),
        ]

        pt_inserted = 0
        pt_skipped = 0
        for term, cat_boost, excludes, priority in product_terms:
            cursor.execute("""
                IF NOT EXISTS (
                    SELECT 1 FROM dbo.ProductTermMap WHERE Term = ?
                )
                INSERT INTO dbo.ProductTermMap (Term, CategoryBoost, ExcludeTerms, Priority)
                VALUES (?, ?, ?, ?)
            """, term, term, cat_boost, excludes, priority)
            if cursor.rowcount > 0:
                pt_inserted += 1
            else:
                pt_skipped += 1

        conn.commit()
        conn.close()
        print(f"Synonyms: {inserted} inserted, {skipped} skipped")
        print(f"ProductTerms: {pt_inserted} inserted, {pt_skipped} skipped")

    except Exception as e:
        import traceback
        print(f"Seed error: {e}")
        traceback.print_exc()

@asynccontextmanager
async def lifespan(app):
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'CategorySubstituteMap'
            )
            BEGIN
                CREATE TABLE dbo.CategorySubstituteMap (
                    ID                  INT IDENTITY PRIMARY KEY,
                    CategoryName        NVARCHAR(200) NOT NULL,
                    SubstituteCategory  NVARCHAR(200) NOT NULL,
                    Priority            INT DEFAULT 1,
                    CreatedDate         DATETIME DEFAULT GETDATE()
                );

                INSERT INTO dbo.CategorySubstituteMap
                    (CategoryName, SubstituteCategory, Priority)
                VALUES
                ('Laptop Computers', 'Laptop Computers', 1),
                ('Laptop Adapters', 'Laptop Adapters', 1),
                ('Laptop Adapters', 'Computer Power Supplies', 2),
                ('Laptop Batteries', 'Laptop Batteries', 1),
                ('Laptop Fans', 'Laptop Fans', 1),
                ('Laptop Fans', 'Computer Fans & Stands', 2),
                ('Laptop Keyboards', 'Laptop Keyboards', 1),
                ('Laptop Screens', 'Laptop Screens', 1),
                ('Desktop Computers', 'Desktop Computers', 1),
                ('Desktop Computers', 'Laptop Computers', 2),
                ('LEDs', 'LEDs', 1),
                ('Resistors', 'Resistors', 1),
                ('Capacitors', 'Capacitors', 1),
                ('Relays', 'Relays', 1),
                ('Motors', 'Motors', 1),
                ('Transformers', 'Transformers', 1),
                ('Power Supplies', 'Power Supplies', 1),
                ('Power Supplies', 'Laptop Adapters', 2),
                ('Multimeters', 'Multimeters', 1),
                ('Arduino', 'Arduino', 1),
                ('Arduino', 'Raspberry Pi', 2),
                ('Raspberry Pi', 'Raspberry Pi', 1),
                ('Raspberry Pi', 'Arduino', 2),
                ('Earbuds & Headsets', 'Earbuds & Headsets', 1),
                ('Bags & Carry Case', 'Bags & Carry Case', 1),
                ('Screen Protectors', 'Screen Protectors', 1),
                ('Mobile Chargers', 'Mobile Chargers', 1),
                ('PCB Drill Bits', 'PCB Drill Bits', 1),
                ('Computer Speakers', 'Computer Speakers', 1),
                ('Surge Protectors', 'Surge Protectors', 1);
            END
        """)
        conn.commit()
        conn.close()
        print("CategorySubstituteMap ready")
    except Exception as e:
        print(f"Startup error: {e}")
    seed_search_intelligence()
    print("Search intelligence seeded")
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "traceback": traceback.format_exc()}
    )

DB_CONN = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={os.environ['DB_SERVER']};"
    f"Database={INVENTORY_DB};"
    f"UID={os.environ['DB_USER']};"
    f"PWD={os.environ['DB_PASS']};"
    "TrustServerCertificate=yes;"
)

LOCAL_DB_CONN = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={LOCAL_DB_SERVER};"
    f"Database={SEARCH_DB};"
    f"UID={LOCAL_DB_USER};"
    f"PWD={LOCAL_DB_PASS};"
    "TrustServerCertificate=yes;"
)

def get_local_conn():
    return pyodbc.connect(LOCAL_DB_CONN, timeout=10)

ai = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def get_conn():
    return pyodbc.connect(DB_CONN, timeout=10)

def get_product_image(autonum: int) -> str:
    """Fetch product thumbnail from image databases. Returns base64 string or empty string."""
    for db in IMAGE_DBS:
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT TOP 1 FileData
                FROM {db}.dbo.SFT
                WHERE AutoNum = ?
                ORDER BY AutoNum
            """, autonum)
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                return base64.b64encode(bytes(row[0])).decode('utf-8')
        except:
            continue
    return ''

def get_product_images_bulk(autonums: list) -> dict:
    """Fetch thumbnails for multiple products in one query per image DB using TocAN join."""
    if not autonums:
        return {}
    images = {}
    remaining = list(autonums)
    for db in IMAGE_DBS:
        if not remaining:
            break
        placeholders = ','.join(['?' for _ in remaining])
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT TOP 1 WITH TIES TocAN, FileData
                FROM {db}.dbo.SFT
                WHERE TocAN IN ({placeholders})
                ORDER BY ROW_NUMBER() OVER (PARTITION BY TocAN ORDER BY AutoNum)
            """, remaining)
            rows = cursor.fetchall()
            conn.close()
            for row in rows:
                toc_an = row[0]
                if toc_an not in images and row[1]:
                    images[toc_an] = base64.b64encode(bytes(row[1])).decode('utf-8')
            remaining = [a for a in remaining if a not in images]
        except:
            continue
    return images

def get_substitute_category_map() -> dict:
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT CategoryName, SubstituteCategory
            FROM dbo.CategorySubstituteMap
            ORDER BY CategoryName, Priority
        """)
        rows = cursor.fetchall()
        conn.close()
        result = {}
        for category, substitute in rows:
            if category not in result:
                result[category] = []
            result[category].append(substitute)
        return result
    except Exception as e:
        print(f"Map load error: {e}")
        return {}

def get_product_term_map() -> list:
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Term, CategoryBoost, ExcludeTerms, Priority
            FROM dbo.ProductTermMap
            ORDER BY Priority ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        result = []
        for term, category_boost, exclude_terms, priority in rows:
            exclude_list = [
                e.strip() for e in (exclude_terms or '').split(',')
                if e.strip()
            ]
            result.append({
                "term": term.lower(),
                "category_boost": category_boost,
                "exclude_terms": exclude_list
            })
        return result
    except Exception as e:
        print(f"ProductTermMap load error: {e}")
        return []

def get_term_aliases() -> list:
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'TermAliases')
            CREATE TABLE dbo.TermAliases (
                ID INT IDENTITY(1,1) PRIMARY KEY,
                Alias NVARCHAR(200) NOT NULL,
                MapsToTerm NVARCHAR(200) NOT NULL
            )
        """)
        conn.commit()
        cursor.execute("SELECT Alias, MapsToTerm FROM dbo.TermAliases ORDER BY LEN(Alias) DESC")
        rows = cursor.fetchall()
        conn.close()
        return [{"alias": row[0].strip().lower(), "maps_to": row[1].strip()} for row in rows]
    except Exception as e:
        print(f"TermAliases load error: {e}")
        return []

def classify_query_rules(query: str) -> dict:
    q = query.strip().lower()
    words = q.split()

    part_number_pattern = re.compile(
        r'^[a-z]{1,5}\d{2,}|^\d{2,}[a-z]+|\b(lm|ne|tl|ua|la|an|ta|ha|ca|mc|cd|sg|uc|pc|ir|tip|bc|bd|bf|2n|1n|in|st|hef|74|40|45)\d+',
        re.IGNORECASE
    )
    is_part_number = bool(part_number_pattern.match(q)) or (
        len(words) == 1 and any(c.isdigit() for c in q) and any(c.isalpha() for c in q)
    )

    if is_part_number:
        return {
            "query_type": "part_number",
            "search_mode": "exact",
            "category_filter": None,
            "category_boost": None,
            "exclude_terms": [],
            "rule_applied": f"Part number detected: {query}"
        }

    accessory_modifiers = {
        "bag": "Bags & Carry Case",
        "case": "Bags & Carry Case",
        "cover": None,
        "charger": "Adapters",
        "adapter": "Adapters",
        "cable": None,
        "fan": "Laptop Fans",
        "battery": "Laptop Batteries",
        "screen protector": "Screen Protectors",
        "keyboard": None,
        "stand": None,
        "dock": None,
        "hub": None,
        "socket": None,
        "jack": None,
        "connector": None,
    }

    for modifier, category in accessory_modifiers.items():
        if modifier in q and len(words) > 1:
            return {
                "query_type": "product_type_specific",
                "search_mode": "filtered",
                "category_filter": category,
                "category_boost": category,
                "exclude_terms": [],
                "rule_applied": f"Accessory modifier detected: '{modifier}'"
            }

    product_term_map = get_product_term_map()
    for config in product_term_map:
        product_term = config["term"]
        if product_term in q:
            has_accessory = any(mod in q for mod in accessory_modifiers.keys())
            if not has_accessory:
                return {
                    "query_type": "product_type_general",
                    "search_mode": "boosted",
                    "category_filter": None,
                    "category_boost": config["category_boost"],
                    "exclude_terms": config["exclude_terms"],
                    "rule_applied": f"Main product detected: '{product_term}'"
                }

    return {
        "query_type": "general",
        "search_mode": "standard",
        "category_filter": None,
        "category_boost": None,
        "exclude_terms": [],
        "rule_applied": "No specific rule matched — standard search"
    }

def interpret_query(query: str) -> dict:
    rule_result = classify_query_rules(query)

    if rule_result["query_type"] == "part_number":
        return {
            "product_type": "Component / Part Number",
            "search_terms": [query],
            "exclude_terms": [],
            "confidence_in_interpretation": 95,
            "interpretation_note": f"Exact part number search for: {query}",
            "preferred_category": None,
            "intent_is_specific": True,
            "query_type": "part_number",
            "search_mode": "exact",
            "category_boost": None,
            "rule_applied": rule_result["rule_applied"],
            "ai_used": False
        }

    rule_hint = ""
    if rule_result["query_type"] == "product_type_general":
        rule_hint = f"""
IMPORTANT CONTEXT: Our rule engine detected this as a GENERAL PRODUCT search for '{query}'.
The user wants the main product, NOT accessories.
preferred_category should be: "{rule_result.get('category_boost') or 'null'}"
Our category is called 'Laptop Computers' not 'Laptops' — use this exact name.
exclude_terms must include: {rule_result.get('exclude_terms', [])}
"""
    elif rule_result["query_type"] == "product_type_specific":
        rule_hint = f"""
IMPORTANT CONTEXT: Our rule engine detected this as a SPECIFIC ACCESSORY search.
preferred_category should be: "{rule_result.get('category_filter') or 'null'}"
"""

    prompt = f"""You are a search interpreter for an electronics inventory system.

PRIORITY RULE: Consumer products (phones, laptops, cables, chargers, cases, speakers, earphones, power banks, smart watches) must always be suggested before technical components (ICs, resistors, capacitors, sensors) when the query is ambiguous.

The inventory covers: electronic components (ICs, resistors, capacitors,
transistors), computers and laptops, cellular accessories, industrial
automation (sensors, PLCs, relays, motors), smart home devices (Arduino,
Raspberry Pi, Sonoff), car service parts, cables, chargers, memory cards,
test equipment, security systems (CCTV, access control).

{rule_hint}

User searched for: "{query}"

Return ONLY valid JSON:
{{
  "product_type": "short product category name",
  "search_terms": ["term1", "term2", "term3"],
  "exclude_terms": ["term1", "term2"],
  "confidence_in_interpretation": 85,
  "interpretation_note": "one sentence explaining what user is looking for",
  "preferred_category": "exact CategoryName if intent is clear, otherwise null",
  "intent_is_specific": true or false,
  "query_type": "part_number | product_type_specific | product_type_general | general"
}}

Rules:
- search_terms: max 4 terms, most specific first
- exclude_terms: only add if you are very confident they are wrong category
- preferred_category must exactly match one of our category names or be null
- query_type must be one of the 4 values above
"""

    try:
        response = ai.messages.create(
            model=AI_FAST_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        result["search_mode"] = rule_result["search_mode"]
        result["category_boost"] = rule_result.get("category_boost") or result.get("preferred_category")
        result["rule_applied"] = rule_result["rule_applied"]
        result["ai_used"] = True
        return result
    except Exception as e:
        return {
            "product_type": query,
            "search_terms": [query],
            "exclude_terms": rule_result.get("exclude_terms", []),
            "confidence_in_interpretation": 50,
            "interpretation_note": f"Direct search for: {query}",
            "preferred_category": rule_result.get("category_boost"),
            "intent_is_specific": True,
            "query_type": rule_result["query_type"],
            "search_mode": rule_result["search_mode"],
            "category_boost": rule_result.get("category_boost"),
            "rule_applied": rule_result["rule_applied"],
            "ai_used": False
        }

def log_search(query: str, interpretation: dict, results: list,
               search_type: str = "text") -> int:
    try:
        top_item = results[0].get('Item', '') if results else ''
        conf_avg = round(
            sum(r.get('_confidence', 0) for r in results) / len(results), 2
        ) if results else 0.0

        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.SearchIntelligence
            (SearchQuery, ClaudeInterpretation, ExpandedKeywords,
             ExcludedTerms, SQLTermsUsed, ResultsCount,
             TopResultItem, ConfidenceAvg, SearchType)
            OUTPUT INSERTED.ID
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            query,
            interpretation.get('interpretation_note', ''),
            ', '.join(interpretation.get('search_terms', [])),
            ', '.join(interpretation.get('exclude_terms', [])),
            ', '.join(interpretation.get('search_terms', [query])),
            len(results),
            top_item,
            conf_avg,
            search_type
        )
        row = cursor.fetchone()
        conn.commit()
        conn.close()
        return row[0] if row else -1
    except Exception as e:
        print(f"Log error: {e}")
        return -1

def calculate_confidence(row: dict, query: str, words: list) -> dict:
    field_weights = {
        'ItemAnotherName': 40,
        'Original_No':     35,
        'Item':            30,
        'Description':     25,
        'Brand':           20,
        'CategoryName':    15,
        'WebDescription':  10,
        'ItemNote':         5,
        'Barcode':          5,
    }

    matched_fields = []
    words_found = set()
    raw_score = 0

    for field, weight in field_weights.items():
        val = str(row.get(field) or '').lower()
        if not val:
            continue
        field_hit = False
        for word in words:
            # word-boundary match so "acer" doesn't match inside "spacer"
            if re.search(r'\b' + re.escape(word.lower()) + r'\b', val):
                words_found.add(word.lower())
                field_hit = True
        if field_hit:
            matched_fields.append(field)
            raw_score += weight

    match_ratio = len(words_found) / len(words) if words else 0
    score = min(int(raw_score * match_ratio), 100)

    # Exact version/model number bonus
    # If query contains numbers, check if those exact numbers
    # appear in description or item name
    query_numbers = re.findall(r'\b\d+\b', query.lower())
    if query_numbers:
        desc_and_item = (
            str(row.get('Description') or '') + ' ' +
            str(row.get('Item') or '') + ' ' +
            str(row.get('ItemAnotherName') or '')
        ).lower()
        all_numbers_match = all(num in desc_and_item for num in query_numbers)
        any_number_match = any(num in desc_and_item for num in query_numbers)
        if all_numbers_match:
            score += 25
            matched_fields.append(f'Exact model match: {", ".join(query_numbers)}')
        elif any_number_match:
            score += 10
            matched_fields.append(f'Partial model match: {", ".join(query_numbers)}')
        else:
            score = score - 40
            matched_fields.append('Model number not found in item')

    balance = float(row.get('Balance') or 0)
    if balance > 0:
        score += 5
    elif balance == 0:
        score = max(score - 5, 0)
    else:
        score = max(score - 10, 0)

    return {
        'score': score,
        'matched_fields': matched_fields,
        'match_ratio': round(match_ratio, 2),
    }

def search_db(query: str, limit: int = 20, category: str = None, category_boost: str = None):
    words = [w.strip() for w in query.split() if len(w.strip()) > 1]
    if not words:
        return []

    word_conditions = []
    params = []
    for word in words:
        substr  = f"%{word}%"          # for codes / barcodes / part numbers
        bounded = f"% {word} %"        # word-boundary match for text fields
        word_conditions.append("""(
            ' ' + LOWER(ISNULL(m.[Description],''))       + ' ' LIKE ? OR
            ' ' + LOWER(ISNULL(m.[DescriptionArabic],'')) + ' ' LIKE ? OR
            m.[Original_No]       LIKE ? OR
            ' ' + LOWER(ISNULL(m.[ItemAnotherName],''))   + ' ' LIKE ? OR
            m.[Item]              LIKE ? OR
            ' ' + LOWER(ISNULL(m.[WebDescription],''))    + ' ' LIKE ? OR
            ' ' + LOWER(ISNULL(m.[ItemNote],''))          + ' ' LIKE ? OR
            m.[Barcode]           LIKE ? OR
            ' ' + LOWER(ISNULL(b.[Name],''))              + ' ' LIKE ?
        )""")
        params.extend([bounded, bounded, substr, bounded, substr, bounded, bounded, substr, bounded])

    where_clause = " AND ".join(word_conditions)

    category_filter_sql = ""
    if category:
        category_filter_sql = "AND c.[CategoryName] = ?"
        params.append(category)

    params.append(category_boost or '')

    sql = f"""
        SELECT TOP ({limit}) *
        FROM (
            SELECT
                m.[Item],
                m.[AutoNum],
                m.[Description],
                m.[DescriptionArabic],
                m.[Original_No],
                m.[ItemAnotherName],
                m.[WebDescription],
                m.[ItemNote],
                m.[Barcode],
                ISNULL(mv.[Balance], m.[Balance]) AS Balance,
                m.[Retail],
                m.[BulkPrice],
                m.[Special],
                m.[ItemLink],
                m.[WebName],
                m.[YouTubeLink],
                c.[CategoryName],
                c.[CatPath]         AS CategoryPath,
                b.[Name]            AS Brand,
                STRING_AGG(
                    CASE WHEN f.[FilterName] IS NOT NULL
                          AND fv.[Value] IS NOT NULL
                         THEN f.[FilterName] + ': ' + fv.[Value]
                         ELSE NULL
                    END, ' | '
                ) AS Filters,
                CASE
                    WHEN m.[ItemLink] LIKE 'http%' THEN m.[ItemLink]
                    WHEN m.[ItemLink] IS NOT NULL AND LEN(m.[ItemLink]) > 0
                        THEN 'https://{STORE_DOMAIN}' + m.[ItemLink]
                    ELSE ''
                END AS WebLink,
                CASE WHEN c.[CategoryName] = ? THEN 0 ELSE 1 END AS CategoryRank,
                CASE WHEN ISNULL(mv.[Balance], m.[Balance]) > 0 THEN 0 ELSE 1 END AS StockRank
            FROM {INVENTORY_DB}.dbo.Materials m
            LEFT JOIN {LIVE_DB}.dbo.Materials_View mv
                ON mv.[AutoNum] = m.[AutoNum]
            LEFT JOIN {INVENTORY_DB}.dbo.MatCategories c
                ON m.[MatCategories_AN] = c.[AutoNum]
            LEFT JOIN {INVENTORY_DB}.dbo.Brands b
                ON m.[Brands_AN] = b.[AutoNum]
            LEFT JOIN {INVENTORY_DB}.dbo.MaterialsFiltersValues fv
                ON fv.[Materials_AN] = m.[AutoNum]
            LEFT JOIN {INVENTORY_DB}.dbo.MatCategoriesFilters f
                ON f.[AutoNum] = fv.[MatCategoriesFilters_AN]
            WHERE m.[MarkAsDeleted] = 0
              AND m.[Hidden] = 0
              AND m.[Block] = 0
              AND ({where_clause})
              {category_filter_sql}
            GROUP BY
                m.[Item], m.[AutoNum], m.[Description], m.[DescriptionArabic],
                m.[Original_No], m.[ItemAnotherName], m.[WebDescription],
                m.[ItemNote], m.[Barcode], mv.[Balance], m.[Balance], m.[Retail],
                m.[BulkPrice], m.[Special], m.[ItemLink], m.[WebName],
                m.[YouTubeLink], c.[CategoryName], c.[CatPath], b.[Name]
        ) AS ranked
        ORDER BY
            CategoryRank ASC
    """

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    for row in rows:
        confidence = calculate_confidence(row, query, words)
        row['_confidence'] = confidence['score']
        row['_matched_fields'] = confidence['matched_fields']
        row['_match_ratio'] = confidence['match_ratio']
        row['_low_confidence'] = confidence['score'] < 40
        row['_out_of_stock'] = float(row.get('Balance') or 0) <= 0

    # Bulk-fetch images using TocAN
    autonums = [row['AutoNum'] for row in rows if row.get('AutoNum')]
    image_map = get_product_images_bulk(autonums)
    for row in rows:
        an = row.get('AutoNum')
        if an and an in image_map:
            row['_image_url'] = f'data:image/jpeg;base64,{image_map[an]}'
        else:
            row['_image_url'] = f'/api/image/{an}' if an else ''

    rows.sort(key=lambda r: r['_confidence'], reverse=True)
    return rows

def get_search_suggestions(query: str) -> list:
    try:
        product_terms = [c["term"] for c in get_product_term_map()]
        terms_sample = ", ".join(product_terms[:60])
        prompt = f"""A user searched for "{query}" in the electronics inventory and got zero results.

The inventory covers: electronic components (ICs, resistors, capacitors, sensors, relays, connectors), computers and laptops, mobile & cellular accessories, chargers, cables, networking gear, industrial automation (PLCs, motors, inverters), Arduino/Raspberry Pi, security cameras, car accessories, power supplies, test equipment.

Known searchable product terms in the system: {terms_sample}

Suggest 6 alternative search keywords the user could try instead.
Rules:
- Each suggestion must be 1-3 words, lowercase
- Prefer terms that are likely to exist in the inventory
- Think about synonyms, broader categories, related products, or spelling variations
- Return ONLY a JSON array of strings, no explanation

Example: ["usb charger", "power adapter", "5v adapter", "phone charger", "wall charger", "mobile charger"]"""

        response = ai.messages.create(
            model=AI_FAST_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        suggestions = json.loads(raw)
        return [s for s in suggestions if isinstance(s, str)][:6]
    except Exception as e:
        print(f"Suggestions error: {e}")
        return []

def find_substitutes_from_db(query: str, interpretation: dict = None,
                              limit: int = 80) -> list:
    category_boost = None
    related_categories = []

    if interpretation:
        category_boost = interpretation.get("category_boost")
        preferred = interpretation.get("preferred_category")
        category_boost = category_boost or preferred

    if category_boost:
        substitute_map = get_substitute_category_map()
        related_categories = substitute_map.get(category_boost, [category_boost])

    if related_categories:
        placeholders = ','.join(['?' for _ in related_categories])
        category_where = f"AND c.[CategoryName] IN ({placeholders})"
        category_params = related_categories
    else:
        category_where = ""
        category_params = []

    sql = f"""
        SELECT TOP (?)
            m.[Item],
            m.[AutoNum],
            m.[Description],
            m.[Original_No],
            m.[ItemAnotherName],
            m.[WebDescription],
            ISNULL(mv.[Balance], m.[Balance]) AS Balance,
            m.[Retail],
            c.[CategoryName],
            b.[Name] AS Brand,
            CASE
                WHEN m.[ItemLink] LIKE 'http%' THEN m.[ItemLink]
                WHEN m.[ItemLink] IS NOT NULL AND LEN(m.[ItemLink]) > 0
                    THEN 'https://' + N'{STORE_DOMAIN}' + m.[ItemLink]
                ELSE ''
            END AS WebLink,
            STRING_AGG(
                CASE WHEN f.[FilterName] IS NOT NULL
                      AND fv.[Value] IS NOT NULL
                     THEN f.[FilterName] + ': ' + fv.[Value]
                     ELSE NULL
                END, ' | '
            ) AS Filters
        FROM {INVENTORY_DB}.dbo.Materials m
        LEFT JOIN {LIVE_DB}.dbo.Materials_View mv
            ON mv.[AutoNum] = m.[AutoNum]
        LEFT JOIN {INVENTORY_DB}.dbo.MatCategories c
            ON m.[MatCategories_AN] = c.[AutoNum]
        LEFT JOIN {INVENTORY_DB}.dbo.Brands b
            ON m.[Brands_AN] = b.[AutoNum]
        LEFT JOIN {INVENTORY_DB}.dbo.MaterialsFiltersValues fv
            ON fv.[Materials_AN] = m.[AutoNum]
        LEFT JOIN {INVENTORY_DB}.dbo.MatCategoriesFilters f
            ON f.[AutoNum] = fv.[MatCategoriesFilters_AN]
        WHERE m.[MarkAsDeleted] = 0
          AND m.[Hidden] = 0
          AND m.[Block] = 0
          AND ISNULL(mv.[Balance], m.[Balance]) > 0
          AND m.[Retail] > 0
          {category_where}
        GROUP BY
            m.[Item], m.[AutoNum], m.[Description], m.[Original_No],
            m.[ItemAnotherName], m.[WebDescription], mv.[Balance], m.[Balance],
            m.[Retail], c.[CategoryName], b.[Name], m.[ItemLink]
        ORDER BY ISNULL(mv.[Balance], m.[Balance]) DESC
    """

    params = [limit] + category_params

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    if not rows and related_categories:
        return find_substitutes_from_db(query, interpretation=None, limit=limit)

    return rows

def find_ai_substitutes(original_query: str, candidates: list) -> list:
    candidates_text = "\n".join([
        f"- Item: {r['Item']} | Category: {r.get('CategoryName','')} | Brand: {r.get('Brand','')} | Desc: {r['Description']} | Filters: {r.get('Filters','')} | Price: ${r['Retail']} | Stock: {r['Balance']}"
        for r in candidates
    ])

    prompt = f"""You are an intelligent inventory search assistant for an electronics store.

ABOUT THE INVENTORY:
- 25,746 items across electronics, industrial automation, computers, cellular accessories, smart devices, car service parts, and test equipment
- Partner groups: Electronic, Cellular, Computer Laptop, Industrial_Automation, Smart, Computer_Network, Car Service, Test Equipment, Security
- 60+ sub-categories including ICs, sensors, cables, chargers, memory cards, PLCs, relays, motors, Arduino, Raspberry Pi, and more
- Brands include: Arduino, Philips, Hoco, Green Lion, HP, Sony, Panasonic, Apple, Schneider, Omron, Samsung, Dell, Lenovo, Mean Well, Canon, and others
- Prices are in USD. Balance = current stock quantity. Negative balance = backorder.

ITEM NAMING CONVENTION:
- Format: [Numeric Prefix] [Product Type] | [Variant] | [Spec] | [Brand]
- Pipe | separates hierarchy from general to specific
- Specs include: capacity (GB), size (inches), amperage (A), voltage (V), connector type (USB-C, HDMI), compatibility

SYNONYM AWARENESS:
- "memory stick" = Memory Cards / External Storage
- "charger" = Power Adapters / Charger Battery
- "sensor" = Inductive / Capacitive / Photoelectric / Proximity / Flow / Pressure / Hall Effect
- "cable" = Audio & Video Cables / HDMI / USB / Ethernet / Optical
- "screen protector" = Mobile Screen Protectors
- "battery" = Laptop / Camera / Lithium / Rechargeable Batteries

A customer is looking for: "{original_query}"

We do not have this exact item in stock. From the list below, find the best substitutes.

SUBSTITUTE RULES:
- Only suggest genuinely compatible or functionally equivalent items
- For electronic components: voltage, current, and power ratings must be compatible. Package type matters (DIP is not SMD unless noted)
- For accessories: connector type and device compatibility must match
- For industrial parts: voltage, current rating, and contact type must be compatible
- Prefer items with higher stock (Balance)
- Maximum 3 substitutes
- Write one clear non-technical sentence per substitute explaining why it works as a replacement
- If no valid substitute exists, return an empty array
- Return ONLY a valid JSON array, no explanation, no markdown

FORMAT:
[
  {{
    "Item": "item code",
    "Description": "full description",
    "Original_No": "part number",
    "Balance": 10,
    "Retail": 2.5,
    "WebLink": "",
    "Reason": "one clear sentence why this substitutes the requested item"
  }}
]

AVAILABLE STOCK:
{candidates_text}
"""

    response = ai.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        substitutes = json.loads(raw)
        substitutes = [
            s for s in substitutes
            if s.get('Item') and s.get('Description')
            and str(s.get('Item', '')).strip() != ''
            and str(s.get('Description', '')).strip() != ''
        ]
        return substitutes
    except Exception as e:
        return [{"error": f"AI parse error: {str(e)}", "raw": raw}]

@app.get("/search")
def search(q: str = Query(..., min_length=1)):
    t0 = time.time()

    alias_applied = None
    q_search = q.strip().lower()
    for entry in get_term_aliases():
        if entry["alias"] in q_search:
            q_search = q_search.replace(entry["alias"], entry["maps_to"].lower())
            alias_applied = f"'{entry['alias']}' → '{entry['maps_to']}'"
            break

    interpretation = interpret_query(q_search)
    interp_time = round((time.time() - t0) * 1000)

    search_terms = interpretation.get('search_terms', [q])
    exclude_terms = interpretation.get('exclude_terms', [])
    preferred_category = interpretation.get('preferred_category')
    intent_specific = interpretation.get('intent_is_specific', True)

    t1 = time.time()
    search_mode = interpretation.get("search_mode", "standard")
    category_boost = interpretation.get("category_boost")
    category_filter = None

    if search_mode == "filtered" and interpretation.get("preferred_category"):
        category_filter = interpretation.get("preferred_category")

    all_results = []
    seen_autonums = set()

    # Always search original query first
    priority_terms = [q] + [t for t in search_terms if t.lower() != q.lower()]

    for term in priority_terms:
        term_results = search_db(
            term,
            limit=60,
            category=category_filter,
            category_boost=interpretation.get('category_boost')
        )
        for r in term_results:
            autonum = r.get('AutoNum')
            if autonum not in seen_autonums:
                seen_autonums.add(autonum)
                all_results.append(r)
        if len(all_results) >= 20:
            break

    consumer_categories = {
        'Cases & Covers', 'Laptops', 'Earbuds & Headsets',
        'USB Cables', 'HDMI Cables', 'Power Banks',
        'Bluetooth Speakers', 'Mobile Screen Protectors',
        'External Storage', 'Wireless Chargers', 'Smart Watches',
        'Car Keys', 'Adapters', 'Power Adapters', 'Routers',
        'Keyboard & Mouse', 'Monitors', 'Desktop Computers',
        'Travel Accessories', 'Mobile Chargers', 'Bags',
    }
    for r in all_results:
        if r.get('CategoryName') in consumer_categories:
            r['_confidence'] = min(r.get('_confidence', 0) + 8, 100)
            if '_matched_fields' in r:
                r['_matched_fields'].append('Consumer tier boost')

    if category_boost:
        for r in all_results:
            if r.get('CategoryName', '').lower() == category_boost.lower():
                r['_confidence'] = min(100, r.get('_confidence', 0) + 50)
                r['_matched_fields'] = r.get('_matched_fields', []) + [f'Category boost: {category_boost}']
            else:
                r['_confidence'] = max(0, r.get('_confidence', 0) - 25)

    if exclude_terms:
        all_results = [r for r in all_results if not any(
            ex.lower() in str(r.get('CategoryName', '')).lower()
            for ex in exclude_terms
        )]

    results = sorted(all_results, key=lambda r: r.get('_confidence', 0), reverse=True)[:20]
    db_time = round((time.time() - t1) * 1000)

    search_id = log_search(q, interpretation, results, "text")

    if results:
        total_time = round((time.time() - t0) * 1000)
        return {
            "found": True,
            "results": results,
            "substitutes": [],
            "search_id": search_id,
            "interpretation": interpretation,
            "timing": {
                "interp_ms": interp_time,
                "db_ms": db_time,
                "ai_ms": 0,
                "total_ms": total_time
            },
            "debug": {
                "stage": "db_search",
                "status": "ok",
                "original_query": q,
                "search_terms_tried": search_terms,
                "exclude_terms": exclude_terms,
                "preferred_category": preferred_category,
                "unique_results_found": len(results),
                "rule_applied": interpretation.get("rule_applied"),
                "search_mode": interpretation.get("search_mode"),
                "category_boost": interpretation.get("category_boost"),
                "ai_used": interpretation.get("ai_used", True),
                "alias_applied": alias_applied
            }
        }

    t2 = time.time()
    candidates = find_substitutes_from_db(q, interpretation=interpretation)
    ai_time = 0

    if not candidates:
        suggestions = get_search_suggestions(q)
        total_time = round((time.time() - t0) * 1000)
        return {
            "found": False,
            "results": [],
            "substitutes": [],
            "suggestions": suggestions,
            "search_id": search_id,
            "interpretation": interpretation,
            "timing": {
                "interp_ms": interp_time,
                "db_ms": db_time,
                "ai_ms": 0,
                "total_ms": total_time
            },
            "debug": {
                "stage": "substitute_lookup",
                "status": "no_candidates",
                "query": q
            }
        }

    try:
        substitutes = find_ai_substitutes(q, candidates)
        ai_time = round((time.time() - t2) * 1000)
        status = "ok"
    except Exception as e:
        substitutes = []
        ai_time = round((time.time() - t2) * 1000)
        status = f"ai_error: {str(e)}"

    suggestions = get_search_suggestions(q)
    total_time = round((time.time() - t0) * 1000)
    return {
        "found": False,
        "results": [],
        "substitutes": substitutes,
        "suggestions": suggestions,
        "search_id": search_id,
        "interpretation": interpretation,
        "timing": {
            "interp_ms": interp_time,
            "db_ms": db_time,
            "ai_ms": ai_time,
            "total_ms": total_time
        },
        "debug": {
            "stage": "substitute_search",
            "status": status,
            "query": q,
            "candidates_sent": len(candidates)
        }
    }

@app.post("/search-by-image")
async def search_by_image(file: UploadFile = File(...)):
    t0 = time.time()
    debug = {"stage": "image_read", "filename": file.filename, "content_type": file.content_type}

    try:
        image_data = await file.read()
        if not image_data:
            return {"error": "File is empty", "debug": {**debug, "status": "empty_file"}}

        debug["file_size_bytes"] = len(image_data)
        debug["stage"] = "ai_vision"

        b64 = base64.standard_b64encode(image_data).decode("utf-8")
        media_type = file.content_type if file.content_type in [
            "image/jpeg", "image/png", "image/gif", "image/webp"
        ] else "image/jpeg"

        vision_response = ai.messages.create(
            model=AI_SMART_MODEL,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64}
                    },
                    {
                        "type": "text",
                        "text": "Identify this product for an electronics store inventory search.\n\nReturn ONLY valid JSON:\n{\n  \"brand\": \"brand name if visible, otherwise null\",\n  \"model\": \"model number if visible, otherwise null\",\n  \"product_type\": \"generic product type in 2-4 words\",\n  \"search_term\": \"best single search term to find this product\"\n}\n\nExamples:\n- ACEFAST travel charger → {\"brand\": \"ACEFAST\", \"model\": \"A9\", \"product_type\": \"travel charger\", \"search_term\": \"ACEFAST A9\"}\n- cigarette lighter plug → {\"brand\": null, \"model\": null, \"product_type\": \"cigarette lighter plug\", \"search_term\": \"cigarette lighter plug\"}\n- Arduino Uno board → {\"brand\": \"Arduino\", \"model\": \"Uno\", \"product_type\": \"microcontroller board\", \"search_term\": \"Arduino Uno\"}\n- generic USB cable → {\"brand\": null, \"model\": null, \"product_type\": \"USB cable\", \"search_term\": \"USB cable\"}"
                    }
                ]
            }]
        )

        raw_vision = vision_response.content[0].text.strip()
        raw_vision = raw_vision.replace("```json", "").replace("```", "").strip()
        try:
            vision_data = json.loads(raw_vision)
        except:
            vision_data = {"brand": None, "model": None, "product_type": raw_vision, "search_term": raw_vision}

        brand        = vision_data.get("brand")
        product_type = vision_data.get("product_type", "")
        search_term  = vision_data.get("search_term", product_type)
        product_name = search_term

        debug["stage"]        = "db_search"
        debug["detected"]     = product_name
        debug["brand"]        = brand
        debug["product_type"] = product_type
        vision_ms = round((time.time() - t0) * 1000)

        t1 = time.time()

        # Step 1: Search by exact brand + model if available
        results = []
        if brand and vision_data.get("model"):
            results = search_db(f"{brand} {vision_data['model']}")

        # Step 2: If not found, search by brand only
        if not results and brand:
            results = search_db(brand)

        # Step 3: If not found, search by product type
        if not results:
            results = search_db(product_type)

        db_ms = round((time.time() - t1) * 1000)

        if results:
            return {
                "detected": product_name,
                "brand": brand,
                "product_type": product_type,
                "found": True,
                "results": results,
                "substitutes": [],
                "timing": {"vision_ms": vision_ms, "db_ms": db_ms, "ai_ms": 0, "total_ms": round((time.time() - t0) * 1000)},
                "debug": {**debug, "status": "ok", "hits": len(results)}
            }

        t2 = time.time()
        substitute_query = product_type or search_term
        candidates = find_substitutes_from_db(substitute_query)
        debug["stage"] = "substitute_search"

        if not candidates:
            return {
                "detected": product_name,
                "brand": brand,
                "product_type": product_type,
                "found": False,
                "results": [],
                "substitutes": [],
                "timing": {"vision_ms": vision_ms, "db_ms": db_ms, "ai_ms": 0, "total_ms": round((time.time() - t0) * 1000)},
                "debug": {**debug, "status": "no_candidates"}
            }

        brand_context = f"The customer has a '{brand}' product. " if brand else ""
        substitutes = find_ai_substitutes(
            f"{brand_context}A customer needs a '{product_type}'. We searched for '{search_term}' and found nothing in stock.",
            candidates
        )
        ai_ms = round((time.time() - t2) * 1000)

        return {
            "detected": product_name,
            "brand": brand,
            "product_type": product_type,
            "found": False,
            "results": [],
            "substitutes": substitutes,
            "timing": {"vision_ms": vision_ms, "db_ms": db_ms, "ai_ms": ai_ms, "total_ms": round((time.time() - t0) * 1000)},
            "debug": {**debug, "status": "ok", "candidates_sent": len(candidates)}
        }

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "debug": {**debug, "status": "exception", "traceback": traceback.format_exc()}
        }

@app.post("/feedback")
async def feedback(request: Request):
    try:
        data = await request.json()
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.SearchFeedback
            (SearchIntelligenceID, ResultItem, ResultAutoNum, WasHelpful)
            VALUES (?, ?, ?, ?)
        """,
            data.get('search_id'),
            data.get('item'),
            data.get('autonum'),
            1 if data.get('helpful') else 0
        )
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/analytics")
def get_analytics():
    try:
        conn = get_local_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP 10 SearchQuery, COUNT(*) as Searches,
                   AVG(ConfidenceAvg) as AvgConfidence,
                   AVG(CAST(ResultsCount AS FLOAT)) as AvgResults
            FROM dbo.SearchIntelligence
            GROUP BY SearchQuery
            ORDER BY Searches DESC
        """)
        top_searches = [
            dict(zip([c[0] for c in cursor.description], row))
            for row in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT TOP 10 SearchQuery, ClaudeInterpretation,
                          ExpandedKeywords, SearchTimestamp
            FROM dbo.SearchIntelligence
            WHERE ResultsCount = 0
            ORDER BY SearchTimestamp DESC
        """)
        no_results = [
            dict(zip([c[0] for c in cursor.description], row))
            for row in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT TOP 10
                si.SearchQuery,
                sf.ResultItem,
                sf.WasHelpful,
                sf.FeedbackTimestamp
            FROM dbo.SearchFeedback sf
            JOIN dbo.SearchIntelligence si
                ON sf.SearchIntelligenceID = si.ID
            ORDER BY sf.FeedbackTimestamp DESC
        """)
        recent_feedback = [
            dict(zip([c[0] for c in cursor.description], row))
            for row in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT
                COUNT(*) as TotalSearches,
                AVG(CAST(ResultsCount AS FLOAT)) as AvgResults,
                SUM(CASE WHEN ResultsCount = 0 THEN 1 ELSE 0 END) as ZeroResultSearches,
                AVG(ConfidenceAvg) as AvgConfidence
            FROM dbo.SearchIntelligence
        """)
        row = cursor.fetchone()
        stats = dict(zip([c[0] for c in cursor.description], row)) if row else {}

        cursor.execute("""
            SELECT TOP 10 ExpandedKeywords, COUNT(*) as Uses
            FROM dbo.SearchIntelligence
            WHERE ExpandedKeywords IS NOT NULL
              AND LEN(ExpandedKeywords) > 0
            GROUP BY ExpandedKeywords
            ORDER BY Uses DESC
        """)
        top_expansions = [
            dict(zip([c[0] for c in cursor.description], row))
            for row in cursor.fetchall()
        ]

        conn.close()
        return {
            "stats": stats,
            "top_searches": top_searches,
            "no_results": no_results,
            "recent_feedback": recent_feedback,
            "top_expansions": top_expansions
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/analytics", response_class=HTMLResponse)
def analytics_page():
    with open("analytics.html") as f:
        return f.read()

@app.get("/api/admin/category-map")
def get_category_map():
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ID, CategoryName, SubstituteCategory, Priority, CreatedDate
            FROM dbo.CategorySubstituteMap
            ORDER BY CategoryName, Priority
        """)
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        conn.close()
        conn2 = get_conn()
        cursor2 = conn2.cursor()
        cursor2.execute("""
            SELECT DISTINCT c.CategoryName
            FROM {INVENTORY_DB}.dbo.MatCategories c
            WHERE c.CategoryName IS NOT NULL
              AND LEN(c.CategoryName) > 0
              AND c.Hidden = 0
            ORDER BY c.CategoryName
        """)
        all_categories = [row[0] for row in cursor2.fetchall()]
        conn2.close()
        return {"map": rows, "all_categories": all_categories}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/admin/category-map")
async def add_category_map(request: Request):
    try:
        data = await request.json()
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM dbo.CategorySubstituteMap
                WHERE CategoryName = ? AND SubstituteCategory = ?
            )
            INSERT INTO dbo.CategorySubstituteMap
                (CategoryName, SubstituteCategory, Priority)
            VALUES (?, ?, ?)
        """,
            data.get('category'),
            data.get('substitute'),
            data.get('category'),
            data.get('substitute'),
            data.get('priority', 1)
        )
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/admin/category-map/{map_id}")
def delete_category_map(map_id: int):
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dbo.CategorySubstituteMap WHERE ID = ?", map_id)
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/admin/categories", response_class=HTMLResponse)
def admin_categories_page():
    with open("admin.html") as f:
        return f.read()

@app.get("/api/admin/product-terms")
def get_product_terms():
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ID, Term, CategoryBoost, ExcludeTerms, Priority
            FROM dbo.ProductTermMap
            ORDER BY Priority ASC
        """)
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        conn.close()
        conn2 = get_conn()
        cursor2 = conn2.cursor()
        cursor2.execute("""
            SELECT DISTINCT CategoryName
            FROM {INVENTORY_DB}.dbo.MatCategories
            WHERE CategoryName IS NOT NULL
              AND LEN(CategoryName) > 0
              AND Hidden = 0
            ORDER BY CategoryName
        """)
        all_categories = [row[0] for row in cursor2.fetchall()]
        conn2.close()
        return {"terms": rows, "all_categories": all_categories}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/admin/product-terms")
async def add_product_term(request: Request):
    try:
        data = await request.json()
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT ISNULL(MAX(Priority), 0) + 1 FROM dbo.ProductTermMap")
        next_priority = cursor.fetchone()[0]
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM dbo.ProductTermMap WHERE Term = ?)
            INSERT INTO dbo.ProductTermMap (Term, CategoryBoost, ExcludeTerms, Priority)
            VALUES (?, ?, ?, ?)
        """,
            data.get('term'),
            data.get('term'),
            data.get('category_boost') or None,
            data.get('exclude_terms', ''),
            next_priority
        )
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/admin/product-terms/{term_id}")
def delete_product_term(term_id: int):
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dbo.ProductTermMap WHERE ID = ?", term_id)
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/admin/generate-aliases")
async def generate_aliases(request: Request):
    data = await request.json()
    query = (data.get('query') or '').strip()
    sources = data.get('sources', ['amazon', 'alibaba', 'aliexpress'])
    if not query:
        return {"error": "Query is required"}

    existing = {e['alias'] for e in get_term_aliases()}

    source_list = ', '.join(s.capitalize() for s in sources)
    search_instructions = '\n'.join(
        f'- Search {s.capitalize()} for real "{query}" product listings and note the exact titles and tags sellers use'
        for s in sources
    )

    prompt = f"""You are helping an electronics store build a search alias database.

YOUR TASK: Search for "{query}" on {source_list}.

{search_instructions}

After browsing real product listings:
1. Collect the actual words and phrases that sellers and buyers use for this product
2. Include: brand shortcuts, model shortcuts, specs used as search terms, Arabic transliterations, colloquial names, common abbreviations, regional terms (Lebanese/Arab market)
3. Map each phrase → a short canonical term that would find this product in an inventory

Return a JSON array of alias objects. Each object must have:
- "alias": the phrase a customer might type (lowercase, 1-6 words)
- "maps_to": short canonical inventory term (1-4 words, lowercase)
- "source": which platform provided this insight (amazon / alibaba / aliexpress / general)
- "reason": one short sentence explaining where this alias came from

Rules:
- alias must differ from maps_to
- Generate 15-25 high-quality, diverse aliases
- Prioritize terms real Lebanese/Arab buyers would type
- Include Arabic transliterations where natural (e.g. "shahin" = charger)
- Return ONLY a valid JSON array, no explanation, no markdown

Example format:
[
  {{"alias": "type c fast charger", "maps_to": "{query}", "source": "amazon", "reason": "Most common Amazon listing title variation"}},
  {{"alias": "pd 65w adapter", "maps_to": "{query}", "source": "alibaba", "reason": "Alibaba sellers list by wattage spec"}},
  {{"alias": "shahin type c", "maps_to": "{query}", "source": "general", "reason": "Arabic transliteration of charger"}}
]"""

    try:
        response = ai.messages.create(
            model=AI_SMART_MODEL,
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        raw = ''
        for block in response.content:
            if hasattr(block, 'text'):
                raw += block.text

        raw = raw.strip().replace('```json', '').replace('```', '').strip()
        start = raw.find('[')
        end   = raw.rfind(']') + 1
        if start >= 0 and end > start:
            raw = raw[start:end]

        suggestions = json.loads(raw)

        valid = []
        seen = set()
        for s in suggestions:
            alias   = str(s.get('alias',   '')).strip().lower()
            maps_to = str(s.get('maps_to', '')).strip().lower()
            if not alias or not maps_to or alias == maps_to or len(alias) < 2:
                continue
            if alias in seen:
                continue
            seen.add(alias)
            valid.append({
                'alias':   alias,
                'maps_to': maps_to,
                'source':  str(s.get('source', 'general')).lower(),
                'reason':  str(s.get('reason', '')),
                'exists':  alias in existing
            })

        return {'suggestions': valid, 'query': query}

    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}


@app.post("/api/admin/bulk-aliases")
async def bulk_save_aliases(request: Request):
    data = await request.json()
    aliases = data.get('aliases', [])
    inserted = 0
    skipped  = 0
    errors   = []
    conn = get_local_conn()
    cursor = conn.cursor()
    for item in aliases:
        alias   = str(item.get('alias',   '')).strip().lower()
        maps_to = str(item.get('maps_to', '')).strip()
        if not alias or not maps_to:
            continue
        try:
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.TermAliases WHERE Alias = ?)
                INSERT INTO dbo.TermAliases (Alias, MapsToTerm) VALUES (?, ?)
            """, (alias, alias, maps_to))
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            errors.append(str(e))
    conn.commit()
    conn.close()
    return {'status': 'ok', 'inserted': inserted, 'skipped': skipped, 'errors': errors}


@app.get("/api/admin/term-aliases")
def get_term_aliases_admin():
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, Alias, MapsToTerm FROM dbo.TermAliases ORDER BY Alias")
        rows = cursor.fetchall()
        conn.close()
        return {"aliases": [{"ID": r[0], "Alias": r[1], "MapsToTerm": r[2]} for r in rows]}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/admin/term-aliases")
async def add_term_alias(request: Request):
    data = await request.json()
    alias = (data.get('alias') or '').strip().lower()
    maps_to = (data.get('maps_to') or '').strip()
    if not alias or not maps_to:
        return {"status": "error", "message": "Both alias and target term are required"}
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM dbo.TermAliases WHERE Alias = ?)
            INSERT INTO dbo.TermAliases (Alias, MapsToTerm) VALUES (?, ?)
        """, (alias, alias, maps_to))
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/admin/term-aliases/{alias_id}")
def delete_term_alias(alias_id: int):
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dbo.TermAliases WHERE ID = ?", alias_id)
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/image/{autonum}")
def get_image(autonum: int):
    from fastapi.responses import Response
    for db in IMAGE_DBS:
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT TOP 1 FileData
                FROM {db}.dbo.SFT
                WHERE TocAN = ?
                ORDER BY AutoNum
            """, autonum)
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                return Response(
                    content=bytes(row[0]),
                    media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=86400"}
                )
        except:
            continue
    return Response(status_code=404)

@app.get("/api/product-image/{autonum}")
def get_product_image(autonum: int):
    for ext in ["jpg", "jpeg", "png", "webp", "gif"]:
        path = os.path.join(IMAGES_DIR, f"{autonum}.{ext}")
        if os.path.exists(path):
            return FileResponse(path)
    return JSONResponse({"error": "No image"}, status_code=404)

@app.post("/api/product-image/{autonum}")
async def upload_product_image(autonum: int, file: UploadFile = File(...)):
    ext = (file.content_type or "image/jpeg").split("/")[-1].replace("jpeg", "jpg")
    if ext not in {"jpg", "png", "webp", "gif"}:
        ext = "jpg"
    # Remove any previous image for this product
    for old_ext in ["jpg", "jpeg", "png", "webp", "gif"]:
        old_path = os.path.join(IMAGES_DIR, f"{autonum}.{old_ext}")
        if os.path.exists(old_path):
            os.remove(old_path)
    save_path = os.path.join(IMAGES_DIR, f"{autonum}.{ext}")
    data = await file.read()
    with open(save_path, "wb") as f:
        f.write(data)
    return {"status": "ok", "autonum": autonum, "file": f"{autonum}.{ext}"}

@app.delete("/api/product-image/{autonum}")
def delete_product_image(autonum: int):
    deleted = False
    for ext in ["jpg", "jpeg", "png", "webp", "gif"]:
        path = os.path.join(IMAGES_DIR, f"{autonum}.{ext}")
        if os.path.exists(path):
            os.remove(path)
            deleted = True
    return {"status": "ok" if deleted else "not_found"}

@app.get("/admin/test-local-db")
def test_local_db():
    try:
        conn = get_local_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_NAME")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"status": "ok", "tables": tables}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html") as f:
        return f.read()