import requests
import sys

# Set UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

base = 'http://127.0.0.1:8000'

# Try the files endpoint
print("=== FILES ENDPOINT ===")
r = requests.get(f'{base}/api/files')
print('Status:', r.status_code)
data = r.json()
print('Success:', data.get('success'))
print('Total files:', data.get('total'))

# Show first few files
for f in data.get('items', [])[:5]:
    print(f"  {f.get('original_path', '')}")
