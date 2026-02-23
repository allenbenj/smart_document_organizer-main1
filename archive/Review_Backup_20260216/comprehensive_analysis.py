import sqlite3

def comprehensive_analysis():
    conn = sqlite3.connect('legal.db')
    cursor = conn.cursor()

    print('=== ENTITY TYPES BREAKDOWN ===')
    cursor.execute('SELECT entity_type, COUNT(*) as count FROM entities GROUP BY entity_type ORDER BY count DESC LIMIT 20')
    entity_types = cursor.fetchall()
    for et in entity_types:
        print(f'{et[0]}: {et[1]} entities')

    print('\n=== CASE NUMBERS ===')
    cursor.execute("SELECT text, COUNT(*) as count FROM entities WHERE entity_type = 'CASE_NUMBER' GROUP BY text ORDER BY count DESC LIMIT 5")
    case_nums = cursor.fetchall()
    for cn in case_nums:
        print(f'Case {cn[0]}: {cn[1]} mentions')

    print('\n=== LAW FIRMS & ATTORNEYS ===')
    cursor.execute("SELECT text, COUNT(*) as count FROM entities WHERE entity_type IN ('LAW_FIRM', 'ATTORNEY', 'LAWYER') GROUP BY text ORDER BY count DESC LIMIT 10")
    lawyers = cursor.fetchall()
    for l in lawyers:
        print(f'{l[0]}: {l[1]} mentions')

    print('\n=== JUDGES ===')
    cursor.execute("SELECT text, COUNT(*) as count FROM entities WHERE entity_type = 'JUDGE' GROUP BY text ORDER BY count DESC LIMIT 10")
    judges = cursor.fetchall()
    for j in judges:
        print(f'Judge {j[0]}: {j[1]} mentions')

    print('\n=== PARTIES TO THE CASE ===')
    cursor.execute("SELECT text, COUNT(*) as count FROM entities WHERE entity_type = 'PARTY' GROUP BY text ORDER BY count DESC LIMIT 10")
    parties = cursor.fetchall()
    for p in parties:
        print(f'Party: {p[0]} ({p[1]} mentions)')

    print('\n=== KEY DATES ===')
    cursor.execute("SELECT text, COUNT(*) as count FROM entities WHERE entity_type = 'DATE' GROUP BY text ORDER BY count DESC LIMIT 10")
    dates = cursor.fetchall()
    for d in dates:
        print(f'{d[0]}: {d[1]} mentions')

    print('\n=== CASE SUMMARY ===')
    cursor.execute('SELECT COUNT(DISTINCT file_id) as files, COUNT(*) as total_entities FROM entities')
    summary = cursor.fetchone()
    print(f'Total indexed files: {summary[0]:,}')
    print(f'Total extracted entities: {summary[1]:,}')

    # Check for specific case mentions
    cursor.execute("SELECT text FROM entities WHERE text LIKE '%Allen%' AND entity_type = 'PERSON' LIMIT 5")
    allens = cursor.fetchall()
    if allens:
        print('\n=== ALLEN FAMILY REFERENCES ===')
        for a in allens:
            print(f'Allen reference: {a[0]}')

    conn.close()

if __name__ == '__main__':
    comprehensive_analysis()