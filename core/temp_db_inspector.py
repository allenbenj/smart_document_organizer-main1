import os
import sqlite3  # noqa: E402

db_path = "development-tools/code_metadata.db"

if not os.path.exists(db_path):
    print("Error: Database file does not exist at the specified path.")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM file_analysis LIMIT 5;")
        rows = cursor.fetchall()
        if rows:
            print("First 5 rows from file_analysis:")
            for row in rows:
                print(row)
        else:
            print("No data found in the file_analysis table.")
        conn.close()
    except Exception as e:
        print(f"An error occurred: {e}")
