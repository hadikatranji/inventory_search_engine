"""
populate_terms.py
Reads categories and brands from the inventory database, then upserts
smart ProductTermMap rules into the local search database.

Safe to re-run: existing terms are never duplicated.
  - Terms already in DB → skipped (preserving any manual edits)
  - New terms → inserted

Run with:
    cd ~/inventory-search && source .env && python3 populate_terms.py
"""

import os
import pyodbc

INVENTORY_DB    = os.environ.get('INVENTORY_DB',    'InventoryDB')
SEARCH_DB       = os.environ.get('SEARCH_DB',       'SearchDB')
LOCAL_DB_SERVER = os.environ.get('LOCAL_DB_SERVER', '127.0.0.1,1433')
LOCAL_DB_USER   = os.environ.get('LOCAL_DB_USER',   'SA')
LOCAL_DB_PASS   = os.environ.get('LOCAL_DB_PASS',   'ChangeMe2024!')

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

# ─── Step 1: Read real categories from inventory database ────────────────────

print("Connecting to inventory database...")
conn = pyodbc.connect(DB_CONN)
cur = conn.cursor()

cur.execute(f"SELECT CategoryName, CatPath FROM {INVENTORY_DB}.dbo.MatCategories ORDER BY CatPath")
categories = {row[0]: row[1] for row in cur.fetchall()}
cat_names = set(categories.keys())
print(f"  Found {len(cat_names)} categories")

cur.execute(f"SELECT DISTINCT Name FROM {INVENTORY_DB}.dbo.Brands WHERE Name IS NOT NULL ORDER BY Name")
brands = [row[0].strip() for row in cur.fetchall() if row[0] and row[0].strip()]
print(f"  Found {len(brands)} brands")

conn.close()

# ─── Step 2: Read existing terms from search database ────────────────────────

print("\nConnecting to search database...")
lconn = pyodbc.connect(LOCAL_CONN)
lcur = lconn.cursor()

lcur.execute("SELECT Term, CategoryBoost, ExcludeTerms, Priority FROM dbo.ProductTermMap ORDER BY Priority")
existing_rows = lcur.fetchall()
existing_terms = {row[0].strip().lower() for row in existing_rows}
print(f"  Found {len(existing_terms)} existing product terms")

if existing_terms:
    print("\n=== ALREADY IN DB (will be skipped) ===")
    for row in existing_rows:
        boost = f"-> {row[1]}" if row[1] else "(no boost)"
        excl  = f"excl: {row[2]}" if row[2] else ""
        print(f"  [{row[3]}] {row[0]:25s}  {boost}  {excl}")

# ─── Step 3: Define product term rules ───────────────────────────────────────
# Format: (term, category_boost, exclude_terms, priority)

def cat(name):
    """Return category name if it exists in DB, else empty string."""
    if name in cat_names:
        return name
    for c in cat_names:
        if c.lower() == name.lower():
            return c
    print(f"  [WARN] Category not found in DB: '{name}'")
    return ''

# ── Laptops / Computers ──────────────────────────────────────────────────────
LAPTOP_EXCL = "socket,jack,connector,hinge,screen,charger,adapter,bag,case,stand,cooling,fan,lock,cable,keyboard,mouse,port,docking"

laptop_rules = [
    ("laptop",           cat("Laptop Computers"), LAPTOP_EXCL,                        1),
    ("laptops",          cat("Laptop Computers"), LAPTOP_EXCL,                        1),
    ("notebook",         cat("Laptop Computers"), LAPTOP_EXCL,                        1),
    ("macbook",          cat("Laptop Computers"), LAPTOP_EXCL,                        1),
    ("macbook pro",      cat("Laptop Computers"), LAPTOP_EXCL,                        1),
    ("macbook air",      cat("Laptop Computers"), LAPTOP_EXCL,                        1),
    ("imac",             cat("Desktop Computers") or cat("Laptop Computers"), "",     2),
    ("desktop",          cat("Desktop Computers") or cat("Laptop Computers"), "",     2),
    ("pc",               cat("Desktop Computers") or cat("Laptop Computers"),
                         "cable,card,case,fan,power,supply,connector,pci,slot",       2),
    ("all in one",       cat("Desktop Computers") or cat("Laptop Computers"), "",     2),
    ("gaming laptop",    cat("Laptop Computers"), LAPTOP_EXCL,                        1),
]

