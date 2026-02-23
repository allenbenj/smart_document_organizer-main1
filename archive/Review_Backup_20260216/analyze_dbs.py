import sqlite3

def analyze_legal_db():
    conn = sqlite3.connect('legal.db')
    cursor = conn.cursor()

    print('=== SAMPLE FILES FROM LEGAL.DB ===')
    cursor.execute('SELECT file_id, first_seen_path, current_path FROM files LIMIT 10')
    files = cursor.fetchall()
    for f in files:
        print(f'ID: {f[0][:16]}... | Path: {f[1][-50:] if f[1] else "None"}')

    print('\n=== TOP ENTITIES BY TYPE ===')
    cursor.execute('SELECT entity_type, text, COUNT(*) as count FROM entities GROUP BY entity_type, text ORDER BY count DESC LIMIT 20')
    entities = cursor.fetchall()
    for e in entities:
        print(f'{e[0]}: {e[1]} ({e[2]} times)')

    print('\n=== EVENT TYPES ===')
    cursor.execute('SELECT event_type, COUNT(*) as count FROM events GROUP BY event_type ORDER BY count DESC LIMIT 10')
    events = cursor.fetchall()
    for e in events:
        print(f'{e[0]}: {e[1]} events')

    print('\n=== PLANS ===')
    cursor.execute('SELECT plan_id, status, plan_data FROM plans')
    plans = cursor.fetchall()
    for p in plans:
        print(f'Plan {p[0]}: {p[1]} - {p[2][:100]}...')

    conn.close()

def analyze_scan_index():
    conn = sqlite3.connect('scan_index.db')
    cursor = conn.cursor()

    print('\n=== SCAN INDEX STATS ===')
    cursor.execute('SELECT COUNT(*) FROM file_index')
    total = cursor.fetchone()[0]
    print(f'Total files indexed: {total:,}')

    cursor.execute('SELECT ext, COUNT(*) as count FROM file_index GROUP BY ext ORDER BY count DESC LIMIT 10')
    extensions = cursor.fetchall()
    print('Top file extensions:')
    for ext, count in extensions:
        print(f'  {ext or "no extension"}: {count:,}')

    cursor.execute('SELECT COUNT(DISTINCT path) FROM file_index')
    unique_paths = cursor.fetchone()[0]
    print(f'Unique paths: {unique_paths:,}')

    print('\n=== SAMPLE FILES FROM SCAN INDEX ===')
    cursor.execute('SELECT path, size, mtime, ext FROM file_index LIMIT 10')
    files = cursor.fetchall()
    for f in files:
        print(f'Path: {f[0][-60:]} | Size: {f[1]:,} | Ext: {f[2] or "none"}')

    conn.close()

if __name__ == '__main__':
    analyze_legal_db()
    analyze_scan_index()