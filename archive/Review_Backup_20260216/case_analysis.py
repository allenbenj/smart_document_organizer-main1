import sqlite3

def analyze_case_details():
    conn = sqlite3.connect('legal.db')
    cursor = conn.cursor()

    print('=== CASE TIMELINE ANALYSIS ===')
    cursor.execute("SELECT strftime('%Y', ingestion_ts) as year, COUNT(*) as count FROM files GROUP BY year ORDER BY year")
    years = cursor.fetchall()
    for y in years:
        print(f'{y[0] or "Unknown"}: {y[1]} files')

    print('\n=== TOP DOCUMENT TYPES ===')
    cursor.execute("SELECT substr(first_seen_path, instr(first_seen_path, '01_Court_Filings')+16, 20) as doc_type, COUNT(*) as count FROM files WHERE first_seen_path LIKE '%01_Court_Filings%' GROUP BY doc_type ORDER BY count DESC LIMIT 10")
    doc_types = cursor.fetchall()
    for dt in doc_types:
        print(f'{dt[0].strip(chr(92))}: {dt[1]} documents')

    print('\n=== KEY PEOPLE/ENTITIES ===')
    cursor.execute("SELECT entity_type, text, COUNT(*) as count FROM entities WHERE entity_type IN ('PERSON', 'LAWYER', 'JUDGE', 'WITNESS') GROUP BY entity_type, text ORDER BY count DESC LIMIT 15")
    people = cursor.fetchall()
    for p in people:
        print(f'{p[0]}: {p[1]} ({p[2]} mentions)')

    print('\n=== CASE NUMBER PATTERNS ===')
    cursor.execute("SELECT text, COUNT(*) as count FROM entities WHERE entity_type = 'CASE_NUMBER' GROUP BY text ORDER BY count DESC LIMIT 10")
    case_nums = cursor.fetchall()
    for cn in case_nums:
        print(f'Case: {cn[0]} ({cn[1]} mentions)')

    conn.close()

if __name__ == '__main__':
    analyze_case_details()