# ── Tablets ───────────────────────────────────────────────────────────────────
tablet_rules = [
    ("tablet",           cat("Tablets"), "charger,adapter,case,screen,stylus,keyboard", 1),
    ("ipad",             cat("Tablets"), "charger,adapter,case,screen,stylus,keyboard", 1),
    ("ipad pro",         cat("Tablets"), "charger,adapter,case,screen,stylus,keyboard", 1),
    ("ipad air",         cat("Tablets"), "charger,adapter,case,screen,stylus,keyboard", 1),
    ("ipad mini",        cat("Tablets"), "charger,adapter,case,screen,stylus,keyboard", 1),
    ("android tablet",   cat("Tablets"), "charger,adapter,case",                        1),
]

# ── Phones / Cellular ─────────────────────────────────────────────────────────
phone_rules = [
    ("iphone",           cat("Mobile Phones") or cat("Smartphones"), "charger,case,screen,adapter,cable", 1),
    ("samsung phone",    cat("Mobile Phones") or cat("Smartphones"), "charger,case,screen",               1),
    ("smartphone",       cat("Mobile Phones") or cat("Smartphones"), "charger,case,screen,adapter",       1),
    ("mobile phone",     cat("Mobile Phones") or cat("Smartphones"), "charger,case,screen",               1),
]

# ── Chargers / Power ──────────────────────────────────────────────────────────
charger_rules = [
    ("charger",          cat("Chargers") or cat("Mobile Chargers") or cat("Laptop Chargers"), "", 1),
    ("power adapter",    cat("Chargers") or cat("Laptop Chargers"), "",                           1),
    ("power bank",       cat("Power Banks") or cat("Power Bank"), "",                              1),
    ("powerbank",        cat("Power Banks") or cat("Power Bank"), "",                              1),
    ("usb charger",      cat("Chargers") or cat("Mobile Chargers"), "",                            1),
    ("wireless charger", cat("Wireless Chargers") or cat("Chargers"), "",                          1),
    ("ups",              cat("UPS") or cat("Power Supply"), "connector,socket,plug",               1),
    ("power supply",     cat("Power Supply") or cat("UPS"), "connector,module",                    1),
]

# ── Cables / Connectors ───────────────────────────────────────────────────────
cable_rules = [
    ("usb cable",        cat("Cables") or cat("USB Cables"), "",                        1),
    ("hdmi cable",       cat("Cables") or cat("HDMI"), "",                              1),
    ("type c cable",     cat("Cables") or cat("USB Cables"), "",                        1),
    ("lightning cable",  cat("Cables") or cat("USB Cables"), "",                        1),
    ("ethernet cable",   cat("Cables") or cat("Network Cables") or cat("Cables"), "",  1),
]

# ── Networking ────────────────────────────────────────────────────────────────
network_rules = [
    ("router",           cat("Routers") or cat("Networking"), "",                       1),
    ("switch",           cat("Network Switches") or cat("Networking"),
                         "power,relay,light,module,button",                             1),
    ("access point",     cat("Access Points") or cat("Networking"), "",                 1),
    ("wifi",             cat("Networking") or cat("Routers"),
                         "module,chip,antenna,esp",                                     1),
    ("network switch",   cat("Network Switches") or cat("Networking"), "",              1),
    ("sfp",              cat("Networking") or cat("Network Switches"), "",              1),
]

# ── Storage ───────────────────────────────────────────────────────────────────
storage_rules = [
    ("ssd",              cat("SSD") or cat("Storage") or cat("Hard Drives"), "",        1),
    ("hard drive",       cat("Hard Drives") or cat("Storage"), "",                      1),
    ("hdd",              cat("Hard Drives") or cat("Storage"), "",                      1),
    ("memory card",      cat("Memory Cards") or cat("Storage"), "",                     1),
    ("microsd",          cat("Memory Cards") or cat("Storage"), "",                     1),
    ("flash drive",      cat("USB Flash Drives") or cat("Flash Drives") or cat("Storage"), "", 1),
    ("usb flash",        cat("USB Flash Drives") or cat("Flash Drives") or cat("Storage"), "", 1),
    ("ram",              cat("RAM") or cat("Memory"), "camera,laptop,phone,slot",       1),
    ("memory",           cat("RAM") or cat("Memory"),
                         "card,foam,controller,module,plc",                             2),
]

# ── Displays / Monitors ───────────────────────────────────────────────────────
display_rules = [
    ("monitor",          cat("Monitors") or cat("Displays"), "cable,stand,arm,vesa",   1),
    ("screen",           cat("Monitors") or cat("Displays"),
                         "protector,guard,film,cleaner,replacement",                    1),
    ("display",          cat("Monitors") or cat("Displays"),
                         "module,7seg,lcd,oled,controller,driver",                      2),
    ("projector",        cat("Projectors") or cat("Displays"), "",                      1),
]

