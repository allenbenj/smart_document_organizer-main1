import sqlite3
import os

def check_db_references():
    # Check legal.db
    if os.path.exists('legal.db'):
        print('=== LEGAL.DB - FILE REFERENCES ===')
        conn = sqlite3.connect('legal.db')
        cursor = conn.cursor()

        # Check for .png files
        cursor.execute("SELECT COUNT(*) FROM files WHERE current_path LIKE '%.png'")
        png_count = cursor.fetchone()[0]
        print(f'PNG files: {png_count}')

        # Check for .py files
        cursor.execute("SELECT COUNT(*) FROM files WHERE current_path LIKE '%.py'")
        py_count = cursor.fetchone()[0]
        print(f'Python files: {py_count}')

        # Check for .js files
        cursor.execute("SELECT COUNT(*) FROM files WHERE current_path LIKE '%.js'")
        js_count = cursor.fetchone()[0]
        print(f'JavaScript files: {js_count}')

        # Check for files with no extension (rough estimate)
        cursor.execute("SELECT COUNT(*) FROM files WHERE current_path NOT LIKE '%.%'")
        no_ext_count = cursor.fetchone()[0]
        print(f'Files with no extension: {no_ext_count}')

        conn.close()

    # Check scan_index.db
    if os.path.exists('scan_index.db'):
        print('\n=== SCAN_INDEX.DB - FILE REFERENCES ===')
        conn = sqlite3.connect('scan_index.db')
        cursor = conn.cursor()

        # Check for .png files
        cursor.execute("SELECT COUNT(*) FROM file_index WHERE ext = '.png'")
        png_count = cursor.fetchone()[0]
        print(f'PNG files: {png_count:,}')

        # Check for .py files
        cursor.execute("SELECT COUNT(*) FROM file_index WHERE ext = '.py'")
        py_count = cursor.fetchone()[0]
        print(f'Python files: {py_count:,}')

        # Check for .js files
        cursor.execute("SELECT COUNT(*) FROM file_index WHERE ext = '.js'")
        js_count = cursor.fetchone()[0]
        print(f'JavaScript files: {js_count:,}')

        # Check for files with no extension
        cursor.execute("SELECT COUNT(*) FROM file_index WHERE ext IS NULL OR ext = ''")
        no_ext_count = cursor.fetchone()[0]
        print(f'Files with no extension: {no_ext_count:,}')

        print('\n=== SAMPLE PATHS IN SCAN_INDEX ===')
        cursor.execute("SELECT path FROM file_index WHERE ext = '.png' LIMIT 5")
        samples = cursor.fetchall()
        for s in samples:
            print(f'  {s[0]}')

        conn.close()

if __name__ == '__main__':
    check_db_references()
