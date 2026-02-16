import sqlite3

def check_tables():
    conn = sqlite3.connect('legal.db')
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    print('=== LEGAL.DB TABLES AND COLUMNS ===')
    for (table_name,) in tables:
        print(f'\n{table_name}:')
        try:
            cursor.execute(f'PRAGMA table_info({table_name})')
            columns = cursor.fetchall()
            for col in columns:
                print(f'  {col[1]} ({col[2]})')
        except Exception as e:
            print(f'  Error: {e}')

    conn.close()

if __name__ == '__main__':
    check_tables()