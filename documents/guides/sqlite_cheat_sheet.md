# SQLite Command Cheat Sheet (Python)

This file documents the most common SQLite operations when using Python's `sqlite3` module.

---

## 📁 Connect to a Database
```python
import sqlite3
conn = sqlite3.connect("my_database.db")
cursor = conn.cursor()
```
---

## 🛠️ Schema (DDL – Data Definition Language)

```sql
CREATE TABLE IF NOT EXISTS table_name (
    id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER
);

DROP TABLE IF EXISTS table_name;

ALTER TABLE table_name RENAME TO new_table_name;
ALTER TABLE table_name ADD COLUMN new_col TEXT;

CREATE INDEX index_name ON table_name (column_name);
DROP INDEX IF EXISTS index_name;

PRAGMA table_info(table_name);
PRAGMA foreign_keys = ON;
```
---

## 📦 Data (DML – Data Manipulation Language)

```sql
INSERT INTO table_name (col1, col2) VALUES (?, ?);
INSERT OR REPLACE INTO table_name (col1) VALUES (?);

UPDATE table_name SET col1 = ? WHERE condition;

DELETE FROM table_name WHERE condition;
DELETE FROM table_name;  -- Remove all rows
```
---

## 🔍 Query (DQL – Data Query Language)

```sql
SELECT * FROM table_name;
SELECT col1, col2 FROM table_name WHERE condition;

SELECT DISTINCT col FROM table_name;
SELECT COUNT(*) FROM table_name;
SELECT MAX(col), MIN(col), AVG(col), SUM(col) FROM table_name;

SELECT col FROM table_name ORDER BY col DESC LIMIT 10 OFFSET 5;

SELECT * FROM table1
JOIN table2 ON table1.col = table2.col;
```
---

## 🔁 Transaction Control

```python
conn.execute("BEGIN;")
# ... perform operations ...
conn.execute("COMMIT;")
conn.execute("ROLLBACK;")
```

---

## 🧠 Introspection & Metadata

```sql
SELECT name FROM sqlite_master WHERE type='table';
SELECT sql FROM sqlite_master WHERE name='table_name';
PRAGMA database_list;
PRAGMA table_list;
```

---

## ⚙️ Useful PRAGMAs

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
```

---

## 🧪 Python Code Examples

```python
# Insert a row
cursor.execute("INSERT INTO files (path, type) VALUES (?, ?)", ("main.py", "script"))

# Fetch all rows
cursor.execute("SELECT * FROM files")
rows = cursor.fetchall()

# Commit and close
conn.commit()
conn.close()
```

---

## 🧰 Reusable Functions (Python)

```python
def get_tables(conn):
    return conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()

def get_table_schema(conn, table):
    return conn.execute(f"PRAGMA table_info({table});").fetchall()

def insert_row(conn, table, data):
    keys = ', '.join(data.keys())
    qmarks = ', '.join(['?'] * len(data))
    values = tuple(data.values())
    conn.execute(f"INSERT INTO {table} ({keys}) VALUES ({qmarks})", values)

def backup_db(db_path, backup_path):
    import shutil
    shutil.copy2(db_path, backup_path)
```