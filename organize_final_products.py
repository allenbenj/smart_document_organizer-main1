import requests
base = 'http://127.0.0.1:8000'

# Try different search approaches
print("=== SEARCH FOR LUKAS FILES ===")

# Search by path
r = requests.post(f'{base}/api/search', json={
    'query': 'Final Products',
    'limit': 20
})
print('Search status:', r.status_code)
print('Search results:', r.text[:2000])