# ── Printers / Scanners ───────────────────────────────────────────────────────
printer_rules = [
    ("printer",          cat("Printers"), "cable,ink,toner,drum",                      1),
    ("ink",              cat("Printers") or cat("Ink Cartridges"), "",                  1),
    ("toner",            cat("Printers") or cat("Toner Cartridges"), "",                1),
    ("scanner",          cat("Scanners") or cat("Printers"), "",                        1),
]

# ── Cameras / Security ────────────────────────────────────────────────────────
camera_rules = [
    ("camera",           cat("Security Cameras") or cat("Cameras"),
                         "module,chip,esp32,arduino,raspberry",                         1),
    ("cctv",             cat("Security Cameras") or cat("CCTV"), "",                   1),
    ("ip camera",        cat("Security Cameras") or cat("IP Cameras"), "",             1),
    ("nvr",              cat("NVR") or cat("Security") or cat("CCTV"), "",             1),
    ("dvr",              cat("DVR") or cat("Security") or cat("CCTV"), "",             1),
]

# ── Arduino / Raspberry Pi / Maker ────────────────────────────────────────────
maker_rules = [
    ("arduino",          cat("Arduino") or cat("Microcontrollers"), "",                1),
    ("raspberry pi",     cat("Raspberry Pi") or cat("Microcontrollers") or cat("SBC"), "", 1),
    ("raspberry",        cat("Raspberry Pi") or cat("SBC"), "",                        1),
    ("esp32",            cat("Microcontrollers") or cat("Arduino"), "",                 1),
    ("esp8266",          cat("Microcontrollers") or cat("Arduino"), "",                 1),
    ("nodemcu",          cat("Microcontrollers") or cat("Arduino"), "",                 1),
    ("microcontroller",  cat("Microcontrollers") or cat("Arduino"), "",                 1),
    ("sensor",           cat("Sensors"), "camera,touch,fingerprint,motion",             2),
    ("relay",            cat("Relays") or cat("Industrial") or cat("PLC"),
                         "network,switch",                                              1),
    ("plc",              cat("PLC") or cat("Industrial Automation"), "",                1),
    ("servo",            cat("Motors") or cat("Servo") or cat("Arduino"), "",           1),
    ("stepper motor",    cat("Motors") or cat("Stepper Motors"), "",                    1),
    ("motor driver",     cat("Motor Drivers") or cat("Arduino"), "",                    1),
]

# ── Industrial / Automation ───────────────────────────────────────────────────
industrial_rules = [
    ("schneider",        cat("PLC") or cat("Industrial Automation"), "",               1),
    ("omron",            cat("PLC") or cat("Industrial Automation") or cat("Sensors"), "", 1),
    ("siemens",          cat("PLC") or cat("Industrial Automation"), "",               1),
    ("inverter",         cat("Inverters") or cat("Industrial"), "",                    1),
    ("circuit breaker",  cat("Circuit Breakers") or cat("Industrial"), "",             1),
    ("contactor",        cat("Contactors") or cat("Industrial"), "",                   1),
    ("panel",            cat("Industrial") or cat("Enclosures"),
                         "solar,touch,display,screen,monitor",                         2),
]

# ── Audio / Visual ────────────────────────────────────────────────────────────
audio_rules = [
    ("headphone",        cat("Headphones") or cat("Audio"), "",                        1),
    ("headset",          cat("Headsets") or cat("Headphones") or cat("Audio"), "",     1),
    ("earphone",         cat("Earphones") or cat("Audio"), "",                         1),
    ("airpods",          cat("Earphones") or cat("Headphones") or cat("Audio"), "",    1),
    ("speaker",          cat("Speakers") or cat("Audio"),
                         "terminal,connector,wire",                                     1),
    ("microphone",       cat("Microphones") or cat("Audio"), "",                       1),
]

# ── Accessories / Peripherals ─────────────────────────────────────────────────
accessory_rules = [
    ("keyboard",         cat("Keyboards") or cat("Computer Accessories"),
                         "piano,musical,instrument",                                    1),
    ("mouse",            cat("Mice") or cat("Computer Mice") or cat("Computer Accessories"), "", 1),
    ("webcam",           cat("Webcams") or cat("Cameras") or cat("Computer Accessories"), "", 1),
    ("cooling fan",      cat("Cooling") or cat("Computer Accessories"), "",             1),
    ("laptop stand",     cat("Laptop Accessories") or cat("Computer Accessories"), "", 1),
    ("laptop bag",       cat("Laptop Bags") or cat("Computer Accessories"), "",        1),
    ("screen protector", cat("Screen Protectors") or cat("Mobile Accessories"), "",    1),
    ("phone case",       cat("Phone Cases") or cat("Mobile Accessories"), "",          1),
    ("car charger",      cat("Car Chargers") or cat("Chargers") or cat("Car Accessories"), "", 1),
]

