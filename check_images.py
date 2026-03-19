"""
check_images.py
Discovers where product images are stored in the inventory database.
Run with: cd ~/inventory-search && source .env && python3 check_images.py
"""
import os
import pyodbc

INVENTORY_DB = os.environ.get('INVENTORY_DB', 'InventoryDB')

DB_CONN = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={os.environ['DB_SERVER']};"
    f"Database={INVENTORY_DB};"
    f"UID={os.environ['DB_USER']};"
    f"PWD={os.environ['DB_PASS']};"
    "TrustServerCertificate=yes;"
)

conn = pyodbc.connect(DB_CONN)
cur = conn.cursor()

# 1. Look for image-related columns in Materials table
print("=== Columns in Materials table ===")
cur.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'Materials'
    ORDER BY ORDINAL_POSITION
""")
for row in cur.fetchall():
    print(f"  {row[0]:40s} {row[1]:20s} {row[2] or ''}")

# 2. Look for any tables with "image", "photo", "picture" in name
print("\n=== Tables with image/photo in name ===")
cur.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%image%'
       OR TABLE_NAME LIKE '%photo%'
       OR TABLE_NAME LIKE '%picture%'
       OR TABLE_NAME LIKE '%img%'
    ORDER BY TABLE_NAME
""")
rows = cur.fetchall()
if rows:
    for row in rows: print(f"  {row[0]}")
else:
    print("  None found")

# 3. Sample a few ItemLink values to see URL pattern
print("\n=== Sample ItemLink values (first 10 non-null) ===")
cur.execute("""
    SELECT TOP 10 Item, ItemLink, WebName
    FROM {INVENTORY_DB}.dbo.Materials
    WHERE ItemLink IS NOT NULL AND LEN(ItemLink) > 0
""")
for row in cur.fetchall():
    print(f"  [{row[0]}]  ItemLink: {row[1]}  WebName: {row[2]}")

# 4. Check for image-related tables in current DB
print("\n=== Tables with image/photo in live DB ===")
cur.execute("""
    SELECT TABLE_CATALOG, TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%image%'
       OR TABLE_NAME LIKE '%photo%'
       OR TABLE_NAME LIKE '%picture%'
       OR TABLE_NAME LIKE '%img%'
    ORDER BY TABLE_NAME
""")
rows = cur.fetchall()
if rows:
    for row in rows: print(f"  {row[0]}.{row[1]}")
else:
    print("  None found")

# 5. Check if any column in Materials looks like an image path/URL
print("\n=== Sample of columns that might contain image paths ===")
cur.execute("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'Materials'
      AND (
        DATA_TYPE IN ('nvarchar','varchar','text')
        AND CHARACTER_MAXIMUM_LENGTH > 50
      )
""")
text_cols = [row[0] for row in cur.fetchall()]

for col in text_cols:
    try:
        cur.execute(f"""
            SELECT TOP 1 [{col}] FROM {INVENTORY_DB}.dbo.Materials
            WHERE [{col}] LIKE '%.jpg%'
               OR [{col}] LIKE '%.png%'
               OR [{col}] LIKE '%.gif%'
               OR [{col}] LIKE '%.webp%'
        """)
        row = cur.fetchone()
        if row:
            print(f"  Column [{col}] contains image path: {row[0][:120]}")
    except:
        pass

conn.close()
print("\nDone.")
