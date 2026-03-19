import os
import pyodbc

conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={os.environ['DB_SERVER']};"
    f"Database={os.environ.get('LIVE_DB', 'LiveDB')};"
    f"UID={os.environ['DB_USER']};"
    f"PWD={os.environ['DB_PASS']};"
    "TrustServerCertificate=yes;"
)

try:
    conn = pyodbc.connect(conn_str, timeout=10)
    cursor = conn.cursor()
    live_db = os.environ.get('LIVE_DB', 'LiveDB')
    cursor.execute(f"SELECT COUNT(*) FROM [{live_db}].[dbo].[Materials_View]")
    row = cursor.fetchone()
    print(f"Connection successful. Total materials: {row[0]}")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
