import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
conn = sqlite3.connect(db_path)

# Check current tags
tags = conn.execute("SELECT DISTINCT tag FROM customers WHERE tag IS NOT NULL AND tag != ''").fetchall()
print("Current distinct tags:", [t[0] for t in tags])

# Map old tags to new
mapping = {
    "hot": "A",
    "warm": "B",
    "cold": "C",
    "closed": "D"
}

for old, new in mapping.items():
    conn.execute("UPDATE customers SET tag=? WHERE tag=?", (new, old))
    print(f"  {old} -> {new}")

conn.commit()

# Verify
tags = conn.execute("SELECT DISTINCT tag FROM customers WHERE tag IS NOT NULL AND tag != ''").fetchall()
print("Updated distinct tags:", [t[0] for t in tags])

# Check traffic table
traffic_count = conn.execute("SELECT COUNT(*) FROM traffic").fetchone()[0]
print("Total traffic records:", traffic_count)

conn.close()
print("Migration complete")