# ── Smart Home / IoT ──────────────────────────────────────────────────────────
smart_rules = [
    ("smart bulb",       cat("Smart Home") or cat("Smart Lighting"), "",               1),
    ("smart plug",       cat("Smart Home") or cat("Smart Plugs"), "",                  1),
    ("smart switch",     cat("Smart Home") or cat("Smart Switches"),
                         "network,cisco,managed",                                       1),
    ("alexa",            cat("Smart Home") or cat("Smart Speakers"), "",               1),
    ("google home",      cat("Smart Home") or cat("Smart Speakers"), "",               1),
]

# ── Brand-based rules ─────────────────────────────────────────────────────────
brand_category_hints = {
    "hp":        cat("Laptop Computers") or cat("Printers"),
    "dell":      cat("Laptop Computers") or cat("Desktop Computers"),
    "lenovo":    cat("Laptop Computers"),
    "apple":     cat("Mobile Phones") or cat("Tablets"),
    "samsung":   cat("Mobile Phones") or cat("Tablets"),
    "canon":     cat("Printers") or cat("Cameras"),
    "epson":     cat("Printers"),
    "cisco":     cat("Networking") or cat("Network Switches"),
    "ubiquiti":  cat("Networking") or cat("Access Points"),
    "mikrotik":  cat("Routers") or cat("Networking"),
    "mean well": cat("Power Supply"),
    "meanwell":  cat("Power Supply"),
    "hoco":      cat("Mobile Accessories") or cat("Chargers"),
    "green lion":cat("Mobile Accessories") or cat("Chargers"),
    "anker":     cat("Chargers") or cat("Power Banks"),
}
brand_rules = [
    (term, boost or '', '', 3)
    for term, boost in brand_category_hints.items()
]

# ─── Combine and deduplicate within this script ───────────────────────────────
ALL_RULES = (
    laptop_rules + tablet_rules + phone_rules + charger_rules +
    cable_rules + network_rules + storage_rules + display_rules +
    printer_rules + camera_rules + maker_rules + industrial_rules +
    audio_rules + accessory_rules + smart_rules + brand_rules
)

seen_in_script = set()
deduped = []
for rule in ALL_RULES:
    term = rule[0].strip().lower()
    if term and term not in seen_in_script:
        seen_in_script.add(term)
        deduped.append((term, rule[1], rule[2], rule[3]))

# ─── Split into new vs already existing ──────────────────────────────────────
to_insert = [(t, cb, ex, p) for (t, cb, ex, p) in deduped if t not in existing_terms]
to_skip   = [(t, cb, ex, p) for (t, cb, ex, p) in deduped if t in existing_terms]

print(f"\n=== SUMMARY ===")
print(f"  Total rules defined : {len(deduped)}")
print(f"  Already in DB       : {len(to_skip)}  (will be skipped)")
print(f"  New — to insert     : {len(to_insert)}")

if to_insert:
    print(f"\n=== NEW RULES TO INSERT ===")
    for r in to_insert:
        boost = f"-> {r[1]}" if r[1] else "(no boost)"
        excl  = f"excl: {r[2]}" if r[2] else ""
        print(f"  [{r[3]}] {r[0]:25s}  {boost}  {excl}")
else:
    print("\n  Nothing new to insert — all rules already exist in DB.")

# ─── Confirm and insert ───────────────────────────────────────────────────────
if not to_insert:
    lconn.close()
    exit()

confirm = input(f"\nInsert {len(to_insert)} new rules? (y/n): ")
if confirm.strip().lower() != 'y':
    print("Aborted.")
    lconn.close()
    exit()

inserted = 0
skipped  = 0
for (term, category_boost, exclude_terms, priority) in to_insert:
    try:
        lcur.execute("""
            INSERT INTO dbo.ProductTermMap (Term, CategoryBoost, ExcludeTerms, Priority)
            VALUES (?, ?, ?, ?)
        """, (term, category_boost or None, exclude_terms or None, priority))
        inserted += 1
    except Exception as e:
        print(f"  [ERROR] {term}: {e}")
        skipped += 1

lconn.commit()
lconn.close()

print(f"\nDone. Inserted: {inserted}, Skipped errors: {skipped}")
print("Restart your server for changes to take effect.")
